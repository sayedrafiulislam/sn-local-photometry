"""
15_offset_colour_test.py

Tests whether host-galaxy nuclear light measurably contaminates the local
aperture colour, using each galaxy as its own control.

Background
----------
12_verify_sn_positions.py established that 58 per cent of supernovae in this
sample sit within 5 kpc of their host's centre, so for those objects the
nucleus falls inside a 5 kpc aperture centred on the explosion site.

A first test compared the calibrated colour against the offset ACROSS objects
and found nothing: Spearman rho = -0.031 with n = 91, and the binned medians
were non-monotonic (0.789, 0.638, 0.814, 0.600 mag). Two explanations fit that
result equally well:

    (a) nuclear light contributes little, or
    (b) galaxy-to-galaxy variation in mass, morphology and dust is so large
        that it buries the effect.

A cross-object comparison cannot separate these. This script uses a
within-object design instead.

The design
----------
local_color_vs_radius.csv contains B-V measured at 19 aperture radii for every
object -- the same galaxy sampled at many distances from the explosion site.
Galaxy-to-galaxy differences cancel exactly, because each object is compared
only against itself.

The prediction is specific:

    An aperture of radius R centred on a supernova that sits at projected
    distance D from the nucleus contains the nucleus only when R > D.

So:
    - Objects with SMALL D (nucleus always enclosed) should show a relatively
      flat colour profile with radius.
    - Objects with LARGE D should show the colour REDDEN as the aperture grows
      past R = D, because the reddest part of the galaxy enters the aperture
      at that point.

If reddening appears at approximately each object's own D, nuclear
contamination is real and has been measured. If the profiles are
indistinguishable regardless of D, contamination is minor.

Why instrumental colours are valid here
---------------------------------------
This script uses `instrumental_B_minus_V`, which carries no photometric zero
point. That is not a problem for this test and is arguably preferable: the zero
point is a single additive constant per object, so it cancels exactly in any
within-object comparison of one radius against another. Using uncalibrated
colours also keeps this test independent of the calibration step, so a fault
there cannot manufacture a result here.

Usage
-----
    python 15_offset_colour_test.py ^
        --colors results\\phase4_aperture\\local_color_vs_radius_ann20-30.csv ^
        --positions results\\sn_position_verification.csv ^
        --out-prefix results\\phase4_aperture\\nuclear_contamination_ann20-30
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# Offsets beyond this are almost certainly not the true host: at these
# separations the "nearest catalogued galaxy" is an unrelated background
# object. See the caveats in C10.
MAX_PLAUSIBLE_OFFSET_KPC = 45.0

# An offset of exactly zero more likely indicates a NED galaxy record created
# from the SN position than a supernova sitting precisely on a nucleus.
MIN_MEANINGFUL_OFFSET_KPC = 0.05

# Minimum number of finite colour points for an object's profile to be usable.
MIN_RADII_PER_OBJECT = 10


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Rank correlation, implemented locally to avoid a scipy dependency."""
    if len(x) < 3:
        return np.nan
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    if np.std(rx) == 0 or np.std(ry) == 0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def load(colors_csv: Path, positions_csv: Path) -> pd.DataFrame:
    col = pd.read_csv(colors_csv)
    pos = pd.read_csv(positions_csv)

    need = {"object", "radius_kpc", "instrumental_B_minus_V"}
    missing = need - set(col.columns)
    if missing:
        raise SystemExit(f"{colors_csv} is missing columns: {sorted(missing)}")

    col = col[col["instrumental_B_minus_V"].notna()].copy()

    pos = pos[["object", "offset_kpc"]].copy()
    pos = pos[pos["offset_kpc"].notna()]
    n0 = len(pos)
    pos = pos[(pos["offset_kpc"] > MIN_MEANINGFUL_OFFSET_KPC) &
              (pos["offset_kpc"] < MAX_PLAUSIBLE_OFFSET_KPC)]
    print(f"Offsets: {n0} measured, {len(pos)} retained "
          f"({MIN_MEANINGFUL_OFFSET_KPC}-{MAX_PLAUSIBLE_OFFSET_KPC} kpc).")

    df = col.merge(pos, on="object", how="inner")

    counts = df.groupby("object")["radius_kpc"].size()
    keep = counts[counts >= MIN_RADII_PER_OBJECT].index
    df = df[df["object"].isin(keep)].copy()

    print(f"Objects with both a usable colour profile and an offset: "
          f"{df['object'].nunique()}")
    return df


