"""
10_curve_of_growth.py

Phase 4, step 2: the actual curve-of-growth photometry. For every
object with both a resolved redshift (Phase 2) and a resolved SN
position (Phase 3 Q2 / script 08), measure aperture flux at a grid of
physical radii (default 1-10 kpc, matching the grid already tested for
seeing-safety in script 07), following Kelsey et al. (2021) Section
4.1's approach of testing a range of aperture sizes rather than
committing to one.

BACKGROUND METHOD (v2): a local annulus around each object, rather
than a whole-image median. The first version used a whole-image
sigma-clipped median, which produced curves that never flattened
(ASAS14ad, KISS13v) -- a residual background offset gets multiplied
by aperture area at every radius, so the "flux" kept climbing all the
way to 10 kpc instead of leveling off once the aperture had captured
the source. A local annulus (here: 10-15 kpc from the SN position,
i.e. just outside the largest aperture tested) gives a background
estimate that's actually representative of the sky near the object,
at the cost of assuming the host's light doesn't extend past 15 kpc --
reasonable for this sample's typical galaxy sizes, but worth
revisiting for any unusually large/nearby host.

No formal per-point flux uncertainty is computed yet either -- that
depends on the zero-point calibration (Phase 5), which hasn't been
incorporated.
"""

import os
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS
from astropy.cosmology import FlatLambdaCDM
from astropy.stats import SigmaClip
from photutils.aperture import CircularAperture, CircularAnnulus, aperture_photometry, ApertureStats

FITS_DIR = r"D:\Thesis\pd\CSPAll"
APERTURE_FLOOR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\aperture_floor_per_object.csv"
COORDS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\curve_of_growth.csv"

COSMO = FlatLambdaCDM(H0=70, Om0=0.3)
PLATE_SCALE_ARCSEC_PER_PIX = 0.23
APERTURE_GRID_KPC = np.arange(1.0, 10.5, 0.5)

LOCAL_ANNULUS_INNER_KPC = 10.0  # matches the largest aperture radius tested
LOCAL_ANNULUS_OUTER_KPC = 15.0  # buffer beyond that


def kpc_to_pixels(radius_kpc, z, cosmo=COSMO, plate_scale=PLATE_SCALE_ARCSEC_PER_PIX):
    """Physical aperture radius (kpc) -> angular size (arcsec) -> pixels, at redshift z."""
    d_a_mpc = cosmo.angular_diameter_distance(z).value
    theta_rad = (radius_kpc / 1000.0) / d_a_mpc  # small-angle approx, same regime as Kelsey et al.
    theta_arcsec = np.rad2deg(theta_rad) * 3600.0
    return theta_arcsec / plate_scale, theta_arcsec


def measure_curve_of_growth(fits_path, x_pix, y_pix, radii_pix, z):
    with fits.open(fits_path) as hdul:
        data = hdul[0].data.astype(float)

    # Local background: sigma-clipped median flux per pixel within an
    # annulus around the object, converted to this object's physical
    # scale so the annulus sits just outside the largest tested aperture.
    r_in_pix, _ = kpc_to_pixels(LOCAL_ANNULUS_INNER_KPC, z)
    r_out_pix, _ = kpc_to_pixels(LOCAL_ANNULUS_OUTER_KPC, z)
    annulus = CircularAnnulus((x_pix, y_pix), r_in=r_in_pix, r_out=r_out_pix)
    annulus_stats = ApertureStats(data, annulus, sigma_clip=SigmaClip(sigma=3.0))
    local_bkg_per_pixel = annulus_stats.median

    fluxes = []
    for r_pix in radii_pix:
        aperture = CircularAperture((x_pix, y_pix), r=r_pix)
        phot_table = aperture_photometry(data, aperture)
        raw_sum = phot_table["aperture_sum"][0]
        bkg_subtracted = raw_sum - local_bkg_per_pixel * aperture.area
        fluxes.append(bkg_subtracted)
    return fluxes


def main():
    floor = pd.read_csv(APERTURE_FLOOR_CSV)
    coords = pd.read_csv(COORDS_CSV)

    merged = floor.merge(coords[["object", "ra_deg", "dec_deg"]], on="object", how="inner")
    n_no_coords = floor["object"].nunique() - merged["object"].nunique()
    if n_no_coords > 0:
        print(f"[warn] {n_no_coords} objects had a seeing-floor measurement "
              f"but no resolved coordinate -- skipped. Expected to be small.")

    results = []
    n_total = len(merged)
    for i, row in enumerate(merged.itertuples(index=False), 1):
        fname = f"{row.object}_{row.filter}_comb_{row.telescope}.fits"
        fits_path = os.path.join(FITS_DIR, fname)
        if not os.path.exists(fits_path):
            print(f"[{i}/{n_total}] [skip] file not found: {fname}")
            continue

        with fits.open(fits_path) as hdul:
            wcs = WCS(hdul[0].header)
        x_pix, y_pix = wcs.all_world2pix(row.ra_deg, row.dec_deg, 0)

        radii_pix, radii_arcsec = zip(*[kpc_to_pixels(r, row.z) for r in APERTURE_GRID_KPC])
        fluxes = measure_curve_of_growth(fits_path, x_pix, y_pix, radii_pix, row.z)

        for r_kpc, r_pix, r_arcsec, flux in zip(APERTURE_GRID_KPC, radii_pix, radii_arcsec, fluxes):
            results.append({
                "object": row.object,
                "telescope": row.telescope,
                "filter": row.filter,
                "z": row.z,
                "radius_kpc": r_kpc,
                "radius_arcsec": r_arcsec,
                "radius_pix": r_pix,
                "flux_bkgsub": flux,
                "seeing_safe": r_kpc >= row.sigma_min_kpc,
            })

        if i % 25 == 0 or i == n_total:
            print(f"[{i}/{n_total}] processed")

    out_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out_df.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(out_df)} rows ({out_df['object'].nunique()} objects "
          f"x {len(APERTURE_GRID_KPC)} radii) -> {OUT_PATH}")


if __name__ == "__main__":
    main()