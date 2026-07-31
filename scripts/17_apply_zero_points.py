"""
17_apply_zero_points.py

Supersedes 15_apply_zero_points.py. The calibration itself is unchanged; eight
defects found in the audit are corrected, and the largest single cut in the
pipeline is made visible instead of being reported as a warning about missing
files.

Runs at step 17. Its output feeds step 18 (quality flags), which feeds step
19 (Galactic extinction).

WHAT THIS DOES
--------------
Converts instrumental flux at the 5.0 kpc fiducial aperture into calibrated
magnitudes and a calibrated local B-V colour, using the supervisor-supplied
zero-point files.

    mag        = ZP - 2.5*log10(flux)
    B-V        = mag_B - mag_V
               = (ZP_B - ZP_V) - 2.5*log10(flux_B/flux_V)
               = (ZP_B - ZP_V) + instrumental_(B-V)

So the calibrated colour is script 11's instrumental colour shifted by one
additive constant per object. That is worth keeping in mind: any analysis
performed WITHIN an object across radii is unaffected by this step entirely,
which is why scripts step 15, step 16 and 18 can work on instrumental colours and remain
independent of everything here.

Zero-point file format, confirmed against B_ZP_dup.dat:

    <object>  <zero_point_mag>  <zero_point_err>  <n_ref_stars>

space-delimited, no header.

Only du Pont B+V is used, consistent with script 11: Swope has 103 V frames and
zero B frames in this data set, so a same-telescope Swope colour does not exist.
(B_ZP_swo.dat is present in the repository and covers 121 objects, but there is
no Swope B imaging to apply it to.)


THE LARGEST CUT IN THE PIPELINE
-------------------------------
Of the objects with a defined local colour at 5 kpc, roughly 45 per cent are
lost here for want of a zero point -- the single largest drop anywhere in the
analysis. Script 15 reported this as one line counting objects "with no matching
zero-point in one or both bands", which is accurate and conceals what is
actually happening.

The exclusion is not random. Splitting by the year in the object name:

    2004-2009 (CSP-I) :  90 objects lack a zero point,   0 have one
    2011-2015 (CSP-II):   1 object  lacks  a zero point, 111 have one

The break falls exactly at 2010, the gap between the two CSP campaigns.
B_ZP_dup.dat holds 177 objects and V_ZP_dup.dat 180, against 266 objects in the
imaging: the supplied calibration files were derived for CSP-II and do not cover
CSP-I. The sole CSP-II-era exception is ASAS14lq.

The consequence is that the published catalogue is a CSP-II sample. CSP-I and
CSP-II differ in target selection and redshift reach, so this reshapes the
redshift distribution and host population rather than thinning the sample
evenly. It must be stated in the paper, and it bears directly on comparability
with Kelsey et al. (2021) and on the planned Hubble-residual work.

This script now classifies every object by epoch and reports the split
explicitly. If CSP-I zero points are later supplied, add the filenames to
ZP_FILES below -- the structure takes a list per (telescope, filter) and
concatenates, so no other change is needed.


WHAT WAS WRONG WITH SCRIPT 15
-----------------------------

(1) THE APERTURE GUARD WAS NOT APPLIED.

    Script 15 reads the curve-of-growth file directly rather than script 11's
    output, so step 14's guard does not protect it. 162 rows with an aperture
    running off the frame edge or containing non-finite pixels flowed into the
    calibrated catalogue.

(2) THE BACKUP FIRED ONCE AND THEN NEVER AGAIN.

        if os.path.exists(OUT_PATH) and not os.path.exists(BACKUP_PATH):

    Once calibrated_color_5kpc_pre_annulus_fix.csv existed this was permanently
    false, so every subsequent run overwrote the catalogue unprotected. The same
    bug is present in scripts 11 and 15b. Replaced with timestamped backups.

(3) THERE WAS NO VALIDITY CHECK ON THE ZERO POINTS.

    LSQ12gef carries zp = inf, zp_err = inf and n_ref_stars = 0 in BOTH du Pont
    files -- a calibration derived from no reference stars. Script 15 computed
    mag = inf - 2.5*log10(flux) = inf, then B-V = inf - inf = NaN, and the object
    vanished through NaN arithmetic rather than by any stated rule. Nothing was
    corrupted, but the exclusion was unrecorded and unintended.

    Zero points are now rejected explicitly if the value or its error is
    non-finite, or if n_ref_stars is below MIN_REF_STARS. Note that C9 lists
    LSQ12gef among objects potentially recoverable under the corrected image
    quality cut; it is not recoverable, because it cannot be calibrated at all.

(4) THE EPOCH CUT WAS UNDECLARED. See above.

(5) THE DOCSTRING NUMBERS WERE SUPERSEDED.

    525 object-images, 1.351/0.189 counts, 86 per cent, 94 per cent, 5.8 per
    cent, 61 millimag. Current values: 532 object-images, 1.6254/0.1931, 88 per
    cent, 95 per cent, 7.0 per cent, 79.3 millimag on flux.

(6) A FLUX BIAS WAS PRESENTED AS A COLOUR BIAS.

    Script 15 stated that the over-subtraction "reached about 5.8 per cent of
    the flux at the 5 kpc fiducial -- some 61 millimag, which propagates directly
    into the magnitudes computed below". True for magnitudes. But this work
    reports B-V, a DIFFERENCE of magnitudes, and both bands are over-subtracted
    through the same annulus on the same galaxy, so the error is largely common
    and cancels. Measured directly across the 202 objects with a colour under
    both annulus settings, the median shift in B-V is 8.4 millimag with a 95 per
    cent interval of 4.4 to 13.4 -- that is, 89 per cent of the single-band bias
    cancels.

    Script 15 also stated that "the median instrumental B-V at 5 kpc shifts by
    about -0.025 mag". That is a difference of medians (1.0154 - 0.9891). The
    per-object median shift is 8.4 millimag. The two differ because the shift is
    strongly flux-dependent: 2.5 millimag in the brightest flux quartile and
    33.2 in the faintest.

(7) NO PROVENANCE WAS WRITTEN TO THE OUTPUT.

    The catalogue carried no record of which background annulus produced it.
    An `annulus_tag` column is now written.

(8) THERE WAS NO DUPLICATE GUARD BEFORE THE FLUX MERGE.

    Two du Pont B frames for one object would have produced duplicated
    catalogue rows silently. Safe as the data stands -- all 541 rows are unique
    in (object, telescope, filter) -- but unguarded in principle.


UNCERTAINTY: STILL INCOMPLETE, AND KNOWN TO BE
----------------------------------------------
B_minus_V_err propagates the two zero-point uncertainties in quadrature and
nothing else. It excludes photon noise on the aperture flux, background
estimation uncertainty, flat-field error, and the flux-dependent annulus
systematic. It is a LOWER BOUND on the true uncertainty and should be described
as one. Across the current catalogue it runs from 0.048 to 0.487 mag with a
median of 0.115.

Closing this gap does not require detector gain or read noise: injection-recovery
photometry after Mowla et al. (2022) section 3.1 -- injecting synthetic sources
of known flux near each target and recovering them through this same pipeline --
measures the total uncertainty empirically.


OUTPUT
------
  calibrated_color_5kpc.csv           the catalogue, for scripts 16 -> 15b -> 17
  calibrated_color_5kpc_exclusions.csv every object dropped, with a reason

Existing files are renamed to *.bak_YYYYmmdd_HHMMSS, never deleted.
"""

