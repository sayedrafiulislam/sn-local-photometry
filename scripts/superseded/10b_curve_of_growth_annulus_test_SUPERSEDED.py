"""
10b_curve_of_growth_annulus_test.py

Revision of 10_curve_of_growth.py. Same measurement, but the local background
annulus is treated as a free parameter to be varied rather than a fixed choice,
and the cases where that annulus is not trustworthy are detected rather than
silently absorbed into the result.

WHY THIS EXISTS
---------------
Script 10 estimates the sky background in a 10-15 kpc annulus around the SN
position, on the assumption that host-galaxy light does not extend that far.
The curve-of-growth output produced by script 10 does not support that
assumption: for roughly two thirds of object-image combinations, background-
subtracted flux is still rising by more than 50 per cent between the 5 and
10 kpc apertures, which is more consistent with host light continuing outward
than with the aperture having enclosed the source.

If host light reaches the annulus, the background is over-estimated and
therefore over-subtracted. Because the subtracted quantity is
(background per pixel) x (aperture area), the resulting deficit scales as r^2.
That is a radius-dependent bias by construction -- indistinguishable in form
from a genuine trend of flux, or colour, with aperture radius. Any conclusion
about how a measured quantity varies with aperture size is therefore suspect
until it has been shown to be stable against this choice.

This script does not assume a correct annulus. It runs several and writes one
output file per setting, so the spread across settings can be propagated as a
systematic rather than ignored.

THE OFF-CHIP PROBLEM
--------------------
A fixed physical annulus has a strongly redshift-dependent angular size. At
0.23 arcsec/pixel and the cosmology below, a 30 kpc radius spans:

    z = 0.004  ->  1578 pixels        z = 0.030  ->   217 pixels
    z = 0.010  ->   636 pixels        z = 0.137  ->    54 pixels

Against a typical frame of ~2470 x 2470 pixels, and with the SN sitting off
centre, the widest annuli do not fit on the detector for the nearest hosts.
Roughly 6 per cent of the sample requires an outer radius beyond 800 pixels.

This matters because photutils does not raise on a partially off-image
aperture. It returns statistics computed from whichever pixels happen to
remain, which biases the background towards whichever side of the annulus
survived -- a silent wrong answer, which is worse than a crash. Every
measurement here therefore records how much of the annulus actually landed on
the detector, and sets a boolean flag when that fraction, or the resulting
pixel count, falls below tolerance. Filter on `annulus_ok` downstream.

EFFICIENCY NOTE
---------------
Raw aperture sums do not depend on the background. They are measured once per
object-image and reused across every annulus setting; only the (cheap) annulus
statistics are recomputed. Running N settings therefore costs roughly one pass
over the imaging, not N.

OUTPUT
------
  curve_of_growth_ann10-15.csv     (reproduces script 10, for comparison)
  curve_of_growth_ann15-25.csv
  curve_of_growth_ann20-30.csv
  annulus_setting_comparison.csv   (per-setting summary)

Existing script 10 outputs are not overwritten. Column names from script 10 are
preserved so that scripts 11 and 15 can consume any of these files unchanged;
the diagnostic columns are additions.
"""

import os
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS
from astropy.cosmology import FlatLambdaCDM
from astropy.stats import SigmaClip
from photutils.aperture import CircularAperture, CircularAnnulus, aperture_photometry

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
FITS_DIR = r"D:\Thesis\pd\CSPAll"
APERTURE_FLOOR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\aperture_floor_per_object.csv"
COORDS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

COSMO = FlatLambdaCDM(H0=70, Om0=0.3)
PLATE_SCALE_ARCSEC_PER_PIX = 0.23
APERTURE_GRID_KPC = np.arange(1.0, 10.5, 0.5)

# (inner_kpc, outer_kpc). The first reproduces script 10 so the comparison is
# like for like; the others progressively move the annulus clear of the host.
ANNULUS_SETTINGS = [
    (10.0, 15.0),
    (15.0, 25.0),
    (20.0, 30.0),
]

# Guard tolerances.
MIN_ANNULUS_FRAC_ON_CHIP = 0.80   # at least this fraction of the annulus on the detector
MIN_ANNULUS_PIXELS = 200          # and at least this many usable pixels
SIGMA_CLIP = SigmaClip(sigma=3.0, maxiters=5)


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
def kpc_to_pixels(radius_kpc, z, cosmo=COSMO, plate_scale=PLATE_SCALE_ARCSEC_PER_PIX):
    """Physical radius (kpc) -> angular size (arcsec) -> pixels, at redshift z."""
    d_a_mpc = cosmo.angular_diameter_distance(z).value
    theta_rad = (radius_kpc / 1000.0) / d_a_mpc      # small-angle, same regime as Kelsey et al.
    theta_arcsec = np.rad2deg(theta_rad) * 3600.0
    return theta_arcsec / plate_scale, theta_arcsec


