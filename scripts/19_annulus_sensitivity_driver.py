"""
19_annulus_sensitivity_driver.py

Runs the full downstream chain once per background-annulus setting and reports
the three answers side by side.

WHAT THIS REPLACES
------------------
After 10b_curve_of_growth_annulus_test.py there is no longer a single
curve_of_growth.csv, but one file per annulus setting. Getting an answer out of
each of them by hand means editing the input path in script 11, running it,
renaming its output, editing the input path in script 18, running that,
renaming again -- then repeating twice more and hoping the files did not get
crossed. This script does that loop instead.

The colour calculation is lifted directly from script 11 and the statistics
from script 18; nothing new is introduced here. Both are reimplemented inline
rather than imported so that a single run cannot half-succeed with mismatched
inputs.

THE QUESTION THIS ANSWERS
-------------------------
Not "what is the scatter", but "does the answer depend on a choice nobody
validated". Two things are being watched:

  1. Does median_bkg_per_pixel fall as the annulus moves outward?
     If it does, the original 10-15 kpc annulus was sitting in host light and
     the background was over-subtracted. If it is flat across settings, the
     original annulus was clean and the concern closes.

  2. Does the SHAPE of scatter-versus-radius survive?
     If the curve keeps its shape across settings, it is a property of the
     data. If it moves by more than the bootstrap uncertainty, it was a
     property of the background, which would also account for the spurious
     signal reported by the first version of this analysis.

Rows where the annulus did not fit on the detector (annulus_ok == False) are
dropped, not kept. Their background was measured from whichever part of the
annulus landed on the chip and is not meaningful.
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
    pivot["instrumental_B_minus_V"] = np.where(
        valid, -2.5 * np.log10(pivot["B"] / pivot["V"]), np.nan)
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
                         f"Run 10b_curve_of_growth_annulus_test.py first.")

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

        if "annulus_ok" in cog.columns:
            n_bad = int((~per_meas["annulus_ok"]).sum())
            cog = cog[cog["annulus_ok"]]
        else:
            print(f"  [warn] {name}: no annulus_ok column -- this looks like an "
                  f"original script 10 output. Proceeding without the guard.")
            n_bad = 0

        loaded[name] = cog
        guard_stats[name] = (n_meas, n_bad)
        keys_here = set(map(tuple, cog[KEYS].drop_duplicates().to_numpy()))
        common = keys_here if common is None else (common & keys_here)

    print(f"Object-images usable in every setting: {len(common)}")
    for nm, (n_meas, n_bad) in guard_stats.items():
        print(f"   {nm:<12} {n_meas - n_bad}/{n_meas} passed the guard "
              f"({n_bad} dropped)")
    print("\nAll cross-setting comparisons below use the common subset, so a\n"
          "change of sample cannot masquerade as a change of background.\n")

    common_idx = pd.MultiIndex.from_tuples(sorted(common), names=KEYS)

    # ----------------------------------------------------------------------
    # PASS 2 -- analyse each setting on the common subset
    # ----------------------------------------------------------------------
    rows, curves = [], {}

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

        cog_fid = cog[np.isclose(cog["radius_kpc"], FIDUCIAL_RADIUS)]
        med_flux_fid = float(np.nanmedian(cog_fid["flux_bkgsub"]))
        med_area_fid = float(np.pi * np.nanmedian(cog_fid["radius_pix"]) ** 2)

        n_meas, n_bad = guard_stats[name]
        print(f"  scatter analysis: {res['n_objects']} objects, "
              f"{res['n_sig']}/{len(res['radii']) - 1} radii significant, "
              f"min p = {res['min_p']:.3f}")
        print()

        rows.append({
            "setting": name,
            "n_object_images_total": n_meas,
            "n_dropped_by_guard": n_bad,
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
    summary_path = os.path.join(OUT_DIR, "annulus_sensitivity_summary.csv")
    summary.to_csv(summary_path, index=False)

    # ----------------------------------------------------------------------
    # Comparison
    # ----------------------------------------------------------------------
    pd.set_option("display.width", 220)
    print("=" * 72)
    print("SIDE-BY-SIDE COMPARISON")
    print("=" * 72)
    print(summary.round(4).to_string(index=False))
    print()

    names = list(curves.keys())

    # Q1: does the background change matter, in FLUX terms?
    #
    # A fractional change in the background is the wrong test. The background is
    # subtracted as (counts per pixel) x (aperture area), so a change far too
    # small to notice against the sky level can still be a large fraction of the
    # source flux. What matters is delta_bkg x area, compared to the flux itself.
    print("-" * 72)
    print("Q1  Was the original annulus contaminated by host light?")
    print("-" * 72)
    bkgs = summary["median_bkg_per_pixel"].to_numpy()
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
        if abs(pct_flux) > 5.0:
            print(f"     This is a {abs(pct_flux):.1f}% flux error -- roughly "
                  f"{abs(pct_flux) / 100 * 2.5 / np.log(10) * 1000:.0f} millimag.")
            print(f"     The 10-15 kpc annulus WAS contaminated. Everything downstream of")
            print(f"     script 10 shifts: rebuild the catalogue from the widest annulus")
            print(f"     that still passes the guard for most objects.")
        elif abs(pct_flux) > 1.0:
            print(f"     A {abs(pct_flux):.1f}% flux error: small, but not negligible against")
            print(f"     a per-object colour uncertainty of ~0.12 mag. Quote the spread across")
            print(f"     settings as a systematic rather than ignoring it.")
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

    # Q2: is the shape of scatter-vs-radius stable?
    print("-" * 72)
    print("Q2  Does the scatter-versus-radius shape survive the change?")
    print("-" * 72)
    if len(names) > 1:
        ref_curve = curves[names[0]]
        common = ref_curve["radii"]
        stack = np.vstack([np.interp(common, curves[n]["radii"], curves[n]["scatter"])
                           for n in names])
        max_dev = float(np.nanmax(np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)))
        typical_ci = float(np.nanmedian(ref_curve["ci_hi"] - ref_curve["ci_lo"]))
        print(f"     Largest disagreement between settings at any radius : {max_dev:.4f} mag")
        print(f"     Typical bootstrap 95% interval width                : {typical_ci:.4f} mag")
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
        print("     Only one setting present; nothing to compare. Re-run 10b with at")
        print("     least two ANNULUS_SETTINGS.")
    print()

    # Q3: does the significance verdict change?
    print("-" * 72)
    print("Q3  Does the significance verdict change?")
    print("-" * 72)
    for nm, ns, mp in zip(summary["setting"], summary["n_radii_significant"],
                          summary["min_p_value"]):
        print(f"     {nm:<12} {ns} radii significant, min p = {mp:.3f}")
    if summary["n_radii_significant"].nunique() == 1 and summary["n_radii_significant"].iloc[0] == 0:
        print("\n     Null result across every setting. Robust to the background choice.")
    else:
        print("\n     The verdict is NOT stable across settings. Do not report a")
        print("     significance conclusion until the background is resolved.")
    print("=" * 72)

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