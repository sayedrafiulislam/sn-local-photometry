import pandas as pd, numpy as np
d = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
SKY = 0.0774
for tag in ["ann10-15","ann20-30"]:
    df = pd.read_csv(d + rf"\curve_of_growth_{tag}.csv")
    g = df[(df.radius_kpc==5.0) & df.annulus_ok & df.aperture_ok
           & (df.telescope=="dup")].copy()
    area = np.pi * g.radius_pix**2
    over = (g.bkg_per_pixel - SKY) * area
    true_flux = g.flux_bkgsub + over
    frac = (over / true_flux).median()
    print(f"{tag}: n={len(g)}  median over-subtraction {100*frac:.2f}% "
          f"= {-2.5*np.log10(1-frac)*1000:.1f} mmag")