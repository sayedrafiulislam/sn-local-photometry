"""
13_curve_of_growth.py

Supersedes 10b_curve_of_growth_annulus_test.py. The measurement and the
multi-annulus design are unchanged; four defects found in the audit of 10b are
corrected, and the guards are extended to cover the aperture as well as the
background annulus.

10b was verified against 10_curve_of_growth.py before this rewrite: the
ann10-15 setting reproduced script 10 across all 10184 rows with a maximum
relative difference of exactly zero. The two backgrounds were computed by
independently written code (ApertureStats with sigma_clip in script 10, a
hand-rolled mask-and-clip here), so that agreement is a genuine check on both
rather than a tautology. Nothing in this file changes that logic.


WHAT WAS WRONG WITH 10b
-----------------------

(1) THE APERTURE HAD NO ON-CHIP GUARD, ONLY THE ANNULUS.

    10b measured how much of the background annulus landed on the detector and
    flagged the cases where too little did. It did not do the same for the
    photometric aperture. photutils.aperture_photometry returns the sum of
    whichever pixels exist without complaint, while aperture.area returns the
    full geometric pi*r^2. Subtracting bkg_per_pixel * area from a partial sum
    removes background for pixels that were never summed. The resulting deficit
    grows as r^2 -- the same functional form as annulus contamination, arriving
    from the opposite direction, and invisible to every check 10b performed.

    At z = 0.004 a 10 kpc aperture spans 526 pixels on a 2470-pixel frame with
    the supernova sitting off centre, so this is reachable, not hypothetical.

    Non-finite pixels are the same problem in a different costume. CSP combined
    stacks carry NaN in the dither margins. A single NaN inside the aperture
    propagates to the sum and the whole curve becomes NaN, silently. 10b
    produced 38 such rows -- two object-images, NaN at every radius -- and
    nothing recorded why.

    Fixed by measuring, for every aperture at every radius,
    `aperture_frac_on_chip` and `aperture_n_nonfinite`, and setting
    `aperture_ok` from both. Note that the pixels are FLAGGED, NOT MASKED.
    Masking would replace a visibly missing measurement with a plausible-looking
    partial one, which is the failure mode being corrected here, not a fix for
    it.

(2) MIN_ANNULUS_PIXELS = 200 WAS A RULE THAT COULD NEVER FIRE.

    For an absolute floor of 200 pixels to bind while the 80 per cent on-chip
    test passed, the annulus would need a total area below roughly 250 pixels.
    The smallest annulus anywhere in this sample is 20-30 kpc at z = 0.137,
    which is pi*(54^2 - 36^2) ~ 5100 pixels: twenty times the threshold. So
    `annulus_ok` was the on-chip fraction and nothing else, while the code and
    the methods section both implied two independent criteria.

    This is the third appearance of one pattern in this pipeline -- a threshold
    in fixed units applied to a sample spanning a wide range of scales. Fixed by
    making the floor relative: a minimum fraction of the pixel count the annulus
    is geometrically expected to contain.

(3) THE PLATE SCALE WAS HARD-CODED AT 0.23 ARCSEC/PIXEL.

    Three scales are present in the imaging: 0.230 (585 frames), 0.430 (119, all
    Swope V, the SITe3 CCD) and 0.159 (12). Assuming 0.230 throughout makes every
    Swope V radius 1.87x too large in pixels, so the aperture labelled 5 kpc
    encloses 9.3 kpc of galaxy.

    Colours are not affected, because script 11 selects du Pont only and du Pont
    is 0.230. The guard is affected: an over-large r_out_pix makes Swope annuli
    appear to overflow detectors they physically fit on, so the usable-measurement
    counts reported from 10b are wrong for those frames.

    Fixed by taking the per-file scale from 07b's audited output, and verifying
    each one against the frame's own WCS at read time. Disagreements are
    reported rather than absorbed.

(4) THE FITS FILENAME WAS RECONSTRUCTED RATHER THAN READ.

    10b built its path as f"{object}_{filter}_comb_{telescope}.fits". Any frame
    whose real name departs from that pattern was reported as missing and
    dropped. The input CSV carries the actual filename in its `file` column;
    this version uses it.


A CONSEQUENCE OF (3) WORTH KNOWING BEFORE YOU RUN THIS
------------------------------------------------------
This script reads aperture_floor_per_object_corrected.csv (541 rows) where 10b
read aperture_floor_per_object.csv (536). The five extra object-images are a
real change of input sample, not a bug in either script, and the row count of
the output will change accordingly. Check the printed funnel.


WHAT IS DELIBERATELY NOT FIXED
------------------------------
The `annulus_ok` guard fails on the largest ANGULAR annuli, which means the
LOWEST-REDSHIFT hosts. Moving from a 10-15 to a 20-30 kpc annulus therefore
changes which objects survive as well as changing the background: 2 failures at
10-15 (median z = 0.059) against 11 at 20-30 (median z = 0.0050). That
crossover reproduces, from the data alone, the z ~ 0.0051 threshold derived
independently from frame geometry.

This is a selection effect, not an error, and the right response is to declare
it in the sample-selection section rather than to code around it. Only one of
the affected objects reaches the final catalogue.


OUTPUT
------
  curve_of_growth_ann10-15.csv
  curve_of_growth_ann15-25.csv
  curve_of_growth_ann20-30.csv
  annulus_setting_comparison.csv

Same filenames as 10b, so scripts 11, 15, 18 and 19 need no path edits. Existing
files are renamed to *.bak_YYYYmmdd_HHMMSS before writing, never deleted.

Column names from script 10 are preserved. New columns are additions:
plate_scale_used, aperture_frac_on_chip, aperture_n_nonfinite, aperture_ok,
annulus_frac_expected_pix.

DOWNSTREAM: filter on `annulus_ok AND aperture_ok`. 10b's instruction to filter
on annulus_ok alone is no longer sufficient.
"""

