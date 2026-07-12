"""
17_plot_final_bv_distribution.py

Generates the calibrated local B-V distribution histogram for the
paper's Results section, using the final clean sample (quality-flagged
and undefined-color objects excluded, same definition as the "clean
sample" printed by script 16).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

IN_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration\calibrated_color_5kpc_flagged.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration\bv_distribution.png"

df = pd.read_csv(IN_PATH)
clean = df[~df["flag_low_flux"] & df["B_minus_V"].notna()]

fig, ax = plt.subplots(figsize=(7, 5))
ax.hist(clean["B_minus_V"], bins=15, color="steelblue", edgecolor="black")
ax.axvline(clean["B_minus_V"].median(), color="black", linestyle="--",
           linewidth=1.2, label=f"median = {clean['B_minus_V'].median():.2f}")
ax.set_xlabel("Local $B-V$ colour (mag)")
ax.set_ylabel("Number of objects")
ax.set_title(f"Calibrated local $B-V$ colour at 5.0 kpc (n={len(clean)})")
ax.legend()

fig.tight_layout()
fig.savefig(OUT_PATH, dpi=150)
print(f"Saved: {OUT_PATH}")
print(f"n = {len(clean)}, median = {clean['B_minus_V'].median():.3f}, "
      f"IQR = [{clean['B_minus_V'].quantile(0.25):.3f}, {clean['B_minus_V'].quantile(0.75):.3f}]")