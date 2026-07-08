"""
00_inspect_headers.py

Purpose
-------
First reconnaissance step for a new FITS dataset. Before we can design a
photometry pipeline (Section 2.2.3-style local aperture photometry, following
Kelsey et al. 2021), we need to know exactly what metadata each file carries:

    - Is there a WCS solution (for converting SN sky coordinates -> pixels)?
    - Is there a redshift keyword anywhere in the header?
    - Is there an SN position keyword, or do we need a separate source list?
    - What filter/band is each file (we were told "B-V files")?
    - What are the pixel scale and image dimensions?

This script does NOT assume any of that -- it just opens every FITS file it
finds under a directory, dumps the header, and produces a summary CSV so we
can decide the next step with real information instead of guessing.

Usage
-----
    python 00_inspect_headers.py --data-dir /path/to/fits/files --out-csv results/header_summary.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from astropy.io import fits
from astropy.wcs import WCS


# Keywords we will actively look for. FITS headers are not standardized
# across pipelines, so we check a list of common aliases for each physical
# quantity rather than a single hard-coded key.
REDSHIFT_KEYS = ["Z", "REDSHIFT", "SN_Z", "ZSN", "ZCMB", "ZHEL"]
RA_KEYS = ["RA", "SN_RA", "RA_SN", "CRVAL1"]
DEC_KEYS = ["DEC", "SN_DEC", "DEC_SN", "CRVAL2"]
FILTER_KEYS = ["FILTER", "BAND", "FILTNAME"]
OBJECT_KEYS = ["OBJECT", "SN_NAME", "TARGET", "SNID"]


def find_first_present(header: fits.Header, keys: list[str]):
    """Return (key, value) for the first key in `keys` present in header."""
    for k in keys:
        if k in header:
            return k, header[k]
    return None, None


def inspect_file(path: Path) -> dict:
    """Open one FITS file and extract everything relevant into a flat dict."""
    row = {"file": str(path), "readable": True, "error": ""}

    try:
        with fits.open(path) as hdul:
            # Some pipelines put WCS/metadata in the primary HDU, others in
            # extension 1 (common for .fits.fz compressed images). We check
            # both and record which one had a usable header.
            header = hdul[0].header
            data_shape = None
            for hdu in hdul:
                if hdu.data is not None:
                    data_shape = hdu.data.shape
                    if hdu.header:
                        header = hdu.header
                    break

            row["n_hdus"] = len(hdul)
            row["data_shape"] = str(data_shape)

            z_key, z_val = find_first_present(header, REDSHIFT_KEYS)
            ra_key, ra_val = find_first_present(header, RA_KEYS)
            dec_key, dec_val = find_first_present(header, DEC_KEYS)
            filt_key, filt_val = find_first_present(header, FILTER_KEYS)
            obj_key, obj_val = find_first_present(header, OBJECT_KEYS)

            row["redshift_key"] = z_key or ""
            row["redshift_val"] = z_val if z_val is not None else ""
            row["ra_key"] = ra_key or ""
            row["ra_val"] = ra_val if ra_val is not None else ""
            row["dec_key"] = dec_key or ""
            row["dec_val"] = dec_val if dec_val is not None else ""
            row["filter_key"] = filt_key or ""
            row["filter_val"] = filt_val if filt_val is not None else ""
            row["object_key"] = obj_key or ""
            row["object_val"] = obj_val if obj_val is not None else ""

            # Check WCS validity -- a header can have CRVAL/CRPIX keywords
            # that don't actually form a usable World Coordinate System.
            try:
                wcs = WCS(header)
                row["has_wcs"] = wcs.has_celestial
                if wcs.has_celestial:
                    scale = wcs.proj_plane_pixel_scales()
                    row["pixscale_arcsec"] = float(
                        (scale[0].to("arcsec").value + scale[1].to("arcsec").value) / 2
                    )
                else:
                    row["pixscale_arcsec"] = ""
            except Exception as e:  # noqa: BLE001
                row["has_wcs"] = False
                row["pixscale_arcsec"] = ""
                row["wcs_error"] = str(e)

    except Exception as e:  # noqa: BLE001
        row["readable"] = False
        row["error"] = str(e)

    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path,
                         help="Directory containing FITS files (searched recursively).")
    parser.add_argument("--out-csv", required=True, type=Path,
                         help="Where to write the summary CSV.")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only inspect the first N files (useful for a quick test on 10GB of data).")
    args = parser.parse_args()

    fits_files = sorted(
        list(args.data_dir.rglob("*.fits")) + list(args.data_dir.rglob("*.fits.fz"))
    )
    if args.limit:
        fits_files = fits_files[: args.limit]

    if not fits_files:
        print(f"No .fits or .fits.fz files found under {args.data_dir}")
        return

    print(f"Inspecting {len(fits_files)} files...")
    rows = [inspect_file(p) for p in fits_files]

    fieldnames = sorted(set(k for row in rows for k in row.keys()))
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote summary to {args.out_csv}")

    # Quick console summary so you get an immediate answer, not just a file.
    n_with_z = sum(1 for r in rows if r.get("redshift_val") not in ("", None))
    n_with_wcs = sum(1 for r in rows if r.get("has_wcs"))
    print(f"Files with a redshift keyword found: {n_with_z}/{len(rows)}")
    print(f"Files with valid celestial WCS:       {n_with_wcs}/{len(rows)}")


if __name__ == "__main__":
    main()