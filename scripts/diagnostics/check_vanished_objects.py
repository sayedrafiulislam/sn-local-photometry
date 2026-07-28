import pandas as pd, numpy as np, os

BASE = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
cog = pd.read_csv(os.path.join(BASE, "curve_of_growth_ann20-30.csv"))
KEYS = ["object", "telescope", "filter"]

frames = cog.drop_duplicates(subset=KEYS)
dup = frames[frames.telescope == "dup"]

before = set(dup.groupby("object")["filter"].apply(set)
             .pipe(lambda s: s[s.apply(lambda x: {"B", "V"} <= x)]).index)

kept = frames[frames.annulus_ok & (frames.telescope == "dup")]
after = set(kept.groupby("object")["filter"].apply(set)
            .pipe(lambda s: s[s.apply(lambda x: {"B", "V"} <= x)]).index)

lost = sorted(before - after)
print(f"objects with du Pont B and V before the guard : {len(before)}")
print(f"                              after the guard : {len(after)}")
print(f"lost                                          : {len(lost)}\n")

z = cog.groupby("object").z.first()
print(f"{'object':<14}{'z':>9}{'ann_out_px':>12}   bands lost")
for o in lost:
    rows = frames[frames.object == o]
    bad = rows[~rows.annulus_ok]
    print(f"{o:<14}{z[o]:>9.4f}{rows.annulus_outer_pix.max():>12.0f}   "
          f"{sorted(bad['filter'].tolist())}")

print(f"\nsample median z : {z.median():.4f}")
print(f"lost objects    : median z {z[lost].median():.4f}"
      if lost else "")

CAL = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"
p = os.path.join(CAL, "calibrated_color_5kpc_dered.csv")
if os.path.exists(p):
    cat = set(pd.read_csv(p).object)
    hit = sorted(set(lost) & cat)
    print(f"\nof the {len(lost)} lost, {len(hit)} are in the published catalogue: {hit}")