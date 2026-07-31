"""
22_annulus_sensitivity.py

Runs the full downstream chain once per background-annulus setting and reports
the answers side by side.

WHAT THIS REPLACES
------------------
After 10b/10c there is no longer a single curve_of_growth.csv, but one file per
annulus setting. Getting an answer out of each of them by hand means editing the
input path in script 11, running it, renaming its output, editing the input path
in script 18, running that, renaming again -- then repeating twice more and
hoping the files did not get crossed. This script does that loop instead.

The colour calculation is lifted directly from script 11 and the statistics from
script 18; nothing new is introduced. Both are reimplemented inline rather than
imported so that a single run cannot half-succeed with mismatched inputs.

THE QUESTION THIS ANSWERS
-------------------------
Not "what is the scatter", but "does the answer depend on a choice nobody
validated". Three things are being watched:

  1. Does median_bkg_per_pixel fall as the annulus moves outward?
     If it does, the original 10-15 kpc annulus was sitting in host light and
     the background was over-subtracted. If it is flat across settings, the
     original annulus was clean and the concern closes.

  2. How large is the induced bias ON COLOUR, which is what the paper reports?
     See the note under Q1b -- this is not the same as the bias on flux.

  3. Does the SHAPE of scatter-versus-radius survive?
     If the curve keeps its shape across settings, it is a property of the data.
     If it moves by more than the bootstrap uncertainty, it was a property of
     the background, which would also account for the spurious signal reported
     by the first version of this analysis.


CHANGES IN THIS VERSION
-----------------------

(1) BOTH GUARDS ARE NOW APPLIED.

    The previous version dropped rows where the background annulus failed
    (`annulus_ok == False`) but knew nothing about the aperture, because it
    predates 10c. 10c added `aperture_ok`, which flags apertures that ran off
    the detector or contained non-finite pixels -- 162 rows, 1.6 per cent.
    Those rows were previously included here.

    Note the two guards differ in grain. `annulus_ok` is a property of the
    frame: one background per frame per setting, so it is all nineteen radii or
    none. `aperture_ok` is a property of a single measurement: a frame can be
    perfectly good at 1 kpc and have run off the chip by 9 kpc. It is therefore
    applied per row, and a frame can survive with a partial radius grid.

(2) THE COLOUR BIAS IS NOW MEASURED, NOT INFERRED (Q1b).

    Q1 reports the bias on FLUX in a single band. The paper reports a bias on
    B-V, which is a DIFFERENCE of two magnitudes. Since both bands are measured
    from the same annulus geometry on the same galaxy, their background errors
    are correlated and partially cancel in the colour. The flux bias is
    therefore an UPPER BOUND on the colour bias, and quoting it as though it
    were the colour bias overstates the effect.

    Q1b measures the colour shift directly: for every object with a valid colour
    at the fiducial radius under both the first and the last annulus setting,
    take the difference, and bootstrap the median. No model, no assumption about
    how much cancels.

(3) EXACT MAGNITUDE CONVERSION.

    The previous version used the linearisation (2.5/ln 10) x f, which
    understates the true -2.5 log10(1 - f) by about 4 per cent at f ~ 0.07 and
    diverges further as f grows. Both are now printed so the difference is
    visible rather than silent.

(4) THE log10 WARNING IS HANDLED RATHER THAN EMITTED.

    Non-positive fluxes are expected -- they are the measurement floor, not a
    fault -- and are already counted and set to NaN. Wrapping the call in
    np.errstate stops pandas printing a RuntimeWarning that looks like an error
    but is not.

INPUT
-----
  curve_of_growth_ann*.csv     (from 13_curve_of_growth.py)

OUTPUT
------
  annulus_sensitivity_summary.csv
  annulus_sensitivity_comparison.png
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.stats import mad_std

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
IN_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
OUT_DIR = IN_DIR
INPUT_GLOB = "curve_of_growth_ann*.csv"

N_BOOT = 5000
RNG_SEED = 42
REFERENCE_RADIUS = 4.0            # pre-specified: Kelsey et al. (2021) fiducial
CI_LOWER, CI_UPPER = 2.5, 97.5    # 95 per cent
FDR_ALPHA = 0.05
MIN_OBJECTS_PER_RADIUS = 5
FIDUCIAL_RADIUS = 5.0             # radius at which the catalogue is built


# --------------------------------------------------------------------------
# Helpers (identical in behaviour to scripts 11 and 18)
# --------------------------------------------------------------------------
def robust_scatter(values):
    values = values[~np.isnan(values)]
    if len(values) < MIN_OBJECTS_PER_RADIUS:
        return np.nan
    return mad_std(values)


def benjamini_hochberg(pvals, alpha=FDR_ALPHA):
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q_ranked = np.minimum.accumulate((ranked * n / np.arange(1, n + 1))[::-1])[::-1]
    q_ranked = np.clip(q_ranked, 0, 1)
    q = np.empty(n)
    q[order] = q_ranked
    return q < alpha, q


def frac_to_millimag(f):
    """Exact conversion of a fractional flux error to millimagnitudes."""
    f = np.asarray(f, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return -2.5 * np.log10(1.0 - f) * 1000.0


def compute_colors(cog):
    """Script 11's logic: same-telescope du Pont B/V instrumental colour."""
    dup = cog[cog["telescope"] == "dup"]
    if len(dup) == 0:
        raise RuntimeError("No du Pont rows present -- cannot form a colour.")

    pivot = dup.pivot_table(
        index=["object", "z", "radius_kpc"],
        columns="filter",
        values="flux_bkgsub",
    ).reset_index()

    if "B" not in pivot.columns or "V" not in pivot.columns:
        raise RuntimeError("Expected both B and V after pivoting.")

    valid = (pivot["B"] > 0) & (pivot["V"] > 0)
    # Non-positive flux is the measurement floor, not an error. Counted, set to
    # NaN, and the warning suppressed rather than printed.
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(valid, pivot["B"].to_numpy() / pivot["V"].to_numpy(), np.nan)
        pivot["instrumental_B_minus_V"] = np.where(
            valid, -2.5 * np.log10(ratio), np.nan)
    return pivot, int((~valid).sum()), len(pivot)