import os
import re
import shutil
import datetime
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
# Must match the tag used in step 14, or the calibrated colours will not correspond
# to the colours analysed in scripts 18 and 19.
ANNULUS_TAG = "ann20-30"

ZP_DIR = r"D:\Thesis\My Work\sn-local-photometry\data"

# A LIST per (telescope, filter), concatenated in order. If CSP-I zero points
# are supplied later, add the filenames here and change nothing else.
ZP_FILES = {
    ("dup", "B"): ["B_ZP_dup.dat"],
    ("dup", "V"): ["V_ZP_dup.dat"],
}

COG_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
COG_CSV = os.path.join(COG_DIR, f"curve_of_growth_{ANNULUS_TAG}.csv")

OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
OUT_PATH = os.path.join(OUT_DIR, "calibrated_color_5kpc.csv")
EXCL_PATH = os.path.join(OUT_DIR, "calibrated_color_5kpc_exclusions.csv")

TELESCOPE = "dup"
FIDUCIAL_RADIUS_KPC = 5.0
KEYS = ["object", "telescope", "filter"]

# A zero point built from no reference stars is not a measurement. Set to 1 so
# that only the unambiguous case is rejected; the full distribution of
# n_ref_stars is reported below so a stricter rule can be chosen later on
# stated grounds rather than by whichever value flatters the result.
MIN_REF_STARS = 1

