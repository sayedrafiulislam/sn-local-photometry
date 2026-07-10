"""
06_clean_group_summary.py

Final Phase 1 deliverable: the per-telescope, per-filter seeing
characterization to be used for the Phase 4 aperture floor calculation,
computed after excluding all images flagged in image_quality_flags.csv.

Flagged images fall into (at least) three confirmed failure modes,
found via visual inspection during Phase 1 development:
  - uniformly soft / likely out-of-focus images (flag_very_soft)
  - images contaminated by satellite/cosmic-ray trails or saturated-star
    bleed artifacts (caught by flag_high_scatter)
  - images where detected "stars" are actually clumps/knots within a
    bright, well-resolved host galaxy rather than field stars (also
    caught by flag_high_scatter)

This is documented here, not silently dropped -- consistent with the
exclusion-logging approach used in Phase 2 (redshift resolution).
"""

import pandas as pd
import numpy as np

PER_STAR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\psf_fwhm_per_star.csv"
FLAGS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\image_quality_flags.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\psf_fwhm_summary_clean.csv"
EXCLUDED_LOG_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\excluded_images_phase1.csv"

stars = pd.read_csv(PER_STAR_CSV)
flags = pd.read_csv(FLAGS_CSV)

flagged_files = set(flags.loc[flags["any_flag"], "file"])
print(f"Excluding {len(flagged_files)} flagged images out of {flags['file'].nunique()} total.\n")

clean_stars = stars[~stars["file"].isin(flagged_files)]

summary = (
    clean_stars.groupby(["telescope", "filter"])["fwhm_avg_arcsec"]
    .agg(n_stars="count", median="median", mean="mean", std="std",
         p16=lambda s: np.percentile(s, 16),
         p84=lambda s: np.percentile(s, 84))
    .reset_index()
)
summary.to_csv(OUT_PATH, index=False)

print("Clean per-group PSF summary (flagged images excluded):\n")
print(summary.to_string(index=False))
print(f"\nSaved to: {OUT_PATH}")

# Auditable exclusion log
excluded = flags.loc[flags["any_flag"],
                      ["telescope", "filter", "file", "n_stars", "median",
                       "flag_high_scatter", "flag_very_soft", "flag_few_stars"]].copy()
excluded.to_csv(EXCLUDED_LOG_PATH, index=False)
print(f"Excluded-image log saved to: {EXCLUDED_LOG_PATH}")

# Quick before/after comparison, for a sanity check on how much this mattered
raw_summary = (
    stars.groupby(["telescope", "filter"])["fwhm_avg_arcsec"]
    .agg(median="median")
    .reset_index()
    .rename(columns={"median": "median_with_flagged"})
)
compare = summary[["telescope", "filter", "median"]].rename(
    columns={"median": "median_clean"}
).merge(raw_summary, on=["telescope", "filter"])
compare["shift_arcsec"] = compare["median_clean"] - compare["median_with_flagged"]
print("\nEffect of exclusion on group median FWHM:\n")
print(compare.to_string(index=False))

