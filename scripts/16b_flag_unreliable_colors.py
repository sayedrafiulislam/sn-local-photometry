"""
16b_flag_unreliable_colors.py

Supersedes 16_flag_low_flux_colors.py. Flags catalogue entries whose colour
cannot be trusted, using two independent criteria instead of one, and expressing
the photometric criterion as a ratio rather than an absolute count.

Nothing is dropped. Flags are written; downstream scripts decide.


WHY SCRIPT 16 NEEDED REPLACING
------------------------------

(1) ITS CENTRAL EMPIRICAL CLAIM IS FALSE.

    Script 16 states that the most implausible colours "all come from objects
    with low absolute flux in at least one band". ASAS14mf has B-V = -0.029 --
    bluer than any integrated stellar population, physically impossible -- with
    53 121 counts in B. That is roughly thirty times the measurement floor and
    sits in the brightest part of the sample.

    Its ZP_B - ZP_V is -0.711, which is 4.3 MAD from the sample median, with a
    zp_err_B five times typical. The cause is a failed calibration, not faint
    photometry, and no flux threshold at any value can remove it.

    The docstring's other examples (CSP13aam at +2.28 mag, SN2011jn at -0.93)
    date from before the background annulus was corrected and no longer describe
    the current catalogue.

(2) AN ABSOLUTE COUNT THRESHOLD IS NOT MEANINGFUL ACROSS THIS SAMPLE.

    MIN_FLUX_COUNTS = 1000 was applied to a sample spanning a factor of 38 in
    redshift and two survey campaigns. Median raw counts at the 5 kpc fiducial
    radius are 240 422 for CSP-I and 22 265 for CSP-II in B -- a factor of 11,
    most of it redshift, the remainder exposure depth. A fixed count threshold
    therefore means something entirely different for each campaign.

    This is the sixth appearance of one pattern in this project: a threshold in
    fixed units applied to a sample spanning a wide range of scales. The
    correction, each time, is to make the threshold relative to something the
    object itself supplies.

(3) THERE WAS NO CALIBRATION-QUALITY CRITERION.

    Two failure modes exist and only one was tested for.

(4) NO BACKUP. The output was overwritten silently.


THE TWO CRITERIA
----------------

A. PHOTOMETRIC -- background fraction at the fiducial radius

       bkg_frac = (bkg_per_pixel * aperture area) / raw enclosed counts

   A ratio, so exposure time, units and campaign cancel. Directly
   interpretable: 0.10 means a tenth of what was measured was sky rather than
   galaxy. Measured across the current sample: median 0.007 in B and 0.004 in
   V, with 90th percentiles of 0.126 and 0.089.

   This replaces the absolute count threshold. It targets the same objects --
   faint ones, where background dominates -- but scales correctly.

B. CALIBRATION -- ZP_B - ZP_V outlier

   A zero point depends on telescope, filter, detector and observing
   conditions, not on the galaxy. The DIFFERENCE between the B and V zero
   points for one object is therefore essentially instrumental, varying only
   with night-to-night transparency and airmass. Across the 176 valid du Pont
   objects it has a median of -0.257 with a MAD-sigma of 0.105.

   An object four MAD from that median is not a galaxy behaving unusually; it
   is a calibration that failed. Twelve objects lie beyond 3 MAD, including
   ASAS14mf (-4.3), KISS13l (-4.1) and SN2012G (+6.3, a failed V zero point
   rather than B).

   Supporting: rho(colour error, n_ref_stars_B) = -0.470, and three objects in
   the catalogue rest on a single reference star.


ON CHOOSING THE THRESHOLDS
--------------------------
Both values are configuration at the top of this file, and the script prints
the full diagnostic distributions BEFORE applying them.

Fix the values on stated grounds and record the choice, THEN look at what they
cost. Selecting the threshold that produces the most agreeable catalogue is
exactly the error identified in script 14, where a reference radius chosen from
the data turned a null result into an apparent discovery. Do not repeat it here.

The defaults are: 3 MAD, which is conventional for outlier rejection; and a
background fraction of 0.10, which sits well into the tail of a distribution
whose median is under 0.01.


CONTAMINATION IS DELIBERATELY NOT A CRITERION
---------------------------------------------
A search for source contamination (non-monotonic enclosed counts) found ten of
437 curves affected, all among the faintest in the sample, of which three reach
the catalogue -- all within a factor of two of the photometric floor. They are
faint objects, not contaminated objects. The absence of source masking is
recorded as a limitation; it does not need a third flag here.


OUTPUT
------
  calibrated_color_5kpc_flagged.csv

Columns added:
  bkg_frac_B, bkg_frac_V     background as a fraction of enclosed flux
  zp_diff, zp_diff_n_mad     ZP_B - ZP_V, and its deviation in MAD
  flag_high_bkg              fails criterion A
  flag_bad_zp                fails criterion B
  flag_low_flux              the legacy absolute-count flag, RETAINED FOR
                             COMPARISON ONLY -- do not filter on this
  flag_exclude               fails A or B. THIS is the flag to filter on.

*** 15b_apply_galactic_extinction.py currently filters on flag_low_flux and
*** must be changed to flag_exclude, or the new criteria will have no effect.
"""

