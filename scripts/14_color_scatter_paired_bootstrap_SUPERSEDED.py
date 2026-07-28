"""
14_color_scatter_paired_bootstrap.py

Fixes a weakness in script 13: that version bootstrapped each radius
INDEPENDENTLY, drawing a separate random resample of objects for every
radius. Since the same ~200 objects appear at every radius, their
per-object noise is shared across radii -- an independent-per-radius
bootstrap can't see that shared structure, so its uncertainty bands
come out wider than necessary (like comparing two matched samples
with an unpaired test instead of a paired one).

This version does a PAIRED bootstrap: each iteration draws one random
set of object indices (with replacement), then computes the scatter
at EVERY radius using that same set of objects. This lets us look
directly at the distribution of (scatter at radius A - scatter at the
apparent minimum) per iteration, cancelling the shared object-level
noise -- a much more sensitive test of whether the dip in script 13
is real.
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
RNG = np.random.default_rng(42)
REFERENCE_RADIUS = 6.5  # the point-estimate minimum from script 13


def robust_scatter_ignore_nan(values):
    values = values[~np.isnan(values)]
    if len(values) < 5:
        return np.nan
    return mad_std(values)


df = pd.read_csv(COLOR_CSV)

# Wide table: one row per object, one column per radius
wide = df.pivot_table(index="object", columns="radius_kpc",
                       values="instrumental_B_minus_V")
radii = sorted(wide.columns.tolist())
n_objects = len(wide)
data = wide[radii].to_numpy()  # shape: (n_objects, n_radii)

boot_scatter = np.empty((N_BOOT, len(radii)))
for i in range(N_BOOT):
    idx = RNG.integers(0, n_objects, size=n_objects)  # same resampled objects for every radius this iteration
    resampled = data[idx, :]
    for j in range(len(radii)):
        boot_scatter[i, j] = robust_scatter_ignore_nan(resampled[:, j])

point_estimate = np.array([robust_scatter_ignore_nan(data[:, j]) for j in range(len(radii))])
band_lo = np.nanpercentile(boot_scatter, 16, axis=0)
band_hi = np.nanpercentile(boot_scatter, 84, axis=0)

ref_idx = radii.index(REFERENCE_RADIUS)
# Paired difference per bootstrap iteration: scatter(r) - scatter(reference),
# using the SAME resampled objects for both -- this is the key improvement.
diff = boot_scatter - boot_scatter[:, [ref_idx]]
diff_lo = np.nanpercentile(diff, 16, axis=0)
diff_hi = np.nanpercentile(diff, 84, axis=0)
significantly_worse = diff_lo > 0  # band entirely above zero -> genuinely worse than the reference

result = pd.DataFrame({
    "radius_kpc": radii,
    "scatter": point_estimate,
    "scatter_lo": band_lo,
    "scatter_hi": band_hi,
    "diff_vs_ref_lo": diff_lo,
    "diff_vs_ref_hi": diff_hi,
    "significantly_worse_than_ref": significantly_worse,
})
out_csv = f"{OUT_DIR}\\color_scatter_paired_bootstrap.csv"
result.to_csv(out_csv, index=False)
print(result.to_string(index=False))
print(f"\nSaved: {out_csv}")

n_sig_worse = significantly_worse.sum()
print(f"\n{n_sig_worse} / {len(radii)} radii are statistically WORSE than "
      f"the {REFERENCE_RADIUS} kpc reference (paired 16-84th percentile of "
      f"the difference excludes zero).")
if n_sig_worse == 0:
    print("None -- the paired test still can't distinguish any radius from "
          "the reference. This is a genuinely different (more powerful) test "
          "than script 13's, so this result carries more weight if it also "
          "comes back flat.")

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(result["radius_kpc"], result["scatter"], marker="o", color="tab:blue")
ax.fill_between(result["radius_kpc"], result["scatter_lo"], result["scatter_hi"],
                alpha=0.25, color="tab:blue", label="independent 16-84th band")
ax.axvline(REFERENCE_RADIUS, color="gray", linestyle="--", linewidth=1,
           label=f"reference: {REFERENCE_RADIUS} kpc")
worse = result[result["significantly_worse_than_ref"]]
if len(worse) > 0:
    ax.scatter(worse["radius_kpc"], worse["scatter"], color="red", zorder=5,
               label="significantly worse (paired test)")
ax.set_xlabel("Aperture radius (kpc)")
ax.set_ylabel("Robust scatter in instrumental B-V (mag)")
ax.set_title("Color scatter vs radius -- paired bootstrap significance test")
ax.legend()

fig.tight_layout()
out_png = f"{OUT_DIR}\\color_scatter_paired_bootstrap.png"
fig.savefig(out_png, dpi=130)
print(f"Saved: {out_png}")