"""
15_apply_zero_points.py

Phase 5: apply the supervisor-provided zero-point calibration files to
convert instrumental flux (at the fiducial 5.0 kpc aperture chosen in
Phase 4) into calibrated B and V magnitudes, and a calibrated local
B-V color.

Zero-point file format (confirmed from B_ZP_dup.dat):
    <object>  <zero_point_mag>  <zero_point_err>  <n_ref_stars>
space-delimited, no header.

mag = ZP - 2.5*log10(flux)
color (B-V) = mag_B - mag_V = (ZP_B - ZP_V) - 2.5*log10(flux_B/flux_V)
            = (ZP_B - ZP_V) + instrumental_(B-V)
i.e. the calibrated color is just the existing uncalibrated color from
script 11, shifted by the zero-point difference for that object.

Only du Pont B+V is used here, consistent with script 11 (Swope has no
B-band imaging in this data set).

UNCERTAINTY NOTE: color_err here only propagates the zero-point
uncertainties (zp_err_B, zp_err_V) in quadrature. It does NOT yet
include the statistical/photon-noise uncertainty on the aperture flux
itself, which hasn't been formally derived anywhere in the pipeline so
far. This is a real gap worth closing before the final paper -- flagged
here rather than presented as a complete error budget.

--------------------------------------------------------------------
REVISION: BACKGROUND ANNULUS
--------------------------------------------------------------------
This script now reads the output of 10b_curve_of_growth_annulus_test.py
rather than the original 10_curve_of_growth.py, for the reasons set out
in script 11.

In brief: the original 10-15 kpc background annulus sat inside the
host's light. Across the 525 object-images common to all three settings
tested, the median background per pixel falls from 1.351 counts
(10-15 kpc) to 0.189 (20-30 kpc), an 86 per cent drop, and a profile fit
implies roughly 94 per cent of the original "background" was galaxy
light rather than sky. Since the subtracted quantity scales with
aperture area, this over-subtraction reached about 5.8 per cent of the
flux at the 5 kpc fiducial -- some 61 millimag, which propagates
directly into the magnitudes computed below.

The effect on colour is smaller than on flux, because B and V are both
over-subtracted and much of the error cancels in the ratio; the residual
is the differential part, driven by the host's colour gradient between
the annulus and the aperture. Measured across settings, the median
instrumental B-V at 5 kpc shifts by about -0.025 mag, and the number of
objects with a defined colour rises (higher fluxes clear the
positive-flux and minimum-count cuts), so the final sample grows
slightly rather than shrinking.

The annulus_ok filter must be applied here as well as in script 11,
since this script reads the curve-of-growth file directly rather than
script 11's output.

To switch annulus settings, change ANNULUS_TAG below; nothing else needs
editing.
"""

import os
import shutil
import numpy as np
import pandas as pd

# Which annulus setting to build the catalogue from. Must match the tag used
# in script 11, or the calibrated colours will not correspond to the colours
# analysed in script 18.
ANNULUS_TAG = "ann20-30"

ZP_DIR = r"D:\Thesis\My Work\sn-local-photometry\data"
ZP_FILES = {
    ("dup", "B"): "B_ZP_dup.dat",
    ("dup", "V"): "V_ZP_dup.dat",
    ("swo", "B"): "B_ZP_swo.dat",
    ("swo", "V"): "V_ZP_swo.dat",
}

COG_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
COG_CSV = os.path.join(COG_DIR, f"curve_of_growth_{ANNULUS_TAG}.csv")

OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
OUT_PATH = os.path.join(OUT_DIR, "calibrated_color_5kpc.csv")
BACKUP_PATH = os.path.join(OUT_DIR, "calibrated_color_5kpc_pre_annulus_fix.csv")

FIDUCIAL_RADIUS_KPC = 5.0


def load_zp_file(path):
    df = pd.read_csv(path, sep=r"\s+", header=None,
                     names=["object", "zp", "zp_err", "n_ref_stars"])
    return df