def annulus_values(data, x_pix, y_pix, r_in_pix, r_out_pix):
    """
    Pixel values inside the annulus that actually lie on the detector and are
    finite. Returns (values, n_pixels, fraction_of_annulus_on_chip).

    photutils silently tolerates an aperture running off the image edge, so the
    returned fraction is the diagnostic that matters -- it is the only thing
    distinguishing a clean background estimate from one measured on whichever
    half of the annulus happened to land on the chip.
    """
    annulus = CircularAnnulus((x_pix, y_pix), r_in=r_in_pix, r_out=r_out_pix)
    mask = annulus.to_mask(method="center")

    try:
        values = mask.get_values(data)              # photutils >= 1.0
    except AttributeError:                          # older photutils
        cutout = mask.multiply(data)
        values = np.array([]) if cutout is None else cutout[mask.data > 0]

    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]

    expected_area = np.pi * (r_out_pix ** 2 - r_in_pix ** 2)
    frac_on_chip = len(values) / expected_area if expected_area > 0 else 0.0
    return values, len(values), float(np.clip(frac_on_chip, 0.0, 1.0))


def background_from_annulus(data, x_pix, y_pix, r_in_pix, r_out_pix):
    """
    Sigma-clipped median background per pixel, with the diagnostics needed to
    decide whether to trust it.
    """
    values, n_pix, frac = annulus_values(data, x_pix, y_pix, r_in_pix, r_out_pix)

    if n_pix == 0:
        return np.nan, 0, 0.0, False

    clipped = SIGMA_CLIP(values, masked=False, copy=False)
    clipped = clipped[np.isfinite(clipped)]
    bkg = float(np.median(clipped)) if len(clipped) else np.nan

    ok = (frac >= MIN_ANNULUS_FRAC_ON_CHIP
          and n_pix >= MIN_ANNULUS_PIXELS
          and np.isfinite(bkg))
    return bkg, n_pix, frac, bool(ok)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    floor = pd.read_csv(APERTURE_FLOOR_CSV)
    coords = pd.read_csv(COORDS_CSV)

    merged = floor.merge(coords[["object", "ra_deg", "dec_deg"]], on="object", how="inner")
    n_no_coords = floor["object"].nunique() - merged["object"].nunique()
    if n_no_coords > 0:
        print(f"[warn] {n_no_coords} objects have a seeing floor but no resolved "
              f"coordinate -- skipped.")

    # One results list per annulus setting.
    results = {setting: [] for setting in ANNULUS_SETTINGS}

    n_total = len(merged)
    n_missing_file = 0

    for i, row in enumerate(merged.itertuples(index=False), 1):
        fname = f"{row.object}_{row.filter}_comb_{row.telescope}.fits"
        fits_path = os.path.join(FITS_DIR, fname)
        if not os.path.exists(fits_path):
            n_missing_file += 1
            print(f"[{i}/{n_total}] [skip] file not found: {fname}")
            continue

        # Read the frame once; every annulus setting reuses it.
        with fits.open(fits_path) as hdul:
            data = hdul[0].data.astype(float)
            wcs = WCS(hdul[0].header)

        x_pix, y_pix = wcs.all_world2pix(row.ra_deg, row.dec_deg, 0)
        x_pix, y_pix = float(x_pix), float(y_pix)

        radii_pix, radii_arcsec = zip(*[kpc_to_pixels(r, row.z) for r in APERTURE_GRID_KPC])

        # --- Raw aperture sums: independent of the background, measured once ---
        raw_sums, areas = [], []
        for r_pix in radii_pix:
            aperture = CircularAperture((x_pix, y_pix), r=r_pix)
            phot = aperture_photometry(data, aperture)
            raw_sums.append(float(phot["aperture_sum"][0]))
            areas.append(float(aperture.area))
        raw_sums = np.array(raw_sums)
        areas = np.array(areas)

        # --- Apply each candidate background ---
        for (ann_in_kpc, ann_out_kpc) in ANNULUS_SETTINGS:
            r_in_pix, _ = kpc_to_pixels(ann_in_kpc, row.z)
            r_out_pix, _ = kpc_to_pixels(ann_out_kpc, row.z)

            bkg, n_pix, frac_on_chip, ann_ok = background_from_annulus(
                data, x_pix, y_pix, r_in_pix, r_out_pix)

            fluxes = raw_sums - bkg * areas

            for r_kpc, r_pix, r_arcsec, flux in zip(
                    APERTURE_GRID_KPC, radii_pix, radii_arcsec, fluxes):
                results[(ann_in_kpc, ann_out_kpc)].append({
                    # --- columns preserved from script 10 ---
                    "object": row.object,
                    "telescope": row.telescope,
                    "filter": row.filter,
                    "z": row.z,
                    "radius_kpc": r_kpc,
                    "radius_arcsec": r_arcsec,
                    "radius_pix": r_pix,
                    "flux_bkgsub": flux,
                    "seeing_safe": r_kpc >= row.sigma_min_kpc,
                    # --- diagnostics added here ---
                    "annulus_inner_kpc": ann_in_kpc,
                    "annulus_outer_kpc": ann_out_kpc,
                    "annulus_outer_pix": r_out_pix,
                    "bkg_per_pixel": bkg,
                    "annulus_n_pix": n_pix,
                    "annulus_frac_on_chip": frac_on_chip,
                    "annulus_ok": ann_ok,
                })

        if i % 25 == 0 or i == n_total:
            print(f"[{i}/{n_total}] processed")

    # ----------------------------------------------------------------------
    # Write one file per setting, plus a comparison summary
    # ----------------------------------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    summary_rows = []

    for (ann_in, ann_out), rows in results.items():
        df = pd.DataFrame(rows)
        tag = f"ann{ann_in:g}-{ann_out:g}"
        path = os.path.join(OUT_DIR, f"curve_of_growth_{tag}.csv")
        df.to_csv(path, index=False)

        per_obj = df.drop_duplicates(subset=["object", "telescope", "filter"])
        n_meas = len(per_obj)
        n_ok = int(per_obj["annulus_ok"].sum())

        # Every statistic below is computed on guard-passing rows ONLY. An
        # annulus that ran off the detector produced a background measured from
        # whichever part of it landed on the chip; including those values makes
        # the cross-setting comparison meaningless, because the objects that
        # fail differ between settings (the nearest hosts fail first, their
        # annuli being largest in pixels). Mixing them in would show a trend in
        # median background that is really a change of sample.
        ok = df[df["annulus_ok"]]
        per_obj_ok = ok.drop_duplicates(subset=["object", "telescope", "filter"])

        piv = ok.pivot_table(index=["object", "telescope", "filter"],
                             columns="radius_kpc", values="flux_bkgsub")
        ratio = np.nan
        if 5.0 in piv.columns and 10.0 in piv.columns:
            rr = (piv[10.0] / piv[5.0]).replace([np.inf, -np.inf], np.nan).dropna()
            ratio = float((rr > 1.5).mean()) if len(rr) else np.nan

        med5 = np.nan
        if 5.0 in piv.columns:
            med5 = float(np.nanmedian(piv[5.0]))

        summary_rows.append({
            "annulus_inner_kpc": ann_in,
            "annulus_outer_kpc": ann_out,
            "n_measurements": n_meas,
            "n_annulus_ok": n_ok,
            "frac_annulus_ok": n_ok / n_meas if n_meas else np.nan,
            "median_bkg_per_pixel": (float(np.nanmedian(per_obj_ok["bkg_per_pixel"]))
                                     if len(per_obj_ok) else np.nan),
            "median_flux_at_5kpc": med5,
            "frac_still_rising_5_to_10kpc": ratio,
            "output_file": os.path.basename(path),
        })
        print(f"\nWrote {len(df)} rows ({n_meas} object-image combinations) -> {path}")
        print(f"  annulus usable for {n_ok}/{n_meas} "
              f"({100 * n_ok / n_meas:.1f}%) at {ann_in:g}-{ann_out:g} kpc")
        print(f"  summary statistics below computed on those {n_ok} only")

    summary = pd.DataFrame(summary_rows)
    summary_path = os.path.join(OUT_DIR, "annulus_setting_comparison.csv")
    summary.to_csv(summary_path, index=False)

    print("\n" + "=" * 78)
    print("ANNULUS SETTING COMPARISON")
    print("=" * 78)
    print(summary.to_string(index=False))
    print("=" * 78)
    print("""
How to read this:

  frac_annulus_ok
      Fraction of measurements where the annulus fitted on the detector with
      enough usable pixels. Expect this to fall as the annulus widens. Objects
      failing the guard need a different background strategy, not a wider
      annulus -- exclude them or treat them separately, but do not let them
      through unflagged.

  median_bkg_per_pixel   (guard-passing measurements only)
      Should DECREASE as the annulus moves outward if the inner annulus was
      contaminated by host light. If it is flat across settings, the original
      10-15 kpc annulus was probably clean after all and the concern is closed.

  median_flux_at_5kpc
      Should INCREASE as the background falls, since less is being subtracted.
      This propagates directly into the calibrated magnitudes and hence the
      final catalogue -- expect the sample to grow slightly, since more objects
      will clear the positive-flux and minimum-count cuts.

  frac_still_rising_5_to_10kpc
      Fraction of curves whose enclosed flux is still climbing by more than
      50 per cent between 5 and 10 kpc.

CAUTION: the objects that fail the guard differ between settings, so the rows
contributing to each line of this table are not the same. Treat this table as a
first look only. For a controlled comparison run 19_annulus_sensitivity_driver.py,
which restricts every setting to the subset of object-images usable in all of
them.

Next: re-run scripts 11 and 18 against each output file, restricted to rows
with annulus_ok == True, and compare the scatter-versus-radius relation across
settings. If its shape is stable, the null result in Section 3 stands and the
spread across settings can be quoted as a systematic. If the shape moves, the
relation was being driven by the background, which would also explain the
spurious signal reported by the earlier version of the analysis.
""")


if __name__ == "__main__":
    main()