def scatter_analysis(colors):
    """Script 18's logic: paired bootstrap, pre-specified reference, FDR."""
    wide = colors.pivot_table(index="object", columns="radius_kpc",
                              values="instrumental_B_minus_V")
    radii = sorted(wide.columns.tolist())
    data = wide[radii].to_numpy()
    n_objects = len(wide)
    n_radii = len(radii)

    if REFERENCE_RADIUS not in radii:
        raise ValueError(f"Reference radius {REFERENCE_RADIUS} not in grid.")
    ref_idx = radii.index(REFERENCE_RADIUS)

    rng = np.random.default_rng(RNG_SEED)
    boot = np.empty((N_BOOT, n_radii))
    for i in range(N_BOOT):
        idx = rng.integers(0, n_objects, size=n_objects)
        resampled = data[idx, :]
        for j in range(n_radii):
            boot[i, j] = robust_scatter(resampled[:, j])

    point = np.array([robust_scatter(data[:, j]) for j in range(n_radii)])
    diff = boot - boot[:, [ref_idx]]

    frac_below = np.nanmean(diff < 0, axis=0)
    p = 2.0 * np.minimum(frac_below, 1.0 - frac_below)
    p = np.clip(p, 1.0 / N_BOOT, 1.0)
    p[ref_idx] = 1.0

    test_mask = np.ones(n_radii, dtype=bool)
    test_mask[ref_idx] = False
    reject_sub, _ = benjamini_hochberg(p[test_mask])
    sig = np.zeros(n_radii, dtype=bool)
    sig[test_mask] = reject_sub

    return {
        "radii": np.array(radii),
        "scatter": point,
        "ci_lo": np.nanpercentile(boot, CI_LOWER, axis=0),
        "ci_hi": np.nanpercentile(boot, CI_UPPER, axis=0),
        "n_objects": n_objects,
        "n_sig": int(sig.sum()),
        "min_p": float(np.nanmin(p[test_mask])),
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    paths = sorted(glob.glob(os.path.join(IN_DIR, INPUT_GLOB)))
    if not paths:
        raise SystemExit(f"No files matching {INPUT_GLOB} in {IN_DIR}. "
                         f"Run 13_curve_of_growth.py first.")

    print(f"Found {len(paths)} annulus setting(s):")
    for p in paths:
        print(f"   {os.path.basename(p)}")
    print()

    KEYS = ["object", "telescope", "filter"]

    # ----------------------------------------------------------------------
    # PASS 1 -- load everything, find the object-images usable in EVERY setting
    #
    # The guard removes different objects at different annulus widths (the
    # lowest-redshift hosts fail first, since their annuli are largest in
    # pixels). Comparing settings on their own samples therefore conflates a
    # change of background with a change of sample: median flux can fall as the
    # background falls, purely because different objects are being averaged.
    # Every cross-setting number below is computed on the common subset.
    # ----------------------------------------------------------------------
    loaded, guard_stats = {}, {}
    common = None

    for path in paths:
        name = os.path.basename(path).replace("curve_of_growth_", "").replace(".csv", "")
        cog = pd.read_csv(path)
        per_meas = cog.drop_duplicates(subset=KEYS)
        n_meas = len(per_meas)
        n_rows_before = len(cog)

        # --- guard 1: the background annulus. A frame-level property. ---
        if "annulus_ok" in cog.columns:
            n_bad = int((~per_meas["annulus_ok"]).sum())
            cog = cog[cog["annulus_ok"]]
        else:
            print(f"  [warn] {name}: no annulus_ok column -- this looks like an "
                  f"original script 10 output. Proceeding without the guard.")
            n_bad = 0

        # --- guard 2: the aperture itself. A row-level property. ---
        # A frame can be sound at 1 kpc and off the chip by 9 kpc, so this is
        # applied per measurement and a frame may survive with a partial grid.
        if "aperture_ok" in cog.columns:
            n_ap_bad = int((~cog["aperture_ok"]).sum())
            cog = cog[cog["aperture_ok"]]
        else:
            print(f"  [warn] {name}: no aperture_ok column -- this predates "
                  f"13_curve_of_growth.py. Aperture guard NOT applied; "
                  f"truncated and NaN-contaminated apertures are included.")
            n_ap_bad = 0

        loaded[name] = cog
        guard_stats[name] = (n_meas, n_bad, n_ap_bad, n_rows_before, len(cog))
        keys_here = set(map(tuple, cog[KEYS].drop_duplicates().to_numpy()))
        common = keys_here if common is None else (common & keys_here)

    print(f"Object-images usable in every setting: {len(common)}")
    for nm, (n_meas, n_bad, n_ap_bad, n_before, n_after) in guard_stats.items():
        print(f"   {nm:<12} annulus {n_meas - n_bad}/{n_meas} frames "
              f"({n_bad} dropped) | aperture {n_ap_bad} rows dropped | "
              f"rows {n_after}/{n_before}")
    print("\nAll cross-setting comparisons below use the common subset, so a\n"
          "change of sample cannot masquerade as a change of background.\n")

    common_idx = pd.MultiIndex.from_tuples(sorted(common), names=KEYS)

    # ----------------------------------------------------------------------
    # PASS 2 -- analyse each setting on the common subset
    # ----------------------------------------------------------------------
    rows, curves, colors_at_fid = [], {}, {}

    for name, cog_full in loaded.items():
        print("=" * 72)
        print(f"SETTING: {name}")
        print("=" * 72)

        cog = cog_full.set_index(KEYS).loc[common_idx].reset_index()

        med_bkg = (float(np.nanmedian(
            cog.drop_duplicates(subset=KEYS)["bkg_per_pixel"]))
            if "bkg_per_pixel" in cog.columns else np.nan)

        colors, n_invalid, n_points = compute_colors(cog)
        print(f"  colour: {n_invalid}/{n_points} (object, radius) points have "
              f"non-positive flux -> NaN")

        res = scatter_analysis(colors)
        curves[name] = res

        at_fid = colors[np.isclose(colors["radius_kpc"], FIDUCIAL_RADIUS)]
        med_color_fid = float(np.nanmedian(at_fid["instrumental_B_minus_V"]))
        n_valid_fid = int(at_fid["instrumental_B_minus_V"].notna().sum())

        # Kept per object so the colour bias can be measured pairwise in Q1b.
        colors_at_fid[name] = (at_fid.groupby("object")["instrumental_B_minus_V"]
                               .first().dropna())

        cog_fid = cog[np.isclose(cog["radius_kpc"], FIDUCIAL_RADIUS)]
        med_flux_fid = float(np.nanmedian(cog_fid["flux_bkgsub"]))
        med_area_fid = float(np.pi * np.nanmedian(cog_fid["radius_pix"]) ** 2)

        # Per-object fractional flux bias, for the median-of-ratios statistic
        # reported in Q1. Kept here so it uses each object's own area and flux
        # rather than the sample medians.
        n_meas, n_bad, n_ap_bad, _, _ = guard_stats[name]
        print(f"  scatter analysis: {res['n_objects']} objects, "
              f"{res['n_sig']}/{len(res['radii']) - 1} radii significant, "
              f"min p = {res['min_p']:.3f}")
        print()

        rows.append({
            "setting": name,
            "n_object_images_total": n_meas,
            "n_dropped_by_annulus_guard": n_bad,
            "n_rows_dropped_by_aperture_guard": n_ap_bad,
            "n_in_common_subset": len(common),
            "median_bkg_per_pixel": med_bkg,
            "median_flux_at_5kpc": med_flux_fid,
            "median_aperture_area_px_at_5kpc": med_area_fid,
            "n_objects_in_scatter": res["n_objects"],
            "n_valid_colors_at_5kpc": n_valid_fid,
            "median_instr_color_at_5kpc": med_color_fid,
            "scatter_min": float(np.nanmin(res["scatter"])),
            "scatter_max": float(np.nanmax(res["scatter"])),
            "scatter_spread": float(np.nanmax(res["scatter"]) - np.nanmin(res["scatter"])),
            "n_radii_significant": res["n_sig"],
            "min_p_value": res["min_p"],
        })

    summary = pd.DataFrame(rows)

    # ----------------------------------------------------------------------
    # Comparison
    # ----------------------------------------------------------------------
    pd.set_option("display.width", 240)
    print("=" * 72)
    print("SIDE-BY-SIDE COMPARISON")
    print("=" * 72)
    print(summary.round(4).to_string(index=False))
    print()

    names = list(curves.keys())

    # ------------------------------------------------------------------
    # Q1: does the background change matter, in FLUX terms?
    #
    # A fractional change in the background is the wrong test. The background is
    # subtracted as (counts per pixel) x (aperture area), so a change far too
    # small to notice against the sky level can still be a large fraction of the
    # source flux. What matters is delta_bkg x area, compared to the flux.
    # ------------------------------------------------------------------
    print("-" * 72)
    print("Q1  Was the original annulus contaminated by host light?")
    print("-" * 72)
    bkgs = summary["median_bkg_per_pixel"].to_numpy()
    pct_flux = np.nan
    if np.all(np.isfinite(bkgs)) and len(bkgs) > 1:
        for nm, b in zip(summary["setting"], bkgs):
            print(f"     {nm:<12} median background/pixel = {b:.4f}")

        delta_bkg = bkgs[0] - bkgs[-1]
        area = summary["median_aperture_area_px_at_5kpc"].iloc[0]
        flux = summary["median_flux_at_5kpc"].iloc[0]
        induced = delta_bkg * area
        pct_flux = 100.0 * induced / flux if flux else np.nan

        print()
        print(f"     change in background            : {delta_bkg:+.4f} counts/pixel "
              f"({100 * delta_bkg / bkgs[0]:+.2f}% of sky)")
        print(f"     median aperture area at {FIDUCIAL_RADIUS:g} kpc  : {area:.0f} px^2")
        print(f"     induced change in measured flux : {induced:+.0f} counts "
              f"({pct_flux:+.1f}% of the flux at {FIDUCIAL_RADIUS:g} kpc)")
        print()
        exact = frac_to_millimag(abs(pct_flux) / 100.0)
        linear = abs(pct_flux) / 100.0 * 2.5 / np.log(10) * 1000
        print(f"     In magnitudes : {exact:.1f} mmag exact "
              f"({linear:.1f} mmag under the linear approximation)")
        print()
        print(f"     CAUTION -- this is a ratio of medians (median delta_bkg x median")
        print(f"     area / median flux), which is dominated by the brighter objects.")
        print(f"     The median of the per-object ratios is a different and generally")
        print(f"     smaller number. Quote whichever you define, and say which.")
        print()
        if abs(pct_flux) > 5.0:
            print(f"     The 10-15 kpc annulus WAS contaminated. Everything downstream")
            print(f"     of script 10 shifts: build the catalogue from the widest")
            print(f"     annulus that still passes the guard for most objects.")
        elif abs(pct_flux) > 1.0:
            print(f"     A {abs(pct_flux):.1f}% flux error: small, but not negligible against")
            print(f"     a per-object colour uncertainty of ~0.12 mag. Quote the spread")
            print(f"     across settings as a systematic rather than ignoring it.")
        else:
            print(f"     Under 1% in flux. The 10-15 kpc annulus was effectively clean.")
            print(f"     Record the check in Limitations and move on.")
        print()
        print(f"     Note: judged in flux, not as a fraction of sky. A background error")
        print(f"     of {100 * delta_bkg / bkgs[0]:.2f}% of the sky level becomes a "
              f"{abs(pct_flux):.1f}% flux error once")
        print(f"     multiplied by the aperture area.")
    else:
        print("     No bkg_per_pixel column found; cannot assess.")
    print()

    # ------------------------------------------------------------------
    # Q1b: the bias ON COLOUR, measured directly
    #
    # Q1 gives the bias on flux in ONE band. The paper reports B-V, a
    # DIFFERENCE of magnitudes. Both bands are measured through the same
    # annulus geometry on the same galaxy, so their background errors are
    # correlated and partially cancel. Q1's number is therefore an upper bound.
    # Here the shift is measured object by object instead of argued about.
    # ------------------------------------------------------------------
    print("-" * 72)
    print("Q1b How large is the bias on COLOUR, which is what the paper reports?")
    print("-" * 72)
    if len(names) > 1:
        first, last = names[0], names[-1]
        joined = pd.concat([colors_at_fid[first].rename("a"),
                            colors_at_fid[last].rename("b")],
                           axis=1, join="inner").dropna()
        if len(joined) >= MIN_OBJECTS_PER_RADIUS:
            d = (joined["a"] - joined["b"]).to_numpy()
            med = float(np.median(d))
            rng = np.random.default_rng(RNG_SEED)
            bs = np.array([np.median(rng.choice(d, size=len(d), replace=True))
                           for _ in range(N_BOOT)])
            lo, hi = np.percentile(bs, [CI_LOWER, CI_UPPER])

            print(f"     Objects with a valid colour at {FIDUCIAL_RADIUS:g} kpc under both")
            print(f"     {first} and {last} : {len(joined)}")
            print()
            print(f"     median colour shift ({first} - {last})")
            print(f"       = {med * 1000:+.1f} mmag   95% CI [{lo * 1000:+.1f}, {hi * 1000:+.1f}]")
            print(f"     mean {np.mean(d) * 1000:+.1f} mmag, "
                  f"scatter (MAD) {mad_std(d) * 1000:.1f} mmag")
            print()
            if np.isfinite(pct_flux):
                bound = frac_to_millimag(abs(pct_flux) / 100.0)
                if bound > 0:
                    print(f"     Single-band flux bias (Q1, upper bound) : {bound:.1f} mmag")
                    print(f"     Measured colour bias                    : {abs(med) * 1000:.1f} mmag")
                    print(f"     Cancellation between B and V removes "
                          f"{100 * (1 - abs(med) * 1000 / bound):.0f}% of it.")
                    print()
            if lo < 0 < hi:
                print("     The interval spans zero: no detectable colour bias from the")
                print("     annulus choice. Report the flux bias as a bound and say the")
                print("     colour is consistent with unaffected.")
            else:
                print("     The colour shift is resolved. This number, not the flux bias,")
                print("     is what belongs in the paper as the annulus systematic on B-V.")
        else:
            print(f"     Only {len(joined)} objects in common -- too few to measure.")
    else:
        print("     Only one setting present; nothing to compare.")
    print()

    # ------------------------------------------------------------------
    # Q2: is the shape of scatter-vs-radius stable?
    # ------------------------------------------------------------------
    print("-" * 72)
    print("Q2  Does the scatter-versus-radius shape survive the change?")
    print("-" * 72)
    max_dev = np.nan
    if len(names) > 1:
        ref_curve = curves[names[0]]
        grid = ref_curve["radii"]
        stack = np.vstack([np.interp(grid, curves[n]["radii"], curves[n]["scatter"])
                           for n in names])
        max_dev = float(np.nanmax(np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)))
        typical_ci = float(np.nanmedian(ref_curve["ci_hi"] - ref_curve["ci_lo"]))
        print(f"     Largest disagreement between settings at any radius : {max_dev:.4f} mag")
        print(f"     Typical bootstrap 95% interval width                : {typical_ci:.4f} mag")
        print()
        print(f"     -> set ANNULUS_SYSTEMATIC_MAG = {max_dev:.4f} at the top of")
        print(f"        18_color_scatter_corrected.py, and update the docstring.")
        print()
        if max_dev < 0.5 * typical_ci:
            print("     The curves agree to well within their own uncertainty. The shape is a")
            print("     property of the data, not of the background choice. The null result")
            print("     stands, and the spread across settings can be quoted as a systematic.")
        elif max_dev < typical_ci:
            print("     The curves differ by less than the bootstrap interval, but not")
            print("     negligibly. Report the spread as a systematic and say so explicitly.")
        else:
            print("     The curves differ by MORE than the bootstrap uncertainty. The shape")
            print("     is being driven by the background, not by the data. No conclusion")
            print("     about aperture radius can be drawn until the background is settled --")
            print("     and this would also explain the spurious signal found earlier.")
    else:
        print("     Only one setting present; nothing to compare. Re-run 10c with at")
        print("     least two ANNULUS_SETTINGS.")
    print()

    # ------------------------------------------------------------------
    # Q3: does the significance verdict change?
    # ------------------------------------------------------------------
    print("-" * 72)
    print("Q3  Does the significance verdict change?")
    print("-" * 72)
    for nm, ns, mp in zip(summary["setting"], summary["n_radii_significant"],
                          summary["min_p_value"]):
        print(f"     {nm:<12} {ns} radii significant, min p = {mp:.3f}")
    if summary["n_radii_significant"].nunique() == 1 and summary["n_radii_significant"].iloc[0] == 0:
        print("\n     Null result across every setting. Robust to the background choice.")
        print("     Note that min p is expected to drift between settings; it is the")
        print("     smallest of 18 correlated comparisons and is not itself a result.")
    else:
        print("\n     The verdict is NOT stable across settings. Do not report a")
        print("     significance conclusion until the background is resolved.")
    print("=" * 72)

    summary_path = os.path.join(OUT_DIR, "annulus_sensitivity_summary.csv")
    summary.to_csv(summary_path, index=False)

    # ----------------------------------------------------------------------
    # Overlay figure
    # ----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    colours = ["#1F3B73", "#C44E52", "#55A868", "#8172B2", "#CCB974"]
    for k, nm in enumerate(names):
        cv = curves[nm]
        c = colours[k % len(colours)]
        ax.fill_between(cv["radii"], cv["ci_lo"], cv["ci_hi"], color=c, alpha=0.15, linewidth=0)
        ax.plot(cv["radii"], cv["scatter"], marker="o", markersize=4.5, linewidth=1.8,
                color=c, label=f"{nm}  (n={cv['n_objects']})")
    ax.axvline(REFERENCE_RADIUS, color="#888888", linestyle="--", linewidth=1.4,
               label=f"Reference: {REFERENCE_RADIUS:g} kpc")
    ax.set_xlabel("Aperture radius (kpc)")
    ax.set_ylabel(r"Scatter in instrumental $B-V$ (mag)")
    ax.set_title("Sensitivity of the scatter-radius relation to background annulus")
    ax.legend(fontsize=9, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig_path = os.path.join(OUT_DIR, "annulus_sensitivity_comparison.png")
    fig.savefig(fig_path, dpi=150)

    print(f"\nSaved: {summary_path}")
    print(f"Saved: {fig_path}")


if __name__ == "__main__":
    main()