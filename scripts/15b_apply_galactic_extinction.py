"""
15b_apply_galactic_extinction.py

Corrects the calibrated local colours for Milky Way dust reddening.
Updated to use `sfdmap` for native Windows compatibility.
"""
import os
import shutil
import sys
import numpy as np
import pandas as pd

# --- ADD THESE 3 LINES TO FIX THE SFDMAP ERROR ---
np.int = int
np.float = float
np.bool = bool

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
CALIB_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
IN_PATH = os.path.join(CALIB_DIR, "calibrated_color_5kpc_flagged.csv")
COORDS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
OUT_PATH = os.path.join(CALIB_DIR, "calibrated_color_5kpc_dered.csv")

# Directory where SFD data maps are stored
DUST_DIR = r"D:\Thesis\dustmaps"

# Schlafly & Finkbeiner (2011) Table 6, R_V = 3.1, per unit E(B-V)_SFD.
COEFF_B = 3.626
COEFF_V = 2.742

# Fractional uncertainty on the SFD map value.
EBV_FRAC_ERR = 0.16


def load_dust_query():
    """
    Return an SFDMap instance, fetching data if not present.
    """
    try:
        import sfdmap
    except ImportError:
        sys.exit(
            "\n  sfdmap is not installed.\n\n"
            "  Run: pip install sfdmap\n"
        )
    
    # Automatically download the SFD data files into D:\Thesis\dustmaps if missing
    try:
        return sfdmap.SFDMap(DUST_DIR)
    except Exception:
        print(f"[info] SFD map files not found in '{DUST_DIR}'. Fetching now...")
        os.makedirs(DUST_DIR, exist_ok=True)
        sfdmap.fetch(mapdir=DUST_DIR)
        return sfdmap.SFDMap(DUST_DIR)


