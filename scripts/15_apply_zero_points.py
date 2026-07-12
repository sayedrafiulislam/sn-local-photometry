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
"""

import os
import numpy as np
import pandas as pd

ZP_DIR = r"D:\Thesis\My Work\sn-local-photometry\data"
ZP_FILES = {
    ("dup", "B"): "B_ZP_dup.dat",
    ("dup", "V"): "V_ZP_dup.dat",
    ("swo", "B"): "B_ZP_swo.dat",
    ("swo", "V"): "V_ZP_swo.dat",
}

COG_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\curve_of_growth.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration\calibrated_color_5kpc.csv"

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

    cog = pd.read_csv(COG_CSV)
    fid = cog[(cog["radius_kpc"] == FIDUCIAL_RADIUS_KPC) & (cog["telescope"] == "dup")]

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
    n_invalid = (~valid).sum()
    print(f"[info] {n_invalid} / {len(merged)} objects have non-positive flux "
          f"at {FIDUCIAL_RADIUS_KPC} kpc -- calibrated color undefined for these.")

    merged["mag_B"] = np.where(valid, merged["zp_B"] - 2.5 * np.log10(merged["flux_B"]), np.nan)
    merged["mag_V"] = np.where(valid, merged["zp_V"] - 2.5 * np.log10(merged["flux_V"]), np.nan)
    merged["B_minus_V"] = merged["mag_B"] - merged["mag_V"]
    merged["B_minus_V_err"] = np.sqrt(merged["zp_err_B"]**2 + merged["zp_err_V"]**2)

    out_cols = ["object", "z", "flux_B", "flux_V", "mag_B", "mag_V",
                "B_minus_V", "B_minus_V_err"]
    result = merged[out_cols]

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    result.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(result)} objects -> {OUT_PATH}")
    print(f"\nCalibrated B-V summary:")
    print(result["B_minus_V"].describe().to_string())


if __name__ == "__main__":
    main()