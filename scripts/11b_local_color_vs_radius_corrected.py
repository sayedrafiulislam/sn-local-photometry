"""
11b_local_color_vs_radius_corrected.py

Supersedes 11_local_color_vs_radius.py. The measurement is unchanged: local
instrumental B-V as a function of aperture radius, from same-telescope du Pont
pairs. Six defects found in the audit are corrected, and the provenance of the
output is made recoverable from the file itself.

WHY COLOUR AND NOT FLUX
-----------------------
Flux from an extended host has no reason to plateau -- three quarters of these
curves are still climbing at 10 kpc, because galaxies have no edge. Colour is a
ratio between two bands, so it can stabilise even while both bands keep growing,
provided the local stellar population is roughly uniform in colour at that scale.
If it does not stabilise, that is a colour gradient and an astrophysical result,
not a fault in the measurement.

WHY DU PONT ONLY
----------------
This is the most consequential decision in the script and it deserves stating
plainly rather than living inside a filter expression.

Forming B-V from two different telescopes would mean differencing measurements
made through different optics, different detectors and different sky. Any
instrumental difference between them enters the colour directly and is
indistinguishable from a real colour. Using one telescope for both bands makes
every instrumental term common to B and V, so it cancels in the subtraction.

Verified against the frame list: du Pont has 223 B and 225 V frames; Swope has
103 V and ZERO B. A same-telescope Swope colour is therefore impossible, not
merely inconvenient. (B_ZP_swo.dat exists in the repository but is unused.)

This is also why the plate-scale error never reached the published colours.
Swope is the telescope with the wrong assumed scale -- 0.430 arcsec/pixel in
reality against 0.230 assumed. This script discards Swope entirely, so the bug
is real, it is present in the background statistics, and it is absent from the
colours.

NOT PHOTOMETRICALLY CALIBRATED
------------------------------
Instrumental colour, -2.5*log10(flux_B/flux_V). This differs from true B-V by a
constant offset per object, applied in Phase 5. Fine for the SHAPE of colour
against radius; not an absolute colour.


WHAT WAS WRONG WITH SCRIPT 11
-----------------------------

(1) THE APERTURE GUARD WAS MISSING.

    Script 11 filtered on `annulus_ok` -- whether the background ring fitted on
    the detector -- but predates 10c, which added `aperture_ok` for the aperture
    itself. photutils tolerates an aperture running off the frame edge and
    returns the sum of whichever pixels exist, while the subtracted background
    still uses the full geometric area. 162 rows across the sample were affected
    and flowed into the colours unchecked.

(2) THE BACKUP FIRED ONCE AND THEN NEVER AGAIN.

        if os.path.exists(OUT_PATH) and not os.path.exists(BACKUP_PATH):

    Once local_color_vs_radius_pre_annulus_fix.csv existed, that condition was
    permanently false and every subsequent run overwrote the output with no
    backup whatsoever. Replaced with timestamped backups, matching 10c.

(3) THE OUTPUT CARRIED NO RECORD OF WHICH BACKGROUND BUILT IT.

    The script read curve_of_growth_ann20-30.csv and wrote plain
    local_color_vs_radius.csv. Nothing in that file said which annulus setting
    produced it; provenance could only be established by comparing file
    modification times, which survives exactly until someone copies the results
    directory. The tag is now written into the filename AND into a column, so it
    travels with the data.

(4) THE EXCLUDED-OBJECT COUNT WAS UNDERSTATED.

    The printed count reported objects with no du Pont frames at all (41). It
    missed the 5 objects that have du Pont data in only one band -- CSP13abm,
    SN05gj and SN08hv with V alone, SN06br and SN07ol with B alone. Those cannot
    yield a colour either, but they fell into the "non-positive flux" NaN count,
    where the message described them incorrectly: they have no flux in that
    band, rather than negative flux. The true count of objects that can never
    produce a colour is 46, and the reasons are now reported separately.

    This also corrects C5 in PAPER_CORRECTIONS.md, which states that 222 of 266
    objects had both B and V. 222 is the number of du Pont B FRAMES. The number
    of OBJECTS with both bands is 220 before the guards and 216 after.

(5) DUPLICATE FRAMES WOULD HAVE BEEN AVERAGED SILENTLY.

    pandas pivot_table defaults to aggfunc="mean". Two du Pont B frames for one
    object at one radius would have been quietly averaged, with no record that
    it happened. As it stands all 541 rows are unique in
    (object, telescope, filter), so this never occurred -- but it was true by
    luck rather than by construction. Now checked explicitly and reported.

(6) THE SAMPLE FUNNEL DID NOT BALANCE (introduced by the first version of THIS
    script, and corrected here).

    Four objects had du Pont B and V before the guards and neither after:
    SN10ae, SN2011iy, SN07af and LSQ14bbv. Losing BOTH bands removes an object
    from the post-guard band table entirely, so it matched none of the printed
    categories -- not "Swope only", since it has du Pont frames in principle, and
    not "one band", since it has none left. Those four simply vanished, and the
    printed counts silently summed to 262 rather than 266.

    The pre-guard band table is now retained and the guard-induced loss is
    reported by name, with a checksum that fails loudly if the funnel ever stops
    balancing again.

    Three of the four are the low-redshift geometric exclusion: at z = 0.0037 to
    0.0050 the 20-30 kpc annulus subtends more sky than the detector covers,
    consistent with the z ~ 0.005 threshold derived independently from frame
    dimensions. The fourth, LSQ14bbv, is a different failure entirely -- it sits
    above the sample median redshift with an annulus of only 115 pixels, and
    fails because the supernova coordinates fall outside the image (C11). The
    two causes must not be reported together.

    None of the four reaches the published catalogue.


OUTPUT
------
  local_color_vs_radius_{TAG}.csv    canonical, provenance in the name
  local_color_vs_radius.csv          identical copy, for scripts 12-18 and 09c/09d

Both are written. Downstream scripts continue to work unchanged while the tagged
file preserves provenance. Existing files are renamed to *.bak_YYYYmmdd_HHMMSS,
never deleted.

DOWNSTREAM: the output now carries an `annulus_tag` column. Any script reading
this file should check it rather than assuming.
"""

