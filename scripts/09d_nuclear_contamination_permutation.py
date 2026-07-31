"""
09d_nuclear_contamination_permutation.py

Control test for the step detected by 09c_nuclear_contamination_test.py.

The result being controlled
---------------------------
09c compared, for each object, the median colour at aperture radii below that
object's own projected galactocentric offset D against the median at radii
above it. D is the radius at which the host nucleus first enters the aperture.
Across 98 objects the median step was

    +0.0197 mag,  95 per cent bootstrap CI [+0.0098, +0.0337]

which excludes zero.

Why that is not yet sufficient
------------------------------
The bootstrap answers "how uncertain is this median?" It does not answer "could
this have arisen without any dependence on D?"

Each object's profile is split at a different radius. If colour profiles share
a common shape -- for instance a general tendency to redden outward for
unrelated reasons -- then splitting a set of similarly-shaped curves at
scattered points can produce a non-zero median step with no genuine link to D
at all. The bootstrap cannot detect this, because it resamples objects while
keeping each object paired with its own offset.

The control
-----------
Break the pairing. Keep every colour profile exactly as measured, but shuffle
the offsets randomly among objects, then recompute the step statistic. Repeat
several thousand times to build the distribution of steps obtainable by chance
pairing.

    If the observed step lies far outside that distribution, the effect is
    genuinely tied to each object's own offset.

    If shuffled data reproduces it, the step is an artifact of profile shape
    and the detection must be withdrawn.

Three tests are run:

  TEST A  Permutation null for the median step. The primary control.

  TEST B  Permutation null for the rank correlation between offset and the
          slope of colour with radius. 09c's Test 2 predicted that objects with
          larger offsets should show more positive slopes, since for them the
          nucleus enters only at large radii. This checks that trend against
          chance pairing.

  TEST C  Fixed-split control. Split every object at the same radius (the
          sample median offset) instead of at its own. Any step surviving this
          comes from common profile shape, not from D. A large step here would
          undermine the result even if Test A passes.

Usage
-----
    python 09d_nuclear_contamination_permutation.py ^
        --colors results\\phase4_aperture\\local_color_vs_radius.csv ^
        --positions results\\sn_position_verification.csv ^
        --out-prefix results\\phase4_aperture\\nuclear_permutation
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# Kept identical to 09c so the observed statistic is reproduced exactly.
MAX_PLAUSIBLE_OFFSET_KPC = 45.0
MIN_MEANINGFUL_OFFSET_KPC = 0.05
MIN_RADII_PER_OBJECT = 10
MIN_POINTS_EACH_SIDE = 3

N_PERMUTATIONS = 5000
SEED = 20260727


def spearman(x, y) -> float:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return np.nan
    rx = pd.Series(x[ok]).rank().to_numpy()
    ry = pd.Series(y[ok]).rank().to_numpy()
    if np.std(rx) == 0 or np.std(ry) == 0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def load_profiles(colors_csv: Path, positions_csv: Path):
    """
    Returns:
        profiles : dict object -> (radii array, colour array), sorted by radius
        offsets  : np.array of offsets, aligned to the object order
        objects  : list of object names
    """
    col = pd.read_csv(colors_csv)
    col = col[col["instrumental_B_minus_V"].notna()].copy()

    pos = pd.read_csv(positions_csv)[["object", "offset_kpc"]]
    pos = pos[pos["offset_kpc"].notna()]
    pos = pos[(pos["offset_kpc"] > MIN_MEANINGFUL_OFFSET_KPC) &
              (pos["offset_kpc"] < MAX_PLAUSIBLE_OFFSET_KPC)]

    df = col.merge(pos, on="object", how="inner")
    counts = df.groupby("object")["radius_kpc"].size()
    df = df[df["object"].isin(counts[counts >= MIN_RADII_PER_OBJECT].index)]

    profiles, offsets, objects = {}, [], []
    for obj, g in df.groupby("object"):
        g = g.sort_values("radius_kpc")
        profiles[obj] = (g["radius_kpc"].to_numpy(),
                         g["instrumental_B_minus_V"].to_numpy())
        offsets.append(float(g["offset_kpc"].iloc[0]))
        objects.append(obj)

    print(f"Objects with a usable profile and an offset: {len(objects)}")
    return profiles, np.array(offsets), objects


def step_statistic(profiles, objects, offsets):
    """
    Median colour step across objects, splitting each profile at the supplied
    offset. Returns (median step, number of qualifying objects).

    An object qualifies only when its split radius leaves at least
    MIN_POINTS_EACH_SIDE measurements on both sides, which is why the
    qualifying count varies between permutations. That variation is part of
    the null and is reported rather than suppressed.
    """
    steps = []
    for obj, d in zip(objects, offsets):
        r, c = profiles[obj]
        inside = c[r < d]
        outside = c[r >= d]
        if len(inside) >= MIN_POINTS_EACH_SIDE and len(outside) >= MIN_POINTS_EACH_SIDE:
            steps.append(np.median(outside) - np.median(inside))
    if not steps:
        return np.nan, 0
    return float(np.median(steps)), len(steps)


def slope_offset_correlation(profiles, objects, offsets) -> float:
    """Rank correlation between an object's offset and its colour-radius slope."""
    slopes = []
    for obj in objects:
        r, c = profiles[obj]
        slopes.append(np.polyfit(r, c, 1)[0] if len(r) >= 3 else np.nan)
    return spearman(offsets, np.array(slopes))