import os
import shutil
import datetime
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from astropy.cosmology import FlatLambdaCDM
from astropy.stats import SigmaClip
from photutils.aperture import CircularAperture, CircularAnnulus, aperture_photometry

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
FITS_DIR = r"D:\Thesis\pd\CSPAll"
BASE_DIR = r"D:\Thesis\My Work\sn-local-photometry\results"
APERTURE_FLOOR_CSV = os.path.join(BASE_DIR, "phase4_aperture",
                                  "aperture_floor_per_object_corrected.csv")
COORDS_CSV = os.path.join(BASE_DIR, "sn_coordinates.csv")
OUT_DIR = os.path.join(BASE_DIR, "phase4_aperture")

COSMO = FlatLambdaCDM(H0=70, Om0=0.3)
APERTURE_GRID_KPC = np.arange(1.0, 10.5, 0.5)

ANNULUS_SETTINGS = [
    (10.0, 15.0),   # reproduces script 10, kept for comparison
    (15.0, 25.0),
    (20.0, 30.0),   # the setting the catalogue is built from
]

# Guards -- all relative, none absolute.
MIN_ANNULUS_FRAC_ON_CHIP = 0.80   # fraction of the annulus landing on detector
MIN_ANNULUS_FRAC_PIXELS = 0.30    # replaces MIN_ANNULUS_PIXELS = 200
MIN_APERTURE_FRAC_ON_CHIP = 0.98  # apertures are small; near-total is required
SIGMA_CLIP = SigmaClip(sigma=3.0, maxiters=5)

# Fall back to this only if a frame carries no usable WCS and no audited scale.
FALLBACK_PLATE_SCALE = 0.23
PLATE_SCALE_TOL = 0.02            # arcsec; CSV vs WCS disagreement worth reporting


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
def kpc_to_pixels(radius_kpc, z, plate_scale, cosmo=COSMO):
    """Physical radius (kpc) -> angular size (arcsec) -> pixels, at redshift z.

    The plate scale is an explicit argument with no default. That is the whole
    point of this version: there is no single correct value to default to.
    """
    d_a_mpc = cosmo.angular_diameter_distance(z).value
    theta_rad = (radius_kpc / 1000.0) / d_a_mpc      # small-angle, as Kelsey et al.
    theta_arcsec = np.rad2deg(theta_rad) * 3600.0
    return theta_arcsec / plate_scale, theta_arcsec


def wcs_plate_scale(wcs):
    """Mean pixel scale in arcsec from the WCS CD/PC matrix, or NaN."""
    try:
        scales = proj_plane_pixel_scales(wcs.celestial) * 3600.0
        return float(np.mean(scales))
    except Exception:
        return np.nan


