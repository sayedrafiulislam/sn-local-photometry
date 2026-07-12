"""
check_per_file_summary.py

Aggregates star-level FWHM measurements up to the image level, so we can
see whether specific files are systematically bad (every star in that
image has poor FWHM -- consistent with a real bad-seeing/tracking-error
night) versus scattered noise across many files (which would instead
point to a detection/fitting issue in the pipeline).
"""

import numpy as np
import pandas as pd
from astropy.stats import mad_std

PER_STAR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\psf_fwhm_per_star.csv"

df = pd.read_csv(PER_STAR_CSV)

per_file = (
    df.groupby(["telescope", "filter", "file"])["fwhm_avg_arcsec"]
    .agg(n_stars="count", median="median", mean="mean", std="std", max="max",
         mad_sigma=lambda s: mad_std(s))
    .reset_index()
    .sort_values("median", ascending=False)
)

print("Per-file PSF summary, worst 15 by median FWHM:\n")
print(per_file.head(15).to_string(index=False))

out_path = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\per_file_summary.csv"
per_file.to_csv(out_path, index=False)
print(f"\nFull per-file summary saved to: {out_path}")
