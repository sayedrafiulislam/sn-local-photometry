"""
check_curve_shapes.py

Sanity check on the Phase 4 curve-of-growth output: plots flux vs
aperture radius for a few representative objects, so the SHAPE can be
checked by eye before trusting the batch. A well-behaved curve of
growth should rise steeply at small radii, then flatten out as the
aperture starts enclosing mostly background/sky rather than new
source flux. Points below each object's own seeing floor (from
Phase 4 step 1) are marked in a different color, since those
shouldn't be over-interpreted.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import os

COG_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\curve_of_growth.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

# A mix: one well-resolved bright host (good test of background handling),
# one "normal" object, one higher-z edge case from the seeing-floor check
CHECK_OBJECTS = ["SN2012fr", "ASAS14ad", "KISS13v"]

df = pd.read_csv(COG_CSV)

for obj in CHECK_OBJECTS:
    sub = df[df["object"] == obj]
    if sub.empty:
        print(f"[skip] {obj} not found in curve_of_growth.csv (may have been "
              f"excluded earlier in the pipeline)")
        continue

    fig, ax = plt.subplots(figsize=(7, 5))
    for (tel, filt), group in sub.groupby(["telescope", "filter"]):
        group = group.sort_values("radius_kpc")
        safe = group[group["seeing_safe"]]
        unsafe = group[~group["seeing_safe"]]
        line, = ax.plot(group["radius_kpc"], group["flux_bkgsub"],
                         marker="o", markersize=3, label=f"{tel}-{filt}")
        if len(unsafe) > 0:
            ax.scatter(unsafe["radius_kpc"], unsafe["flux_bkgsub"],
                       color=line.get_color(), marker="x", s=60, zorder=5)

    ax.set_xlabel("Aperture radius (kpc)")
    ax.set_ylabel("Background-subtracted flux (counts)")
    ax.set_title(f"Curve of growth: {obj}\n(x markers = below that image's seeing floor)")
    ax.legend()
    ax.axhline(0, color="gray", linewidth=0.7, linestyle="--")

    out_path = os.path.join(OUT_DIR, f"cog_check_{obj}.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Saved: {out_path}")