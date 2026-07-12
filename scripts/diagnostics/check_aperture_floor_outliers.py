import pandas as pd

df = pd.read_csv(r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture\aperture_floor_per_object.csv")

worst = df.sort_values("sigma_min_kpc", ascending=False).head(10)
print(worst[["object", "telescope", "filter", "z", "fwhm_arcsec",
             "sigma_min_kpc", "smallest_safe_grid_radius_kpc"]].to_string(index=False))