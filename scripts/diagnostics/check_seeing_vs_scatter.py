import pandas as pd, numpy as np, os
from astropy.stats import mad_std

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
cog = pd.read_csv(os.path.join(BASE, "curve_of_growth_ann20-30.csv"))
col = pd.read_csv(os.path.join(BASE, "local_color_vs_radius_ann20-30.csv"))

dup = cog[(cog.telescope == "dup") & cog.annulus_ok & cog.aperture_ok]
safe = (dup.groupby(["object", "radius_kpc"]).seeing_safe.all()
        .rename("seeing_safe").reset_index())
m = col.merge(safe, on=["object", "radius_kpc"], how="left")

print(f"{'r(kpc)':>7}{'n':>6}{'%safe':>8}{'sc_all':>9}{'sc_safe':>9}{'sc_unsafe':>11}")
for r in sorted(m.radius_kpc.unique()):
    g = m[np.isclose(m.radius_kpc, r) & m.instrumental_B_minus_V.notna()]
    s = g[g.seeing_safe == True].instrumental_B_minus_V
    u = g[g.seeing_safe == False].instrumental_B_minus_V
    f = lambda x: f"{mad_std(x):.4f}" if len(x) >= 5 else "    --"
    print(f"{r:>7.1f}{len(g):>6d}{100*len(s)/max(len(g),1):>7.0f}%"
          f"{mad_std(g.instrumental_B_minus_V):>9.4f}{f(s):>9}{f(u):>11}")

print("\nIf sc_safe at 1-2 kpc matches the mid-radius values while sc_unsafe")
print("sits well below, the small-radius dip is a resolution artefact and")
print("those radii should be reported as seeing-limited.")