import os
import re
import shutil
import datetime
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Configuration -- fix these on stated grounds BEFORE examining their effect
# --------------------------------------------------------------------------
# Criterion A: reject if background exceeds this fraction of enclosed flux in
# either band. Sample median is 0.007 (B) and 0.004 (V).
MAX_BKG_FRAC = 0.10

# Criterion B: reject if |ZP_B - ZP_V| deviates from the sample median by more
# than this many MAD. Three is conventional for outlier rejection.
MAX_ZP_DIFF_N_MAD = 3.0

# Retained only so the old behaviour can be compared. NOT used for flag_exclude.
LEGACY_MIN_FLUX_COUNTS = 1000

ANNULUS_TAG = "ann20-30"
FIDUCIAL_RADIUS_KPC = 5.0
TELESCOPE = "dup"

CAL_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
COG_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
ZP_DIR = r"D:\Thesis\My Work\sn-local-photometry\data"

IN_PATH = os.path.join(CAL_DIR, "calibrated_color_5kpc.csv")
OUT_PATH = os.path.join(CAL_DIR, "calibrated_color_5kpc_flagged.csv")
COG_CSV = os.path.join(COG_DIR, f"curve_of_growth_{ANNULUS_TAG}.csv")
ZP_B_FILE = os.path.join(ZP_DIR, "B_ZP_dup.dat")
ZP_V_FILE = os.path.join(ZP_DIR, "V_ZP_dup.dat")


def backup(path):
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


