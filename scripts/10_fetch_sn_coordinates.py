"""
10_fetch_sn_coordinates.py

Phase 3, Question 2 / Phase 4 dependency: fetch a sky position (RA/Dec)
for every SN host galaxy with a resolved redshift, so that curve-of-
growth photometry apertures can be placed automatically rather than by
manual DS9 inspection.

Reuses the ned_resolved_name column already present in
sn_catalog_final.csv (the exact name NED recognized during Phase 2),
so no alternate-name generation is needed here -- we already know
which name NED accepts for each object.

NOTE: this queries the *object*, not the SN explosion site specifically.
NED's positional entry for a supernova is normally the SN position
itself (as reported to IAU/TNS), not the host galaxy centre -- but this
is worth a quick manual spot-check against DS9 for 2-3 objects before
trusting it for the full sample, since it directly determines where
your local aperture gets centred. Flagged clearly at the end of this
script's output.

Retry logic mirrors Phase 2: exponential backoff (2s/4s/8s) only for
genuine timeouts, not clean "not found" responses.
"""

import time
import pandas as pd
from astroquery.ipac.ned import Ned
import requests

CATALOG_CSV = r"D:\Thesis\My Work\sn-local-photometry\results\sn_catalog_final.csv"
OUT_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates.csv"
FAILED_LOG_PATH = r"D:\Thesis\My Work\sn-local-photometry\results\sn_coordinates_failed.csv"

MAX_RETRIES = 3
BACKOFF_SECONDS = [2, 4, 8]
POLITE_DELAY_SECONDS = 1.0  # be a reasonable citizen of NED's servers over ~266 queries


def get_ra_dec(name):
    """
    Query NED for a single object's position. Returns (ra_deg, dec_deg, error)
    where error is None on success or a short string reason on failure.
    """
    for attempt in range(MAX_RETRIES):
        try:
            result = Ned.query_object(name)
            if result is None or len(result) == 0:
                return None, None, "no_ned_entry"

            row = result[0]
            # Column naming has varied across astroquery versions -- try
            # the modern name first, fall back to the older one.
            for ra_col, dec_col in [("RA", "DEC"), ("RA(deg)", "DEC(deg)")]:
                if ra_col in result.colnames and dec_col in result.colnames:
                    return float(row[ra_col]), float(row[dec_col]), None

            return None, None, f"unexpected_columns:{result.colnames}"

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])
                continue
            return None, None, "timeout_after_retries"
        except Exception as e:
            # Non-timeout errors (e.g. NED-side "object not recognized")
            # are not retried -- retrying won't fix a genuine non-match.
            return None, None, f"error:{type(e).__name__}:{e}"

    return None, None, "unknown_failure"


def main():
    catalog = pd.read_csv(CATALOG_CSV)

    # One row per object, using the confirmed NED name from Phase 2
    objects = (
        catalog[["object", "ned_resolved_name", "redshift"]]
        .drop_duplicates(subset="object")
        .dropna(subset=["ned_resolved_name"])
    )
    print(f"Querying NED for positions of {len(objects)} objects...\n")

    results = []
    for i, row in enumerate(objects.itertuples(index=False), 1):
        name = row.ned_resolved_name
        ra, dec, error = get_ra_dec(name)
        status = "ok" if ra is not None else f"FAILED ({error})"
        print(f"[{i}/{len(objects)}] {row.object} ({name}) -> {status}")

        results.append({
            "object": row.object,
            "ned_resolved_name": name,
            "redshift": row.redshift,
            "ra_deg": ra,
            "dec_deg": dec,
            "error": error,
        })
        time.sleep(POLITE_DELAY_SECONDS)

    results_df = pd.DataFrame(results)

    ok = results_df[results_df["ra_deg"].notna()]
    failed = results_df[results_df["ra_deg"].isna()]

    ok.drop(columns=["error"]).to_csv(OUT_PATH, index=False)
    failed.to_csv(FAILED_LOG_PATH, index=False)

    print(f"\nResolved coordinates for {len(ok)}/{len(objects)} objects -> {OUT_PATH}")
    if len(failed) > 0:
        print(f"{len(failed)} objects failed -- logged with reasons -> {FAILED_LOG_PATH}")

    print("\n[IMPORTANT] NED's position entry for a supernova is normally the "
          "explosion site itself (as reported to IAU/TNS), not the host "
          "galaxy's centre -- but this has NOT been verified against your "
          "actual images yet. Before trusting this for the full sample, "
          "spot-check 2-3 objects: convert the RA/Dec here to a pixel "
          "position via each image's WCS, and confirm it visually lands "
          "on the SN (or its former position) rather than the galaxy "
          "nucleus or some other point.")


if __name__ == "__main__":
    main()