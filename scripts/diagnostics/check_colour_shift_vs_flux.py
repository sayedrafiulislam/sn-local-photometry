import pandas as pd, numpy as np

d = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

def col(tag):
    df = pd.read_csv(d + rf"\curve_of_growth_{tag}.csv")
    df = df[(df.radius_kpc == 5.0) & df.annulus_ok & df.aperture_ok
            & (df.telescope == "dup")]
    p = df.pivot_table(index="object", columns="filter", values="flux_bkgsub")
    p = p[(p.B > 0) & (p.V > 0)]
    return pd.DataFrame({"c": -2.5 * np.log10(p.B / p.V), "fB": p.B})

a, b = col("ann10-15"), col("ann20-30")
j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")

# renamed from "shift" -- that name collides with the pandas DataFrame.shift()
# method, so j.groupby(...).shift returns the METHOD, not the column, and
# .agg() then fails with "'function' object has no attribute 'agg'".
j["colour_shift_mmag"] = (j.c_a - j.c_b) * 1000

q = pd.qcut(j.fB_b, 4, labels=["faintest", "Q2", "Q3", "brightest"])

print(j.groupby(q, observed=True)["colour_shift_mmag"]
      .agg(["count", "median", "mean"]).round(1))
print("\nSpearman shift vs flux:",
      j["colour_shift_mmag"].corr(j.fB_b, method="spearman").round(3))