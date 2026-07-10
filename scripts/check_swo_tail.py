"""
check_swo_tail.py

Quick diagnostic: load the per-star PSF FWHM measurements, isolate the
Swope (swo) telescope entries, and print the 20 worst (largest FWHM)
individual star measurements. Used to check whether the right-skewed
swo-V distribution seen in the Phase 1 summary is driven by a handful
of genuinely bad-seeing images/nights, or by a fitting/detection issue
(e.g. repeated identical positions, one file dominating the list).
"""

import pandas as pd

PER_STAR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\psf_fwhm_per_star.csv"

df = pd.read_csv(PER_STAR_CSV)

swo = df[df["telescope"] == "swo"].copy()
swo_sorted = swo.sort_values("fwhm_avg_arcsec", ascending=False)

cols_to_show = ["object", "filter", "file", "x", "y", "fwhm_avg_pix", "fwhm_avg_arcsec"]

print(f"Total swo star measurements: {len(swo)}\n")
print("Top 20 worst (largest FWHM) swo star measurements:\n")
print(swo_sorted[cols_to_show].head(20).to_string(index=False))

out_path = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\swo_tail_check.csv"
swo_sorted[cols_to_show].head(20).to_csv(out_path, index=False)
print(f"\nAlso saved to: {out_path}")