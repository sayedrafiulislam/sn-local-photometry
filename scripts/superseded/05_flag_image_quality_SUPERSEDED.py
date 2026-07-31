"""
05_flag_image_quality.py

Applies simple, documented rules to flag individual images as likely
defective (out-of-focus, cloud-affected, tracking error) based on their
per-image PSF FWHM statistics, rather than requiring manual visual
inspection of all 715 files.

Rules (tune thresholds after checking a handful of flagged/unflagged
examples by eye):

  1. HIGH_SCATTER  : mad_sigma(FWHM) > SCATTER_THRESHOLD_ARCSEC
     A large robust scatter (median absolute deviation, scaled to be
     comparable to a standard deviation) within a single image is the
     signature of a non-Gaussian PSF (e.g. a donut-shaped out-of-focus
     PSF), confirmed visually in ASAS14lq_V_comb_swo.fits.
     NOTE: earlier versions tried raw std, then percentile-based IQR.
     Both proved unreliable at n=16-25 stars: std is overly sensitive
     to a single bad-fit outlier, and IQR (p84-p16) is set by roughly
     the 3rd/4th most extreme value at this sample size, so it can
     either barely react to real problems or overreact to 1-2 stray
     points landing near that rank. mad_std uses the median of absolute
     deviations from the median -- a nested-median statistic that isn't
     dominated by tail rank position the way percentiles are.

  2. VERY_SOFT      : median(FWHM) > SOFT_THRESHOLD_ARCSEC
     Uniformly poor seeing across the whole image (confirmed visually
     in ASAS14mw_V_comb_swo.fits) -- data may still be usable but
     should be excluded from a "typical seeing" characterization, and
     may need special handling in the aperture floor calculation.

  3. FEW_STARS      : n_stars < MIN_STARS
     Too few valid star fits to trust the per-image statistic at all.

Output: image_quality_flags.csv, an auditable log of every image, its
statistics, and any flag(s) raised -- following the same
"document, don't silently drop" principle used for the Phase 2
redshift exclusion log.
"""

import pandas as pd

PER_FILE_SUMMARY_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\per_file_summary.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\image_quality_flags.csv"

# --- thresholds: starting points, revisit after checking a few examples ---
SCATTER_THRESHOLD_ARCSEC = 0.6   # comparable scale to std, but computed
                                  # via the more robust mad_std estimator
SOFT_THRESHOLD_ARCSEC = 2.0      # ASAS14mw (median=2.52) should trip this;
                                  # your dup/swo group medians are ~0.9-1.2
MIN_STARS = 8                    # below this, don't trust the per-image statistic

df = pd.read_csv(PER_FILE_SUMMARY_CSV)

df["flag_high_scatter"] = df["mad_sigma"] > SCATTER_THRESHOLD_ARCSEC
df["flag_very_soft"] = df["median"] > SOFT_THRESHOLD_ARCSEC
df["flag_few_stars"] = df["n_stars"] < MIN_STARS

df["any_flag"] = df[["flag_high_scatter", "flag_very_soft", "flag_few_stars"]].any(axis=1)

df.to_csv(OUT_PATH, index=False)

n_flagged = df["any_flag"].sum()
print(f"Flagged {n_flagged} / {len(df)} images for review.\n")
print(df[df["any_flag"]][
    ["telescope", "filter", "file", "n_stars", "median", "mad_sigma", "std",
     "flag_high_scatter", "flag_very_soft", "flag_few_stars"]
].to_string(index=False))
print(f"\nFull log (all images, flagged or not) saved to: {OUT_PATH}")
