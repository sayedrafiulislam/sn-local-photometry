import pandas as pd, numpy as np, os

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

cog = pd.read_csv(os.path.join(BASE, "curve_of_growth_ann20-30.csv"))
dup = cog[(cog.telescope == "dup") & cog.annulus_ok & cog.aperture_ok].copy()
dup["area"] = np.pi * dup.radius_pix**2
dup["raw"]  = dup.flux_bkgsub + dup.bkg_per_pixel * dup.area
dup["bkg_frac"] = (dup.bkg_per_pixel * dup.area) / dup.raw.replace(0, np.nan)

# --- is the background normalisation campaign-dependent? -------------------
import re
def year(n):
    m = re.search(r"(\d{4}|\d{2})", str(n)); v = int(m.group(1)) if m else np.nan
    return v if v > 1000 else 2000 + v
per = dup.drop_duplicates(subset=["object", "filter"]).copy()
per["epoch"] = np.where(per.object.map(year) <= 2009, "CSP-I", "CSP-II")
print("median bkg_per_pixel by epoch and filter:")
print(per.pivot_table(index="epoch", columns="filter",
                      values="bkg_per_pixel", aggfunc="median").round(3))
print("\nmedian raw counts at 5 kpc by epoch and filter:")
r5 = dup[np.isclose(dup.radius_kpc, 5.0)]
r5 = r5.assign(epoch=np.where(r5.object.map(year) <= 2009, "CSP-I", "CSP-II"))
print(r5.pivot_table(index="epoch", columns="filter",
                     values="raw", aggfunc="median").round(0))

# --- scale-free background fraction, per filter ---------------------------
print("\n--- background fraction at 5 kpc, by filter ---")
for f in ["B", "V"]:
    s = r5[r5["filter"] == f].bkg_frac.dropna()
    print(f"  {f}: median {s.median():.3f}  90th {s.quantile(.9):.3f}  "
          f"max {s.max():.3f}  (n={len(s)})")

# --- severe non-monotonicity only ----------------------------------------
print("\n--- raw flux decreasing by more than 50% ---")
bad = []
for (o, f), g in dup.groupby(["object", "filter"]):
    g = g.sort_values("radius_kpc"); raw = g.raw.to_numpy()
    d = np.diff(raw) / np.abs(raw[:-1])
    if (d < -0.5).any():
        bad.append({"object": o, "filter": f, "worst": float(d.min()),
                    "bkg_frac_5kpc": float(
                        r5[(r5.object == o) & (r5["filter"] == f)]
                        .bkg_frac.iloc[0]) if len(
                        r5[(r5.object == o) & (r5["filter"] == f)]) else np.nan})
b = pd.DataFrame(bad)
print(f"{len(b)} of {dup.groupby(['object','filter']).ngroups} curves")
if len(b):
    print(b.sort_values("worst").to_string(index=False))

cat = set(pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc.csv")).object)
hit = sorted(set(b.object) & cat) if len(b) else []
print(f"\nIN THE CATALOGUE and severely non-monotonic: {len(hit)}")
print(hit)