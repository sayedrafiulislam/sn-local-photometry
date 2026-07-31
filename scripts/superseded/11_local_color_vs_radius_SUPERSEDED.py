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

--------------------------------------------------------------------
REVISION: BACKGROUND ANNULUS
--------------------------------------------------------------------
This script now reads the output of 10b_curve_of_growth_annulus_test.py
rather than the original 10_curve_of_growth.py.

The original background annulus at 10-15 kpc was contaminated by host
light. Measured across 525 object-images common to all three settings,
the median background per pixel falls from 1.351 counts (10-15 kpc) to
0.364 (15-25 kpc) to 0.189 (20-30 kpc) -- an 86 per cent drop. Fitting
an exponential-plus-constant profile to those three points gives a disk
scale length of 5.2 kpc and a true sky level of 0.078 counts per pixel,
implying that roughly 94 per cent of what the original annulus measured
as "background" was in fact galaxy light.

Because the subtracted quantity is (background per pixel) x (aperture
area), that error is multiplied by pi*r^2 and therefore grows with
aperture radius. At the 5 kpc fiducial it amounted to about 5.8 per cent
of the measured flux, or 61 millimag. The 20-30 kpc annulus adopted here
leaves an estimated 5 millimag of residual over-subtraction, which is
negligible against the 117 millimag per-object colour uncertainty; a
wider annulus is therefore not required.

Rows where the annulus did not fit on the detector are excluded via the
annulus_ok flag. Their background was measured from whichever part of
the annulus landed on the chip and is not meaningful. Note that this
filter must be applied here rather than downstream, since photutils does
not raise on a partially off-image aperture -- it silently returns
statistics from the surviving pixels.

To switch annulus settings, change ANNULUS_TAG below; nothing else needs
editing.
"""

import os
import shutil
import numpy as np
import pandas as pd

# Which annulus setting to build the analysis from. One of the tags written
# by 10b_curve_of_growth_annulus_test.py: "ann10-15", "ann15-25", "ann20-30".
ANNULUS_TAG = "ann20-30"

BASE_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
COG_CSV = os.path.join(BASE_DIR, f"curve_of_growth_{ANNULUS_TAG}.csv")
OUT_PATH = os.path.join(BASE_DIR, "local_color_vs_radius.csv")

# Written once, the first time this script overwrites a pre-existing result,
# so the original 10-15 kpc version is never lost to a re-run.
BACKUP_PATH = os.path.join(BASE_DIR, "local_color_vs_radius_pre_annulus_fix.csv")


def main():
    if not os.path.exists(COG_CSV):
        raise SystemExit(
            f"Input not found:\n  {COG_CSV}\n"
            f"Run 10b_curve_of_growth_annulus_test.py first, or change "
            f"ANNULUS_TAG at the top of this script."
        )

    print(f"Annulus setting: {ANNULUS_TAG}")
    print(f"Reading: {os.path.basename(COG_CSV)}\n")

    df = pd.read_csv(COG_CSV)
    n_rows_raw = len(df)

    # --- exclude measurements whose annulus did not fit on the detector ---
    if "annulus_ok" in df.columns:
        keys = ["object", "telescope", "filter"]
        per_meas = df.drop_duplicates(subset=keys)
        n_meas = len(per_meas)
        n_bad = int((~per_meas["annulus_ok"]).sum())
        df = df[df["annulus_ok"]]
        print(f"[info] annulus guard: {n_meas - n_bad}/{n_meas} object-images "
              f"usable ({n_bad} excluded, annulus off the detector)")
    else:
        print("[warn] no annulus_ok column found -- this looks like output from "
              "the original script 10. Proceeding without the guard, but the "
              "background may be contaminated by host light.")

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
                           "that the curve-of-growth file actually contains both "
                           "filters for at least some du Pont objects.")

    # Color is only defined for positive flux in both bands -- negative or
    # zero flux (possible at small radii for faint objects, or from
    # background-subtraction noise) makes log10 undefined.
    valid = (pivot["B"] > 0) & (pivot["V"] > 0)
    n_invalid = int((~valid).sum())
    print(f"[info] {n_invalid} / {len(pivot)} (object, radius) points have "
          f"non-positive flux in B and/or V -- color undefined for these, "
          f"marked as NaN rather than dropped, so gaps are visible rather "
          f"than silently missing.")

    # Suppress the expected log10-of-negative warning; those entries are
    # already masked to NaN by `valid`.
    with np.errstate(invalid="ignore", divide="ignore"):
        pivot["instrumental_B_minus_V"] = np.where(
            valid, -2.5 * np.log10(pivot["B"] / pivot["V"]), np.nan
        )

    # --- preserve any previous result before overwriting ---
    if os.path.exists(OUT_PATH) and not os.path.exists(BACKUP_PATH):
        shutil.copy2(OUT_PATH, BACKUP_PATH)
        print(f"\n[info] previous result backed up -> {os.path.basename(BACKUP_PATH)}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    pivot.to_csv(OUT_PATH, index=False)

    print(f"\nWrote {len(pivot)} rows ({pivot['object'].nunique()} objects) -> {OUT_PATH}")

    at_5 = pivot[np.isclose(pivot["radius_kpc"], 5.0)]
    print(f"\nAt the 5.0 kpc fiducial radius:")
    print(f"  objects with a defined instrumental colour : "
          f"{int(at_5['instrumental_B_minus_V'].notna().sum())}")
    print(f"  median instrumental B-V                    : "
          f"{np.nanmedian(at_5['instrumental_B_minus_V']):.4f}")


if __name__ == "__main__":
    main()