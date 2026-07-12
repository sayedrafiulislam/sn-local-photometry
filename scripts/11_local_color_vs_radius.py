"""
11_local_color_vs_radius.py

The actual quantity of interest for the thesis: local B-V color as a
function of aperture radius, not raw single-band flux. Flux from an
extended host galaxy has no reason to plateau (Phase 4 diagnostic:
ASAS14ad's light genuinely extends past 15 kpc) -- but color, being a
ratio between two bands, can stabilize even while both bands' raw
flux keep growing, IF the local stellar population is roughly uniform
in colour at that scale. If it doesn't stabilize, that is itself an
astrophysically interesting result (a color gradient), not a bug.

SCOPE NOTE: only du Pont B+V pairs are used here (same telescope, same
night-to-night systematics). Swope only has V-band imaging in this
dataset, so no same-telescope color is possible for swo-only objects
-- those are excluded from this step, not silently dropped (see the
printed count below).

NOT YET PHOTOMETRICALLY CALIBRATED: this uses instrumental
(zero-point-free) color, -2.5*log10(flux_B/flux_V), which differs
from the true calibrated B-V color by a constant offset that depends
on the Phase 5 zero-point calibration (not yet incorporated). This is
fine for looking at the SHAPE of color vs radius, not for absolute
color values yet.
"""

import numpy as np
import pandas as pd

COG_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\curve_of_growth.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\local_color_vs_radius.csv"

df = pd.read_csv(COG_CSV)

# Only du Pont has both B and V -- restrict to that telescope for a
# same-telescope color, and pivot so B and V flux sit side by side per
# object/radius.
dup = df[df["telescope"] == "dup"]
n_swo_only_objects = df[~df["object"].isin(dup["object"])]["object"].nunique()
if n_swo_only_objects > 0:
    print(f"[info] {n_swo_only_objects} objects have no du Pont B/V pair "
          f"(Swope-only) -- excluded from local color, not silently lost "
          f"from the project overall.")

pivot = dup.pivot_table(
    index=["object", "z", "radius_kpc"],
    columns="filter",
    values="flux_bkgsub"
).reset_index()

if "B" not in pivot.columns or "V" not in pivot.columns:
    raise RuntimeError("Expected both B and V columns after pivoting -- check "
                        "that curve_of_growth.csv actually contains both filters "
                        "for at least some du Pont objects.")

# Color is only defined for positive flux in both bands -- negative or
# zero flux (possible at small radii for faint objects, or from
# background-subtraction noise) makes log10 undefined.
valid = (pivot["B"] > 0) & (pivot["V"] > 0)
n_invalid = (~valid).sum()
print(f"[info] {n_invalid} / {len(pivot)} (object, radius) points have "
      f"non-positive flux in B and/or V -- color undefined for these, "
      f"marked as NaN rather than dropped, so gaps are visible rather "
      f"than silently missing.")

pivot["instrumental_B_minus_V"] = np.where(
    valid, -2.5 * np.log10(pivot["B"] / pivot["V"]), np.nan
)

pivot.to_csv(OUT_PATH, index=False)
print(f"\nWrote {len(pivot)} rows ({pivot['object'].nunique()} objects) -> {OUT_PATH}")