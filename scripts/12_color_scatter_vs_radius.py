"""
12_color_scatter_vs_radius.py

Population-level view of local color vs radius, mirroring the logic
of Kelsey et al. (2021) Fig. 10: rather than looking at 2-3 individual
objects, look at how the SCATTER in local color across the whole
sample changes with aperture radius. This is what actually informs a
fiducial aperture choice -- a radius where scatter is small suggests
color measurements there are stable/trustworthy across the sample; a
radius where scatter blows up suggests noise or contamination (as
seen individually in KISS13v) is dominating.

Also reports the fraction of objects with a DEFINED color at each
radius, since Phase 4 testing showed ~11% of points have undefined
color from non-positive flux -- this fraction may itself vary with
radius (e.g. worse at small radii for faint objects) and is worth
seeing directly rather than only looking at scatter among the objects
that do have a valid value.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astropy.stats import mad_std

COLOR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\local_color_vs_radius.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

df = pd.read_csv(COLOR_CSV)

summary = (
    df.groupby("radius_kpc")
    .agg(
        n_total=("object", "count"),
        n_valid=("instrumental_B_minus_V", lambda s: s.notna().sum()),
        median_color=("instrumental_B_minus_V", "median"),
        scatter_mad=("instrumental_B_minus_V", lambda s: mad_std(s.dropna()) if s.notna().sum() > 1 else np.nan),
    )
    .reset_index()
)
summary["valid_fraction"] = summary["n_valid"] / summary["n_total"]

out_csv = f"{OUT_DIR}\\color_scatter_summary.csv"
summary.to_csv(out_csv, index=False)
print("Population-level local color summary by aperture radius:\n")
print(summary.to_string(index=False))
print(f"\nSaved: {out_csv}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)

ax1.plot(summary["radius_kpc"], summary["scatter_mad"], marker="o")
ax1.set_ylabel("Robust scatter in instrumental B-V\n(mad_std, mag)")
ax1.set_title("Local color scatter across the sample vs aperture radius")

ax2.plot(summary["radius_kpc"], summary["valid_fraction"], marker="o", color="tab:orange")
ax2.set_ylabel("Fraction of objects\nwith defined color")
ax2.set_xlabel("Aperture radius (kpc)")
ax2.set_ylim(0, 1.05)

fig.tight_layout()
out_png = f"{OUT_DIR}\\color_scatter_vs_radius.png"
fig.savefig(out_png, dpi=130)
print(f"Saved: {out_png}")


