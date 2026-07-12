"""
16_flag_low_flux_colors.py

Empirical finding (from checking the most extreme calibrated colors):
the most implausible B-V values (e.g. CSP13aam at +2.28 mag, SN2011jn
at -0.93 mag) all come from objects with low absolute flux in at least
one band -- a few hundred counts, versus thousands-to-hundreds-of-
thousands for the more believable measurements. This is consistent
with noise dominating a small flux value rather than a real
astrophysical color gradient, but this is a heuristic flag, not a
formal signal-to-noise cut (which would require photon/read noise and
gain information not yet incorporated anywhere in this pipeline --
flagged as a real gap, not glossed over).

This script flags (does not silently drop) objects where flux_B or
flux_V falls below MIN_FLUX_COUNTS, following the same
document-don't-drop approach used throughout this project.
"""

import pandas as pd

IN_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration\calibrated_color_5kpc.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration\calibrated_color_5kpc_flagged.csv"

MIN_FLUX_COUNTS = 1000  # heuristic threshold -- revisit once formal S/N is available

df = pd.read_csv(IN_PATH)

df["flag_low_flux"] = (df["flux_B"] < MIN_FLUX_COUNTS) | (df["flux_V"] < MIN_FLUX_COUNTS)

n_flagged = df["flag_low_flux"].sum()
n_valid_color = df["B_minus_V"].notna().sum()
print(f"{n_flagged} / {len(df)} objects flagged for low flux "
      f"(< {MIN_FLUX_COUNTS} counts in B and/or V).")

df.to_csv(OUT_PATH, index=False)
print(f"Saved: {OUT_PATH}")

clean = df[~df["flag_low_flux"] & df["B_minus_V"].notna()]
print(f"\nClean sample (flux-flagged and undefined-color objects excluded): "
      f"{len(clean)} objects")
print(clean["B_minus_V"].describe().to_string())