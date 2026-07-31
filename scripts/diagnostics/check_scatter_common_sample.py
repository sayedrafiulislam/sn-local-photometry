import pandas as pd, numpy as np, os
from astropy.stats import mad_std

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
df = pd.read_csv(os.path.join(BASE, "local_color_vs_radius_ann20-30.csv"))
wide = df.pivot_table(index="object", columns="radius_kpc",
                      values="instrumental_B_minus_V")
radii = sorted(wide.columns)

full = wide[radii]
common = full.dropna()
print(f"all objects        : {len(full)}")
print(f"valid at EVERY radius: {len(common)}  "
      f"({100*len(common)/len(full):.0f}%)\n")

print(f"{'r(kpc)':>7}{'n_all':>7}{'sc_all':>9}{'sc_common':>11}{'diff':>9}")
rows = []
for r in radii:
    a = full[r].dropna()
    c = common[r]
    sa, sc = mad_std(a), mad_std(c)
    rows.append((r, len(a), sa, sc))
    print(f"{r:>7.1f}{len(a):>7d}{sa:>9.4f}{sc:>11.4f}{sc-sa:>+9.4f}")

sa = np.array([x[2] for x in rows]); sc = np.array([x[3] for x in rows])
print(f"\nspread, all objects   : {sa.max()-sa.min():.4f} mag")
print(f"spread, common sample : {sc.max()-sc.min():.4f} mag")
print(f"\nlowest-scatter radius, all    : {radii[int(np.argmin(sa))]:.1f} kpc")
print(f"lowest-scatter radius, common : {radii[int(np.argmin(sc))]:.1f} kpc")

# do the objects missing at 1 kpc have higher scatter where they DO appear?
missing = set(full.index) - set(full[1.0].dropna().index)
print(f"\n{len(missing)} objects have no colour at 1.0 kpc")
if missing:
    at6 = wide[6.5]
    print(f"  their scatter at 6.5 kpc  : "
          f"{mad_std(at6.loc[list(missing)].dropna()):.4f} mag")
    print(f"  everyone else at 6.5 kpc  : "
          f"{mad_std(at6.drop(index=list(missing)).dropna()):.4f} mag")