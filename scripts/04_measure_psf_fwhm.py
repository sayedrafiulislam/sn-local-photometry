"""
04_measure_psf_fwhm.py

Phase 1 of the local aperture photometry pipeline: measure the point-spread
function (PSF) full width at half maximum (FWHM) for each CSP telescope +
filter combination (dup-B, dup-V, swo-B, swo-V).

--------------------------------------------------------------------------
Motivation (Kelsey et al. 2021, MNRAS 501, 4861, Section 2.2.3)
--------------------------------------------------------------------------
The local aperture used to measure host-galaxy photometry cannot be made
arbitrarily small. Below some radius set by the PSF, the aperture no
longer encloses a well-defined fraction of the source light and
photometric uncertainties blow up. Kelsey et al. impose a single maximum
PSF cut (FWHM = 1.3 arcsec) across their seeing-optimized stacks, and
convert this into a minimum usable aperture radius via the Gaussian
relation

    FWHM = 2 * sqrt(2 * ln 2) * sigma ~= 2.355 * sigma

giving sigma_min ~= 0.55 arcsec (their Section 2.2.3).

CSP images are individual combined frames per object rather than a
uniformly seeing-cut stack (as in DES/W20), across two different
telescopes (du Pont 2.5m, Swope 1m) with different diffraction limits.
We therefore cannot assume a single fixed PSF for the whole sample.
Instead we measure FWHM empirically, grouped by telescope + filter, to
establish the seeing floor(s) relevant to this dataset before choosing a
physical aperture grid in Phase 4 (curve-of-growth analysis).

--------------------------------------------------------------------------
Method
--------------------------------------------------------------------------
1. Detect point sources in each image with DAOStarFinder.
2. Reject non-stellar / blended / saturated detections using sharpness,
   roundness, and peak-flux cuts.
3. Optionally mask out a region around the known SN position, so a
   still-visible SN (open Question 1: are these stacks SN-light-free?)
   cannot masquerade as a calibration star.
4. Fit each retained star with a 2D Gaussian (astropy.modeling) to get
   FWHM_x, FWHM_y -> average FWHM in pixels.
5. Convert to arcsec using the CSP plate scale (0.23 arcsec/pixel).
6. Aggregate to a median (and scatter) per telescope+filter group, and
   save both a per-star table and a per-group summary.
"""

import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.modeling import models, fitting
from astropy.stats import sigma_clipped_stats
from astropy.nddata import Cutout2D
from photutils.detection import DAOStarFinder

# --------------------------------------------------------------------
# Config -- adjust these for your setup
# --------------------------------------------------------------------
PLATE_SCALE_ARCSEC_PER_PIX = 0.23          # confirmed from WCS headers
FWHM_TO_SIGMA = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))  # 2.355 factor

CUTOUT_HALF_SIZE = 15          # pixels, half-width of the fit box around each star
MIN_SEPARATION_PIX = 25        # reject stars closer together than this (blending)
SN_EXCLUSION_RADIUS_PIX = 20   # mask radius around the SN position, if known
MAX_STARS_PER_IMAGE = 25       # cap for speed; DAOStarFinder often over-detects
DAOFIND_FWHM_GUESS = 4.0       # rough initial guess in pixels, only used for detection
DAOFIND_THRESHOLD_NSIGMA = 8.0 # detection threshold in units of background sigma
BORDER_MARGIN_PIX = 60         # exclude detections within this many pixels of any edge
                                # (edge/overscan artifacts can otherwise be misidentified
                                # as point sources -- confirmed visually in Phase 1 testing)

FILENAME_RE = re.compile(r"^(?P<obj>.+?)_(?P<filt>[BV])_comb_(?P<tel>dup|swo)\.fits$")


def parse_filename(path: Path):
    """Extract object name, filter, and telescope from a CSP filename."""
    m = FILENAME_RE.match(path.name)
    if not m:
        return None
    return m.group("obj"), m.group("filt"), m.group("tel")


