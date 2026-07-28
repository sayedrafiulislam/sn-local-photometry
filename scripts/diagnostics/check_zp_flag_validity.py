import pandas as pd, numpy as np, os

CAL = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
COG = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

fl = pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc_flagged.csv"))
col = pd.read_csv(os.path.join(COG, "local_color_vs_radius_ann20-30.csv"))
inst = (col[np.isclose(col.radius_kpc, 5.0)]
        .set_index("object")["instrumental_B_minus_V"])
fl["instr"] = fl.object.map(inst)

def z(series, value):
    m, s = series.median(), 1.4826*np.median(np.abs(series - series.median()))
    return (value - m) / s

ok = fl[~fl.flag_exclude]
print(f"retained sample: instrumental median {ok.instr.median():.4f}, "
      f"calibrated median {ok.B_minus_V.median():.4f}\n")

print(f"{'object':<11}{'instr':>9}{'instr_z':>9}{'calib':>9}{'calib_z':>9}"
      f"{'zp_mad':>9}  verdict")
for _, r in fl[fl.flag_bad_zp].sort_values("zp_diff_n_mad").iterrows():
    iz = z(fl.instr.dropna(), r.instr)
    cz = z(fl.B_minus_V.dropna(), r.B_minus_V)
    verdict = ("ZP is the problem" if abs(iz) < 2 and abs(cz) > 2
               else "object also odd instrumentally" if abs(iz) > 2
               else "calibrated colour is normal -- flag may be unnecessary")
    print(f"{r.object:<11}{r.instr:>9.3f}{iz:>9.2f}{r.B_minus_V:>9.3f}"
          f"{cz:>9.2f}{r.zp_diff_n_mad:>9.2f}  {verdict}")

# is the ZP difference distribution Gaussian-cored, or intrinsically broad?
zb = pd.read_csv(os.path.join(r"D:\Thesis\My Work\sn-local-photometry\data",
                              "B_ZP_dup.dat"), sep=r"\s+", header=None,
                 names=["object","zp","zp_err","n_ref"])
zv = pd.read_csv(os.path.join(r"D:\Thesis\My Work\sn-local-photometry\data",
                              "V_ZP_dup.dat"), sep=r"\s+", header=None,
                 names=["object","zp","zp_err","n_ref"])
m = zb.merge(zv, on="object", suffixes=("_B","_V"))
m = m[np.isfinite(m.zp_B) & np.isfinite(m.zp_V)]
d = m.zp_B - m.zp_V
med, mad = d.median(), 1.4826*np.median(np.abs(d - d.median()))
print(f"\nZP_B - ZP_V: {len(d)} objects, median {med:+.4f}, MAD {mad:.4f}")
print("  a Gaussian would put 0.3% beyond 3 sigma and 0.00006% beyond 5")
for k in [2, 3, 4, 5, 6]:
    n = int((np.abs(d - med) > k*mad).sum())
    print(f"    beyond {k} MAD: {n:3d} ({100*n/len(d):5.1f}%)")

print("\n  do the outliers have larger quoted zp errors?")
m["n_mad"] = (d - med)/mad
for lab, sub in [("within 3 MAD", m[m.n_mad.abs() <= 3]),
                 ("beyond 3 MAD", m[m.n_mad.abs() > 3])]:
    print(f"    {lab}: n={len(sub):3d}  median zp_err_B {sub.zp_err_B.median():.4f}"
          f"  median n_ref_B {sub.n_ref_B.median():.1f}")