def mad_sigma(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def main():
    for p in (IN_PATH, COG_CSV, ZP_B_FILE, ZP_V_FILE):
        if not os.path.exists(p):
            raise SystemExit(f"\nInput not found:\n  {p}\n")

    df = pd.read_csv(IN_PATH)
    print(f"Catalogue in : {os.path.basename(IN_PATH)}  ({len(df)} objects)")
    if "annulus_tag" in df.columns:
        tags = df["annulus_tag"].unique()
        print(f"Annulus tag  : {list(tags)}")
        if len(tags) == 1 and tags[0] != ANNULUS_TAG:
            print(f"  [WARN] catalogue was built with {tags[0]} but this script "
                  f"is configured for {ANNULUS_TAG}. The background fractions "
                  f"below will not correspond to the catalogue fluxes.")

    # ----------------------------------------------------------------------
    # Criterion A -- background fraction at the fiducial radius
    # ----------------------------------------------------------------------
    cog = pd.read_csv(COG_CSV)
    fid = cog[np.isclose(cog["radius_kpc"], FIDUCIAL_RADIUS_KPC)
              & (cog["telescope"] == TELESCOPE)].copy()
    fid["area"] = np.pi * fid["radius_pix"] ** 2
    fid["raw"] = fid["flux_bkgsub"] + fid["bkg_per_pixel"] * fid["area"]
    with np.errstate(divide="ignore", invalid="ignore"):
        fid["bkg_frac"] = (fid["bkg_per_pixel"] * fid["area"]) / fid["raw"]

    for band in ("B", "V"):
        s = (fid[fid["filter"] == band]
             .set_index("object")["bkg_frac"].rename(f"bkg_frac_{band}"))
        df = df.merge(s, left_on="object", right_index=True, how="left")

    # ----------------------------------------------------------------------
    # Criterion B -- ZP_B - ZP_V outlier
    # ----------------------------------------------------------------------
    def read_zp(path):
        return pd.read_csv(path, sep=r"\s+", header=None,
                           names=["object", "zp", "zp_err", "n_ref"])

    zb, zv = read_zp(ZP_B_FILE), read_zp(ZP_V_FILE)
    zpd = (zb[["object", "zp"]].rename(columns={"zp": "zp_B"})
           .merge(zv[["object", "zp"]].rename(columns={"zp": "zp_V"}),
                  on="object", how="inner"))
    zpd = zpd[np.isfinite(zpd["zp_B"]) & np.isfinite(zpd["zp_V"])]
    zpd["zp_diff"] = zpd["zp_B"] - zpd["zp_V"]

    # The reference distribution is taken over ALL valid du Pont objects, not
    # only those in the catalogue, so that the instrumental spread is estimated
    # from the largest available sample and does not shift as cuts are applied.
    med = float(np.median(zpd["zp_diff"]))
    mad = mad_sigma(zpd["zp_diff"])
    zpd["zp_diff_n_mad"] = (zpd["zp_diff"] - med) / mad

    df = df.merge(zpd[["object", "zp_diff", "zp_diff_n_mad"]],
                  on="object", how="left")

    # ----------------------------------------------------------------------
    # Report the distributions BEFORE applying any cut
    # ----------------------------------------------------------------------
    print("\n" + "=" * 74)
    print("DIAGNOSTIC DISTRIBUTIONS  (before any cut)")
    print("=" * 74)
    print("  background fraction at the fiducial radius:")
    for band in ("B", "V"):
        s = df[f"bkg_frac_{band}"].dropna()
        print(f"    {band}: median {s.median():.4f}   75th {s.quantile(.75):.4f}   "
              f"90th {s.quantile(.90):.4f}   max {s.max():.4f}   (n={len(s)})")

    print(f"\n  ZP_B - ZP_V across {len(zpd)} valid du Pont objects:")
    print(f"    median {med:+.4f}   MAD-sigma {mad:.4f}   "
          f"range {zpd['zp_diff'].min():+.3f} to {zpd['zp_diff'].max():+.3f}")
    s = df["zp_diff_n_mad"].abs().dropna()
    print(f"    |deviation| within the catalogue: median {s.median():.2f} MAD, "
          f"90th {s.quantile(.90):.2f}, max {s.max():.2f}")

    print(f"\n  quoted colour uncertainty (zero-point terms only):")
    e = df["B_minus_V_err"].dropna()
    print(f"    median {e.median():.4f}   90th {e.quantile(.90):.4f}   "
          f"max {e.max():.4f} mag")

    # ----------------------------------------------------------------------
    # Apply
    # ----------------------------------------------------------------------
    df["flag_high_bkg"] = ((df["bkg_frac_B"] > MAX_BKG_FRAC)
                           | (df["bkg_frac_V"] > MAX_BKG_FRAC)
                           | df["bkg_frac_B"].isna()
                           | df["bkg_frac_V"].isna())
    df["flag_bad_zp"] = df["zp_diff_n_mad"].abs() > MAX_ZP_DIFF_N_MAD
    df["flag_bad_zp"] = df["flag_bad_zp"].fillna(True)

    # Legacy, retained for comparison only.
    df["flag_low_flux"] = ((df["flux_B"] < LEGACY_MIN_FLUX_COUNTS)
                           | (df["flux_V"] < LEGACY_MIN_FLUX_COUNTS))

    df["flag_exclude"] = df["flag_high_bkg"] | df["flag_bad_zp"]

    print("\n" + "=" * 74)
    print("FLAGS APPLIED")
    print("=" * 74)
    print(f"  criterion A, background fraction > {MAX_BKG_FRAC:.2f} : "
          f"{int(df['flag_high_bkg'].sum()):3d} objects")
    print(f"  criterion B, |ZP_B - ZP_V| > {MAX_ZP_DIFF_N_MAD:.0f} MAD    : "
          f"{int(df['flag_bad_zp'].sum()):3d} objects")
    print(f"  both criteria                          : "
          f"{int((df['flag_high_bkg'] & df['flag_bad_zp']).sum()):3d} objects")
    print(f"  excluded by either                     : "
          f"{int(df['flag_exclude'].sum()):3d} objects")
    print(f"  RETAINED                               : "
          f"{int((~df['flag_exclude']).sum()):3d} objects")
    print()
    print(f"  legacy flux cut (< {LEGACY_MIN_FLUX_COUNTS} counts), for comparison "
          f"only : {int(df['flag_low_flux'].sum()):3d} objects")
    caught = int((df["flag_exclude"] & ~df["flag_low_flux"]).sum())
    missed = int((~df["flag_exclude"] & df["flag_low_flux"]).sum())
    print(f"    caught by the new criteria and NOT by the old : {caught}")
    print(f"    caught by the old and NOT by the new          : {missed}")

    for name, col in [("high background", "flag_high_bkg"),
                      ("bad zero point", "flag_bad_zp")]:
        sub = df[df[col]]
        if len(sub):
            print(f"\n  --- {name} ---")
            cols = ["object", "B_minus_V", "B_minus_V_err", "flux_B",
                    "bkg_frac_B", "bkg_frac_V", "zp_diff_n_mad"]
            print(sub[cols].sort_values("object").round(4).to_string(index=False))

    # ----------------------------------------------------------------------
    # Did the cuts do what they were meant to?
    # ----------------------------------------------------------------------
    print("\n" + "=" * 74)
    print("EFFECT ON THE SAMPLE")
    print("=" * 74)
    kept = df[~df["flag_exclude"]]
    for label, s in [("all", df), ("retained", kept)]:
        c = s["B_minus_V"].dropna()
        if len(c):
            print(f"  {label:9s} n={len(c):3d}  median {c.median():.4f}  "
                  f"16-84 pct {c.quantile(.16):.4f} - {c.quantile(.84):.4f}  "
                  f"min {c.min():+.4f}  max {c.max():+.4f}")

    unphys = kept[kept["B_minus_V"] < 0.0]
    print(f"\n  unphysical colours (B-V < 0) surviving : {len(unphys)}")
    if len(unphys):
        print("    " + ", ".join(unphys["object"].tolist()))
        print("    These are not removed by either criterion. Investigate before")
        print("    quoting the catalogue.")

    # ----------------------------------------------------------------------
    # Write
    # ----------------------------------------------------------------------
    print()
    backup(OUT_PATH)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} objects -> {os.path.basename(OUT_PATH)}")

    print(f"""
IMPORTANT: filter downstream on `flag_exclude`, not `flag_low_flux`.
15b_apply_galactic_extinction.py currently filters on flag_low_flux and MUST be
updated, or the calibration criterion will have no effect on the final sample.

The thresholds above ({MAX_BKG_FRAC:g} and {MAX_ZP_DIFF_N_MAD:g} MAD) are
proposals. Record the values agreed with your supervisor and the reasoning, then
report what they cost -- not the reverse.""")


if __name__ == "__main__":
    main()