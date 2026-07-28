import pandas as pd, numpy as np, os

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
lost = ['LSQ12gzm', 'LSQ13dby', 'LSQ14ip', 'SN2013hn']

cog = pd.read_csv(os.path.join(BASE, "curve_of_growth_ann20-30.csv"))
at5 = cog[np.isclose(cog.radius_kpc, 5.0) & (cog.telescope == "dup")]

print(f"{'object':<12}{'filt':>5}{'flux':>12}{'ann_ok':>8}{'ap_ok':>7}"
      f"{'ap_frac':>9}{'n_nan':>7}")
for o in lost:
    rows = at5[at5.object == o]
    if not len(rows):
        print(f"{o:<12}  -- no du Pont row at 5 kpc at all")
        continue
    for _, r in rows.iterrows():
        print(f"{o:<12}{r['filter']:>5}{r.flux_bkgsub:>12.1f}"
              f"{str(r.annulus_ok):>8}{str(r.aperture_ok):>7}"
              f"{r.aperture_frac_on_chip:>9.3f}{r.aperture_n_nonfinite:>7.0f}")

ex = os.path.join(CAL, "calibrated_color_5kpc_exclusions.csv")
if os.path.exists(ex):
    e = pd.read_csv(ex)
    print("\n--- exclusion log entries ---")
    print(e[e.object.isin(lost)].to_string(index=False))