def mask_values(data, aperture):
    """
    Finite pixel values inside an aperture that actually lie on the detector,
    plus the counts needed to judge whether the measurement can be trusted.

    Returns (values, n_finite, n_nonfinite, frac_on_chip).

    photutils tolerates an aperture running off the image edge and returns
    statistics from whatever remains. The returned fraction is the only thing
    distinguishing a clean measurement from one made on half an aperture.
    """
    mask = aperture.to_mask(method="center")
    try:
        raw = mask.get_values(data)                 # photutils >= 1.0
    except AttributeError:                          # older photutils
        cutout = mask.multiply(data)
        raw = np.array([]) if cutout is None else cutout[mask.data > 0]

    raw = np.asarray(raw, dtype=float)
    finite = np.isfinite(raw)
    values = raw[finite]

    expected = aperture.area
    frac = len(raw) / expected if expected > 0 else 0.0
    return values, len(values), int((~finite).sum()), float(np.clip(frac, 0.0, 1.0))


def background_from_annulus(data, x_pix, y_pix, r_in_pix, r_out_pix):
    """Sigma-clipped median background per pixel, with its trust diagnostics."""
    ann = CircularAnnulus((x_pix, y_pix), r_in=r_in_pix, r_out=r_out_pix)
    values, n_pix, _, frac = mask_values(data, ann)

    expected_pix = ann.area
    frac_expected = n_pix / expected_pix if expected_pix > 0 else 0.0

    if n_pix == 0:
        return np.nan, 0, 0.0, 0.0, False

    clipped = SIGMA_CLIP(values, masked=False, copy=True)
    clipped = clipped[np.isfinite(clipped)]
    bkg = float(np.median(clipped)) if len(clipped) else np.nan

    ok = (frac >= MIN_ANNULUS_FRAC_ON_CHIP
          and frac_expected >= MIN_ANNULUS_FRAC_PIXELS
          and np.isfinite(bkg))
    return bkg, n_pix, frac, float(frac_expected), bool(ok)