def main():
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    for path, what in [(IN_PATH, "calibrated colours (run script 16 first)"),
                       (COORDS_CSV, "SN coordinates (run script 08 first)")]:
        if not os.path.exists(path):
            sys.exit(f"\n  Input not found -- {what}:\n    {path}\n")

    calib = pd.read_csv(IN_PATH)
    coords = pd.read_csv(COORDS_CSV)

    df = calib.merge(coords[["object", "ra_deg", "dec_deg"]], on="object", how="left")

    n_no_coord = int(df["ra_deg"].isna().sum())
    if n_no_coord:
        print(f"[warn] {n_no_coord} objects have no resolved coordinate -- their "
              f"dereddened colour will be NaN, not silently left uncorrected.")

    sfd = load_dust_query()

    has_coord = df["ra_deg"].notna() & df["dec_deg"].notna()
    df["ebv_sfd"] = np.nan
    if has_coord.any():
        # sfdmap takes RA and Dec directly in degrees
        ras = df.loc[has_coord, "ra_deg"].values
        decs = df.loc[has_coord, "dec_deg"].values
        df.loc[has_coord, "ebv_sfd"] = sfd.ebv(ras, decs)

    # Extinction in each band, and the colour excess actually applied.
    df["A_B"] = COEFF_B * df["ebv_sfd"]
    df["A_V"] = COEFF_V * df["ebv_sfd"]
    df["ebv_applied"] = df["A_B"] - df["A_V"]

    df["mag_B_dered"] = df["mag_B"] - df["A_B"]
    df["mag_V_dered"] = df["mag_V"] - df["A_V"]
    df["B_minus_V_dered"] = df["B_minus_V"] - df["ebv_applied"]

    # Propagate a 16 per cent uncertainty on E(B-V) into the colour error.
    ebv_err = EBV_FRAC_ERR * df["ebv_applied"].abs()
    df["B_minus_V_dered_err"] = np.sqrt(df["B_minus_V_err"] ** 2 + ebv_err ** 2)

    # Galactic latitude, purely for the diagnostic below.
    gal = SkyCoord(df["ra_deg"].values * u.deg, df["dec_deg"].values * u.deg,
                   frame="icrs").galactic
    df["gal_b_deg"] = gal.b.deg

    if os.path.exists(OUT_PATH):
        backup = OUT_PATH.replace(".csv", "_previous.csv")
        if not os.path.exists(backup):
            shutil.copy2(OUT_PATH, backup)
            print(f"[info] previous result backed up -> {os.path.basename(backup)}")

    df.to_csv(OUT_PATH, index=False)

    # ----------------------------------------------------------------------
    # Report
    # ----------------------------------------------------------------------
    clean = df[(~df["flag_low_flux"]) & df["B_minus_V_dered"].notna()]
    obs = clean["B_minus_V"]
    ded = clean["B_minus_V_dered"]

    def mad(x):
        return float(1.4826 * np.median(np.abs(x - np.median(x))))

    print(f"\nWrote {len(df)} objects -> {OUT_PATH}")
    print("\n" + "=" * 74)
    print("GALACTIC EXTINCTION CORRECTION")
    print("=" * 74)
    print(f"Clean sample                    : {len(clean)} objects")
    print(f"|b| range                       : {np.nanmin(np.abs(clean['gal_b_deg'])):.1f} "
          f"- {np.nanmax(np.abs(clean['gal_b_deg'])):.1f} deg")
    print()
    print(f"E(B-V)_SFD    median            : {clean['ebv_sfd'].median():.4f} mag")
    print(f"              16-84th pct       : {clean['ebv_sfd'].quantile(0.16):.4f} - "
          f"{clean['ebv_sfd'].quantile(0.84):.4f} mag")
    print(f"              maximum           : {clean['ebv_sfd'].max():.4f} mag")
    print(f"Colour excess applied, median   : {clean['ebv_applied'].median():.4f} mag "
          f"({COEFF_B:.3f} - {COEFF_V:.3f} = {COEFF_B - COEFF_V:.3f} x E(B-V)_SFD)")
    print()
    print(f"{'':32s}{'observed':>12s}{'dereddened':>13s}{'change':>10s}")
    for label, fo, fd in [("median B-V (mag)", obs.median(), ded.median()),
                          ("mean B-V (mag)", obs.mean(), ded.mean()),
                          ("scatter, sigma_MAD (mag)", mad(obs), mad(ded)),
                          ("std dev (mag)", obs.std(), ded.std()),
                          ("25th percentile", obs.quantile(.25), ded.quantile(.25)),
                          ("75th percentile", obs.quantile(.75), ded.quantile(.75))]:
        print(f"  {label:30s}{fo:12.4f}{fd:13.4f}{fd - fo:+10.4f}")

    var = mad(obs) ** 2 - mad(ded) ** 2
    if var > 0:
        print(f"\n  implied foreground scatter term : {np.sqrt(var):.4f} mag "
              f"(removed in quadrature)")
    else:
        print(f"\n  scatter did not decrease; the foreground term is not resolvable "
              f"in this sample")

    try:
        from scipy import stats
        r_o, p_o = stats.spearmanr(clean["ebv_sfd"], clean["B_minus_V"])
        r_d, p_d = stats.spearmanr(clean["ebv_sfd"], clean["B_minus_V_dered"])
        print(f"\n  Spearman rho(E(B-V), colour)")
        print(f"    before correction : {r_o:+.3f}  (p = {p_o:.4f})")
        print(f"    after correction  : {r_d:+.3f}  (p = {p_d:.4f})")
        print("    The residual correlation should be consistent with zero. If it is")
        print("    not, either the map is being queried at the wrong coordinates or")
        print("    something else in the sample tracks Galactic latitude.")
    except ImportError:
        pass

    print("\n  Next: quote the dereddened median as the catalogue value. Script 18")
    print("  does NOT need re-running -- extinction is constant per object and")
    print("  cancels in the paired radius comparison.")
    print("=" * 74)


if __name__ == "__main__":
    main()