def detect_stars(data, bkg_mean, bkg_std):
    """Run DAOStarFinder and return a source table sorted by brightness."""
    daofind = DAOStarFinder(
        fwhm=DAOFIND_FWHM_GUESS,
        threshold=DAOFIND_THRESHOLD_NSIGMA * bkg_std,
        sharpness_range=(0.2, 1.0),  # reject cosmic rays (too sharp) / galaxies (too flat)
        roundness_range=(-0.5, 0.5),  # reject elongated / blended sources
    )
    sources = daofind(data - bkg_mean)
    if sources is None or len(sources) == 0:
        return None
    sources.sort("flux")
    sources.reverse()
    return sources


def filter_edge_sources(sources, shape, margin=BORDER_MARGIN_PIX):
    """Drop detections within `margin` pixels of any image edge.

    Prevents overscan strips, edge glow, or reduction artifacts near the
    frame border from being misidentified as stars (confirmed visually
    in ASAS14lq_V_comb_swo.fits, where a row of false detections hugged
    the y=0 edge).
    """
    ny, nx = shape
    x, y = sources["x_centroid"], sources["y_centroid"]
    keep = (x > margin) & (x < nx - margin) & (y > margin) & (y < ny - margin)
    return sources[keep]


def filter_isolated(sources, min_sep=MIN_SEPARATION_PIX):
    """Keep only stars with no neighbour within min_sep pixels (avoid blends)."""
    keep = np.ones(len(sources), dtype=bool)
    xs, ys = sources["x_centroid"], sources["y_centroid"]
    for i in range(len(sources)):
        if not keep[i]:
            continue
        d = np.hypot(xs - xs[i], ys - ys[i])
        d[i] = np.inf
        if np.any(d < min_sep):
            keep[i] = False
            keep[np.argmin(d)] = False
    return sources[keep]


def mask_sn_position(sources, sn_xy, radius=SN_EXCLUSION_RADIUS_PIX):
    """Drop any detection within `radius` pixels of the known SN pixel position."""
    if sn_xy is None:
        return sources
    sn_x, sn_y = sn_xy
    d = np.hypot(sources["x_centroid"] - sn_x, sources["y_centroid"] - sn_y)
    return sources[d > radius]


def fit_gaussian_fwhm(data, x0, y0, half_size=CUTOUT_HALF_SIZE):
    """
    Fit a 2D Gaussian to a cutout centred on (x0, y0).
    Returns (fwhm_x_pix, fwhm_y_pix) or None if the fit fails / is unphysical.
    """
    try:
        cutout = Cutout2D(data, (x0, y0), size=2 * half_size + 1, mode="partial",
                           fill_value=np.nan)
    except Exception:
        return None

    cdata = cutout.data
    if np.any(~np.isfinite(cdata)) or cdata.size == 0:
        cdata = np.nan_to_num(cdata, nan=np.nanmedian(cdata))

    yy, xx = np.mgrid[0:cdata.shape[0], 0:cdata.shape[1]]
    amp_guess = np.nanmax(cdata) - np.nanmedian(cdata)
    if amp_guess <= 0:
        return None

    g_init = models.Gaussian2D(
        amplitude=amp_guess,
        x_mean=cdata.shape[1] / 2, y_mean=cdata.shape[0] / 2,
        x_stddev=2.0, y_stddev=2.0,
    ) + models.Const2D(amplitude=np.nanmedian(cdata))

    fitter = fitting.LevMarLSQFitter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fitted = fitter(g_init, xx, yy, cdata)
        except Exception:
            return None

    g = fitted[0]  # the Gaussian2D component
    sigma_x, sigma_y = abs(g.x_stddev.value), abs(g.y_stddev.value)

    # sanity checks: reject clearly failed / unphysical fits
    if not (0.5 < sigma_x < half_size) or not (0.5 < sigma_y < half_size):
        return None

    fwhm_x = sigma_x / FWHM_TO_SIGMA
    fwhm_y = sigma_y / FWHM_TO_SIGMA
    return fwhm_x, fwhm_y


