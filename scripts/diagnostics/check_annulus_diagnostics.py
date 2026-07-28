import pandas as pd, numpy as np
d = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
old  = pd.read_csv(d + r"\curve_of_growth.csv")
a15  = pd.read_csv(d + r"\curve_of_growth_ann10-15.csv")
a30  = pd.read_csv(d + r"\curve_of_growth_ann20-30.csv")
key  = ["object","telescope","filter","radius_kpc"]

# Q1 -- does ann10-15 reproduce script 10?
m = old.merge(a15, on=key, suffixes=("_old","_new"))
rel = ((m.flux_bkgsub_new - m.flux_bkgsub_old).abs()
       / m.flux_bkgsub_old.abs().replace(0, np.nan))
print("Q1 matched rows:", len(m), "of", len(old))
print("   rel diff  median %.2e  max %.2e" % (rel.median(), rel.max()))
print("   rows >1%% different:", int((rel > 0.01).sum()))

# Q2 -- did the negatives go away, and are NaNs present?
for name, df in [("script10", old), ("ann10-15", a15), ("ann20-30", a30)]:
    neg = df.flux_bkgsub < 0
    print(f"Q2 {name:9s} neg {int(neg.sum()):5d}  nan {int(df.flux_bkgsub.isna().sum()):4d}"
          f"  neg median radius {df.loc[neg,'radius_kpc'].median()}")
print("   ann20-30 neg among annulus_ok:", int(((a30.flux_bkgsub<0) & a30.annulus_ok).sum()))

# Q3 -- F4: is the guard failure redshift-dependent?
per = lambda df: df.drop_duplicates(subset=["object","telescope","filter"])
for name, df in [("ann10-15", a15), ("ann20-30", a30)]:
    p = per(df)
    print(f"Q3 {name}: ok {int(p.annulus_ok.sum())}/{len(p)}  "
          f"median z ok={p.loc[p.annulus_ok,'z'].median():.4f} "
          f"fail={p.loc[~p.annulus_ok,'z'].median():.4f}")
print("   Swope share of failures (ann20-30):",
      per(a30).query("not annulus_ok").telescope.value_counts().to_dict())