import pandas as pd, numpy as np, os, re

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

cog = pd.read_csv(os.path.join(BASE, "curve_of_growth_ann20-30.csv"))
dup = cog[(cog.telescope == "dup") & cog.annulus_ok & cog.aperture_ok].copy()
dup["area"] = np.pi * dup.radius_pix**2
dup["raw"]  = dup.flux_bkgsub + dup.bkg_per_pixel * dup.area

def yr(n):
    m = re.search(r"(\d{4}|\d{2})", str(n)); v = int(m.group(1)) if m else np.nan
    return v if v > 1000 else 2000 + v

# does redshift explain the CSP-I / CSP-II count difference?
per = dup.drop_duplicates(subset=["object"]).copy()
per["epoch"] = np.where(per.object.map(yr) <= 2009, "CSP-I", "CSP-II")
print("median redshift by epoch:")
print(per.groupby("epoch").z.agg(["count", "median"]).round(4).to_string())
zi, zii = per[per.epoch=="CSP-I"].z.median(), per[per.epoch=="CSP-II"].z.median()
print(f"naive flux ratio from distance alone, (z_II/z_I)^2 = {(zii/zi)**2:.1f}x")
print("  (compare with the ~11x observed; the remainder is exposure depth)")

# scale-free drop: normalise by the curve's own peak, not the previous point
rows = []
for (o, f), g in dup.groupby(["object", "filter"]):
    g = g.sort_values("radius_kpc"); raw = g.raw.to_numpy()
    scale = np.nanmax(np.abs(raw))
    if not np.isfinite(scale) or scale == 0:
        continue
    rows.append({"object": o, "filter": f,
                 "drop_vs_peak": float(np.min(np.diff(raw)) / scale),
                 "peak_raw": float(scale),
                 "min_raw": float(np.nanmin(raw))})
d = pd.DataFrame(rows)

print(f"\ndrop as a fraction of each curve's own peak:")
print(f"  median {d.drop_vs_peak.median():+.4f}   "
      f"5th pct {d.drop_vs_peak.quantile(.05):+.4f}   "
      f"min {d.drop_vs_peak.min():+.4f}")

sev = d[d.drop_vs_peak < -0.10].sort_values("drop_vs_peak")
print(f"\n--- drops exceeding 10% of the curve's own peak: {len(sev)} of {len(d)} ---")
print(sev.to_string(index=False) if len(sev) else "none")

cat = set(pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc.csv")).object)
hit = sorted(set(sev.object) & cat) if len(sev) else []
print(f"\nIN THE CATALOGUE: {len(hit)} -> {hit}")

print("\n--- CSP13aam, the one clear case ---")
c = dup[(dup.object == "CSP13aam")].sort_values(["filter", "radius_kpc"])
print(c[["filter", "radius_kpc", "radius_pix", "flux_bkgsub", "raw",
         "bkg_per_pixel"]].round(1).to_string(index=False))