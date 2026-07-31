"""
13_color_scatter_bootstrap.py

Adds uncertainty bands to the color-scatter-vs-radius curve via
bootstrap resampling of OBJECTS (not individual points), so the
result properly accounts for object-to-object variation rather than
treating each (object, radius) row as an independent sample.

At each radius, resample the set of objects with replacement N_BOOT
times, recompute the robust scatter (mad_std) for each resample, and
take the 16th/84th percentile of the resulting distribution as an
uncertainty band. This tells us whether the dip seen in the raw curve
(script 12) is a real, statistically supported minimum or just noise
in a scatter estimate built from ~200 objects.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.stats import mad_std

COLOR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\local_color_vs_radius.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

N_BOOT = 1000
RNG = np.random.default_rng(42)  # fixed seed -- reproducible, document this in the paper


def bootstrap_scatter(values, n_boot=N_BOOT, rng=RNG):
    """Bootstrap the robust scatter (mad_std) of an array of color values."""
    values = values.dropna().to_numpy()
    if len(values) < 5:
        return np.nan, np.nan, np.nan
    n = len(values)
    boot_scatters = np.empty(n_boot)
    for i in range(n_boot):
        resample = rng.choice(values, size=n, replace=True)
        boot_scatters[i] = mad_std(resample)
    point_estimate = mad_std(values)
    lo, hi = np.percentile(boot_scatters, [16, 84])
    return point_estimate, lo, hi


df = pd.read_csv(COLOR_CSV)

rows = []
for radius, group in df.groupby("radius_kpc"):
    point, lo, hi = bootstrap_scatter(group["instrumental_B_minus_V"])
    rows.append({"radius_kpc": radius, "scatter": point,
                 "scatter_lo": lo, "scatter_hi": hi})

result = pd.DataFrame(rows)
out_csv = f"{OUT_DIR}\\color_scatter_bootstrap.csv"
result.to_csv(out_csv, index=False)
print(result.to_string(index=False))
print(f"\nSaved: {out_csv}")

best_idx = result["scatter"].idxmin()
best_radius = result.loc[best_idx, "radius_kpc"]
print(f"\nMinimum point-estimate scatter at radius = {best_radius} kpc")

# Which radii have an uncertainty band overlapping the minimum's band?
# Those are statistically indistinguishable from "best" -- can't be
# treated as significantly worse just because their point estimate is
# slightly higher.
best_lo, best_hi = result.loc[best_idx, ["scatter_lo", "scatter_hi"]]
overlapping = result[(result["scatter_lo"] <= best_hi) & (result["scatter_hi"] >= best_lo)]
print(f"Radii statistically indistinguishable from the minimum (overlapping "
      f"16-84th percentile bands): {sorted(overlapping['radius_kpc'].tolist())}")

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(result["radius_kpc"], result["scatter"], marker="o", color="tab:blue")
ax.fill_between(result["radius_kpc"], result["scatter_lo"], result["scatter_hi"],
                alpha=0.25, color="tab:blue")
ax.axvline(best_radius, color="gray", linestyle="--", linewidth=1,
           label=f"minimum: {best_radius} kpc")
ax.set_xlabel("Aperture radius (kpc)")
ax.set_ylabel("Robust scatter in instrumental B-V (mag)")
ax.set_title("Local color scatter vs radius, with bootstrap 16-84th percentile band")
ax.legend()

fig.tight_layout()
out_png = f"{OUT_DIR}\\color_scatter_bootstrap.png"
fig.savefig(out_png, dpi=130)
print(f"Saved: {out_png}")