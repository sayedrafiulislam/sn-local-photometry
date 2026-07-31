# RUN_ORDER.md — reproducing every result

Repository: `D:\Thesis\My Work\sn-local-photometry`
FITS archive: `D:\Thesis\pd\CSPAll`

Scripts are numbered **00 to 22 in true execution order**. The number is the run
order. No letter suffixes, no exceptions, nothing that runs out of sequence.

```powershell
.\run_pipeline.ps1 -DryRun      # print the commands without running them
.\run_pipeline.ps1              # everything
.\run_pipeline.ps1 -Phase 4     # one phase
.\run_pipeline.ps1 -SkipSlow    # skip 06 and 13, which read every FITS file
.\run_pipeline.ps1 -SkipNetwork # skip 02, 03, 10, 12, which query NED
```

Always `cd` to the repository root first.

---

## Two things to know before running

**`ANNULUS_TAG = "ann20-30"` must match across steps 13, 14, 17, 18 and 21.**
If they disagree, the colours analysed will not correspond to the catalogue.
Step 21 verifies this against the `annulus_tag` column in its input and refuses
to run on a mismatch.

**Twelve steps use hard-coded paths rather than command-line arguments** — 06,
10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22. The `-DataDir` switch does not reach
them. If you move the FITS archive, edit `FITS_DIR` at the top of steps 06 and
13, which are the only ones that read raw frames.

---

## Phase 0 — Reconnaissance

| # | script | reads | writes |
|---|---|---|---|
| 00 | `00_inspect_headers.py` | FITS archive | `header_summary_full.csv` |
| 01 | `01_audit_plate_scales.py` | `header_summary_full.csv` | `plate_scale_status.csv` |

**00 must run over every frame.** The original reconnaissance used a `--limit`
flag and, because the file listing is alphabetical, sampled only du Pont frames.
That produced the single-plate-scale assumption which propagated for months.

Establishes: 716 frames, all readable, all with a usable WCS, no redshift
keyword anywhere, and three distinct plate scales — 0.230″ (585 frames), 0.430″
(119, all Swope V) and 0.159″ (12).

## Phase 1 — Catalogue, redshifts and epochs

| # | script | reads | writes |
|---|---|---|---|
| 02 | `02_build_catalog.py` | FITS filenames, NED | `sn_catalog_v2.csv` |
| 03 | `03_retry_failed_ned.py` | `excluded_objects_log.csv`, NED | `ned_retry_results.csv` |
| 04 | `04_apply_redshift_cut.py` | `sn_catalog_v2.csv` | `sn_catalog_final.csv`, `excluded_objects_log.csv` |
| 05 | `05_get_positions_and_epochs.py` | FITS archive | `phase0_catalog/positions_epochs.csv` |

**338 objects in, 266 out.** Nine excluded on a transient NED server error
rather than a genuine absence of redshift; they still need re-querying.

**Run 05 with `--skip-ned`.** Steps 02 and 10 already fetch redshifts and
positions; only the observation dates are new. Those dates are what address the
open question of whether the stacks contain supernova light.

## Phase 2 — Image quality

| # | script | reads | writes |
|---|---|---|---|
| 06 | `06_measure_psf_fwhm.py` | FITS archive | `phase1_psf/psf_fwhm_per_star.csv`, `per_file_summary.csv` |
| 07 | `07_flag_image_quality.py` | per-star table, `header_summary_full.csv` | `image_quality_flags_corrected.csv`, `excluded_images_phase1_corrected.csv` |
| 08 | `08_summarise_psf.py` | per-star table, plate scales, exclusions | `psf_fwhm_summary_corrected.csv` → **paper Table 2** |
| 09 | `09_aperture_floor_per_object.py` | per-star table, flags, `sn_catalog_final.csv` | `phase4_aperture/aperture_floor_per_object_corrected.csv` |

**06 is slow** — it opens every FITS file. Everything downstream works from the
per-star table, so it only needs re-running if the raw data changes.

Step 07 scales its thresholds to each frame's own plate scale and rejects
detections narrower than half their frame's median width — 876 cosmic rays and
hot pixels, 5.1 per cent of detections.

