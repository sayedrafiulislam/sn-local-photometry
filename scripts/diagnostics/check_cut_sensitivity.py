import pandas as pd, numpy as np, os

CAL = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
df = pd.read_csv(os.path.join(CAL, "calibrated_color_5kpc_flagged.csv"))

def apply(bkg_thr, err_thr):
    bad = ((df.bkg_frac_B.abs() > bkg_thr) | (df.bkg_frac_V.abs() > bkg_thr)
           | df.bkg_frac_B.isna() | df.bkg_frac_V.isna()
           | (df.B_minus_V_err > err_thr))
    k = df[~bad].B_minus_V.dropna()
    return len(k), k.median(), k.quantile(.84) - k.quantile(.16), k.min()

print(f"{'bkg':>6}{'err':>7}{'n':>6}{'median':>9}{'spread':>9}{'min':>9}")
for bkg in [0.05, 0.10, 0.20, 0.50, 9.99]:
    for err in [0.20, 0.25, 0.30, 0.40, 9.99]:
        n, m, s, lo = apply(bkg, err)
        print(f"{bkg:>6.2f}{err:>7.2f}{n:>6d}{m:>9.4f}{s:>9.4f}{lo:>+9.4f}")

print("\nno cuts at all:", apply(9.99, 9.99))
print("\nIf the median is stable across this grid, the thresholds are not")
print("driving the result and the choice can be defended as immaterial.")