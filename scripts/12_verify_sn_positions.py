"""
12_verify_sn_positions.py

Quantitative replacement for the three-object visual spot check.

Why this exists
---------------
Script 08 fetches a sky position for every object and warns, correctly, that
the assumption behind it has not been tested:

    "NED's position entry for a supernova is normally the explosion site
     itself (as reported to IAU/TNS), not the host galaxy's centre -- but
     this has NOT been verified against your actual images yet."

This matters more than any other assumption in the pipeline, because it is the
only one whose failure is invisible downstream. A wrong plate scale eventually
produced an implausible seeing value. A wrong redshift would produce absurd
aperture sizes. A wrong position produces a perfectly ordinary-looking B-V
measured at the wrong place. Nothing in the photometry, the calibration or the
final distribution would look unusual.

The existing check is three PNG cutouts inspected by eye, out of 266 objects.
Visual inspection has already misled this project once (ASAS14mw was confirmed
by eye as defocused; at its true plate scale it is ordinary), so this script
replaces the eye with two measurements.

What it tests
-------------
TEST 1 -- OBJECT TYPE. NED labels every entry with a type. If a name resolved
to a record of type "SN", the coordinates are the explosion site and the
assumption holds for that object. If it resolved to type "G" (galaxy), the
coordinates are the galaxy's centre, and the "local" aperture for that object
is in fact centred on the nucleus. This is a direct test, not an inference.

TEST 2 -- OFFSET FROM THE NEAREST GALAXY. For each position, search NED's
neighbourhood for galaxies and measure the angular separation to the nearest
one. Converted to kpc at the object's own redshift, this is the projected
galactocentric distance of the supernova. Two things fall out:

  - An offset of exactly zero means the position IS a galaxy entry, confirming
    Test 1 independently.

  - The distribution of non-zero offsets is scientifically meaningful in its
    own right. If a large fraction of supernovae sit within ~1-2 kpc of their
    host's centre, then a 5 kpc aperture centred on them substantially
    overlaps the nucleus, and "local colour" is closer to "central colour"
    than the term implies. That is a limitation worth knowing about and
    stating, whether or not it changes any number.

Cost
----
Two NED queries per object, roughly 9 minutes for 266 objects at the default
delay. Use --limit for a quick trial before committing to a full run. Nothing
is modified; one new CSV is written.

Usage
-----
    python 12_verify_sn_positions.py --coords results\\sn_coordinates.csv ^
        --out-csv results\\sn_position_verification.csv --limit 20
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

# NED occasionally returns a name-checker backend error ("EGRET error") that
# is transient. Scripts 01 and 08 both treat it as fatal because they only
# retry on timeouts. Here it is treated as retryable, as in 01b.
MAX_RETRIES = 4
BASE_BACKOFF_S = 3
POLITE_DELAY_S = 1.0

# Radius of the neighbourhood search for a host galaxy. Generous: at z = 0.01
# one arcmin is roughly 12 kpc, so this comfortably contains any plausible
# host while staying small enough to avoid unrelated background galaxies
# dominating the result.
SEARCH_RADIUS_ARCMIN = 1.0

# Below this separation the "nearest galaxy" is almost certainly the same
# record as the queried object rather than a genuine host detection.
SAME_OBJECT_ARCSEC = 0.5


def is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "not currently recognized" in msg or "not recognized" in msg:
        return False
    return any(m in msg for m in (
        "timed out", "timeout", "remote service returned", "egret",
        "connection", "temporarily", "unavailable", "500", "502", "503", "504",
    ))


def retrying(fn, *args, **kwargs):
    """Call fn with retries on transient NED failures. Returns (result, error)."""
    last = ""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs), None
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            if not is_transient(e):
                return None, last
            if attempt < MAX_RETRIES - 1:
                time.sleep(BASE_BACKOFF_S * (2 ** attempt))
    return None, last


def first_col(table, candidates):
    """Return the first column name present, since astroquery renames these."""
    for c in candidates:
        if c in table.colnames:
            return c
    return None


def angular_sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    """
    Great-circle separation in arcsec.

    The cos(dec) factor on the RA difference is essential: one degree of RA
    spans a smaller angle on the sky the further you are from the equator.
    Omitting it inflates separations for southern targets, and this sample is
    almost entirely southern.
    """
    d2r = np.pi / 180.0
    dra = (ra2 - ra1) * np.cos(0.5 * (dec1 + dec2) * d2r)
    ddec = dec2 - dec1
    return float(np.hypot(dra, ddec) * 3600.0)


def kpc_per_arcsec(z, cosmo) -> float:
    d_a_mpc = cosmo.angular_diameter_distance(z).value
    return float(np.deg2rad(1.0 / 3600.0) * d_a_mpc * 1000.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coords", required=True, type=Path,
                    help="sn_coordinates.csv from script 08.")
    ap.add_argument("--out-csv", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None,
                    help="Only check the first N objects. Use for a trial run.")
    ap.add_argument("--radius-arcmin", type=float, default=SEARCH_RADIUS_ARCMIN)
    args = ap.parse_args()

    try:
        from astropy import units as u
        from astropy.coordinates import SkyCoord
        from astropy.cosmology import FlatLambdaCDM
        from astroquery.ipac.ned import Ned
    except ImportError as e:
        raise SystemExit("Requires astropy and astroquery. "
                         "pip install astropy astroquery") from e

    cosmo = FlatLambdaCDM(H0=70, Om0=0.3)

    df = pd.read_csv(args.coords)
    if args.limit:
        df = df.head(args.limit).copy()
    print(f"Verifying {len(df)} object positions. "
          f"Two NED queries each, roughly {len(df) * 2 * POLITE_DELAY_S / 60:.0f} "
          f"minutes.\n")

    rows = []
    for i, rec in enumerate(df.itertuples(index=False), start=1):
        name = rec.ned_resolved_name
        out = {
            "object": rec.object,
            "ned_resolved_name": name,
            "z": rec.redshift,
            "ra_deg": rec.ra_deg,
            "dec_deg": rec.dec_deg,
            "ned_type": "",
            "n_galaxies_nearby": np.nan,
            "nearest_galaxy": "",
            "offset_arcsec": np.nan,
            "offset_kpc": np.nan,
            "verdict": "",
            "error": "",
        }

        # --- Test 1: what kind of object did this name resolve to? --------
        tbl, err = retrying(Ned.query_object, name)
        if tbl is None or len(tbl) == 0:
            out["error"] = err or "no record"
            out["verdict"] = "UNRESOLVED"
            rows.append(out)
            print(f"[{i}/{len(df)}] {rec.object:12s} -> UNRESOLVED")
            time.sleep(POLITE_DELAY_S)
            continue

        tcol = first_col(tbl, ["Type", "Object Type", "type"])
        if tcol:
            out["ned_type"] = str(tbl[0][tcol]).strip()

        # --- Test 2: how far to the nearest catalogued galaxy? -------------
        coord = SkyCoord(ra=rec.ra_deg * u.deg, dec=rec.dec_deg * u.deg)
        reg, rerr = retrying(Ned.query_region, coord,
                             radius=args.radius_arcmin * u.arcmin)

        if reg is not None and len(reg) > 0:
            rcol = first_col(reg, ["RA", "RA(deg)"])
            dcol = first_col(reg, ["DEC", "DEC(deg)"])
            rtcol = first_col(reg, ["Type", "Object Type", "type"])
            ncol = first_col(reg, ["Object Name", "Name"])

            if rcol and dcol and rtcol:
                best_sep, best_name, n_gal = np.inf, "", 0
                for r in reg:
                    if str(r[rtcol]).strip() != "G":
                        continue
                    n_gal += 1
                    sep = angular_sep_arcsec(rec.ra_deg, rec.dec_deg,
                                             float(r[rcol]), float(r[dcol]))
                    if sep < best_sep:
                        best_sep, best_name = sep, str(r[ncol]) if ncol else ""
                out["n_galaxies_nearby"] = n_gal
                if np.isfinite(best_sep):
                    out["offset_arcsec"] = best_sep
                    if pd.notna(rec.redshift) and rec.redshift > 0:
                        out["offset_kpc"] = best_sep * kpc_per_arcsec(
                            rec.redshift, cosmo)
        elif rerr:
            out["error"] = rerr

        # --- verdict --------------------------------------------------------
        t = out["ned_type"].upper()
        sep = out["offset_arcsec"]
        if t.startswith("SN"):
            out["verdict"] = "SN_POSITION"
        elif t == "G":
            out["verdict"] = "GALAXY_ENTRY"
        elif np.isfinite(sep) and sep < SAME_OBJECT_ARCSEC:
            out["verdict"] = "GALAXY_ENTRY"
        elif np.isfinite(sep):
            out["verdict"] = "OFFSET_FROM_GALAXY"
        else:
            out["verdict"] = "NO_HOST_FOUND"

        rows.append(out)
        s = f"{sep:6.1f}\"" if np.isfinite(sep) else "   n/a"
        k = f"{out['offset_kpc']:5.2f} kpc" if pd.notna(out["offset_kpc"]) else ""
        print(f"[{i}/{len(df)}] {rec.object:12s} type={out['ned_type']:>10s} "
              f"sep={s} {k:>10s}  {out['verdict']}")
        time.sleep(POLITE_DELAY_S)

    res = pd.DataFrame(rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(args.out_csv, index=False)

    # ---------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("TEST 1 -- what did each name resolve to?")
    print("=" * 72)
    for t, n in res["ned_type"].replace("", "(none)").value_counts().items():
        print(f"  {t:>14s} : {n}")

    n_sn = int(res["verdict"].eq("SN_POSITION").sum())
    n_gal = int(res["verdict"].eq("GALAXY_ENTRY").sum())
    print(f"\n  positions that are the supernova itself : {n_sn}")
    print(f"  positions that are a galaxy centre      : {n_gal}")
    if n_gal:
        print("\n  For these objects the aperture is centred on the nucleus, not")
        print("  on the explosion site. Their 'local' colour is a central colour:")
        print(res.loc[res["verdict"] == "GALAXY_ENTRY",
                      ["object", "ned_resolved_name", "ned_type"]].to_string(index=False))

    print("\n" + "=" * 72)
    print("TEST 2 -- projected distance from the nearest catalogued galaxy")
    print("=" * 72)
    ok = res[np.isfinite(res["offset_kpc"])]
    if len(ok):
        q = ok["offset_kpc"].quantile([0.10, 0.25, 0.50, 0.75, 0.90])
        print(f"  n = {len(ok)}")
        print(f"  p10 {q[0.10]:.2f} | p25 {q[0.25]:.2f} | median {q[0.50]:.2f} | "
              f"p75 {q[0.75]:.2f} | p90 {q[0.90]:.2f}  kpc")
        for thr in (1.0, 2.0, 5.0):
            n = int((ok["offset_kpc"] < thr).sum())
            print(f"  within {thr:.0f} kpc of the host centre: {n} "
                  f"({100 * n / len(ok):.0f}%)")
        print("""
  Interpretation. A 5 kpc aperture centred on a supernova that sits 1 kpc from
  its host's nucleus contains the nucleus. For those objects the measured
  colour is not a local colour in the sense the term implies. This does not
  invalidate the measurement, but it does constrain how the result should be
  described, and it is worth reporting the fraction affected.""")
    else:
        print("  No usable offsets. Check whether the region queries returned "
              "anything -- see the error column.")

    n_nohost = int(res["verdict"].eq("NO_HOST_FOUND").sum())
    if n_nohost:
        print(f"\n  {n_nohost} objects have no catalogued galaxy within "
              f"{args.radius_arcmin} arcmin. Worth inspecting individually: a "
              f"genuinely hostless SN is rare, so this more often means the "
              f"host is uncatalogued or the position is wrong.")

    print(f"\nWrote {args.out_csv}. No existing file was modified.")


if __name__ == "__main__":
    main()