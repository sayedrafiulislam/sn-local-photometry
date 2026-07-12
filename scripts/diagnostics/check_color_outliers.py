import pandas as pd

df = pd.read_csv(r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration\calibrated_color_5kpc.csv")
df = df.dropna(subset=["B_minus_V"])

print("Bluest (most negative B-V):\n")
print(df.sort_values("B_minus_V").head(5).to_string(index=False))

print("\nReddest (most positive B-V):\n")
print(df.sort_values("B_minus_V", ascending=False).head(5).to_string(index=False))