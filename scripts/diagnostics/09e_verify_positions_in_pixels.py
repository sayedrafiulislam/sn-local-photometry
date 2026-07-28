"""
09e_verify_positions_in_pixels.py

Verifies that the sky positions confirmed by 09b actually land where they
should inside your own FITS frames.

Why this is a separate check
----------------------------
09b established that NED's coordinates are supernova positions rather than
host-galaxy centres, for all 266 objects. 09c and 09d then used those positions
to measure a real colour effect. None of those three scripts opens a FITS file.

A correct sky coordinate placed through a faulty World Coordinate System still
lands on the wrong pixel. Every failure below would pass 09b, 09c and 09d and
still corrupt the photometry:

  - a bad astrometric solution in one frame, so correct coordinates convert to
    the wrong pixel;
  - an axis or indexing convention error (FITS is 1-based, numpy 0-based);
  - a mislabelled file, placing the aperture on an entirely different galaxy at
    a perfectly valid pixel.

This is more than a formality here. The data set contains three plate scales,
and twelve frames are finer-sampled products from a different reduction path
(C2). Resampling rewrites the WCS, so those are precisely the frames where an
astrometric error is most plausible.

The existing check, script 09, writes three PNG cutouts for visual inspection
out of 552 frames. Visual inspection has already misled this project once
(ASAS14mw was confirmed by eye as defocused; at its true plate scale it is
ordinary). This script replaces the eye with four measurements applied to every
frame.

The four checks
---------------
1. GEOMETRY. Does the sky position convert to a pixel inside the array, and is
   there room for the 5 kpc aperture and the 20-30 kpc background annulus? The
   annulus is the binding constraint: at z < 0.0051 its outer edge exceeds the
   frame half-width (C4).

2. SIGNAL. Is there flux above the local background at that position? The
   supernova itself may have faded, but the host galaxy should be there. Blank
   sky means the position or the WCS is wrong.

3. CROSS-FILTER CONSISTENCY. This is the strongest test and it needs no
   external truth. For each frame, measure the vector from the supernova
   position to the flux-weighted centroid of the surrounding galaxy light. If
   the astrometry of both frames is sound, that vector must agree between B and
   V, because it describes the same physical geometry. A disagreement means one
   frame's WCS is wrong, and it identifies which object is affected even when
   both frames individually look reasonable.

4. PLATE SCALE AGREEMENT. Compare the scale recorded in the header summary
   against the scale implied by the WCS as read here. A mismatch means the two
   were computed from different solutions.

Note on the centroid: a cutout centred on the supernova will have its centroid
pulled toward the host nucleus, which is expected and not a fault. The
measurement of interest is whether that pull is *consistent between filters*,
not whether it is zero.

Usage
-----
    python 09e_verify_positions_in_pixels.py ^
        --coords results\\sn_coordinates.csv ^
        --catalog results\\sn_catalog_final.csv ^
        --header-summary results\\header_summary_full.csv ^
        --data-dir "D:\\Thesis\\pd\\CSPAll" ^
        --out-csv results\\position_pixel_verification.csv
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Fiducial aperture and background annulus, in kpc, matching the pipeline.
APERTURE_KPC = 5.0
ANNULUS_IN_KPC = 20.0
ANNULUS_OUT_KPC = 30.0

# Half-width of the cutout used for the centroid, as a multiple of the 5 kpc
# aperture radius. Large enough to contain the host, small enough to exclude
# unrelated neighbours.
CENTROID_BOX_FACTOR = 3.0

# A centroid vector disagreeing between filters by more than this is flagged.
# Generous: real differences arise because B and V trace different stellar
# populations, so only gross astrometric errors should trip it.
CENTROID_DISAGREE_ARCSEC = 3.0

# Minimum signal-to-noise of the flux inside the aperture for the position to
# be considered to contain a galaxy at all.
MIN_APERTURE_SNR = 3.0

SCALE_DP = 4


def basename(p) -> str:
    return Path(str(p).replace("\\", "/")).name


def kpc_per_arcsec(z, cosmo) -> float:
    d_a_mpc = cosmo.angular_diameter_distance(z).value
    return float(np.deg2rad(1.0 / 3600.0) * d_a_mpc * 1000.0)


def robust_background(a: np.ndarray, n_iter: int = 5, sigma: float = 3.0):
    """Sigma-clipped median and standard deviation, implemented locally."""
    a = a[np.isfinite(a)]
    if a.size == 0:
        return np.nan, np.nan
    for _ in range(n_iter):
        med, sd = np.median(a), np.std(a)
        if sd == 0:
            break
        keep = np.abs(a - med) < sigma * sd
        if keep.sum() < 10 or keep.all():
            break
        a = a[keep]
    return float(np.median(a)), float(np.std(a))


def flux_centroid(cut: np.ndarray, bkg: float):
    """
    Flux-weighted centroid of a background-subtracted cutout.

    Negative pixels are clipped to zero first, otherwise noise in the sky
    regions drags the centroid unpredictably.
    """
    w = cut - bkg
    w[~np.isfinite(w)] = 0.0
    w[w < 0] = 0.0
    total = w.sum()
    if total <= 0:
        return np.nan, np.nan
    yy, xx = np.mgrid[0:w.shape[0], 0:w.shape[1]]
    return float((w * xx).sum() / total), float((w * yy).sum() / total)


def circular_sum(data: np.ndarray, x: float, y: float, r: float):
    """Simple circular aperture sum and pixel count, centre in array coords."""
    h, w = data.shape
    x0, x1 = max(0, int(x - r) - 1), min(w, int(x + r) + 2)
    y0, y1 = max(0, int(y - r) - 1), min(h, int(y + r) + 2)
    if x1 <= x0 or y1 <= y0:
        return np.nan, 0
    sub = data[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    m = ((xx - x) ** 2 + (yy - y) ** 2) <= r * r
    vals = sub[m]
    vals = vals[np.isfinite(vals)]
    return float(vals.sum()), int(vals.size)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coords", required=True, type=Path)
    ap.add_argument("--catalog", required=True, type=Path)
    ap.add_argument("--header-summary", required=True, type=Path)
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    warnings.filterwarnings("ignore")
    from astropy.io import fits
    from astropy.wcs import WCS
    from astropy.cosmology import FlatLambdaCDM

    cosmo = FlatLambdaCDM(H0=70, Om0=0.3)

    # Take redshift from the catalogue only. Both files carry a `redshift`
    # column, and merging on both would produce redshift_x / redshift_y.
    coords = pd.read_csv(args.coords)[["object", "ra_deg", "dec_deg"]]
    catalog = pd.read_csv(args.catalog)
    hdr = pd.read_csv(args.header_summary)
    hdr["fname"] = hdr["file"].apply(basename)
    scale_map = dict(zip(hdr["fname"], hdr["pixscale_arcsec"].round(SCALE_DP)))

    work = catalog.merge(coords, on="object", how="inner")
    work = work[work["filter"].isin(["B", "V"])].copy()
    if "redshift" not in work.columns:
        raise SystemExit("No 'redshift' column after the merge. Expected it in "
                         f"{args.catalog}.")
    n_before = len(work)
    work = work[work["redshift"].notna() & (work["redshift"] > 0)]
    if len(work) < n_before:
        print(f"Dropped {n_before - len(work)} frames with no usable redshift.")
    work["fname"] = work["file"].apply(basename)
    if args.limit:
        work = work.head(args.limit)

    print(f"Checking {len(work)} frames across {work['object'].nunique()} objects.\n")

    rows = []
    for i, rec in enumerate(work.itertuples(index=False), start=1):
        path = args.data_dir / rec.fname
        out = {
            "object": rec.object, "filter": rec.filter, "telescope": rec.telescope,
            "file": rec.fname, "z": rec.redshift,
            "x_pix": np.nan, "y_pix": np.nan,
            "nx": np.nan, "ny": np.nan, "edge_dist_pix": np.nan,
            "plate_scale_hdr": scale_map.get(rec.fname, np.nan),
            "plate_scale_wcs": np.nan,
            "aperture_r_pix": np.nan, "annulus_out_pix": np.nan,
            "aperture_fits": False, "annulus_fits": False,
            "aperture_snr": np.nan,
            "centroid_dx_arcsec": np.nan, "centroid_dy_arcsec": np.nan,
            "status": "", "note": "",
        }

        if not path.exists():
            out["status"] = "FILE_MISSING"
            rows.append(out)
            continue

        try:
            with fits.open(path, memmap=True) as hdul:
                hdu = next((h for h in hdul if h.data is not None), None)
                if hdu is None:
                    out["status"] = "NO_DATA"
                    rows.append(out)
                    continue

                w = WCS(hdu.header)
                if not w.has_celestial:
                    out["status"] = "NO_WCS"
                    rows.append(out)
                    continue

                sc = w.proj_plane_pixel_scales()
                pix = float((sc[0].to("arcsec").value + sc[1].to("arcsec").value) / 2)
                out["plate_scale_wcs"] = round(pix, SCALE_DP)

                x, y = w.celestial.world_to_pixel_values(rec.ra_deg, rec.dec_deg)
                x, y = float(x), float(y)
                out["x_pix"], out["y_pix"] = x, y

                ny, nx = hdu.data.shape
                out["nx"], out["ny"] = nx, ny
                out["edge_dist_pix"] = float(min(x, y, nx - 1 - x, ny - 1 - y))

                if not (0 <= x < nx and 0 <= y < ny):
                    out["status"] = "OFF_IMAGE"
                    rows.append(out)
                    print(f"[{i}/{len(work)}] {rec.object:12s} {rec.filter} OFF_IMAGE")
                    continue

                kpa = kpc_per_arcsec(rec.redshift, cosmo)
                r_ap = (APERTURE_KPC / kpa) / pix
                r_out = (ANNULUS_OUT_KPC / kpa) / pix
                out["aperture_r_pix"] = r_ap
                out["annulus_out_pix"] = r_out
                out["aperture_fits"] = bool(out["edge_dist_pix"] >= r_ap)
                out["annulus_fits"] = bool(out["edge_dist_pix"] >= r_out)

                # Cutout for background, signal and centroid.
                half = int(max(20, CENTROID_BOX_FACTOR * r_ap))
                y0, y1 = max(0, int(y) - half), min(ny, int(y) + half + 1)
                x0, x1 = max(0, int(x) - half), min(nx, int(x) + half + 1)
                cut = np.array(hdu.data[y0:y1, x0:x1], dtype=float)

                bkg, noise = robust_background(cut)
                s, npix = circular_sum(cut - bkg, x - x0, y - y0, max(3.0, r_ap))
                if npix > 0 and np.isfinite(noise) and noise > 0:
                    out["aperture_snr"] = s / (noise * np.sqrt(npix))

                cx, cy = flux_centroid(cut, bkg)
                if np.isfinite(cx):
                    out["centroid_dx_arcsec"] = (cx - (x - x0)) * pix
                    out["centroid_dy_arcsec"] = (cy - (y - y0)) * pix

        except Exception as e:  # noqa: BLE001
            out["status"] = "ERROR"
            out["note"] = f"{type(e).__name__}: {e}"[:120]
            rows.append(out)
            continue

        flags = []
        if not out["aperture_fits"]:
            flags.append("APERTURE_OFF_EDGE")
        if not out["annulus_fits"]:
            flags.append("ANNULUS_TRUNCATED")
        if np.isfinite(out["aperture_snr"]) and out["aperture_snr"] < MIN_APERTURE_SNR:
            flags.append("NO_SIGNAL")
        if (np.isfinite(out["plate_scale_hdr"]) and
                abs(out["plate_scale_hdr"] - out["plate_scale_wcs"]) > 0.001):
            flags.append("SCALE_MISMATCH")
        out["status"] = ",".join(flags) if flags else "OK"

        rows.append(out)
        if i % 50 == 0 or i == len(work):
            print(f"  ...{i}/{len(work)}")

    res = pd.DataFrame(rows)

    # ---- cross-filter consistency (check 3) --------------------------------
    res["centroid_disagreement_arcsec"] = np.nan
    for obj, g in res.groupby("object"):
        b = g[g["filter"] == "B"]
        v = g[g["filter"] == "V"]
        if len(b) == 0 or len(v) == 0:
            continue
        bx, by = b["centroid_dx_arcsec"].mean(), b["centroid_dy_arcsec"].mean()
        vx, vy = v["centroid_dx_arcsec"].mean(), v["centroid_dy_arcsec"].mean()
        if np.isfinite(bx) and np.isfinite(vx):
            res.loc[g.index, "centroid_disagreement_arcsec"] = float(
                np.hypot(bx - vx, by - vy))

    bad = res["centroid_disagreement_arcsec"] > CENTROID_DISAGREE_ARCSEC
    res.loc[bad, "status"] = res.loc[bad, "status"].replace("OK", "") \
        .str.cat(pd.Series(["CENTROID_DISAGREE"] * int(bad.sum()),
                           index=res.index[bad]), sep=",").str.strip(",")

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(args.out_csv, index=False)

    # ---- report -------------------------------------------------------------
    print("\n" + "=" * 74)
    print("RESULT")
    print("=" * 74)
    n_ok = int((res["status"] == "OK").sum())
    print(f"  frames checked : {len(res)}")
    print(f"  clean          : {n_ok} ({100 * n_ok / len(res):.1f}%)")
    print("\n  issues found:")
    for st, n in res.loc[res["status"] != "OK", "status"].value_counts().items():
        print(f"    {st:>40s} : {n}")

    print("\n  Geometry:")
    print(f"    aperture does not fit in frame : {int((~res['aperture_fits']).sum())}")
    print(f"    20-30 kpc annulus truncated    : {int((~res['annulus_fits']).sum())}")

    print("\n  Cross-filter centroid agreement (the strongest astrometric test):")
    cd = res["centroid_disagreement_arcsec"].dropna()
    if len(cd):
        print(f"    objects tested : {res.loc[cd.index, 'object'].nunique()}")
        print(f"    median {cd.median():.2f}\"  p90 {cd.quantile(0.9):.2f}\"  "
              f"max {cd.max():.2f}\"")
        worst = (res[res["centroid_disagreement_arcsec"] > CENTROID_DISAGREE_ARCSEC]
                 [["object", "centroid_disagreement_arcsec"]]
                 .drop_duplicates("object")
                 .sort_values("centroid_disagreement_arcsec", ascending=False))
        if len(worst):
            print(f"\n    objects disagreeing by more than "
                  f"{CENTROID_DISAGREE_ARCSEC}\":")
            print(worst.round(2).to_string(index=False))
        else:
            print("    no object exceeds the threshold: astrometry is consistent "
                  "between filters throughout.")

    print("\n  Plate scale, header summary vs WCS read here:")
    mm = res[res["status"].str.contains("SCALE_MISMATCH", na=False)]
    print(f"    mismatches: {len(mm)}")

    print(f"\nWrote {args.out_csv}")


if __name__ == "__main__":
    main()