Step 08 bootstraps over **images**, not stars: the ~24 stars in one frame share
that frame's atmosphere and are not independent.

## Phase 3 — Supernova positions

| # | script | reads | writes |
|---|---|---|---|
| 10 | `10_fetch_sn_coordinates.py` | `sn_catalog_final.csv`, NED | `sn_coordinates.csv` |
| 11 | `11_spotcheck_sn_coordinates.py` | `sn_coordinates.csv`, FITS | inspection PNGs |
| 12 | `12_verify_sn_positions.py` | `sn_coordinates.csv`, NED | `sn_position_verification.csv` |

**11 is optional** — visual confirmation only, no downstream dependency.

**12 is required by steps 15 and 16.** It confirms all 266 objects are NED type
`SN` — the coordinates are explosion sites, not galaxy centres — and measures
each supernova's projected offset from its host centre (median 4.22 kpc, 58 per
cent within 5 kpc).

## Phase 4 — Photometry and colour

| # | script | reads | writes |
|---|---|---|---|
| 13 | `13_curve_of_growth.py` | FITS, `aperture_floor_per_object_corrected.csv`, `sn_coordinates.csv` | `curve_of_growth_ann{10-15,15-25,20-30}.csv`, `annulus_setting_comparison.csv` |
| 14 | `14_local_colour_vs_radius.py` | `curve_of_growth_ann20-30.csv` | `local_color_vs_radius_ann20-30.csv` + untagged copy |

**13 is the slow step** — one pass over 541 frames, roughly 20–40 minutes.

**Check that 14 prints `accounted for : 266 of 266`.** If it does not, objects
are being lost without a recorded reason and something upstream has changed.

14 writes two identical files. The tagged one is canonical; the untagged copy
exists so older scripts keep working.

## Phase 5 — The offset–colour result

| # | script | reads | writes |
|---|---|---|---|
| 15 | `15_offset_colour_test.py` | `local_color_vs_radius_ann20-30.csv`, `sn_position_verification.csv` | `nuclear_contamination_ann20-30_*` |
| 16 | `16_offset_colour_permutation.py` | same two files | `nuclear_permutation_ann20-30_*` |

Both take `--colors`, `--positions` and `--out-prefix`; `run_pipeline.ps1`
supplies them.

**These consume step 14's output**, which is why they run here and not at 09.
Under the old numbering they were 09c and 09d, and the numbering lied about the
order. Nothing downstream depends on them.

## Phase 6 — Calibration and results

| # | script | reads | writes |
|---|---|---|---|
| 17 | `17_apply_zero_points.py` | `curve_of_growth_ann20-30.csv`, `B_ZP_dup.dat`, `V_ZP_dup.dat` | `calibrated_color_5kpc.csv`, exclusions log |
| 18 | `18_flag_unreliable_colours.py` | above + curve of growth + ZP files | `calibrated_color_5kpc_flagged.csv` |
| 19 | `19_apply_galactic_extinction.py` | flagged catalogue, `sn_coordinates.csv`, SFD maps | `calibrated_color_5kpc_dered.csv` |
| 20 | `20_plot_bv_distribution.py` | dereddened catalogue | `bv_distribution.png`, summary txt → **paper Figure 2** |
| 21 | `21_colour_scatter_vs_radius.py` | `local_color_vs_radius_ann20-30.csv`, flagged catalogue | `color_scatter_corrected.csv/.png` → **paper Figure 3** |
| 22 | `22_annulus_sensitivity.py` | all three `curve_of_growth_ann*.csv` | `annulus_sensitivity_summary.csv/.png` |

17 reads the curve-of-growth file directly rather than step 14's output, so it
applies both geometric guards itself. **Watch its epoch crosstab** — the supplied
zero points cover CSP-II only.

19 requires the SFD98 dust maps at `D:\Thesis\dustmaps` and the `sfdmap` package.

**Downstream must filter on `flag_exclude`, not `flag_low_flux`.** The latter is
retained by step 18 for comparison only.