def per_object_gradients(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per object: how its colour changes with aperture radius, and
    whether the change appears at the radius where the nucleus enters.
    """
    rows = []
    for obj, g in df.groupby("object"):
        g = g.sort_values("radius_kpc")
        r = g["radius_kpc"].to_numpy()
        c = g["instrumental_B_minus_V"].to_numpy()
        d = float(g["offset_kpc"].iloc[0])

        # Overall trend of colour with radius.
        rho = spearman(r, c)
        slope = float(np.polyfit(r, c, 1)[0]) if len(r) >= 3 else np.nan

        # The direct test: colour inside vs outside the radius at which the
        # nucleus first enters the aperture. Only defined when that radius
        # falls inside the sampled grid with points on both sides.
        inside = c[r < d]
        outside = c[r >= d]
        if len(inside) >= 3 and len(outside) >= 3:
            step = float(np.median(outside) - np.median(inside))
        else:
            step = np.nan

        rows.append({
            "object": obj,
            "offset_kpc": d,
            "n_radii": len(r),
            "rho_colour_vs_radius": rho,
            "slope_mag_per_kpc": slope,
            "colour_range": float(np.nanmax(c) - np.nanmin(c)),
            "step_at_nucleus_entry": step,
        })
    return pd.DataFrame(rows)


def report(grad: pd.DataFrame, df: pd.DataFrame) -> None:
    print("\n" + "=" * 74)
    print("TEST 1 -- does colour change with aperture radius at all?")
    print("=" * 74)
    r = grad["rho_colour_vs_radius"].dropna()
    n_red = int((r < 0).sum())   # rho < 0 means colour rises as radius falls
    print(f"  objects with a usable profile : {len(r)}")
    print(f"  median rho (colour vs radius) : {r.median():+.3f}")
    print(f"  reddening inward (rho < 0)    : {n_red} ({100 * n_red / len(r):.0f}%)")
    print("""
  If apertures were dominated by a red nucleus at small radii, most objects
  would redden inward and rho would be consistently negative. A median near
  zero with a roughly even split means no systematic radial colour trend
  across the sample.""")

    print("\n" + "=" * 74)
    print("TEST 2 -- is the trend different for objects whose nucleus is")
    print("          enclosed at all radii, versus those where it is not?")
    print("=" * 74)
    bins = [0, 2, 5, 10, MAX_PLAUSIBLE_OFFSET_KPC]
    grad["offset_bin"] = pd.cut(grad["offset_kpc"], bins)
    t = grad.groupby("offset_bin", observed=True).agg(
        n=("object", "count"),
        median_rho=("rho_colour_vs_radius", "median"),
        median_slope=("slope_mag_per_kpc", "median"),
        median_range=("colour_range", "median"),
    ).round(4)
    print(t.to_string())
    print("""
  The prediction: objects with a LARGE offset should show a stronger positive
  slope, because for them the nucleus only enters the aperture at large radii.
  Objects with a small offset enclose the nucleus throughout and should be
  flatter. If median_slope does not increase with offset, that prediction
  fails and nuclear contamination is not driving the colour profiles.""")

    print("\n" + "=" * 74)
    print("TEST 3 -- direct step test at the nucleus-entry radius")
    print("=" * 74)
    s = grad["step_at_nucleus_entry"].dropna()
    if len(s) >= 5:
        # Bootstrap the median rather than assume a distribution.
        rng = np.random.default_rng(42)
        boot = [np.median(rng.choice(s.values, len(s), replace=True))
                for _ in range(5000)]
        lo, hi = np.percentile(boot, [2.5, 97.5])
        print(f"  objects where the entry radius falls inside the grid: {len(s)}")
        print(f"  median colour step (outside - inside) : {s.median():+.4f} mag")
        print(f"  95% CI from bootstrap                 : [{lo:+.4f}, {hi:+.4f}]")
        if lo <= 0 <= hi:
            print("\n  The interval spans zero: no detectable step. Nuclear light")
            print("  entering the aperture does not measurably change the colour.")
        else:
            print("\n  The interval excludes zero: a real step is detected.")
            print("  Nuclear contamination is measurable at this sample size.")
    else:
        print(f"  Only {len(s)} objects have the entry radius inside the sampled")
        print("  grid, which is too few to test. This happens when most offsets")
        print("  fall outside the 1-10 kpc aperture range.")

    print("\n" + "=" * 74)
    print("For scale: how large is the effect we could have detected?")
    print("=" * 74)
    print(f"  typical within-object colour range across radii : "
          f"{grad['colour_range'].median():.3f} mag")
    print(f"  object-to-object scatter in colour (MAD)        : "
          f"{1.4826 * np.median(np.abs(df.groupby('object')['instrumental_B_minus_V'].median() - df.groupby('object')['instrumental_B_minus_V'].median().median())):.3f} mag")


def make_plot(df: pd.DataFrame, grad: pd.DataFrame, out_png: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\nmatplotlib not available; skipping the figure.")
        return

    # Colour relative to each object's own value at the smallest radius, so
    # every profile starts at zero and the shapes can be compared directly.
    d = df.sort_values(["object", "radius_kpc"]).copy()
    first = d.groupby("object")["instrumental_B_minus_V"].transform("first")
    d["delta"] = d["instrumental_B_minus_V"] - first
    d = d.merge(grad[["object", "offset_kpc"]].drop_duplicates(),
                on="object", how="left", suffixes=("", "_g"))

    bins = [0, 2, 5, 10, MAX_PLAUSIBLE_OFFSET_KPC]
    d["offset_bin"] = pd.cut(d["offset_kpc"], bins)

    fig, ax = plt.subplots(figsize=(8, 5))
    for label, g in d.groupby("offset_bin", observed=True):
        prof = g.groupby("radius_kpc")["delta"].median()
        ax.plot(prof.index, prof.values, marker="o", ms=3,
                label=f"SN offset {label} kpc  (n={g['object'].nunique()})")

    ax.axhline(0, color="0.6", lw=0.8, ls="--")
    ax.set_xlabel("Aperture radius (kpc)")
    ax.set_ylabel(r"$\Delta$(B$-$V) relative to smallest aperture (mag)")
    ax.set_title("Colour profile by supernova galactocentric offset")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    print(f"\nWrote {out_png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--colors", required=True, type=Path)
    ap.add_argument("--positions", required=True, type=Path)
    ap.add_argument("--out-prefix", required=True, type=Path)
    args = ap.parse_args()

    df = load(args.colors, args.positions)
    if df.empty:
        raise SystemExit("No objects survive the merge. Check that the object "
                         "names match between the two files.")

    grad = per_object_gradients(df)
    report(grad, df)

    out_csv = Path(str(args.out_prefix) + "_per_object.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    grad.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}")

    make_plot(df, grad, Path(str(args.out_prefix) + "_profiles.png"))


if __name__ == "__main__":
    main()