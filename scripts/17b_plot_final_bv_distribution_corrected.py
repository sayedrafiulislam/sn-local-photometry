"""
17b_plot_final_bv_distribution_corrected.py

Supersedes 17_plot_final_bv_distribution.py. Produces the local B-V colour
distribution for the Results section.


WHAT WAS WRONG WITH SCRIPT 17
-----------------------------

(1) IT PLOTTED THE PRE-EXTINCTION COLOURS.  [correction C8]

    Script 17 read calibrated_color_5kpc_flagged.csv and histogrammed
    `B_minus_V`. The dereddened catalogue produced by the extinction step was
    read by nothing at all. The paper quotes the dereddened median as its
    headline result while the figure showed the uncorrected distribution -- a
    difference of roughly 0.08 mag, which is visible on this axis.

(2) IT FILTERED ON `flag_low_flux`.

    That was script 16's single absolute-count criterion. 16c replaces it with
    two scale-free criteria combined into `flag_exclude`. This script prefers
    the new flag and falls back loudly.

(3) THE BINS WERE FINER THAN THE MEASUREMENT UNCERTAINTY.

    `bins=15` over a range of about 1.24 mag gives bins 0.083 mag wide. The
    median per-object colour uncertainty is 0.117 mag. Every object is therefore
    smeared across more than one bin, and any peak or gap in that histogram is
    structure the data cannot resolve -- but a reader will see it and interpret
    it.

    Bin width is now the LARGER of the Freedman-Diaconis width and the median
    per-object uncertainty, and the chosen width is annotated on the figure so
    the resolution limit is explicit rather than implied.

(4) THE MEDIAN HAD NO UNCERTAINTY.

    A dashed line at the median, with no indication of how well that median is
    determined. Now bootstrapped, with the interval shaded and quoted.

(5) NO BACKUP.


WHAT THE FIGURE SHOWS
---------------------
Main panel: the dereddened distribution, with the observed distribution as a
step outline behind it so the size and direction of the extinction correction
are visible in one image rather than requiring two figures.

The uncertainty scale is drawn as a horizontal bar of width equal to the median
per-object error. Structure narrower than that bar is not resolved.


READ THIS BEFORE QUOTING THE NUMBERS
------------------------------------
The quoted uncertainties are the two zero-point terms in quadrature plus the
16 per cent SFD map term. They omit photon noise, background uncertainty,
flat-field error, and the flux-dependent annulus systematic (2.5 mmag in the
brightest flux quartile, 33.2 in the faintest). They are LOWER BOUNDS.

The sample is CSP-II only. The supplied du Pont zero points do not cover CSP-I,
which removes 90 objects at the calibration stage. That is a cut by survey
epoch, not by data quality, and must be stated in the sample description.


OUTPUT
------
  bv_distribution.png
  bv_distribution_summary.txt      the numbers, ready to paste into the paper
"""

import os
import shutil
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
CALIB_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
IN_PATH = os.path.join(CALIB_DIR, "calibrated_color_5kpc_dered.csv")
OUT_PNG = os.path.join(CALIB_DIR, "bv_distribution.png")
OUT_TXT = os.path.join(CALIB_DIR, "bv_distribution_summary.txt")

FIDUCIAL_RADIUS_KPC = 5.0
N_BOOT = 5000
RNG_SEED = 42

# NO KELSEY COMPARISON LINE IS POSSIBLE, AND NONE SHOULD BE ADDED.
#
# Kelsey et al. (2021) measure rest-frame U-R, not B-V. There is no Kelsey B-V
# median to plot. Drawing their U-R value on a B-V axis would compare two
# different quantities that happen to share units, and a reader would take the
# offset between them to mean something.
#
# The comparison with Kelsey et al. is methodological -- local aperture
# photometry at a fixed physical radius, and the choice of that radius -- and
# belongs in prose, not on this figure.


def backup(path):
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


