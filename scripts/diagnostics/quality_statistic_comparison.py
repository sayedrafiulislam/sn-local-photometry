"""
quality_statistic_comparison.py

A teaching / justification script. It does not modify the pipeline. Its only
job is to demonstrate, on real frames from this data set, why the per-image
scatter statistic used by 05_flag_image_quality.py is mad_std and not the
standard deviation or a percentile-based interquartile range.

The question
------------
Each image yields 13-25 individual stellar FWHM measurements. To decide whether
an image is defective we need one number describing how much those measurements
disagree with each other. A large disagreement means the PSF is not behaving
like a single well-defined Gaussian -- for example a defocused frame, where the
profile is a donut and the fit returns a different width depending on which part
of the ring dominates.

Three candidates:

  std        the standard deviation.
             Breakdown point 0%: a single bad value moves it without limit.

  p84 - p16  the central 68% range.
             Breakdown point 16%: robust in principle, but at n = 13-25 the
             16th percentile is interpolated around the 3rd or 4th sorted
             value. Its behaviour is governed by rank position, so it responds
             in steps rather than smoothly.

  mad_std    1.4826 x median(|x - median(x)|).
             Breakdown point 50%: half the data must be corrupted before it
             is misled. The scale factor makes it estimate the same quantity
             as std for Gaussian data, so thresholds are interpretable on the
             same scale.

What "breakdown point" means: the fraction of the sample that must be corrupted
before the statistic can be made arbitrarily wrong. It is the standard way of
comparing robust estimators (see e.g. Huber & Ronchetti, Robust Statistics,
2nd ed., Wiley 2009, Ch. 1).

The demonstrations
------------------
1. CONTROLLED INJECTION. Take a real, clean frame and add cosmic-ray-like
   detections one at a time. Watch each statistic respond.

2. RANK ANALYSIS. Show which sorted value actually sets p16 and p84 at the
   sample sizes present in this data set.

3. REAL FRAMES. Compare a clean frame, a contaminated frame, and a genuinely
   defocused frame, and ask which statistic separates them.

4. DISCRIMINATION. Across all images, check how cleanly each statistic
   separates the frames that were flagged from those that were not.

Usage
-----
    python quality_statistic_comparison.py --per-star results\\phase1_psf\\psf_fwhm_per_star.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# A clean du Pont frame with the full 25 stars and no sub-half-median
# detections. Used as the uncontaminated baseline for the injection test.
DEFAULT_CLEAN = "LSQ12aor_V_comb_dup.fits"

# A frame carrying many spurious sharp detections.
DEFAULT_CONTAMINATED = "CSP14aaa_B_comb_dup.fits"

# A frame independently confirmed by eye as defocused -- the case the
# scatter flag exists to catch.
DEFAULT_DEFOCUSED = "ASAS14mw_V_comb_swo.fits"

# Typical width of a cosmic ray or hot pixel once fitted: about one pixel.
ARTIFACT_FWHM_PIX = 1.30


def mad_std(x) -> float:
    """
    Median absolute deviation, scaled to be comparable to a standard deviation.

    The factor 1.4826 = 1 / Phi^-1(0.75) makes this an unbiased estimator of
    sigma when the data really are Gaussian, so a threshold set in these units
    means the same thing it would mean for std.
    """
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.nan
    return 1.4826 * np.median(np.abs(x - np.median(x)))


def iqr_68(x) -> float:
    """The central 68 per cent range, p84 - p16."""
    x = np.asarray(x, dtype=float)
    return float(np.percentile(x, 84) - np.percentile(x, 16))


def stats_row(x) -> dict:
    x = np.asarray(x, dtype=float)
    return {
        "n": len(x),
        "median": float(np.median(x)),
        "std": float(np.std(x, ddof=1)),
        "iqr": iqr_68(x),
        "mad": mad_std(x),
    }


def demo_injection(base: np.ndarray, fname: str, k_max: int = 8) -> None:
    print("=" * 74)
    print("1. CONTROLLED INJECTION")
    print("=" * 74)
    print(f"Baseline frame: {fname}")
    print(f"  n = {len(base)} stars, median FWHM = {np.median(base):.3f} px, "
          f"no spurious detections.")
    print(f"\nAdding artificial {ARTIFACT_FWHM_PIX} px detections one at a time")
    print("(this is what a cosmic ray or hot pixel looks like after fitting):\n")

    print(f"{'added':>6s} {'n':>4s} {'median':>8s} {'std':>8s} "
          f"{'p84-p16':>9s} {'mad_std':>9s}")
    ref = None
    for k in range(k_max + 1):
        v = np.concatenate([base, np.full(k, ARTIFACT_FWHM_PIX)])
        s = stats_row(v)
        if ref is None:
            ref = s
        print(f"{k:6d} {s['n']:4d} {s['median']:8.3f} {s['std']:8.3f} "
              f"{s['iqr']:9.3f} {s['mad']:9.3f}")

    print("\nPercentage change relative to the clean frame:\n")
    print(f"{'added':>6s} {'std':>10s} {'p84-p16':>10s} {'mad_std':>10s}")
    for k in range(1, k_max + 1):
        v = np.concatenate([base, np.full(k, ARTIFACT_FWHM_PIX)])
        s = stats_row(v)
        print(f"{k:6d} {100 * (s['std'] / ref['std'] - 1):+9.1f}% "
              f"{100 * (s['iqr'] / ref['iqr'] - 1):+9.1f}% "
              f"{100 * (s['mad'] / ref['mad'] - 1):+9.1f}%")

    print("""