import os
import shutil
import datetime
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
# One of the tags written by 10c_curve_of_growth_final.py:
# "ann10-15", "ann15-25", "ann20-30".
ANNULUS_TAG = "ann20-30"

BASE_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
COG_CSV = os.path.join(BASE_DIR, f"curve_of_growth_{ANNULUS_TAG}.csv")

OUT_TAGGED = os.path.join(BASE_DIR, f"local_color_vs_radius_{ANNULUS_TAG}.csv")
OUT_COMPAT = os.path.join(BASE_DIR, "local_color_vs_radius.csv")

TELESCOPE = "dup"
FIDUCIAL_RADIUS = 5.0
KEYS = ["object", "telescope", "filter"]


def backup(path):
    """Rename an existing output out of the way. Nothing is ever deleted."""
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


def band_sets(frame, telescope):
    """object -> set of filters present, for one telescope."""
    sub = frame[frame["telescope"] == telescope]
    if len(sub) == 0:
        return pd.Series(dtype=object)
    return sub.groupby("object")["filter"].apply(lambda s: set(s))


def main():
    if not os.path.exists(COG_CSV):
        raise SystemExit(
            f"Input not found:\n  {COG_CSV}\n"
            f"Run 10c_curve_of_growth_final.py first, or change ANNULUS_TAG "
            f"at the top of this script."
        )

    print(f"Annulus setting : {ANNULUS_TAG}")
    print(f"Reading         : {os.path.basename(COG_CSV)}\n")

    df = pd.read_csv(COG_CSV)

    # Pre-guard snapshot. Needed so that objects removed BY the guards can be
    # reported by name rather than disappearing from every printed category.
    raw = df.copy()
    n_obj_raw = raw["object"].nunique()

    print("=" * 74)
    print("SAMPLE FUNNEL")
    print("=" * 74)
    print(f"  rows in                                 : {len(raw)}")
    print(f"  distinct objects                        : {n_obj_raw}")

    # ----------------------------------------------------------------------
    # Guard 1 -- the background annulus. A property of the FRAME, so it is all
    # nineteen radii or none.
    # ----------------------------------------------------------------------
    if "annulus_ok" in df.columns:
        per_meas = df.drop_duplicates(subset=KEYS)
        n_meas = len(per_meas)
        n_bad = int((~per_meas["annulus_ok"]).sum())
        df = df[df["annulus_ok"]]
        print(f"  annulus guard                           : {n_meas - n_bad}/{n_meas} "
              f"object-images kept ({n_bad} excluded)")
    else:
        print("  [warn] no annulus_ok column -- this looks like output from the "
              "original script 10. The background may be contaminated by host "
              "light. Proceeding without the guard.")

    # ----------------------------------------------------------------------
    # Guard 2 -- the aperture itself. A property of a SINGLE MEASUREMENT: a
    # frame can be sound at 1 kpc and off the chip by 9 kpc, so this is applied
    # per row and a frame may survive with a partial radius grid.
    # ----------------------------------------------------------------------
    if "aperture_ok" in df.columns:
        n_ap_bad = int((~df["aperture_ok"]).sum())
        df = df[df["aperture_ok"]]
        print(f"  aperture guard                          : {n_ap_bad} rows excluded "
              f"(off-chip or non-finite pixels)")
    else:
        print("  [warn] no aperture_ok column -- this predates "
              "10c_curve_of_growth_final.py. Truncated and NaN-contaminated "
              "apertures are being included.")

    # ----------------------------------------------------------------------
    # Telescope selection, with every lost object accounted for BY REASON
    # ----------------------------------------------------------------------
    dup = df[df["telescope"] == TELESCOPE]
    if len(dup) == 0:
        raise RuntimeError(f"No {TELESCOPE} rows present -- cannot form a colour.")

    bands_post = band_sets(df, TELESCOPE)
    bands_pre = band_sets(raw, TELESCOPE)

    def has_both(s):
        return {"B", "V"} <= s

    obj_both = set(bands_post[bands_post.apply(has_both)].index)
    obj_both_pre = set(bands_pre[bands_pre.apply(has_both)].index)

    obj_one_band = set(bands_post.index) - obj_both
    obj_no_dup = set(raw["object"]) - set(bands_pre.index)
    obj_lost_to_guards = sorted(obj_both_pre - obj_both)

    z_by_obj = raw.groupby("object")["z"].first()

    print()
    print(f"  objects with du Pont B and V, pre-guard : {len(obj_both_pre)}")
    print(f"  objects lost to the guards              : {len(obj_lost_to_guards)}")
    for o in obj_lost_to_guards:
        print(f"      {o:<14} z = {z_by_obj[o]:.4f}")
    print(f"  objects with du Pont B and V, post-guard: {len(obj_both)}")
    print(f"  objects excluded, no du Pont frames     : {len(obj_no_dup)} "
          f"(Swope V only -- Swope has no B imaging)")
    print(f"  objects excluded, du Pont one band      : {len(obj_one_band)}")
    for o in sorted(obj_one_band):
        print(f"      {o:<14} has only {sorted(bands_post[o])}")

    checksum = (len(obj_both) + len(obj_lost_to_guards)
                + len(obj_no_dup) + len(obj_one_band))
    print(f"  -> accounted for                        : {checksum} of {n_obj_raw}")
    if checksum != n_obj_raw:
        print(f"  [WARN] FUNNEL DOES NOT BALANCE -- "
              f"{n_obj_raw - checksum} object(s) unaccounted for. Every drop in "
              f"this pipeline must be traceable to a named reason; investigate "
              f"before trusting anything downstream.")

    # ----------------------------------------------------------------------
    # Duplicate check -- pivot_table would average these silently
    # ----------------------------------------------------------------------
    dup_counts = dup.groupby(KEYS + ["radius_kpc"]).size()
    n_dupes = int((dup_counts > 1).sum())
    if n_dupes:
        print(f"\n  [WARN] {n_dupes} (object, telescope, filter, radius) "
              f"combinations appear more than once.")
        print(f"         pivot_table will AVERAGE them silently. If that is not "
              f"what you want, resolve the duplicates before trusting these "
              f"colours.")
        print(dup_counts[dup_counts > 1].head(10).to_string())
    else:
        print(f"  duplicate check                         : none "
              f"(every object/filter/radius appears exactly once)")
    print("=" * 74 + "\n")

    # ----------------------------------------------------------------------
    # Colour
    # ----------------------------------------------------------------------
    pivot = dup.pivot_table(
        index=["object", "z", "radius_kpc"],
        columns="filter",
        values="flux_bkgsub",
    ).reset_index()

    if "B" not in pivot.columns or "V" not in pivot.columns:
        raise RuntimeError(
            "Expected both B and V columns after pivoting -- check that the "
            "curve-of-growth file contains both filters for at least some "
            "du Pont objects.")

    # Three distinct reasons a colour can be undefined. Script 11 collapsed
    # these into one count labelled "non-positive flux", which described only
    # the third and mislabelled the second.
    missing = pivot["B"].isna() | pivot["V"].isna()
    nonpos = (~missing) & ((pivot["B"] <= 0) | (pivot["V"] <= 0))
    valid = (~missing) & (~nonpos)

    print(f"colour defined for {int(valid.sum())} / {len(pivot)} "
          f"(object, radius) points")
    print(f"  undefined, band absent entirely : {int(missing.sum())}")
    print(f"  undefined, flux non-positive    : {int(nonpos.sum())}")
    print(f"     (non-positive flux is the measurement floor, not a fault: where")
    print(f"      local surface brightness sits at sky level, the "
          f"background-subtracted")
    print(f"      value is noise, and noise is negative half the time.)")

    with np.errstate(invalid="ignore", divide="ignore"):
        pivot["instrumental_B_minus_V"] = np.where(
            valid,
            -2.5 * np.log10(pivot["B"].to_numpy() / pivot["V"].to_numpy()),
            np.nan,
        )

    # Provenance travels with the data, not just in the filename.
    pivot["annulus_tag"] = ANNULUS_TAG

    # ----------------------------------------------------------------------
    # Write
    # ----------------------------------------------------------------------
    os.makedirs(BASE_DIR, exist_ok=True)
    print()
    for path in (OUT_TAGGED, OUT_COMPAT):
        backup(path)
        pivot.to_csv(path, index=False)

    print(f"\nWrote {len(pivot)} rows ({pivot['object'].nunique()} objects)")
    print(f"  canonical : {os.path.basename(OUT_TAGGED)}")
    print(f"  compat    : {os.path.basename(OUT_COMPAT)}  "
          f"(identical; for scripts 12-18 and 09c/09d)")

    at_fid = pivot[np.isclose(pivot["radius_kpc"], FIDUCIAL_RADIUS)]
    n_fid = int(at_fid["instrumental_B_minus_V"].notna().sum())
    print(f"\nAt the {FIDUCIAL_RADIUS:g} kpc fiducial radius:")
    print(f"  objects with a defined instrumental colour : {n_fid}")
    print(f"  median instrumental B-V                    : "
          f"{np.nanmedian(at_fid['instrumental_B_minus_V']):.4f}")

    print("\nNOTE: this is instrumental colour. The zero point from script 15 is "
          "\n      one additive constant per object and has not been applied.")


if __name__ == "__main__":
    main()