def boot_median(values, n_boot=N_BOOT, seed=RNG_SEED):
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    rng = np.random.default_rng(seed)
    b = np.array([np.median(rng.choice(v, size=len(v), replace=True))
                  for _ in range(n_boot)])
    return float(np.median(v)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def mad_sigma(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def main():
    if not os.path.exists(IN_PATH):
        raise SystemExit(
            f"\nInput not found:\n  {IN_PATH}\n"
            f"Run 15d_apply_galactic_extinction_corrected.py first.\n"
            f"(Order is 15c -> 16c -> 15d -> 17b, despite the numbering.)")

    df = pd.read_csv(IN_PATH)

    # (1) the dereddened colour is the one the paper reports
    if "B_minus_V_dered" not in df.columns:
        raise SystemExit(
            "\nNo B_minus_V_dered column -- this file has not been through the "
            "extinction step. Run 15d first.\n")

    # (2) prefer the combined flag
    if "flag_exclude" in df.columns:
        flag_col = "flag_exclude"
    elif "flag_low_flux" in df.columns:
        flag_col = "flag_low_flux"
        print("[WARN] no flag_exclude column -- falling back to flag_low_flux. "
              "The calibration-quality criterion is NOT applied.")
    else:
        flag_col = None
        print("[WARN] no exclusion flag found -- plotting the full sample.")

    keep = ~df[flag_col].astype(bool) if flag_col else pd.Series(True, index=df.index)
    clean = df[keep & df["B_minus_V_dered"].notna()].copy()

    obs = clean["B_minus_V"].to_numpy()
    ded = clean["B_minus_V_dered"].to_numpy()
    err = clean["B_minus_V_dered_err"].to_numpy()
    n = len(clean)

    med, lo, hi = boot_median(ded)
    med_obs, _, _ = boot_median(obs)
    med_err = float(np.nanmedian(err))

    # ----------------------------------------------------------------------
    # (3) do not bin finer than the measurement can resolve
    # ----------------------------------------------------------------------
    q75, q25 = np.percentile(ded, [75, 25])
    fd_width = 2.0 * (q75 - q25) / np.cbrt(n) if n > 1 else med_err
    bin_width = max(fd_width, med_err)
    lo_edge = np.floor(min(ded.min(), obs.min()) / bin_width) * bin_width
    hi_edge = np.ceil(max(ded.max(), obs.max()) / bin_width) * bin_width
    bins = np.arange(lo_edge, hi_edge + bin_width, bin_width)

    print(f"Sample            : {n} objects (flag: {flag_col})")
    print(f"Freedman-Diaconis : {fd_width:.4f} mag")
    print(f"median per-object : {med_err:.4f} mag")
    print(f"bin width adopted : {bin_width:.4f} mag  ({len(bins)-1} bins)")
    if bin_width == med_err:
        print("  -> limited by the measurement uncertainty, not by sample size")

    # ----------------------------------------------------------------------
    # Figure
    # ----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.5, 5.0))

    ax.hist(obs, bins=bins, histtype="step", linewidth=1.4,
            color="#999999", label=f"observed (median {med_obs:.3f})")
    ax.hist(ded, bins=bins, color="#4C72B0", edgecolor="white", linewidth=0.6,
            alpha=0.85, label=f"dereddened (median {med:.3f})")

    ax.axvspan(lo, hi, color="#C44E52", alpha=0.18, zorder=0)
    ax.axvline(med, color="#C44E52", linestyle="--", linewidth=1.6,
               label=f"median = {med:.3f} [{lo:.3f}, {hi:.3f}]")

    # the resolution limit, drawn rather than described
    ymax = ax.get_ylim()[1]
    xbar = np.percentile(ded, 92)
    ax.errorbar([xbar], [ymax * 0.88], xerr=[med_err / 2], fmt="none",
                ecolor="black", capsize=3, linewidth=1.2)
    ax.text(xbar, ymax * 0.91, "median\nuncertainty", ha="center", va="bottom",
            fontsize=8)

    ax.set_xlabel(r"Local $B-V$ colour (mag)")
    ax.set_ylabel("Number of objects")
    ax.set_title(f"Local $B-V$ at {FIDUCIAL_RADIUS_KPC:g} kpc  "
                 f"($n={n}$, bin width {bin_width:.3f} mag)")
    ax.legend(frameon=False, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    backup(OUT_PNG)
    fig.savefig(OUT_PNG, dpi=150)

    # ----------------------------------------------------------------------
    # Numbers for the paper
    # ----------------------------------------------------------------------
    lines = []
    def out(s=""):
        print(s)
        lines.append(s)

    out()
    out("=" * 74)
    out(f"LOCAL B-V AT {FIDUCIAL_RADIUS_KPC:g} kpc")
    out("=" * 74)
    out(f"  sample                     : {n} objects")
    out(f"  exclusion flag             : {flag_col}")
    out()
    out(f"  median, dereddened         : {med:.4f} mag   "
        f"95% CI [{lo:.4f}, {hi:.4f}]")
    out(f"  median, observed           : {med_obs:.4f} mag")
    out(f"  extinction correction      : {med - med_obs:+.4f} mag")
    out()
    out(f"  16th-84th percentile       : {np.percentile(ded, 16):.4f} - "
        f"{np.percentile(ded, 84):.4f} mag")
    out(f"  interquartile range        : {np.percentile(ded, 25):.4f} - "
        f"{np.percentile(ded, 75):.4f} mag")
    out(f"  robust scatter (sigma_MAD) : {mad_sigma(ded):.4f} mag")
    out(f"  full range                 : {ded.min():+.4f} to {ded.max():+.4f} mag")
    out()
    out(f"  median per-object error    : {med_err:.4f} mag  (LOWER BOUND --")
    out(f"    zero points and the SFD map term only. Omits photon noise,")
    out(f"    background uncertainty, flat-field error, and the flux-dependent")
    out(f"    annulus systematic.)")
    out()
    out(f"  scatter/error ratio        : {mad_sigma(ded)/med_err:.2f}")
    if mad_sigma(ded) / med_err < 1.5:
        out(f"    Below ~1.5 the observed spread is comparable to the")
        out(f"    measurement errors, so little of it can be claimed as")
        out(f"    intrinsic variation between host environments.")
    else:
        out(f"    Above ~1.5 the spread exceeds the errors, so some of it is")
        out(f"    plausibly intrinsic. Quantifying how much requires the full")
        out(f"    error budget, which is not yet available.")
    out()
    out("  SAMPLE CAVEAT: CSP-II only. The supplied du Pont zero points do not")
    out("  cover CSP-I, removing 90 objects at the calibration stage. That is a")
    out("  cut by survey epoch, not by data quality.")
    out("=" * 74)

    backup(OUT_TXT)
    with open(OUT_TXT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"\nSaved: {os.path.basename(OUT_PNG)}")
    print(f"Saved: {os.path.basename(OUT_TXT)}")


if __name__ == "__main__":
    main()