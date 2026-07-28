import pandas as pd, numpy as np, os

APER = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

def at5(tag):
    df = pd.read_csv(os.path.join(APER, f"curve_of_growth_{tag}.csv"))
    df = df[(df.radius_kpc == 5.0) & df.annulus_ok & df.aperture_ok
            & (df.telescope == "dup")]
    p = df.pivot_table(index="object", columns="filter", values="flux_bkgsub")
    r = df.groupby("object").radius_pix.first()
    z = df.groupby("object").z.first()
    p = p[(p.B > 0) & (p.V > 0)]
    out = pd.DataFrame({"c": -2.5*np.log10(p.B/p.V), "fB": p.B})
    out["area"] = np.pi * r.reindex(out.index)**2
    out["z"] = z.reindex(out.index)
    return out

a, b = at5("ann10-15"), at5("ann20-30")
j = b.copy()
j["colour_shift_mmag"] = (a.c.reindex(b.index) - b.c) * 1000
j = j.dropna(subset=["colour_shift_mmag"])
j["surf_bright"] = j.fB / j.area

print("Spearman correlation of |colour shift| with:")
for name in ["fB", "area", "z", "surf_bright"]:
    rho = j.colour_shift_mmag.abs().corr(j[name], method="spearman")
    print(f"   {name:12s} {rho:+.3f}")

cat = pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc_dered.csv"))
cat = cat.set_index("object")
j["flagged"] = cat.flag_low_flux.reindex(j.index).fillna(False).astype(bool)

print("\ndoes flag_low_flux select the vulnerable objects?")
for lab, s in [("flagged low-flux", j[j.flagged]), ("kept", j[~j.flagged])]:
    if len(s):
        print(f"   {lab:18s} n={len(s):3d}  median shift "
              f"{s.colour_shift_mmag.median():6.1f}  median surf.bright "
              f"{s.surf_bright.median():8.2f}")

print("\nwhat a surface-brightness cut would do instead:")
for pct in [10, 25, 40]:
    thr = j.surf_bright.quantile(pct/100)
    kept = j[j.surf_bright > thr]
    print(f"   cut lowest {pct:2d}% by surface brightness -> n={len(kept):3d}  "
          f"median {kept.colour_shift_mmag.median():5.1f}  "
          f"90th pct {kept.colour_shift_mmag.quantile(0.9):6.1f} mmag")