Read the table this way:

  std      moves immediately and enormously. One artifact is enough. It has no
           resistance at all, which is the practical meaning of a 0% breakdown
           point. An image is judged defective because of a single hot pixel.

  p84-p16  barely reacts at first, then jumps by a large factor once enough
           artifacts accumulate to push the 16th percentile past the boundary
           between the artifacts and the real stars. This step is the problem:
           the statistic is not measuring the scatter, it is reporting which
           sorted value happens to sit at that rank. Below the step it is
           blind; above it, it overreacts.

  mad_std  changes gradually and by a bounded amount throughout. It is neither
           fooled by one bad point nor thrown by several.
""")


def demo_ranks(sizes=(13, 16, 20, 25)) -> None:
    print("=" * 74)
    print("2. WHICH SORTED VALUE ACTUALLY SETS p16 AND p84?")
    print("=" * 74)
    print("numpy interpolates percentiles at position (n-1) * q/100.\n")
    print(f"{'n stars':>8s} {'p16 at index':>14s} {'uses values':>16s} "
          f"{'p84 at index':>14s} {'uses values':>16s}")
    for n in sizes:
        i16 = (n - 1) * 0.16
        i84 = (n - 1) * 0.84
        print(f"{n:8d} {i16:14.2f} {f'#{int(np.floor(i16))+1}, #{int(np.ceil(i16))+1}':>16s} "
              f"{i84:14.2f} {f'#{int(np.floor(i84))+1}, #{int(np.ceil(i84))+1}':>16s}")

    print("""
At these sample sizes p16 is set by the 3rd or 4th smallest measurement and p84
by the 3rd or 4th largest. The statistic therefore depends on the position of a
handful of individual points. Two stray detections landing near that rank can
change it completely, and two landing just outside it change nothing. That is
the instability the injection test makes visible.

mad_std uses the median of the absolute deviations -- a median of a median. No
individual rank position controls it.
""")


def demo_real_frames(d: pd.DataFrame, names: list[str]) -> None:
    print("=" * 74)
    print("3. THREE REAL FRAMES")
    print("=" * 74)
    rows = []
    for nm in names:
        sub = d[d["fname"] == nm]
        if sub.empty:
            print(f"  [skip] {nm} not found in the per-star table.")
            continue
        v = sub["fwhm_avg_pix"].values
        med = np.median(v)
        s = stats_row(v)
        s["frame"] = nm
        s["n_sharp"] = int((v < 0.5 * med).sum())
        rows.append(s)

    if not rows:
        return
    out = pd.DataFrame(rows)[["frame", "n", "n_sharp", "median", "std", "iqr", "mad"]]
    print(out.round(3).to_string(index=False))

    print("""
