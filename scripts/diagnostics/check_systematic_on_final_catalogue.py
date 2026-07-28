import pandas as pd, numpy as np, os

APER = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

def col(tag):
    df = pd.read_csv(os.path.join(APER, f"curve_of_growth_{tag}.csv"))
    df = df[(df.radius_kpc == 5.0) & df.annulus_ok & df.aperture_ok
            & (df.telescope == "dup")]
    p = df.pivot_table(index="object", columns="filter", values="flux_bkgsub")
    p = p[(p.B > 0) & (p.V > 0)]
    return pd.DataFrame({"c": -2.5 * np.log10(p.B / p.V), "fB": p.B})

a, b = col("ann10-15"), col("ann20-30")
j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
j["colour_shift_mmag"] = (j.c_a - j.c_b) * 1000

# the published catalogue -- fall back through the likely filenames
cat = None
for fn in ["calibrated_color_5kpc_dered.csv",
           "calibrated_color_5kpc_flagged.csv",
           "calibrated_color_5kpc.csv"]:
    p = os.path.join(CAL, fn)
    if os.path.exists(p):
        cat = pd.read_csv(p); print(f"catalogue file: {fn}  ({len(cat)} rows)"); break
if cat is None:
    raise SystemExit("No calibrated catalogue found -- check the CAL path.")

if "flag_low_flux" in cat.columns:
    kept = cat[~cat.flag_low_flux.astype(bool)]
    print(f"after removing flag_low_flux: {len(kept)} objects")
else:
    kept = cat
    print("no flag_low_flux column -- using all rows")

inside  = j[j.index.isin(kept.object)]
outside = j[~j.index.isin(kept.object)]

print(f"\nof {len(j)} objects measured at 5 kpc, "
      f"{len(inside)} are in the final catalogue, {len(outside)} are not\n")

for label, s in [("IN the catalogue", inside), ("cut from it", outside)]:
    if len(s):
        v = s["colour_shift_mmag"]
        print(f"{label:>18}: n={len(v):3d}  median {v.median():6.1f}  "
              f"mean {v.mean():6.1f}  90th pct {v.quantile(0.9):6.1f} mmag")

if len(inside):
    v = inside["colour_shift_mmag"].to_numpy()
    rng = np.random.default_rng(42)
    bs = np.array([np.median(rng.choice(v, len(v), replace=True)) for _ in range(5000)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"\nannulus systematic ON THE PUBLISHED CATALOGUE:")
    print(f"  median {np.median(v):.1f} mmag   95% CI [{lo:.1f}, {hi:.1f}]")
    print(f"  -> this is the number for the error budget, not the 8.4 mmag "
          f"from all 202 objects.")