def main():
    zp_tables = {}
    for (tel, filt), fname in ZP_FILES.items():
        path = os.path.join(ZP_DIR, fname)
        if not os.path.exists(path):
            print(f"[warn] not found, skipping: {path}")
            continue
        zp_tables[(tel, filt)] = load_zp_file(path)
        print(f"Loaded {fname}: {len(zp_tables[(tel, filt)])} objects")

    if ("dup", "B") not in zp_tables or ("dup", "V") not in zp_tables:
        raise RuntimeError("Need both B_ZP_dup.dat and V_ZP_dup.dat to compute "
                           "du Pont B-V color -- check ZP_DIR path above.")

    if not os.path.exists(COG_CSV):
        raise SystemExit(
            f"\nInput not found:\n  {COG_CSV}\n"
            f"Run 10b_curve_of_growth_annulus_test.py first, or change "
            f"ANNULUS_TAG at the top of this script."
        )

    print(f"\nAnnulus setting: {ANNULUS_TAG}")
    print(f"Reading: {os.path.basename(COG_CSV)}\n")

    cog = pd.read_csv(COG_CSV)

    # --- exclude measurements whose annulus did not fit on the detector ---
    if "annulus_ok" in cog.columns:
        keys = ["object", "telescope", "filter"]
        per_meas = cog.drop_duplicates(subset=keys)
        n_meas = len(per_meas)
        n_bad = int((~per_meas["annulus_ok"]).sum())
        cog = cog[cog["annulus_ok"]]
        print(f"[info] annulus guard: {n_meas - n_bad}/{n_meas} object-images "
              f"usable ({n_bad} excluded, annulus off the detector)")
    else:
        print("[warn] no annulus_ok column found -- this looks like output from "
              "the original script 10. Proceeding without the guard, but the "
              "background may be contaminated by host light.")

    # np.isclose rather than == : the grid comes from np.arange, and exact
    # float equality on a CSV round-trip is a fragile thing to depend on.
    fid = cog[np.isclose(cog["radius_kpc"], FIDUCIAL_RADIUS_KPC)
              & (cog["telescope"] == "dup")]

    if len(fid) == 0:
        raise RuntimeError(f"No du Pont rows at {FIDUCIAL_RADIUS_KPC} kpc -- "
                           f"check that the aperture grid includes this radius.")

    flux_b = fid[fid["filter"] == "B"][["object", "z", "flux_bkgsub"]].rename(
        columns={"flux_bkgsub": "flux_B"})
    flux_v = fid[fid["filter"] == "V"][["object", "flux_bkgsub"]].rename(
        columns={"flux_bkgsub": "flux_V"})
    flux = flux_b.merge(flux_v, on="object", how="inner")

    zp_b = zp_tables[("dup", "B")].rename(columns={"zp": "zp_B", "zp_err": "zp_err_B"})
    zp_v = zp_tables[("dup", "V")].rename(columns={"zp": "zp_V", "zp_err": "zp_err_V"})

    merged = flux.merge(zp_b[["object", "zp_B", "zp_err_B"]], on="object", how="inner")
    merged = merged.merge(zp_v[["object", "zp_V", "zp_err_V"]], on="object", how="inner")

    n_no_zp = flux["object"].nunique() - merged["object"].nunique()
    if n_no_zp > 0:
        print(f"[warn] {n_no_zp} objects had flux measurements but no matching "
              f"zero-point in one or both bands -- excluded, not silently lost.")

    valid = (merged["flux_B"] > 0) & (merged["flux_V"] > 0)
    n_invalid = int((~valid).sum())
    print(f"[info] {n_invalid} / {len(merged)} objects have non-positive flux "
          f"at {FIDUCIAL_RADIUS_KPC} kpc -- calibrated color undefined for these.")

    with np.errstate(invalid="ignore", divide="ignore"):
        merged["mag_B"] = np.where(
            valid, merged["zp_B"] - 2.5 * np.log10(merged["flux_B"]), np.nan)
        merged["mag_V"] = np.where(
            valid, merged["zp_V"] - 2.5 * np.log10(merged["flux_V"]), np.nan)

    merged["B_minus_V"] = merged["mag_B"] - merged["mag_V"]
    merged["B_minus_V_err"] = np.sqrt(merged["zp_err_B"]**2 + merged["zp_err_V"]**2)

    out_cols = ["object", "z", "flux_B", "flux_V", "mag_B", "mag_V",
                "B_minus_V", "B_minus_V_err"]
    result = merged[out_cols]

    os.makedirs(OUT_DIR, exist_ok=True)

    # --- preserve any previous result before overwriting ---
    if os.path.exists(OUT_PATH) and not os.path.exists(BACKUP_PATH):
        shutil.copy2(OUT_PATH, BACKUP_PATH)
        print(f"\n[info] previous result backed up -> {os.path.basename(BACKUP_PATH)}")

    result.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(result)} objects -> {OUT_PATH}")

    print(f"\nCalibrated B-V summary:")
    print(result["B_minus_V"].describe().to_string())
    print(f"\nmedian B-V             : {result['B_minus_V'].median():.4f}")
    print(f"median B-V uncertainty : {result['B_minus_V_err'].median():.4f}  "
          f"(zero-point term only; a lower bound)")


if __name__ == "__main__":
    main()