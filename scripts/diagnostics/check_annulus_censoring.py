import pandas as pd, numpy as np, os

APER = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CAL  = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

def flux_at5(tag):
    df = pd.read_csv(os.path.join(APER, f"curve_of_growth_{tag}.csv"))
    df = df[(df.radius_kpc == 5.0) & df.annulus_ok & df.aperture_ok
            & (df.telescope == "dup")]
    p = df.pivot_table(index="object", columns="filter", values="flux_bkgsub")
    p["valid"] = (p.B > 0) & (p.V > 0)
    return p

a, b = flux_at5("ann10-15"), flux_at5("ann20-30")
both = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")

va, vb = both.valid_a, both.valid_b
print(f"object-images with B and V measured at 5 kpc : {len(both)}")
print(f"  valid colour under ann10-15 (contaminated) : {int(va.sum())}")
print(f"  valid colour under ann20-30 (clean)        : {int(vb.sum())}")
print(f"  valid under BOTH -- the shift sample        : {int((va & vb).sum())}")
print(f"  LOST to over-subtraction (clean only)      : {int((~va & vb).sum())}")
print(f"  present in contaminated only               : {int((va & ~vb).sum())}")

lost = both[~va & vb]
kept = both[va & vb]
print("\nhow faint are the censored objects?")
for lab, s in [("censored", lost), ("in shift sample", kept)]:
    if len(s):
        print(f"   {lab:18s} n={len(s):3d}  median B flux (clean) "
              f"{s.B_b.median():10.1f}")

cat = pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc_dered.csv"))
in_cat = set(cat.object)
print(f"\nof the {len(lost)} censored objects, "
      f"{len(set(lost.index) & in_cat)} are in the published catalogue")

print("\nwhat the shift would have been, if flux had stayed positive:")
if len(lost):
    est = -2.5*np.log10(lost.B_b/lost.V_b) * 0 + np.nan  # placeholder
    print("   unmeasurable by construction -- that is the point.")
    print("   Report as: n objects for which the contaminated annulus")
    print("   destroys the measurement entirely, rather than biasing it.")