def backup(path):
    """Rename an existing output out of the way. Nothing is ever deleted."""
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    floor = pd.read_csv(APERTURE_FLOOR_CSV)
    coords = pd.read_csv(COORDS_CSV)

    has_scale_col = "plate_scale" in floor.columns
    if not has_scale_col:
        print("[warn] input carries no plate_scale column -- falling back to the "
              "frame WCS for every file. Prefer 07b's corrected output.")

    merged = floor.merge(coords[["object", "ra_deg", "dec_deg"]],
                         on="object", how="inner")

    print("=" * 78)
    print("INPUT FUNNEL")
    print("=" * 78)
    print(f"  aperture-floor rows          : {len(floor)}")
    print(f"  distinct objects             : {floor['object'].nunique()}")
    print(f"  after merge on coordinates   : {len(merged)} rows, "
          f"{merged['object'].nunique()} objects")
    print(f"  lost for want of coordinates : "
          f"{floor['object'].nunique() - merged['object'].nunique()} objects")
    print("=" * 78 + "\n")

    results = {s: [] for s in ANNULUS_SETTINGS}
    n_total = len(merged)
    n_missing_file, n_no_wcs, n_scale_mismatch = 0, 0, 0
    scale_report = []

    for i, row in enumerate(merged.itertuples(index=False), 1):
        # (4) use the recorded filename, do not reconstruct it
        fname = getattr(row, "file", None)
        if not isinstance(fname, str) or not fname:
            fname = f"{row.object}_{row.filter}_comb_{row.telescope}.fits"
        fits_path = os.path.join(FITS_DIR, fname)

        if not os.path.exists(fits_path):
            n_missing_file += 1
            print(f"[{i}/{n_total}] [skip] file not found: {fname}")
            continue

        with fits.open(fits_path) as hdul:
            data = hdul[0].data.astype(float)
            try:
                wcs = WCS(hdul[0].header)
            except Exception:
                wcs = None

        if wcs is None or not wcs.has_celestial:
            n_no_wcs += 1
            print(f"[{i}/{n_total}] [skip] no usable WCS: {fname}")
            continue

        # (3) per-file plate scale, audited value preferred, WCS as the check
        scale_wcs = wcs_plate_scale(wcs)
        scale_csv = float(getattr(row, "plate_scale", np.nan)) if has_scale_col else np.nan

        if np.isfinite(scale_csv):
            plate_scale = scale_csv
            if np.isfinite(scale_wcs) and abs(scale_wcs - scale_csv) > PLATE_SCALE_TOL:
                n_scale_mismatch += 1
                scale_report.append((fname, scale_csv, scale_wcs))
        elif np.isfinite(scale_wcs):
            plate_scale = scale_wcs
        else:
            plate_scale = FALLBACK_PLATE_SCALE

        ny, nx = data.shape
        x_pix, y_pix = wcs.all_world2pix(row.ra_deg, row.dec_deg, 0)
        x_pix, y_pix = float(x_pix), float(y_pix)

        radii_pix, radii_arcsec = zip(
            *[kpc_to_pixels(r, row.z, plate_scale) for r in APERTURE_GRID_KPC])

        # ------------------------------------------------------------------
        # (1) Raw sums AND aperture guards. Background-independent, so both
        #     are measured once per frame and reused across annulus settings.
        # ------------------------------------------------------------------
        raw_sums, areas, ap_fracs, ap_nans, ap_oks = [], [], [], [], []
        for r_pix in radii_pix:
            ap = CircularAperture((x_pix, y_pix), r=r_pix)
            phot = aperture_photometry(data, ap)
            raw_sums.append(float(phot["aperture_sum"][0]))
            areas.append(float(ap.area))

            _, _, n_bad, frac = mask_values(data, ap)
            ap_fracs.append(frac)
            ap_nans.append(n_bad)
            ap_oks.append(bool(frac >= MIN_APERTURE_FRAC_ON_CHIP and n_bad == 0))

        raw_sums = np.array(raw_sums)
        areas = np.array(areas)

        # ------------------------------------------------------------------
        # Apply each candidate background
        # ------------------------------------------------------------------
        for (ann_in_kpc, ann_out_kpc) in ANNULUS_SETTINGS:
            r_in_pix, _ = kpc_to_pixels(ann_in_kpc, row.z, plate_scale)
            r_out_pix, _ = kpc_to_pixels(ann_out_kpc, row.z, plate_scale)

            bkg, n_pix, frac_chip, frac_exp, ann_ok = background_from_annulus(
                data, x_pix, y_pix, r_in_pix, r_out_pix)

            fluxes = raw_sums - bkg * areas

            for j, r_kpc in enumerate(APERTURE_GRID_KPC):
                results[(ann_in_kpc, ann_out_kpc)].append({
                    # --- preserved from script 10 ---
                    "object": row.object,
                    "telescope": row.telescope,
                    "filter": row.filter,
                    "z": row.z,
                    "radius_kpc": r_kpc,
                    "radius_arcsec": radii_arcsec[j],
                    "radius_pix": radii_pix[j],
                    "flux_bkgsub": fluxes[j],
                    "seeing_safe": r_kpc >= row.sigma_min_kpc,
                    # --- annulus diagnostics, from 10b ---
                    "annulus_inner_kpc": ann_in_kpc,
                    "annulus_outer_kpc": ann_out_kpc,
                    "annulus_outer_pix": r_out_pix,
                    "bkg_per_pixel": bkg,
                    "annulus_n_pix": n_pix,
                    "annulus_frac_on_chip": frac_chip,
                    "annulus_frac_expected_pix": frac_exp,
                    "annulus_ok": ann_ok,
                    # --- new here ---
                    "file": fname,
                    "plate_scale_used": plate_scale,
                    "aperture_frac_on_chip": ap_fracs[j],
                    "aperture_n_nonfinite": ap_nans[j],
                    "aperture_ok": ap_oks[j],
                })

        if i % 25 == 0 or i == n_total:
            print(f"[{i}/{n_total}] processed")

    # ----------------------------------------------------------------------
    # Write
    # ----------------------------------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    summary_rows = []

    for (ann_in, ann_out), rows in results.items():
        df = pd.DataFrame(rows)
        tag = f"ann{ann_in:g}-{ann_out:g}"
        path = os.path.join(OUT_DIR, f"curve_of_growth_{tag}.csv")
        backup(path)
        df.to_csv(path, index=False)

        per_obj = df.drop_duplicates(subset=["object", "telescope", "filter"])
        n_meas = len(per_obj)
        n_ann_ok = int(per_obj["annulus_ok"].sum())

        # Both guards, on rows only -- aperture_ok is per radius, not per frame.
        good = df[df["annulus_ok"] & df["aperture_ok"]]
        per_good = good.drop_duplicates(subset=["object", "telescope", "filter"])

        piv = good.pivot_table(index=["object", "telescope", "filter"],
                               columns="radius_kpc", values="flux_bkgsub")
        ratio = np.nan
        if 5.0 in piv.columns and 10.0 in piv.columns:
            rr = (piv[10.0] / piv[5.0]).replace([np.inf, -np.inf], np.nan).dropna()
            ratio = float((rr > 1.5).mean()) if len(rr) else np.nan
        med5 = float(np.nanmedian(piv[5.0])) if 5.0 in piv.columns else np.nan

        summary_rows.append({
            "annulus_inner_kpc": ann_in,
            "annulus_outer_kpc": ann_out,
            "n_measurements": n_meas,
            "n_annulus_ok": n_ann_ok,
            "frac_annulus_ok": n_ann_ok / n_meas if n_meas else np.nan,
            "n_rows_both_guards_ok": len(good),
            "n_rows_total": len(df),
            "median_bkg_per_pixel": (float(np.nanmedian(per_good["bkg_per_pixel"]))
                                     if len(per_good) else np.nan),
            "median_flux_at_5kpc": med5,
            "frac_still_rising_5_to_10kpc": ratio,
            "n_negative_flux_rows": int((good["flux_bkgsub"] < 0).sum()),
            "output_file": os.path.basename(path),
        })

        print(f"\nWrote {len(df)} rows ({n_meas} object-images) -> {path}")
        print(f"  annulus usable      : {n_ann_ok}/{n_meas} "
              f"({100 * n_ann_ok / n_meas:.1f}%)")
        print(f"  rows passing BOTH   : {len(good)}/{len(df)} "
              f"({100 * len(good) / len(df):.1f}%)")

    summary = pd.DataFrame(summary_rows)
    summary_path = os.path.join(OUT_DIR, "annulus_setting_comparison.csv")
    backup(summary_path)
    summary.to_csv(summary_path, index=False)

    # ----------------------------------------------------------------------
    # Report
    # ----------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("PLATE SCALE")
    print("=" * 78)
    all_rows = pd.DataFrame(results[ANNULUS_SETTINGS[0]])
    if len(all_rows):
        used = all_rows.drop_duplicates(subset=["file"])["plate_scale_used"]
        print("  scales used, by frame:")
        print(used.round(3).value_counts().sort_index().to_string())
    print(f"  frames skipped, file missing : {n_missing_file}")
    print(f"  frames skipped, no WCS       : {n_no_wcs}")
    print(f"  CSV/WCS disagreements >{PLATE_SCALE_TOL}\" : {n_scale_mismatch}")
    for fname, s_csv, s_wcs in scale_report[:10]:
        print(f"    {fname}: csv {s_csv:.3f}  wcs {s_wcs:.3f}")

    print("\n" + "=" * 78)
    print("ANNULUS SETTING COMPARISON")
    print("=" * 78)
    print(summary.to_string(index=False))
    print("=" * 78)
    print("""
How to read this:

  frac_annulus_ok
      Fraction of frames where the annulus fitted on the detector. Expect it to
      fall as the annulus widens, and expect the failures to be the nearest
      hosts, whose annuli are largest in pixels. Those objects need a different
      background strategy, not a wider annulus.

  n_rows_both_guards_ok
      New here. A row can have a perfectly good background and still be
      unusable because the aperture itself ran off the chip or contained
      non-finite pixels. Everything below is computed on these rows only.

  median_bkg_per_pixel
      Should FALL as the annulus moves outward if the inner annulus was sitting
      in host light. Flat across settings would mean the 10-15 kpc annulus was
      clean and the concern closes.

  median_flux_at_5kpc
      Should RISE as the background falls, since less is being subtracted.

  n_negative_flux_rows
      Now measured on guard-passing rows only, so a residual count here is a
      statement about the measurement floor rather than about geometry: where
      the local surface brightness is at sky level, background-subtracted flux
      is noise, and noise is negative half the time.

CAUTION: the frames failing the guard differ between settings, so the rows
behind each line are not the same sample. For a controlled comparison run
22_annulus_sensitivity.py, which restricts every setting to the frames
usable in all of them.

DOWNSTREAM: filter on annulus_ok AND aperture_ok. 10b's instruction to filter on
annulus_ok alone no longer covers everything that can go wrong.
""")


if __name__ == "__main__":
    main()