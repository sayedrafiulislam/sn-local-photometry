"""
plot_flagged_swo.py

Quick visual sanity check for the two swo-V images flagged as PSF
outliers (ASAS14lq_V_comb_swo.fits, ASAS14mw_V_comb_swo.fits).

For each flagged file, produces a PNG showing:
  - the full image (log-scaled for visibility)
  - the detected star positions overlaid, color-coded by their
    measured FWHM (so spatial patterns -- e.g. worse FWHM on one side
    of the frame, consistent with tracking drift -- are visible at a
    glance)

Upload the resulting PNGs back into the chat for a joint look.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from pathlib import Path

FITS_DIR = r"D:\Thesis\pd\CSPAll"
PER_STAR_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf\psf_fwhm_per_star.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf"

FLAGGED_FILES = [
    "SN07ol_V_comb_dup.fits",     # most extreme std (2.24) among newly-flagged; mad_sigma=0.868
    "SN2012fr_B_comb_dup.fits",   # flagged in both B and V (cross-filter consistency check)
]

df = pd.read_csv(PER_STAR_CSV)

for fname in FLAGGED_FILES:
    fits_path = Path(FITS_DIR) / fname
    if not fits_path.exists():
        print(f"[skip] not found: {fits_path}")
        continue

    with fits.open(fits_path) as hdul:
        data = hdul[0].data.astype(float)

    mean, median, std = sigma_clipped_stats(data, sigma=3.0)

    stars = df[df["file"] == fname]

    fig, ax = plt.subplots(figsize=(9, 9))
    vmin = max(median, 1)
    vmax = median + 50 * std
    im = ax.imshow(
        data, origin="lower", cmap="gray",
        norm=LogNorm(vmin=vmin, vmax=vmax),
    )

    sc = ax.scatter(
        stars["x"], stars["y"],
        c=stars["fwhm_avg_arcsec"], cmap="autumn_r",
        s=80, edgecolors="cyan", linewidths=1.2,
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("FWHM (arcsec)")

    ax.set_title(f"{fname}\n(n={len(stars)} stars, median FWHM = "
                 f"{stars['fwhm_avg_arcsec'].median():.2f}\")")
    ax.set_xlabel("x (pixels)")
    ax.set_ylabel("y (pixels)")

    out_path = Path(OUT_DIR) / f"diagnostic_{fname.replace('.fits', '.png')}"
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Saved: {out_path}")