def process_image(path: Path, sn_positions: dict | None = None):
    """Measure per-star FWHM values for a single FITS image."""
    parsed = parse_filename(path)
    if parsed is None:
        print(f"  [skip] filename does not match CSP convention: {path.name}")
        return []
    obj, filt, tel = parsed

    with fits.open(path) as hdul:
        data = hdul[0].data.astype(float)

    mean, median, std = sigma_clipped_stats(data, sigma=3.0)
    sources = detect_stars(data, median, std)
    if sources is None:
        print(f"  [warn] no sources detected: {path.name}")
        return []

    sources = filter_edge_sources(sources, data.shape)
    if len(sources) == 0:
        print(f"  [warn] all detections were within the border margin: {path.name}")
        return []

    sources = filter_isolated(sources)

    sn_xy = sn_positions.get(obj) if sn_positions else None
    sources = mask_sn_position(sources, sn_xy)

    if len(sources) == 0:
        print(f"  [warn] no isolated non-SN stars survived cuts: {path.name}")
        return []

    sources = sources[:MAX_STARS_PER_IMAGE]

    rows = []
    for row in sources:
        result = fit_gaussian_fwhm(data, row["x_centroid"], row["y_centroid"])
        if result is None:
            continue
        fwhm_x_pix, fwhm_y_pix = result
        fwhm_avg_pix = 0.5 * (fwhm_x_pix + fwhm_y_pix)
        rows.append({
            "object": obj,
            "filter": filt,
            "telescope": tel,
            "file": path.name,
            "x": row["x_centroid"],
            "y": row["y_centroid"],
            "flux": row["flux"],
            "fwhm_x_pix": fwhm_x_pix,
            "fwhm_y_pix": fwhm_y_pix,
            "fwhm_avg_pix": fwhm_avg_pix,
            "fwhm_avg_arcsec": fwhm_avg_pix * PLATE_SCALE_ARCSEC_PER_PIX,
        })
    return rows


def run(fits_dir: str, out_dir: str, sn_positions: dict | None = None,
        max_images: int | None = None):
    fits_dir = Path(fits_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(fits_dir.glob("*.fits"))
    if max_images is not None:
        files = files[:max_images]

    all_rows = []
    for i, path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {path.name}")
        all_rows.extend(process_image(path, sn_positions))

    if not all_rows:
        raise RuntimeError("No star FWHM measurements were obtained. "
                            "Check detection/fit thresholds and file paths.")

    per_star = pd.DataFrame(all_rows)
    per_star_path = out_dir / "psf_fwhm_per_star.csv"
    per_star.to_csv(per_star_path, index=False)
    print(f"\nSaved per-star measurements -> {per_star_path}")

    summary = (
        per_star.groupby(["telescope", "filter"])["fwhm_avg_arcsec"]
        .agg(n_stars="count", median="median", mean="mean", std="std",
             p16=lambda s: np.percentile(s, 16),
             p84=lambda s: np.percentile(s, 84))
        .reset_index()
    )
    summary_path = out_dir / "psf_fwhm_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Saved per-group summary      -> {summary_path}\n")
    print(summary.to_string(index=False))

    return per_star, summary


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Edit these before running:
    # ------------------------------------------------------------------
    FITS_DIR = r"D:\Thesis\pd\CSPAll"
    OUT_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase1_psf"

    # If you have SN pixel coordinates available (e.g. from a WCS lookup
    # of the RA/Dec in your catalog), populate this dict as
    #   {"04dt": (x_pix, y_pix), ...}
    # Leave as None to skip SN masking (not recommended until Question 1
    # -- SN-light-free stacks -- is confirmed with your supervisor).
    SN_POSITIONS = None

    # Start with a manageable subset (e.g. 40-60 files spanning both
    # telescopes and both filters) before running on all 716.
    # Validated on a 60-file batch -- set to None to run the full dataset.
    MAX_IMAGES = None

    run(FITS_DIR, OUT_DIR, sn_positions=SN_POSITIONS, max_images=MAX_IMAGES)