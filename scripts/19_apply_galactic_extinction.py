"""
19_apply_galactic_extinction.py

Supersedes 15b_apply_galactic_extinction.py. The physics is unchanged and was
correct; five defects around it are fixed.

Runs at step 19, after step 18 has written the quality flags. See
NUMBERING.md for the full order.


WHAT THIS DOES
--------------
Light from a distant galaxy passes through the Milky Way's dust on its way to
us. Dust scatters blue light more than red, so everything looks redder than it
is. The SFD98 dust map gives the reddening along any line of sight, and
Schlafly & Finkbeiner (2011) give the extinction per band.

    A_B = 3.626 * E(B-V)_SFD        A_V = 2.742 * E(B-V)_SFD
    corrected colour = observed - (A_B - A_V)


THE SF11 RECALIBRATION IS APPLIED THROUGH THE COEFFICIENTS
----------------------------------------------------------
This is subtle and a reader will look for something that is not there, so it is
worth stating explicitly.

The coefficients above are Schlafly & Finkbeiner (2011) Table 6 for R_V = 3.1,
applied to the UNMODIFIED SFD98 map value. Their difference is

    3.626 - 2.742 = 0.884

so the colour excess applied is 0.884 x E(B-V)_SFD rather than 1.0 x E(B-V)_SFD.

That is deliberate. SF11 established that SFD98 overestimates E(B-V) by roughly
14 per cent, with a recalibration factor of 0.86. Applying SF11's per-band
coefficients to the raw SFD map reproduces that recalibration automatically, so
no separate 0.86 scaling appears anywhere in this script. Cite both papers, and
say in the text that the recalibration enters through the coefficients --
otherwise a reader will search for a factor that was never written down.

Schlegel, Finkbeiner & Davis (1998), ApJ 500, 525 -- the map, and the 16 per
cent uncertainty adopted below.
Schlafly & Finkbeiner (2011), ApJ 737, 103, Table 6 -- the coefficients.


WHAT WAS WRONG WITH 15b
-----------------------

(1) IT FILTERED ON THE WRONG FLAG.

    `flag_low_flux` was script 16's single absolute-count criterion. step 18
    replaces it with two scale-free criteria and writes the combined result as
    `flag_exclude`. Filtering on the old flag means the calibration-quality
    criterion never reaches the final sample.

    This script now prefers `flag_exclude` and falls back to `flag_low_flux`
    with a warning, so it cannot silently use the wrong one.

(2) THE BACKUP FIRED ONCE AND THEN NEVER AGAIN.

        if not os.path.exists(backup): shutil.copy2(...)

    Once the backup existed the condition was permanently false and every later
    run overwrote the output unprotected. The same bug was present in scripts 11
    and 15 -- when one bug appears three times independently it is a house
    style, not an accident. Replaced with timestamped backups.

(3) `ebv_applied` WAS MISNAMED.

    It holds A_B - A_V = 0.884 x E(B-V), not E(B-V). The printed output
    explained the distinction; the variable name contradicted it. Renamed to
    `colour_excess_BV`, with `ebv_applied` retained as a duplicate column so
    nothing downstream breaks.

(4) THE NUMPY PATCH WAS UNDOCUMENTED.

    np.int, np.float and np.bool were removed in numpy 1.24. The `sfdmap`
    package still refers to them, so they are restored below purely so the
    import succeeds. This is a global patch affecting every module imported
    afterwards, which is worth knowing rather than discovering.

(5) THE EXECUTION ORDER CONTRADICTS THE NUMBERING.

    This script reads the FLAGGED catalogue, which script step 18 writes. The real
    order is step 17 -> 18 -> 19 -> 20. Script numbers now match run order; see
    NUMBERING.md.


CORRECT, AND WORTH KEEPING
--------------------------
15b noted that script 18 does not need re-running after this step. That is right,
for two independent reasons: Galactic extinction is a single additive constant
per object, so it cancels in any within-object comparison across radii; and
script 18 operates on instrumental colours, which never receive the correction.
The same argument makes the offset-colour result of step 15/step 16 independent of this
entire calibration chain.


OUTPUT
------
  calibrated_color_5kpc_dered.csv

All rows are written with flags preserved. Filtering is left to script step 20.
"""

import os
import re
import sys
import shutil
import datetime
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# sfdmap still refers to np.int / np.float / np.bool, removed in numpy 1.24.
# Restored here ONLY so the import succeeds. This is a global patch and affects
# every module imported after this point.
# --------------------------------------------------------------------------
if not hasattr(np, "int"):
    np.int = int
