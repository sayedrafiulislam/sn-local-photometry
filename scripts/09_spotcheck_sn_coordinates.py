"""
09_spotcheck_sn_coordinates.py

Verifies what the NED-returned RA/Dec in sn_coordinates.csv actually
points at: the SN explosion site (what we need for local aperture
photometry) or the host galaxy's centre (which would NOT be usable
as-is, and would mean Phase 3 Question 2 is still open).

For a handful of representative objects, converts the NED RA/Dec to a
pixel position using each image's own WCS, and plots it on the image
so this can be checked by eye -- the same diagnostic-PNG approach used
in Phase 1.

Chosen objects:
  - SN2012fr: well-resolved bright spiral host (NGC 1365) -- if the
    marker lands on/near the bright nucleus, that's a strong sign NED
    is giving the galaxy centre, not the SN site. If it lands
    noticeably offset from the nucleus, that's evidence for the SN
    site.
  - ASAS14ad: a "normal" object, no particular reason to expect a
    problem -- a baseline sanity check.
  - KISS13v: one of the Phase 4 seeing-floor edge cases (high z) --
    useful to check this one specifically since it matters for the
    aperture-floor analysis.
"""

import glob
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS
from astropy.stats import sigma_clipped_stats

FITS_DIR = r"D:\Thesis\pd\CSPAll"
COORDS_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"

SPOTCHECK_OBJECTS = ["SN2012fr", "ASAS14ad", "KISS13v"]


def find_image_for_object(obj):
    """Prefer a dup-V image if available, else any B/V image for this object."""
    candidates = glob.glob(os.path.join(FITS_DIR, f"{obj}_V_comb_dup.fits"))
    if not candidates:
        candidates = glob.glob(os.path.join(FITS_DIR, f"{obj}_*_comb_*.fits"))
        candidates = [c for c in candidates if not c.endswith("_r_comb_dup.fits")]
    return candidates[0] if candidates else None


coords = pd.read_csv(COORDS_CSV)
os.makedirs(OUT_DIR, exist_ok=True)

for obj in SPOTCHECK_OBJECTS:
    row = coords[coords["object"] == obj]
    if row.empty:
        print(f"[skip] {obj} not found in sn_coordinates.csv")
        continue
    ra, dec = row.iloc[0]["ra_deg"], row.iloc[0]["dec_deg"]

    fits_path = find_image_for_object(obj)
    if fits_path is None:
        print(f"[skip] no image file found for {obj}")
        continue

    with fits.open(fits_path) as hdul:
        data = hdul[0].data.astype(float)
        wcs = WCS(hdul[0].header)

    x_pix, y_pix = wcs.all_world2pix(ra, dec, 0)

    mean, median, std = sigma_clipped_stats(data, sigma=3.0)

    fig, ax = plt.subplots(figsize=(9, 9))
    vmin = max(median, 1)
    vmax = median + 50 * std
    ax.imshow(data, origin="lower", cmap="gray", norm=LogNorm(vmin=vmin, vmax=vmax))
    ax.scatter([x_pix], [y_pix], s=300, facecolors="none",
               edgecolors="red", linewidths=2, marker="o")
    ax.scatter([x_pix], [y_pix], s=20, color="red", marker="+")
    ax.set_title(f"{obj}  (NED RA={ra:.5f}, Dec={dec:.5f})\n"
                 f"file: {os.path.basename(fits_path)}")
    ax.set_xlabel("x (pixels)")
    ax.set_ylabel("y (pixels)")

    # Zoom to a region around the marked point so it's easy to judge
    # by eye whether it sits on a point source or diffuse galaxy light
    zoom = 300
    ax.set_xlim(max(0, x_pix - zoom), x_pix + zoom)
    ax.set_ylim(max(0, y_pix - zoom), y_pix + zoom)

    out_path = os.path.join(OUT_DIR, f"spotcheck_{obj}.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    print(f"Saved: {out_path}  (marker at pixel {x_pix:.1f}, {y_pix:.1f})")