# CSP-I ran 2004-2009, CSP-II from 2011. Nothing in the sample falls in 2010.
CSP1_LAST_YEAR = 2009


def backup(path):
    """Rename an existing output out of the way. Nothing is ever deleted."""
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


def object_year(name):
    """
    Discovery year from the object designation.

    Handles both conventions in this sample: four-digit (SN2012fr) and two-digit
    (SN04ef, ASAS14ad, CSP13aam, KISS13v, LSQ12gef). The four-digit alternative
    is tried first so that SN2011iy does not parse as 20.
    """
    m = re.search(r"(\d{4}|\d{2})", str(name))
    if not m:
        return np.nan
    v = int(m.group(1))
    return v if v > 1000 else 2000 + v


def epoch(year):
    if not np.isfinite(year):
        return "unknown"
    return "CSP-I" if year <= CSP1_LAST_YEAR else "CSP-II"


def load_zp(tel, filt):
    """Concatenate every zero-point file listed for one telescope and filter."""
    frames = []
    for fname in ZP_FILES.get((tel, filt), []):
        path = os.path.join(ZP_DIR, fname)
        if not os.path.exists(path):
            print(f"  [warn] not found, skipping: {path}")
            continue
        t = pd.read_csv(path, sep=r"\s+", header=None,
                        names=["object", "zp", "zp_err", "n_ref_stars"])
        t["zp_source"] = fname
        frames.append(t)
        print(f"  loaded {fname:16s} {len(t):4d} objects")
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    n_dup = int(out["object"].duplicated().sum())
    if n_dup:
        print(f"  [warn] {n_dup} objects appear in more than one {tel} {filt} "
              f"file; keeping the first occurrence.")
        out = out.drop_duplicates(subset="object", keep="first")
    return out