if not hasattr(np, "float"):
    np.float = float
if not hasattr(np, "bool"):
    np.bool = bool

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
CALIB_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
IN_PATH = os.path.join(CALIB_DIR, "calibrated_color_5kpc_flagged.csv")
COORDS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
OUT_PATH = os.path.join(CALIB_DIR, "calibrated_color_5kpc_dered.csv")

DUST_DIR = r"D:\Thesis\dustmaps"

# Schlafly & Finkbeiner (2011) Table 6, R_V = 3.1, per unit E(B-V)_SFD.
COEFF_B = 3.626
COEFF_V = 2.742

# SFD98 quote a 16 per cent uncertainty on the map value.
EBV_FRAC_ERR = 0.16


def backup(path):
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


def load_dust_query():
    try:
        import sfdmap
    except ImportError:
        sys.exit("\n  sfdmap is not installed.\n\n  Run: pip install sfdmap\n")
    try:
        return sfdmap.SFDMap(DUST_DIR)
    except Exception:
        print(f"[info] SFD maps not found in '{DUST_DIR}'. Fetching...")
        os.makedirs(DUST_DIR, exist_ok=True)
        sfdmap.fetch(mapdir=DUST_DIR)
        return sfdmap.SFDMap(DUST_DIR)


def mad(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def main():
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    for path, what in [(IN_PATH, "flagged colours (run step 18 first)"),
                       (COORDS_CSV, "SN coordinates (run script 08 first)")]:
        if not os.path.exists(path):
            sys.exit(f"\n  Input not found -- {what}:\n    {path}\n")

    calib = pd.read_csv(IN_PATH)
    coords = pd.read_csv(COORDS_CSV)

    # (1) prefer the combined flag; fall back loudly, never silently
    if "flag_exclude" in calib.columns:
        flag_col = "flag_exclude"
    elif "flag_low_flux" in calib.columns:
        flag_col = "flag_low_flux"
        print("[WARN] no flag_exclude column found -- this catalogue predates "
              "18_flag_unreliable_colours.py. Falling back to flag_low_flux, "
              "which applies only the old absolute-count criterion. The "
              "calibration-quality criterion will NOT be reflected below.")
    else:
        flag_col = None
        print("[WARN] no exclusion flag at all -- reporting on the full sample.")

    df = calib.merge(coords[["object", "ra_deg", "dec_deg"]],
                     on="object", how="left")

    n_no_coord = int(df["ra_deg"].isna().sum())
    if n_no_coord:
        print(f"[warn] {n_no_coord} objects have no resolved coordinate -- their "
              f"dereddened colour will be NaN, not silently left uncorrected.")

    sfd = load_dust_query()

    has_coord = df["ra_deg"].notna() & df["dec_deg"].notna()
    df["ebv_sfd"] = np.nan
    if has_coord.any():
        df.loc[has_coord, "ebv_sfd"] = sfd.ebv(
            df.loc[has_coord, "ra_deg"].values,
            df.loc[has_coord, "dec_deg"].values)

    df["A_B"] = COEFF_B * df["ebv_sfd"]
    df["A_V"] = COEFF_V * df["ebv_sfd"]

    # (3) A_B - A_V is the colour excess, NOT E(B-V). It equals
    #     (3.626 - 2.742) x E(B-V)_SFD = 0.884 x E(B-V)_SFD.
    df["colour_excess_BV"] = df["A_B"] - df["A_V"]
    df["ebv_applied"] = df["colour_excess_BV"]   # legacy name, kept for compat

    df["mag_B_dered"] = df["mag_B"] - df["A_B"]
    df["mag_V_dered"] = df["mag_V"] - df["A_V"]
    df["B_minus_V_dered"] = df["B_minus_V"] - df["colour_excess_BV"]

    ebv_err = EBV_FRAC_ERR * df["colour_excess_BV"].abs()
    df["B_minus_V_dered_err"] = np.sqrt(df["B_minus_V_err"] ** 2 + ebv_err ** 2)

    df["gal_b_deg"] = np.nan
    if has_coord.any():
        gal = SkyCoord(df.loc[has_coord, "ra_deg"].values * u.deg,
                       df.loc[has_coord, "dec_deg"].values * u.deg,
                       frame="icrs").galactic
        df.loc[has_coord, "gal_b_deg"] = gal.b.deg

    backup(OUT_PATH)
    df.to_csv(OUT_PATH, index=False)

    # ----------------------------------------------------------------------
    # Report
    # ----------------------------------------------------------------------
    keep = ~df[flag_col].astype(bool) if flag_col else pd.Series(True, index=df.index)
    clean = df[keep & df["B_minus_V_dered"].notna()]
    obs, ded = clean["B_minus_V"], clean["B_minus_V_dered"]

    print(f"\nWrote {len(df)} objects -> {os.path.basename(OUT_PATH)}")
    print("\n" + "=" * 74)
    print("GALACTIC EXTINCTION CORRECTION")
    print("=" * 74)
    print(f"Exclusion flag used             : {flag_col}")
    print(f"Clean sample                    : {len(clean)} objects")
    print(f"|b| range                       : "
          f"{np.nanmin(np.abs(clean['gal_b_deg'])):.1f} - "
          f"{np.nanmax(np.abs(clean['gal_b_deg'])):.1f} deg")
    print()
    print(f"E(B-V)_SFD    median            : {clean['ebv_sfd'].median():.4f} mag")
    print(f"              16-84th pct       : {clean['ebv_sfd'].quantile(0.16):.4f} - "
          f"{clean['ebv_sfd'].quantile(0.84):.4f} mag")
    print(f"              maximum           : {clean['ebv_sfd'].max():.4f} mag")
    print(f"Colour excess applied, median   : "
          f"{clean['colour_excess_BV'].median():.4f} mag")
    print(f"   = ({COEFF_B:.3f} - {COEFF_V:.3f}) x E(B-V)_SFD "
          f"= {COEFF_B - COEFF_V:.3f} x E(B-V)_SFD")
    print(f"   The SF11 recalibration enters through these coefficients; there is")
    print(f"   deliberately no separate 0.86 factor.")
    print()
    print(f"{'':32s}{'observed':>12s}{'dereddened':>13s}{'change':>10s}")
    for label, fo, fd in [("median B-V (mag)", obs.median(), ded.median()),
                          ("mean B-V (mag)", obs.mean(), ded.mean()),
                          ("scatter, sigma_MAD (mag)", mad(obs), mad(ded)),
                          ("std dev (mag)", obs.std(), ded.std()),
                          ("16th percentile", obs.quantile(.16), ded.quantile(.16)),
                          ("84th percentile", obs.quantile(.84), ded.quantile(.84))]:
        print(f"  {label:30s}{fo:12.4f}{fd:13.4f}{fd - fo:+10.4f}")

    var = mad(obs) ** 2 - mad(ded) ** 2
    if var > 0:
        print(f"\n  implied foreground scatter term : {np.sqrt(var):.4f} mag "
              f"(removed in quadrature)")
    else:
        print(f"\n  scatter did not decrease; the foreground term is not "
              f"resolvable in this sample")

    try:
        from scipy import stats
        r_o, p_o = stats.spearmanr(clean["ebv_sfd"], clean["B_minus_V"])
        r_d, p_d = stats.spearmanr(clean["ebv_sfd"], clean["B_minus_V_dered"])
        print(f"\n  Spearman rho(E(B-V), colour)")
        print(f"    before correction : {r_o:+.3f}  (p = {p_o:.4f})")
        print(f"    after correction  : {r_d:+.3f}  (p = {p_d:.4f})")
        print("    The residual should be consistent with zero. If it is not,")
        print("    either the map is queried at the wrong coordinates, or")
        print("    something else in the sample tracks Galactic latitude --")
        print("    field crowding at low |b| is the usual culprit.")
        low_b = clean[np.abs(clean["gal_b_deg"]) < 20]
        if len(low_b) > 5:
            r_hi, p_hi = stats.spearmanr(
                clean[np.abs(clean["gal_b_deg"]) >= 20]["ebv_sfd"],
                clean[np.abs(clean["gal_b_deg"]) >= 20]["B_minus_V_dered"])
            print(f"    excluding |b| < 20 deg ({len(low_b)} objects): "
                  f"rho = {r_hi:+.3f} (p = {p_hi:.4f})")
    except ImportError:
        pass

    print("\n  Next: 20_plot_bv_distribution.py, which plots")
    print("  B_minus_V_dered from this file. Script 18 does NOT need re-running:")
    print("  extinction is one additive constant per object and cancels in the")
    print("  paired radius comparison, which uses instrumental colours anyway.")
    print("=" * 74)


if __name__ == "__main__":
    main()