def summarise_null(name, observed, null, out_lines):
    null = np.asarray([v for v in null if np.isfinite(v)])
    if null.size == 0 or not np.isfinite(observed):
        print(f"  {name}: could not be evaluated.")
        return
    # Two-sided empirical p-value, with the +1 correction so that p is never
    # reported as exactly zero from a finite number of permutations.
    p = (np.sum(np.abs(null - np.mean(null)) >= abs(observed - np.mean(null))) + 1) / (null.size + 1)
    lo, hi = np.percentile(null, [2.5, 97.5])
    z = (observed - np.mean(null)) / np.std(null) if np.std(null) > 0 else np.nan
    print(f"  observed          : {observed:+.4f}")
    print(f"  null mean         : {np.mean(null):+.4f}")
    print(f"  null 95% range    : [{lo:+.4f}, {hi:+.4f}]")
    print(f"  z-score           : {z:+.2f}")
    print(f"  two-sided p-value : {p:.4f}  ({null.size} permutations)")
    out_lines.append({"test": name, "observed": observed,
                      "null_mean": float(np.mean(null)),
                      "null_lo95": float(lo), "null_hi95": float(hi),
                      "z": float(z), "p_value": float(p),
                      "n_permutations": int(null.size)})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--colors", required=True, type=Path)
    ap.add_argument("--positions", required=True, type=Path)
    ap.add_argument("--out-prefix", required=True, type=Path)
    ap.add_argument("--n-perm", type=int, default=N_PERMUTATIONS)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    profiles, offsets, objects = load_profiles(args.colors, args.positions)
    if len(objects) < 20:
        raise SystemExit("Too few objects to permute meaningfully.")

    results = []

    # ---------------- TEST A ------------------------------------------------
    obs_step, n_qual = step_statistic(profiles, objects, offsets)
    print("\n" + "=" * 74)
    print("TEST A -- permutation null for the median colour step")
    print("=" * 74)
    print(f"  qualifying objects (observed pairing): {n_qual}")

    null_steps, null_counts = [], []
    for _ in range(args.n_perm):
        s, n = step_statistic(profiles, objects, rng.permutation(offsets))
        null_steps.append(s)
        null_counts.append(n)
    print(f"  qualifying objects under permutation : median {int(np.median(null_counts))}")
    summarise_null("median_step", obs_step, null_steps, results)

    # ---------------- TEST B ------------------------------------------------
    print("\n" + "=" * 74)
    print("TEST B -- permutation null for the offset/slope correlation")
    print("=" * 74)
    obs_rho = slope_offset_correlation(profiles, objects, offsets)
    null_rho = [slope_offset_correlation(profiles, objects, rng.permutation(offsets))
                for _ in range(min(args.n_perm, 2000))]
    summarise_null("offset_slope_rho", obs_rho, null_rho, results)

    # ---------------- TEST C ------------------------------------------------
    print("\n" + "=" * 74)
    print("TEST C -- fixed-split control (every object cut at the same radius)")
    print("=" * 74)
    median_offset = float(np.median(offsets))
    fixed = np.full(len(objects), median_offset)
    fixed_step, fixed_n = step_statistic(profiles, objects, fixed)
    print(f"  split radius applied to all objects : {median_offset:.2f} kpc")
    print(f"  qualifying objects                  : {fixed_n}")
    print(f"  median step with a common split     : {fixed_step:+.4f} mag")
    print(f"  median step with each object's own D: {obs_step:+.4f} mag")
    if np.isfinite(fixed_step) and abs(fixed_step) > 0.5 * abs(obs_step):
        print("\n  WARNING: a common split reproduces much of the step. That points")
        print("  to a shared profile shape rather than a dependence on D.")
    else:
        print("\n  A common split does not reproduce the step, so the effect does")
        print("  not arise from a shape shared by all profiles.")
    results.append({"test": "fixed_split_step", "observed": fixed_step,
                    "null_mean": np.nan, "null_lo95": np.nan, "null_hi95": np.nan,
                    "z": np.nan, "p_value": np.nan, "n_permutations": 0})

    # ---------------- verdict ----------------------------------------------
    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    pa = next((r["p_value"] for r in results if r["test"] == "median_step"), np.nan)
    if np.isfinite(pa) and pa < 0.05:
        print(f"  The observed step of {obs_step:+.4f} mag cannot be reproduced by")
        print(f"  randomly pairing profiles with offsets (p = {pa:.4f}). The effect")
        print("  is tied to each object's own galactocentric offset, which is the")
        print("  signature expected if nuclear light entering the aperture reddens")
        print("  the measured colour.")
    else:
        print(f"  Chance pairing reproduces the observed step (p = {pa:.4f}). The")
        print("  detection is not supported and should be withdrawn.")

    out_csv = Path(str(args.out_prefix) + "_results.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}")

    # ---------------- figure ------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ax.hist([v for v in null_steps if np.isfinite(v)], bins=60,
                color="0.75", edgecolor="none",
                label=f"shuffled offsets (n={args.n_perm})")
        ax.axvline(obs_step, color="crimson", lw=2,
                   label=f"observed {obs_step:+.4f} mag")
        ax.axvline(0, color="0.4", lw=0.8, ls="--")
        ax.set_xlabel("Median colour step at the nucleus-entry radius (mag)")
        ax.set_ylabel("Permutations")
        ax.set_title("Is the step tied to each object's own offset?")
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        png = Path(str(args.out_prefix) + "_null.png")
        fig.savefig(png, dpi=150)
        print(f"Wrote {png}")
    except ImportError:
        print("matplotlib not available; skipping the figure.")


if __name__ == "__main__":
    main()