def main():
    excl = []   # every dropped object, with a reason

    def drop(objects, stage, reason):
        for o in sorted(set(objects)):
            excl.append({"object": o, "stage": stage, "reason": reason})

    # ----------------------------------------------------------------------
    # Zero points
    # ----------------------------------------------------------------------
    print("=" * 74)
    print("ZERO POINTS")
    print("=" * 74)
    zp_b = load_zp(TELESCOPE, "B")
    zp_v = load_zp(TELESCOPE, "V")
    if zp_b is None or zp_v is None:
        raise RuntimeError(
            f"Need both {TELESCOPE} B and V zero-point files to form a colour. "
            f"Check ZP_DIR:\n  {ZP_DIR}")

    # (3) reject zero points that are not measurements
    def screen(t, label):
        bad_val = ~np.isfinite(t["zp"]) | ~np.isfinite(t["zp_err"])
        bad_ref = t["n_ref_stars"] < MIN_REF_STARS
        bad = bad_val | bad_ref
        if bad.any():
            print(f"\n  {label}: rejecting {int(bad.sum())} zero point(s)")
            for _, r in t[bad].iterrows():
                why = []
                if not np.isfinite(r["zp"]):
                    why.append("zp non-finite")
                if not np.isfinite(r["zp_err"]):
                    why.append("zp_err non-finite")
                if r["n_ref_stars"] < MIN_REF_STARS:
                    why.append(f"n_ref_stars={r['n_ref_stars']:g}")
                print(f"      {r['object']:<14} {', '.join(why)}")
                drop([r["object"]], "zero point",
                     f"{label} invalid: {', '.join(why)}")
        return t[~bad]

    zp_b = screen(zp_b, "B")
    zp_v = screen(zp_v, "V")

    print(f"\n  n_ref_stars distribution (B, after screening):")
    print("   ", zp_b["n_ref_stars"].describe().round(1).to_dict())
    print(f"  zp_err (B): median {zp_b['zp_err'].median():.4f}, "
          f"max {zp_b['zp_err'].max():.4f} mag")

    # ----------------------------------------------------------------------
    # Photometry
    # ----------------------------------------------------------------------
    if not os.path.exists(COG_CSV):
        raise SystemExit(
            f"\nInput not found:\n  {COG_CSV}\n"
            f"Run 13_curve_of_growth.py first, or change ANNULUS_TAG.")

    print("\n" + "=" * 74)
    print(f"PHOTOMETRY  (annulus {ANNULUS_TAG})")
    print("=" * 74)
    cog = pd.read_csv(COG_CSV)
    all_objects = set(cog["object"])
    print(f"  rows in                          : {len(cog)}")
    print(f"  distinct objects                 : {len(all_objects)}")

    # Guard 1 -- background annulus. A property of the FRAME.
    if "annulus_ok" in cog.columns:
        per_meas = cog.drop_duplicates(subset=KEYS)
        n_meas, n_bad = len(per_meas), int((~per_meas["annulus_ok"]).sum())
        cog = cog[cog["annulus_ok"]]
        print(f"  annulus guard                    : {n_meas - n_bad}/{n_meas} "
              f"object-images kept ({n_bad} excluded)")
    else:
        print("  [warn] no annulus_ok column -- output predates 10b/step 13. The "
              "background may be contaminated by host light.")

    # (1) Guard 2 -- the aperture itself. A property of a SINGLE MEASUREMENT.
    if "aperture_ok" in cog.columns:
        n_ap_bad = int((~cog["aperture_ok"]).sum())
        cog = cog[cog["aperture_ok"]]
        print(f"  aperture guard                   : {n_ap_bad} rows excluded")
    else:
        print("  [warn] no aperture_ok column -- output predates step 13. Truncated "
              "and NaN-contaminated apertures are being included.")

    fid = cog[np.isclose(cog["radius_kpc"], FIDUCIAL_RADIUS_KPC)
              & (cog["telescope"] == TELESCOPE)]
    if len(fid) == 0:
        raise RuntimeError(
            f"No {TELESCOPE} rows at {FIDUCIAL_RADIUS_KPC} kpc -- check that the "
            f"aperture grid includes this radius.")

    # (8) duplicate guard
    dupes = fid.groupby(["object", "filter"]).size()
    if (dupes > 1).any():
        print(f"\n  [WARN] {int((dupes > 1).sum())} (object, filter) pairs appear "
              f"more than once at the fiducial radius. The merge below would "
              f"duplicate catalogue rows. Resolve before trusting the output.")
        print(dupes[dupes > 1].head(10).to_string())
    else:
        print(f"  duplicate check                  : none")

    flux_b = (fid[fid["filter"] == "B"][["object", "z", "flux_bkgsub"]]
              .rename(columns={"flux_bkgsub": "flux_B"}))
    flux_v = (fid[fid["filter"] == "V"][["object", "flux_bkgsub"]]
              .rename(columns={"flux_bkgsub": "flux_V"}))

    only_b = set(flux_b["object"]) - set(flux_v["object"])
    only_v = set(flux_v["object"]) - set(flux_b["object"])
    drop(only_b, "photometry", "du Pont B only at the fiducial radius")
    drop(only_v, "photometry", "du Pont V only at the fiducial radius")
    drop(all_objects - set(flux_b["object"]) - set(flux_v["object"]),
         "photometry", "no du Pont flux at the fiducial radius")

    flux = flux_b.merge(flux_v, on="object", how="inner")
    print(f"  objects with du Pont B and V     : {len(flux)}")

    nonpos = (flux["flux_B"] <= 0) | (flux["flux_V"] <= 0)
    drop(flux.loc[nonpos, "object"], "photometry",
         "non-positive flux at the fiducial radius")
    print(f"  of those, non-positive flux      : {int(nonpos.sum())}")

    usable = flux[~nonpos].copy()

    # ----------------------------------------------------------------------
    # (4) The epoch cut, made visible
    # ----------------------------------------------------------------------
    usable["year"] = usable["object"].map(object_year)
    usable["epoch"] = usable["year"].map(epoch)
    have_zp = set(zp_b["object"]) & set(zp_v["object"])
    usable["has_zp"] = usable["object"].isin(have_zp)

    print("\n" + "=" * 74)
    print("ZERO-POINT COVERAGE BY SURVEY EPOCH")
    print("=" * 74)
    tab = pd.crosstab(usable["epoch"], usable["has_zp"])
    for col in (False, True):
        if col not in tab.columns:
            tab[col] = 0
    tab = tab[[False, True]]
    tab.columns = ["no zero point", "has zero point"]
    print(tab.to_string())

    missing = usable[~usable["has_zp"]]
    drop(missing["object"], "zero point",
         "no du Pont zero point available for this object")

    n_csp1_missing = int((missing["epoch"] == "CSP-I").sum())
    if n_csp1_missing:
        print(f"""
  {n_csp1_missing} CSP-I objects are excluded here for want of a zero point,
  and no CSP-I object has one. This is the largest single cut in the
  pipeline and it is by SURVEY EPOCH, not by data quality.

  The resulting catalogue is a CSP-II sample. CSP-I and CSP-II differ in
  target selection and redshift reach, so this reshapes the redshift
  distribution rather than thinning the sample evenly. It must be stated
  in the paper's sample description.

  SUPERVISOR QUESTION: do du Pont zero points exist for the CSP-I objects
  (2004-2009), or were B_ZP_dup.dat and V_ZP_dup.dat derived for CSP-II
  only? If they exist, add the filenames to ZP_FILES at the top of this
  script; the calibrated sample roughly doubles.""")

    late_missing = missing[missing["epoch"] != "CSP-I"]
    if len(late_missing):
        print(f"\n  Also lacking a zero point, outside CSP-I: "
              f"{sorted(late_missing['object'])}")

    # ----------------------------------------------------------------------
    # Calibration
    # ----------------------------------------------------------------------
    merged = usable[usable["has_zp"]].merge(
        zp_b[["object", "zp", "zp_err", "n_ref_stars"]].rename(
            columns={"zp": "zp_B", "zp_err": "zp_err_B",
                     "n_ref_stars": "n_ref_B"}), on="object", how="inner")
    merged = merged.merge(
        zp_v[["object", "zp", "zp_err", "n_ref_stars"]].rename(
            columns={"zp": "zp_V", "zp_err": "zp_err_V",
                     "n_ref_stars": "n_ref_V"}), on="object", how="inner")

    merged["mag_B"] = merged["zp_B"] - 2.5 * np.log10(merged["flux_B"])
    merged["mag_V"] = merged["zp_V"] - 2.5 * np.log10(merged["flux_V"])
    merged["B_minus_V"] = merged["mag_B"] - merged["mag_V"]
    merged["B_minus_V_err"] = np.sqrt(merged["zp_err_B"] ** 2
                                      + merged["zp_err_V"] ** 2)
    merged["annulus_tag"] = ANNULUS_TAG   # (7) provenance travels with the data

    out_cols = ["object", "z", "flux_B", "flux_V", "mag_B", "mag_V",
                "B_minus_V", "B_minus_V_err", "annulus_tag",
                "epoch", "zp_err_B", "zp_err_V", "n_ref_B", "n_ref_V"]
    result = merged[out_cols].sort_values("object").reset_index(drop=True)

    # ----------------------------------------------------------------------
    # Write
    # ----------------------------------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    print()
    backup(OUT_PATH)
    result.to_csv(OUT_PATH, index=False)

    excl_df = pd.DataFrame(excl).drop_duplicates(subset=["object", "stage"])
    backup(EXCL_PATH)
    excl_df.to_csv(EXCL_PATH, index=False)

    # ----------------------------------------------------------------------
    # Report
    # ----------------------------------------------------------------------
    print("\n" + "=" * 74)
    print("RESULT")
    print("=" * 74)
    print(f"  calibrated objects : {len(result)}")
    print(f"  by epoch           : {result['epoch'].value_counts().to_dict()}")
    print(f"  written to         : {os.path.basename(OUT_PATH)}")
    print(f"  exclusions logged  : {len(excl_df)} -> {os.path.basename(EXCL_PATH)}")
    print()
    print(f"  median B-V             : {result['B_minus_V'].median():.4f} mag")
    print(f"  16th-84th percentile   : "
          f"{result['B_minus_V'].quantile(0.16):.4f} - "
          f"{result['B_minus_V'].quantile(0.84):.4f} mag")
    print(f"  full range             : {result['B_minus_V'].min():.4f} - "
          f"{result['B_minus_V'].max():.4f} mag")
    print()
    print(f"  median B-V uncertainty : {result['B_minus_V_err'].median():.4f} mag")
    print(f"  worst                  : {result['B_minus_V_err'].max():.4f} mag "
          f"({result.loc[result['B_minus_V_err'].idxmax(), 'object']})")
    print(f"""
  This uncertainty is the two zero-point terms in quadrature and NOTHING
  ELSE. It omits photon noise, background-estimation uncertainty, flat-field
  error, and the flux-dependent annulus systematic (2.5 mmag in the brightest
  flux quartile, 33.2 in the faintest). Report it as a LOWER BOUND.

  NOTE: this is the observed colour. Galactic extinction has not been applied.
  Next: 18_flag_unreliable_colours.py, then 19_apply_galactic_extinction.py.""")
    print("=" * 74)


if __name__ == "__main__":
    main()