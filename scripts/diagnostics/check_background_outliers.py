import pandas as pd, numpy as np, os

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

cog = pd.read_csv(os.path.join(BASE, "curve_of_growth_ann20-30.csv"))
dup = cog[(cog.telescope == "dup") & cog.annulus_ok & cog.aperture_ok]

per = dup.drop_duplicates(subset=["object", "filter"])[
    ["object", "filter", "z", "bkg_per_pixel", "annulus_outer_pix"]]
med = per.bkg_per_pixel.median()
mad = 1.4826 * np.median(np.abs(per.bkg_per_pixel - med))
per["n_mad"] = (per.bkg_per_pixel - med) / mad

print(f"background per pixel: median {med:.3f}, MAD-sigma {mad:.3f}")
print(f"frames beyond +5 MAD : {int((per.n_mad > 5).sum())} of {len(per)}\n")

worst = per[per.n_mad > 5].sort_values("n_mad", ascending=False)
print(worst.head(25).to_string(index=False))

# non-monotonic raw flux = something bright entering the aperture
print("\n--- non-monotonic curves (raw flux must only increase) ---")
bad = []
for (o, f), g in dup.groupby(["object", "filter"]):
    g = g.sort_values("radius_kpc")
    raw = g.flux_bkgsub + g.bkg_per_pixel * np.pi * g.radius_pix**2
    d = np.diff(raw.to_numpy())
    if (d < -0.02 * np.abs(raw.to_numpy()[:-1])).any():
        bad.append({"object": o, "filter": f,
                    "worst_drop_frac": float(np.min(d / np.abs(raw.to_numpy()[:-1]))),
                    "bkg_n_mad": float(per[(per.object == o)
                                           & (per['filter'] == f)].n_mad.iloc[0])})
b = pd.DataFrame(bad)
print(f"{len(b)} of {dup.groupby(['object','filter']).ngroups} curves affected")
if len(b):
    print(b.sort_values("worst_drop_frac").head(20).to_string(index=False))

cat = pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc.csv"))
flagged = set(worst.object) | set(b.object if len(b) else [])
print(f"\nof {len(cat)} catalogue objects, "
      f"{len(set(cat.object) & flagged)} show a contamination signature")
print(sorted(set(cat.object) & flagged))