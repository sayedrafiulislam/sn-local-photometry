"""
check_aperture_overlay.py

Diagnostic for the two curve-of-growth anomalies:
- ASAS14ad: curve never flattens even with the local-annulus background
  fix -- testing whether this is simply a large galaxy whose light
  genuinely extends past the 10 kpc grid maximum.
- KISS13v: sharp upturn past ~7 kpc -- testing whether the aperture is
  sweeping up a nearby field star as it grows.

Plots the SN position with aperture circles at 5 kpc, 10 kpc, and
15 kpc (a bit past the current grid edge) overlaid directly on the
image, zoomed out enough to see what's actually inside the largest
circle.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Circle
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS
from astropy.cosmology import FlatLambdaCDM
from astropy.stats import sigma_clipped_stats
import numpy as np

FITS_DIR = r"D:\Thesis\pd\CSPAll"
COORDS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

COSMO = FlatLambdaCDM(H0=70, Om0=0.3)
PLATE_SCALE = 0.23

CHECKS = [
    ("ASAS14ad", "ASAS14ad_V_comb_dup.fits"),
    ("KISS13v", "KISS13v_V_comb_dup.fits"),
]
CHECK_RADII_KPC = [5.0, 10.0, 15.0]


def kpc_to_pixels(radius_kpc, z):
    d_a_mpc = COSMO.angular_diameter_distance(z).value
    theta_rad = (radius_kpc / 1000.0) / d_a_mpc
    theta_arcsec = np.rad2deg(theta_rad) * 3600.0
    return theta_arcsec / PLATE_SCALE


coords = pd.read_csv(COORDS_CSV)

for obj, fname in CHECKS:
    row = coords[coords["object"] == obj]
    if row.empty:
        print(f"[skip] {obj} not in sn_coordinates.csv")
        continue
    ra, dec = row.iloc[0]["ra_deg"], row.iloc[0]["dec_deg"]
    z = row.iloc[0]["redshift"] if "redshift" in row.columns else None

    fits_path = os.path.join(FITS_DIR, fname)
    with fits.open(fits_path) as hdul:
        data = hdul[0].data.astype(float)
        wcs = WCS(hdul[0].header)

    x_pix, y_pix = wcs.all_world2pix(ra, dec, 0)
    mean, median, std = sigma_clipped_stats(data, sigma=3.0)

    fig, ax = plt.subplots(figsize=(9, 9))
    vmin = max(median, 1)
    vmax = median + 50 * std
    ax.imshow(data, origin="lower", cmap="gray", norm=LogNorm(vmin=vmin, vmax=vmax))

    colors = ["cyan", "yellow", "red"]
    for r_kpc, color in zip(CHECK_RADII_KPC, colors):
        r_pix = kpc_to_pixels(r_kpc, z)
        circ = Circle((x_pix, y_pix), r_pix, fill=False, edgecolor=color,
                      linewidth=1.5, label=f"{r_kpc} kpc")
        ax.add_patch(circ)

    ax.scatter([x_pix], [y_pix], s=20, color="lime", marker="+")
    ax.set_title(f"{obj}  (z={z})\n{fname}")
    ax.legend(loc="upper right")

    max_r_pix = kpc_to_pixels(max(CHECK_RADII_KPC), z)
    pad = max_r_pix * 1.3
    ax.set_xlim(x_pix - pad, x_pix + pad)
    ax.set_ylim(y_pix - pad, y_pix + pad)

    out_path = os.path.join(OUT_DIR, f"aperture_overlay_{obj}.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Saved: {out_path}")