21 uses `flag_exclude` **only** to derive the median per-object uncertainty for
scale. It deliberately does not apply it to the colour profiles, because those
are instrumental colours in which the zero point cancels. Objects excluded from
the calibrated catalogue for a poor zero point have perfectly sound instrumental
colours — several are among the best-measured in the sample. The same reasoning
applies to steps 15 and 16.

22 reimplements steps 14 and 21 internally and runs the full chain once per
annulus setting. Its agreement with step 14 on four independent quantities is a
meaningful validation, so **do not refactor it to import from them**.

---

## Diagnostics

Read-only. They open CSV files, print numbers, and change nothing. Safe to run
in any order. Kept in `scripts/diagnostics/`.

| script | what it establishes |
|---|---|
| `check_annulus_diagnostics.py` | the rewrite reproduced the original exactly (10184/10184 rows, zero difference) |
| `check_background_bias_millimag.py` | per-object flux bias from the annulus change |
| `check_colour_shift_vs_flux.py` | the annulus shift is flux-dependent: 2.5 mmag brightest quartile, 33.2 faintest |
| `check_systematic_on_final_catalogue.py` | the systematic on the published objects specifically |
| `check_lowflux_cut_effectiveness.py` | total flux predicts the shift better than surface brightness |
| `check_annulus_censoring.py` | only 7 objects censored; the change is one-directional; floor at ~1400 counts |
| `check_catalogue_delta.py` | which objects the corrected pipeline gains and loses |
| `check_lost_four.py`, `check_vanished_objects.py` | names every object lost to the geometric guards |
| `check_zp_flag_validity.py` | refutes the ZP-difference criterion: only 3 of 8 flagged were real failures |
| `check_cut_sensitivity.py` | the median varies by 0.046 mag across a 5×5 threshold grid |
| `check_contamination_v2.py`, `_v3.py` | background is under 1 per cent of enclosed flux; no contamination case in the catalogue |
| `check_scatter_common_sample.py`, `check_seeing_vs_scatter.py` | refute survivorship and seeing as causes of the small-radius dip |
| `check_background_outliers.py` | **withdrawn** — pooled B and V, absolute threshold across two campaigns, MAD on a skewed quantity |

---

## Superseded scripts

`scripts/superseded/` holds sixteen files under their **original** names. They
are kept rather than deleted because they document errors that were found and
corrected, and `PAPER_CORRECTIONS.md` refers to them by their original numbers.

Renumbering them would destroy that link. They are not part of the reproduction
path and nothing reads their outputs.

`09e_verify_positions_in_pixels_RETRACTED.py` is a separate case: its
diagnostics used a fixed 3.0″ threshold across a factor of 37 in redshift, so
they selected nearby galaxies rather than bad positions. Its centroid test also
assumed B and V centroids should coincide, which presumes galaxies have no
internal colour structure — the very thing this project measures.

---

## Conventions

**Never overwrite.** Existing outputs are renamed `*.bak_YYYYmmdd_HHMMSS`. Three
scripts previously used a one-shot backup — `if not os.path.exists(backup)` —
which silently stopped protecting anything after its first run.

**Provenance travels with the data.** Outputs carry an `annulus_tag` column, not
only a tag in the filename. Step 21 verifies it on input.

**Flag, never drop.** Exclusions are recorded with a reason. Step 14 checksums
its funnel and fails loudly if objects go unaccounted for; step 17 writes an
exclusion log; step 18 writes four separate flags plus a combined one.

**No absolute thresholds.** Every cut is expressed relative to something the
object itself supplies. The opposite error was found six times independently,
including once in a diagnostic written during the audit.

---

## Open items

1. **Nine objects excluded on a NED server error** need re-querying against a
   healthy service.
2. **Script 13 from the old numbering is missing from disk** while its outputs
   remain in `results/archive/`. Either recreate it or delete the orphans —
   results no script can regenerate are not reproducible.
3. **CSP-I zero points.** Whether they exist is the highest-value outstanding
   question; if they do, the calibrated sample roughly doubles.