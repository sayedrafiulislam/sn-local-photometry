"""
18_flag_unreliable_colours.py

Supersedes 16_flag_low_flux_colors.py and 16b_flag_unreliable_colors.py.
Flags catalogue entries whose colour cannot be trusted, using two independent
criteria, both expressed relative to something the object itself supplies.

Nothing is dropped. Flags are written; downstream scripts decide.


WHY SCRIPT 16 NEEDED REPLACING
------------------------------

(1) ITS CENTRAL EMPIRICAL CLAIM IS FALSE.

    Script 16 states that the most implausible colours "all come from objects
    with low absolute flux in at least one band". ASAS14mf has B-V = -0.029 --
    bluer than any integrated stellar population -- with 53 121 counts in B,
    roughly thirty times the measurement floor. The calibration failed; the
    photometry did not. No flux threshold at any value can remove it.

    Confirmed by the flag distributions: the background-limited objects have a
    median flux_B near 1 500, the calibration-limited ones near 150 000, with
    SN2011iv at 1.2e7. The two failure modes sit at OPPOSITE ends of the
    brightness distribution and share no objects.

(2) AN ABSOLUTE COUNT THRESHOLD IS NOT MEANINGFUL ACROSS THIS SAMPLE.

    MIN_FLUX_COUNTS = 1000 was applied across a factor of 38 in redshift and two
    survey campaigns whose median raw counts differ by a factor of 11. This is
    the sixth appearance of one pattern in this project: a threshold in fixed
    units applied to a sample spanning a wide range of scales.

(3) THERE WAS NO CALIBRATION-QUALITY CRITERION.

(4) NO BACKUP. The output was overwritten silently.


WHY 16b ALSO NEEDED REPLACING
-----------------------------
16b used an outlier test on ZP_B - ZP_V, on the reasoning that a zero point
depends on the instrument rather than the galaxy, so the difference between the
B and V zero points should be nearly constant across objects. That reasoning
was tested and does not hold.

    tail fraction of ZP_B - ZP_V     observed     Gaussian
      beyond 2 MAD                     13.1%         4.6%
      beyond 3 MAD                      6.8%         0.3%
      beyond 5 MAD                      2.8%      0.00006%

The distribution is intrinsically broad, not a tight core with a few failures,
so a 3 MAD cut slices into the body rather than trimming a tail.

Validated against the instrumental colours, which never touch a zero point: of
the 8 objects it flagged, only 3 showed the signature of a genuine calibration
failure (normal instrumental colour, anomalous calibrated colour). Four had
entirely normal calibrated colours. One, SN2011iv, has an instrumental colour of
1.858 (+3.1 sigma) and a calibrated colour of 0.916 -- the zero point is
CORRECTING that object, not corrupting it, and flagging it would discard real
data.

The corroborating evidence was also weak: flagged objects have a median zp_err_B
of 0.0975 against 0.0683 for the rest, a factor of 1.4, and 6 reference stars
against 8. A genuine calibration failure should declare itself in its own error
bar far more strongly than that.

ZP_B - ZP_V is therefore REPORTED as a diagnostic here but is no longer a cut.
That 12 of 176 objects lie beyond 3 MAD in a near-instrumental quantity remains
a real observation about the calibration files and belongs in the supervisor
discussion.


THE TWO CRITERIA
----------------

A. PHOTOMETRIC -- background fraction at the fiducial radius

       bkg_frac = (bkg_per_pixel * aperture area) / raw enclosed counts

   A ratio, so exposure time, units and survey campaign all cancel. Directly
   interpretable: 0.10 means a tenth of what was measured was sky rather than
   galaxy. Sample medians are 0.008 in B and 0.006 in V, so the threshold sits
   well into the tail.

   Tested on |bkg_frac|, not bkg_frac. A large NEGATIVE background fraction is
   as wrong as a large positive one -- it means flux is being added rather than
   removed. Negative values are legitimate in small amounts, since these stacks
   have already had a sky level subtracted and the annulus median can come out
   below zero. 16b tested only the positive side.

B. CALIBRATION -- the object's own quoted colour uncertainty

   B_minus_V_err is the two zero-point errors in quadrature. An object whose
   stated uncertainty exceeds MAX_COLOUR_ERR cannot constrain the population it
   belongs to.

   Chosen over the ZP-difference test because it is:
     - not circular: it never inspects the colour VALUE, only how well that
       value was determined;
     - self-declared: the calibration states its own reliability rather than
       having it inferred from the spread of other objects;
     - conservative: B_minus_V_err omits photon noise, background uncertainty
       and flat-field error, so it is a LOWER BOUND. If even the lower bound is
       too large, the true uncertainty is worse.

   The threshold is tied to the sample rather than chosen as a round number:
   the retained 16th-84th percentile spread is approximately 0.50 mag, so
   0.25 is half the spread the measurement is meant to constrain.


ON CHOOSING THE THRESHOLDS
--------------------------
Both are configuration below, and the diagnostic distributions are printed
BEFORE the cuts are applied.

Fix the values on stated grounds, record the reasoning, THEN look at what they
cost. Selecting the threshold that produces the most agreeable catalogue is the
error identified in script 14, where a reference radius chosen from the data
turned a null result into an apparent discovery.


CONTAMINATION IS DELIBERATELY NOT A CRITERION
---------------------------------------------
A search for source contamination found ten of 437 curves with non-monotonic
enclosed counts, all among the faintest in the sample, three of which reach the
catalogue -- all within a factor of two of the photometric floor. They are faint
objects, not contaminated objects. The absence of source masking is recorded as
a limitation; it does not need a third flag.


OUTPUT
------
  calibrated_color_5kpc_flagged.csv

Columns added:
  bkg_frac_B, bkg_frac_V     background as a fraction of enclosed flux
  zp_diff, zp_diff_n_mad     ZP_B - ZP_V and its deviation -- DIAGNOSTIC ONLY
  flag_high_bkg              fails criterion A
  flag_large_err             fails criterion B
  flag_zp_outlier            beyond 3 MAD in ZP_B - ZP_V -- REPORTED, NOT CUT
  flag_low_flux              legacy absolute-count flag, COMPARISON ONLY
  flag_exclude               fails A or B. THIS is the flag to filter on.

*** 15b_apply_galactic_extinction.py currently filters on flag_low_flux and
*** must be changed to flag_exclude, or these criteria will have no effect.
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

# Criterion B: reject if the quoted colour uncertainty exceeds this. The
# retained 16th-84th percentile spread is about 0.50 mag, so this is half the
# spread the measurement is meant to constrain.
MAX_COLOUR_ERR = 0.25

# Reported only, never used to exclude. See the docstring for why the
# ZP-difference outlier test was demoted from a criterion to a diagnostic.
REPORT_ZP_DIFF_N_MAD = 3.0

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
    # abs(): a large NEGATIVE background fraction is as wrong as a large
    # positive one -- it means flux is being added rather than removed. 16b
    # tested only the positive side.
    df["flag_high_bkg"] = ((df["bkg_frac_B"].abs() > MAX_BKG_FRAC)
                           | (df["bkg_frac_V"].abs() > MAX_BKG_FRAC)
                           | df["bkg_frac_B"].isna()
                           | df["bkg_frac_V"].isna())

    df["flag_large_err"] = df["B_minus_V_err"] > MAX_COLOUR_ERR
    df["flag_large_err"] = df["flag_large_err"].fillna(True)

    # Diagnostic only -- NOT part of flag_exclude.
    df["flag_zp_outlier"] = (df["zp_diff_n_mad"].abs()
                             > REPORT_ZP_DIFF_N_MAD).fillna(False)

    # Legacy, retained for comparison only.
    df["flag_low_flux"] = ((df["flux_B"] < LEGACY_MIN_FLUX_COUNTS)
                           | (df["flux_V"] < LEGACY_MIN_FLUX_COUNTS))

    df["flag_exclude"] = df["flag_high_bkg"] | df["flag_large_err"]

    print("\n" + "=" * 74)
    print("FLAGS APPLIED")
    print("=" * 74)
    print(f"  criterion A, background fraction > {MAX_BKG_FRAC:.2f} : "
          f"{int(df['flag_high_bkg'].sum()):3d} objects")
    print(f"  criterion B, colour error > {MAX_COLOUR_ERR:.2f} mag     : "
          f"{int(df['flag_large_err'].sum()):3d} objects")
    print(f"  both criteria                          : "
          f"{int((df['flag_high_bkg'] & df['flag_large_err']).sum()):3d} objects")
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

    print(f"\n  ZP_B - ZP_V beyond {REPORT_ZP_DIFF_N_MAD:.0f} MAD "
          f"(DIAGNOSTIC ONLY, not excluded) : "
          f"{int(df['flag_zp_outlier'].sum()):3d} objects")
    zpo = df[df["flag_zp_outlier"]]
    if len(zpo):
        print("    " + ", ".join(
            f"{r.object}({r.zp_diff_n_mad:+.1f})" for _, r in zpo.iterrows()))
        also = int((zpo["flag_exclude"]).sum())
        print(f"    of these, {also} are excluded by criterion A or B anyway; "
              f"{len(zpo) - also} are retained.")

    for name, col in [("high background", "flag_high_bkg"),
                      ("large quoted uncertainty", "flag_large_err")]:
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
Steps 19 and 20 already do. flag_low_flux is retained for comparison only.

The thresholds above (background fraction {MAX_BKG_FRAC:g}, colour error
{MAX_COLOUR_ERR:g} mag) are proposals. Record the values agreed with your
supervisor and the reasoning, then report what they cost -- not the reverse.

The ZP_B - ZP_V outlier count is reported for information only and does not
affect flag_exclude. It was tested as a criterion and rejected: the distribution
is intrinsically broad (6.8 per cent beyond 3 MAD against 0.3 per cent for a
Gaussian), and validation against the zero-point-free instrumental colours
showed only 3 of 8 flagged objects had a genuine calibration failure.""")


if __name__ == "__main__":
    main()