The defocused frame is the one the flag exists to catch. Note that its median
FWHM is already extreme, so the soft-seeing rule would catch it anyway -- the
scatter rule matters for frames whose median looks acceptable but whose stars
disagree with one another.

The contaminated frame is the trap. Its stars are fine; it simply carries
several one-pixel detections. std and p84-p16 both report a large scatter for
it, which would exclude a perfectly usable image. mad_std does not.
""")


def demo_discrimination(d: pd.DataFrame) -> None:
    print("=" * 74)
    print("4. DISCRIMINATION ACROSS ALL IMAGES")
    print("=" * 74)

    g = d.groupby("fname")["fwhm_avg_pix"]
    per_img = pd.DataFrame({
        "n": g.size(),
        "median": g.median(),
        "std": g.std(ddof=1),
        "iqr": g.apply(iqr_68),
        "mad": g.apply(mad_std),
    })
    med_map = per_img["median"]
    d = d.copy()
    d["img_med"] = d["fname"].map(med_map)
    per_img["n_sharp"] = d.assign(
        bad=d["fwhm_avg_pix"] < 0.5 * d["img_med"]
    ).groupby("fname")["bad"].sum()

    contaminated = per_img[per_img["n_sharp"] > 0]
    clean = per_img[per_img["n_sharp"] == 0]

    print(f"images with at least one spurious sharp detection: {len(contaminated)}")
    print(f"images with none:                                  {len(clean)}\n")
    print("Median value of each statistic, contaminated vs clean images.")
    print("A statistic that is not fooled by contamination should show a")
    print("similar value in both columns.\n")
    print(f"{'statistic':>10s} {'clean':>10s} {'contaminated':>14s} {'inflation':>11s}")
    for col in ["std", "iqr", "mad"]:
        a, b = clean[col].median(), contaminated[col].median()
        print(f"{col:>10s} {a:10.3f} {b:14.3f} {b / a:10.2f}x")

    print("""
std and p84-p16 are inflated on contaminated images even though nothing is
wrong with the seeing in those frames. Using either as the flagging statistic
would exclude good data. mad_std is far less affected, so a threshold set on it
responds mainly to genuine PSF misbehaviour rather than to detector artifacts.
""")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-star", required=True, type=Path)
    ap.add_argument("--clean", default=DEFAULT_CLEAN)
    ap.add_argument("--contaminated", default=DEFAULT_CONTAMINATED)
    ap.add_argument("--defocused", default=DEFAULT_DEFOCUSED)
    args = ap.parse_args()

    d = pd.read_csv(args.per_star)
    d["fname"] = d["file"].apply(lambda p: Path(str(p).replace("\\", "/")).name)

    base = d[d["fname"] == args.clean]["fwhm_avg_pix"].values
    if base.size == 0:
        raise SystemExit(f"Baseline frame {args.clean} not found. Pass --clean "
                         "with a frame name present in the per-star table.")

    demo_injection(base, args.clean)
    demo_ranks()
    demo_real_frames(d, [args.clean, args.contaminated, args.defocused])
    demo_discrimination(d)

    print("=" * 74)
    print("CONCLUSION")
    print("=" * 74)
    print("""At 13-25 stars per image, the standard deviation has no resistance to a
single bad fit, and a percentile range is controlled by the rank position of
three or four individual points. Both are inflated by cosmic rays and hot
pixels, which are common in this data set and are not a defect of the image.
mad_std retains half the sample as its breakdown point and is scaled to be
read on the same units as a standard deviation, so it responds to genuine PSF
misbehaviour rather than to isolated detector artifacts.
""")


if __name__ == "__main__":
    main()