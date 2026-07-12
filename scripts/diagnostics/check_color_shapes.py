"""
check_color_shapes.py

Plots instrumental B-V color vs aperture radius for a few
representative objects. This is the shape that actually matters for
choosing an aperture radius (unlike raw flux, which has no reason to
plateau for an extended galaxy) -- following Kelsey et al.'s logic of
looking at how a derived local quantity behaves across a radius grid,
adapted here to straight aperture color as a first pass.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import os

COLOR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\local_color_vs_radius.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

CHECK_OBJECTS = ["SN2012fr", "ASAS14ad", "KISS13v"]

df = pd.read_csv(COLOR_CSV)

for obj in CHECK_OBJECTS:
    sub = df[df["object"] == obj].sort_values("radius_kpc")
    if sub.empty:
        print(f"[skip] {obj} not in local_color_vs_radius.csv "
              f"(likely Swope-only, excluded from this step)")
        continue

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sub["radius_kpc"], sub["instrumental_B_minus_V"], marker="o", markersize=4)
    ax.set_xlabel("Aperture radius (kpc)")
    ax.set_ylabel("Instrumental B - V (uncalibrated)")
    ax.set_title(f"Local color vs radius: {obj}")

    out_path = os.path.join(OUT_DIR, f"color_check_{obj}.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Saved: {out_path}")