import pandas as pd, numpy as np, os

CAL = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
new = pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc.csv"))

old_path = [f for f in os.listdir(CAL)
            if f.startswith("calibrated_color_5kpc.csv.bak_")]
old = pd.read_csv(os.path.join(CAL, sorted(old_path)[-1])) if old_path else None

print(f"new catalogue : {len(new)} objects")
if old is not None:
    print(f"previous      : {len(old)} objects")
    lost = sorted(set(old.object) - set(new.object))
    gained = sorted(set(new.object) - set(old.object))
    print(f"lost   : {lost}")
    print(f"gained : {gained}")

print("\n--- unphysical or marginal colours ---")
odd = new[(new.B_minus_V < 0.0) | (new.B_minus_V > 1.5)]
print(odd[["object", "B_minus_V", "B_minus_V_err", "flux_B", "flux_V",
           "n_ref_B", "n_ref_V"]].to_string(index=False) if len(odd) else "none")

print("\n--- weak zero points ---")
for n in [1, 2, 3, 5]:
    w = new[(new.n_ref_B <= n) | (new.n_ref_V <= n)]
    print(f"  n_ref <= {n}: {len(w):3d} objects, "
          f"median colour err {w.B_minus_V_err.median():.4f}" if len(w) else
          f"  n_ref <= {n}: 0")

print("\n--- objects whose colour is not a measurement ---")
bad = new[new.B_minus_V_err > 0.25].sort_values("B_minus_V_err", ascending=False)
print(bad[["object", "B_minus_V", "B_minus_V_err", "n_ref_B", "n_ref_V"]]
      .to_string(index=False) if len(bad) else "none above 0.25 mag")

print(f"\nfraction of catalogue with err > 0.25 mag : "
      f"{100*len(bad)/len(new):.1f}%")
print(f"Spearman rho(colour err, n_ref_B) : "
      f"{new.B_minus_V_err.corr(new.n_ref_B, method='spearman'):.3f}")