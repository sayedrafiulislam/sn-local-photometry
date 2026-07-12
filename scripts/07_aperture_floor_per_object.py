"""
07_aperture_floor_per_object.py

Phase 4, step 1: for every object in the working sample, determine the
seeing-limited minimum physical aperture radius (in kpc) at its own
redshift, using its own measured image FWHM rather than one fixed
group-wide number.

This is the direct analogue of Kelsey et al. (2021), Fig. 2 / Section
2.2.3 / 4.1: they show the apparent angular size of fixed physical
apertures (3, 4, 5 kpc) as a function of redshift, and compare against
a single seeing floor (sigma_min ~= 0.55") to find where a fixed-kpc
aperture becomes seeing-limited. Here, because per-image FWHM is
available (Phase 1) rather than one number for the whole sample, each
object's own image quality sets its own floor.

Method:
1. For each object, look up its FWHM (per relevant telescope+filter
   image) from the Phase 1 clean per-star/per-file measurements, and
   its redshift from the Phase 2 resolved catalog.
2. Convert FWHM -> sigma_min (arcsec) via FWHM = 2.355 * sigma.
3. Convert sigma_min (arcsec) -> a physical size (kpc) at the object's
   redshift, using the same FlatLambdaCDM(H0=70, Om0=0.3) cosmology
   used throughout this project, via the angular diameter distance.
4. For a candidate aperture grid (default 1-10 kpc in 0.5 kpc steps),
   flag which grid radii are seeing-safe (i.e. larger than the
   object's own floor) versus seeing-limited, for that object.

Output: aperture_floor_per_object.csv -- one row per object per
telescope+filter combination it has imaging in, with its redshift,
measured FWHM, sigma_min in arcsec and kpc, and the smallest safe
grid radius.
"""

import numpy as np
import pandas as pd
from astropy.cosmology import FlatLambdaCDM

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
COSMO = FlatLambdaCDM(H0=70, Om0=0.3)
FWHM_TO_SIGMA = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))  # 2.355 factor

# Candidate physical aperture grid to test in the curve-of-growth step
APERTURE_GRID_KPC = np.arange(1.0, 10.5, 0.5)

PER_FILE_SUMMARY_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\per_file_summary.csv"
FLAGS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\image_quality_flags.csv"
REDSHIFT_CATALOG_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_catalog_final.csv"  # confirmed columns: file, object, filter, telescope, redshift, ned_resolved_name, ned_error
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\aperture_floor_per_object.csv"


def sigma_min_arcsec(fwhm_arcsec):
    """Seeing-limited minimum aperture radius, in arcsec (Kelsey et al. relation)."""
    return fwhm_arcsec * FWHM_TO_SIGMA


def arcsec_to_kpc(theta_arcsec, z, cosmo=COSMO):
    """
    Convert an angular size to a physical size at redshift z, using the
    angular diameter distance. This is the same physical<->angular
    conversion direction used throughout the project (just inverted --
    elsewhere we go kpc -> arcsec for a fixed aperture; here we go
    arcsec -> kpc for the seeing floor).
    """
    d_a_mpc = cosmo.angular_diameter_distance(z).value  # Mpc
    theta_rad = np.deg2rad(theta_arcsec / 3600.0)
    return theta_rad * d_a_mpc * 1000.0  # kpc


def main():
    per_file = pd.read_csv(PER_FILE_SUMMARY_CSV)
    flags = pd.read_csv(FLAGS_CSV)
    redshifts = pd.read_csv(REDSHIFT_CATALOG_CSV)

    # sn_catalog_final.csv has one row per FILE (object+filter+telescope),
    # with the same redshift repeated for every file belonging to that
    # object. De-duplicate down to one redshift per object before merging,
    # so we don't accidentally create extra rows.
    redshifts_by_object = (
        redshifts[["object", "redshift"]]
        .drop_duplicates(subset="object")
        .rename(columns={"redshift": "z"})
    )

    # Drop flagged (excluded) images, same as the Phase 1 clean summary
    flagged_files = set(flags.loc[flags["any_flag"], "file"])
    clean = per_file[~per_file["file"].isin(flagged_files)].copy()

    # Extract object name from filename (matches the <object>_<filter>_comb_<telescope>.fits convention)
    clean["object"] = clean["file"].str.extract(r"^(.+?)_[BV]_comb_(?:dup|swo)\.fits$")

    # Merge in redshift. Matching on "object" alone sidesteps the fact that
    # the redshift catalog spells telescopes "duPont"/"Swope" while the
    # Phase 1 outputs use "dup"/"swo" -- redshift doesn't depend on
    # telescope anyway, so this is a safe simplification, not a shortcut.
    merged = clean.merge(redshifts_by_object, on="object", how="inner")

    n_unmatched = clean["object"].nunique() - merged["object"].nunique()
    if n_unmatched > 0:
        print(f"[warn] {n_unmatched} objects with PSF measurements had no "
              f"redshift match -- likely objects excluded in Phase 2. "
              f"This is expected, not an error.")

    merged["sigma_min_arcsec"] = sigma_min_arcsec(merged["median"])
    merged["sigma_min_kpc"] = merged.apply(
        lambda row: arcsec_to_kpc(row["sigma_min_arcsec"], row["z"]), axis=1
    )

    # Smallest grid radius that clears this object's own seeing floor
    def smallest_safe_radius(sigma_min_kpc):
        safe = APERTURE_GRID_KPC[APERTURE_GRID_KPC >= sigma_min_kpc]
        return safe[0] if len(safe) > 0 else np.nan

    merged["smallest_safe_grid_radius_kpc"] = merged["sigma_min_kpc"].apply(smallest_safe_radius)

    out_cols = ["object", "telescope", "filter", "file", "z", "median",
                "sigma_min_arcsec", "sigma_min_kpc", "smallest_safe_grid_radius_kpc"]
    result = merged[out_cols].rename(columns={"median": "fwhm_arcsec"})

    import os
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    result.to_csv(OUT_PATH, index=False)

    print(f"Wrote {len(result)} rows -> {OUT_PATH}\n")
    print("Summary of sigma_min_kpc (how small is the seeing floor, physically):")
    print(result.groupby(["telescope", "filter"])["sigma_min_kpc"].describe().to_string())

    n_all_safe = (result["smallest_safe_grid_radius_kpc"] <= APERTURE_GRID_KPC.min()).sum()
    print(f"\n{n_all_safe} / {len(result)} images have a seeing floor below "
          f"the smallest grid radius tested ({APERTURE_GRID_KPC.min()} kpc) -- "
          f"i.e. the entire aperture grid is seeing-safe for these.")


if __name__ == "__main__":
    main()