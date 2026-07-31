# RENAME_LOG.md — what changed to what

Record of the repository reorganisation carried out after the pipeline audit.
Two operations, in this order:

1. **Restructure** — superseded scripts marked and moved, outputs archived,
   diagnostic images separated, backup generations pruned.
2. **Renumber** — the 23 live scripts renumbered 00–22 in true execution order.

Kept because `PAPER_CORRECTIONS.md`, `AUDIT_SUMMARY.md` and the git history all
refer to scripts by their **old** names. This file is the bridge between them.

---

## 1. Renumbered scripts (the reproduction path)

Twenty-three scripts, renumbered so that **the number is the run order**. No
letter suffixes, no exceptions, nothing that runs out of sequence.

| new | old | why the number changed |
|---|---|---|
| `00_inspect_headers.py` | `00_inspect_headers.py` | unchanged |
| `01_audit_plate_scales.py` | `00b_plate_scale_audit.py` | was a "b" variant |
| `02_build_catalog.py` | `01_build_catalog.py` | shifted by the insertion above |
| `03_retry_failed_ned.py` | `01b_retry_failed_ned.py` | was a "b" variant |
| `04_apply_redshift_cut.py` | `02_apply_redshift_cut.py` | shifted |
| `05_get_positions_and_epochs.py` | `03_get_positions_and_epochs.py` | shifted |
| `06_measure_psf_fwhm.py` | `04_measure_psf_fwhm.py` | shifted |
| `07_flag_image_quality.py` | `05b_flag_image_quality_corrected.py` | corrected version promoted |
| `08_summarise_psf.py` | `06b_psf_summary_corrected.py` | corrected version promoted |
| `09_aperture_floor_per_object.py` | `07b_aperture_floor_per_object_corrected.py` | corrected version promoted |
| `10_fetch_sn_coordinates.py` | `08_fetch_sn_coordinates.py` | shifted |
| `11_spotcheck_sn_coordinates.py` | `09_spotcheck_sn_coordinates.py` | shifted |
| `12_verify_sn_positions.py` | `09b_verify_sn_positions.py` | was a "b" variant |
| `13_curve_of_growth.py` | `10c_curve_of_growth_final.py` | third revision promoted |
| `14_local_colour_vs_radius.py` | `11b_local_color_vs_radius_corrected.py` | corrected version promoted |
| `15_offset_colour_test.py` | `09c_nuclear_contamination_test.py` | **ran out of order** |
| `16_offset_colour_permutation.py` | `09d_nuclear_contamination_permutation.py` | **ran out of order** |
| `17_apply_zero_points.py` | `15c_apply_zero_points_corrected.py` | corrected version promoted |
| `18_flag_unreliable_colours.py` | `16c_flag_unreliable_colors.py` | third revision promoted |
| `19_apply_galactic_extinction.py` | `15d_apply_galactic_extinction_corrected.py` | **ran out of order** |
| `20_plot_bv_distribution.py` | `17b_plot_final_bv_distribution_corrected.py` | corrected version promoted |
| `21_colour_scatter_vs_radius.py` | `18b_color_scatter_corrected.py` | corrected version promoted |
| `22_annulus_sensitivity.py` | `19_annulus_sensitivity_driver.py` | shifted |

### The three that ran out of order

Worth recording, because these were the reason renumbering was necessary rather
than cosmetic.

**`09c` and `09d` → steps 15 and 16.** They were numbered 09 because that is
when they were written, during the position-verification work. But they consume
`local_color_vs_radius_ann20-30.csv`, which step 14 produces. Running them at
position 09 would fail on a missing file, or silently use a stale one.

**`15d` → step 19.** It reads the flagged catalogue that `16c` writes, so the
real order was 15c → 16c → 15d → 17b. Anyone reading the repository would have
assumed 15 → 15b → 16 and been wrong.

### Naming changes beyond the number

| new | old | change |
|---|---|---|
| `13_curve_of_growth.py` | `10c_curve_of_growth_final.py` | dropped "final" — every current script is final |
| `14_local_colour_vs_radius.py` | `11b_local_color_vs_radius_corrected.py` | dropped "corrected"; British spelling |
| `15_offset_colour_test.py` | `09c_nuclear_contamination_test.py` | "nuclear contamination" over-specifies the mechanism; what was measured is a dependence on projected offset |
| `16_offset_colour_permutation.py` | `09d_nuclear_contamination_permutation.py` | same |
| `18_flag_unreliable_colours.py` | `16c_flag_unreliable_colors.py` | British spelling |
| `21_colour_scatter_vs_radius.py` | `18b_color_scatter_corrected.py` | dropped "corrected"; British spelling |
| `22_annulus_sensitivity.py` | `19_annulus_sensitivity_driver.py` | dropped "driver" |

**Output filenames were not changed.** `local_color_vs_radius_ann20-30.csv` and
`calibrated_color_5kpc.csv` keep American spelling, because renaming them would
have meant regenerating everything downstream for no analytical gain.

---

## 2. Superseded scripts

Sixteen files moved to `scripts/superseded/` and tagged. **Their original names
are preserved** — `PAPER_CORRECTIONS.md` refers to them by those names, and
renumbering would break every reference.

| now in `scripts/superseded/` | was | superseded by |
|---|---|---|
| `05_flag_image_quality_SUPERSEDED.py` | `scripts/05_flag_image_quality.py` | step 07 |
| `06_clean_group_summary_SUPERSEDED.py` | `scripts/06_clean_group_summary.py` | step 08 |
| `07_aperture_floor_per_object_SUPERSEDED.py` | `scripts/07_aperture_floor_per_object.py` | step 09 |
| `09e_verify_positions_in_pixels_RETRACTED.py` | `scripts/diagnostics/09e_...py` | **retracted, not replaced** |
| `10_curve_of_growth_SUPERSEDED.py` | `scripts/10_curve_of_growth_SUPERSEDED.py.py` | step 13 |
| `10b_curve_of_growth_annulus_test_SUPERSEDED.py` | `scripts/10b_curve_of_growth_annulus_test.py` | step 13 |
| `11_local_color_vs_radius_SUPERSEDED.py` | `scripts/11_local_color_vs_radius.py` | step 14 |
| `12_color_scatter_vs_radius_SUPERSEDED.py` | `scripts/12_...` (already tagged) | step 21 |
| `13_color_scatter_bootstrap_SUPERSEDED.py` | `scripts/13_color_scatter_bootstrap.py` | step 21 |
| `14_color_scatter_paired_bootstrap_SUPERSEDED.py` | `scripts/14_...` (already tagged) | step 21 |
| `15_apply_zero_points_SUPERSEDED.py` | `scripts/15_apply_zero_points.py` | step 17 |
| `15b_apply_galactic_extinction_SUPERSEDED.py` | `scripts/15b_apply_galactic_extinction.py` | step 19 |
| `16_flag_low_flux_colors_SUPERSEDED.py` | `scripts/16_flag_low_flux_colors.py` | step 18 |
| `16b_flag_unreliable_colors_SUPERSEDED.py` | `scripts/16b_...` (already tagged) | step 18 |
| `17_plot_final_bv_distribution_SUPERSEDED.py` | `scripts/17_plot_final_bv_distribution.py` | step 20 |
| `18_color_scatter_corrected_SUPERSEDED.py` | `scripts/18_color_scatter_corrected.py` | step 21 |

**Deleted:** `scripts/archive/13_color_scatter_bootstrap.py` — an exact
duplicate of the copy in `scripts/`.

**One file had a double extension.** `10_curve_of_growth_SUPERSEDED.py.py`
became `10_curve_of_growth_SUPERSEDED.py`.

### Why keep them at all

They document errors that were found and corrected. Script 14 in particular
contains the three statistical faults — a reference radius chosen from the data,
a 68 per cent interval used as a significance threshold, and eighteen
comparisons with no multiplicity correction — that turned a null result into an
apparent discovery. Deleting it would remove the evidence that the error was
found rather than never made.

---

## 3. Promoted from diagnostics to the pipeline

Three scripts were living in `scripts/diagnostics/` but are pipeline steps.

| now | was |
|---|---|
| `scripts/12_verify_sn_positions.py` | `scripts/diagnostics/09b_verify_sn_positions.py` |
| `scripts/15_offset_colour_test.py` | `scripts/diagnostics/09c_nuclear_contamination_test.py` |
| `scripts/16_offset_colour_permutation.py` | `scripts/diagnostics/09d_nuclear_contamination_permutation.py` |

Step 12 writes `sn_position_verification.csv`, which steps 15 and 16 require.
Steps 15 and 16 produce the offset–colour result. None of the three is optional
or read-only, which is what `diagnostics/` is for.

`09e` went the other way — from `diagnostics/` to `superseded/`, tagged
`_RETRACTED`.

---

## 4. Files moved

### Images out of `images/`

| now | was |
|---|---|
| `results/phase0_catalog/redshift_distribution.png` | `images/redshift_distribution.png` |

The `images/` folder held one file and is now empty.

### Offset–colour outputs consolidated

Four files moved from `results/` into `results/phase4_aperture/`, where the rest
of the phase-4 outputs live:

```
nuclear_contamination_ann20-30_per_object.csv
nuclear_contamination_ann20-30_profiles.png
nuclear_permutation_ann20-30_null.png
nuclear_permutation_ann20-30_results.csv
```

### Outputs archived — `results/archive/`

Twenty files that no current script reads.

| file | superseded by |
|---|---|
| `curve_of_growth.csv` | the tagged `curve_of_growth_ann*.csv` |
| `color_scatter_summary.csv` | step 21 |
| `color_scatter_vs_radius.png` | step 21 |
| `color_scatter_bootstrap.csv` / `.png` | step 21 |
| `color_scatter_paired_bootstrap.csv` / `.png` | step 21 |
| `nuclear_contamination_profiles.png` | the `_ann20-30` version |
| `nuclear_permutation_null.png` | the `_ann20-30` version |
| `nuclear_contamination_per_object.csv` | the `_ann20-30` version |
| `nuclear_permutation_results.csv` | the `_ann20-30` version |
| `aperture_floor_per_object.csv` | step 09's corrected version |
| `local_color_vs_radius_pre_annulus_fix.csv` | manual backup |
| `local_color_vs_radius_pre10c.csv` | manual backup |
| `calibrated_color_5kpc_pre_annulus_fix.csv` | manual backup |
| `psf_fwhm_summary.csv` | step 08 |
| `psf_fwhm_summary_clean.csv` | step 08 |
| `image_quality_flags.csv` | step 07 |
| `excluded_images_phase1.csv` | step 07 |
| `swo_tail_check.csv` | one-off check |

Two of these — `color_scatter_bootstrap.csv` and `.png` — are **orphaned**:
their producing script is missing from disk. Either recreate it or delete them;
results no script can regenerate are not reproducible.

### Diagnostic images — `results/diagnostics/`

Fourteen large PNGs (~8 MB) moved out of the results folders. Visual inspection
only; nothing reads them.

```
diagnostic_ASAS14lq_V_comb_swo.png    spotcheck_ASAS14ad.png
diagnostic_ASAS14mw_V_comb_swo.png    spotcheck_KISS13v.png
diagnostic_SN07ol_V_comb_dup.png      spotcheck_SN2012fr.png
diagnostic_SN2012fr_B_comb_dup.png    aperture_overlay_ASAS14ad.png
cog_check_ASAS14ad.png                aperture_overlay_KISS13v.png
cog_check_KISS13v.png                 color_check_ASAS14ad.png
cog_check_SN2012fr.png                color_check_KISS13v.png
```

### Repository root

| now | was |
|---|---|
| `tools/show_structure.ps1` | root |
| `tools/show_clutter.ps1` | root |
| `tools/fix_docstrings.py` | root |

Deleted: `structure_audit.txt` (generated report).

---

## 5. Backups pruned

Twenty `.bak_*` files totalling 7.7 MB. The **oldest of each group** was kept —
that is the pre-audit state, worth retaining until the paper is submitted — and
the intermediate re-runs deleted.

| kept | deleted |
|---|---|
| `annulus_setting_comparison.csv.bak_20260728_161036` | — |
| `curve_of_growth_ann10-15.csv.bak_20260728_161035` | — |
| `curve_of_growth_ann15-25.csv.bak_20260728_161035` | — |
| `curve_of_growth_ann20-30.csv.bak_20260728_161035` | — |
| `local_color_vs_radius.csv.bak_20260728_215234` | 4 later generations |
| `local_color_vs_radius_ann20-30.csv.bak_20260728_220638` | 3 later generations |
| `calibrated_color_5kpc.csv.bak_20260729_021820` | — |
| `calibrated_color_5kpc_flagged.csv.bak_20260729_024544` | 1 later generation |
| `calibrated_color_5kpc_dered.csv.bak_20260729_104134` | — |
| `bv_distribution.png.bak_20260729_104141` | — |
| `color_scatter_corrected.csv.bak_20260729_104945` | — |
| `color_scatter_corrected.png.bak_20260729_104945` | — |

Nine deletions, all redundant re-runs from within a single session.

---

## 6. Cross-references rewritten

Renaming files breaks the references inside them. Two passes handled it.

**Full filenames** — 23 replacements applied across every live script, `.md` and
`.ps1` file. For example `"Run 10c_curve_of_growth_final.py first"` became
`"Run 13_curve_of_growth.py first"`. Replacements ran longest-name-first so that
`15c_apply_zero_points_corrected.py` could not be partially matched.

**Bare tokens** — prose referred to scripts as `09c`, `11b`, `16c` without the
extension, which the first pass missed. These were mapped to step numbers:

```
09b -> step 12    10c -> step 13    15c -> step 17    17b -> step 20
09c -> step 15    11b -> step 14    15d -> step 19    18b -> step 21
09d -> step 16                      16c -> step 18
```

Tokens for superseded scripts — `10b`, `15b`, `16b`, `09e` — were deliberately
left alone, so sentences like *"Supersedes 10b_curve_of_growth_annulus_test.py"*
remain accurate.

Three stale passages also needed rewording rather than renaming: an obsolete
naming rationale in step 17, a run-order instruction naming superseded scripts,
and a warning in step 18 that step 19 needed updating — which it already had
been. Script 16's docstring additionally quoted the pre-audit result values
(+0.0197 mag across 98 objects); corrected to +0.0220 across 101.

---

## 7. What deliberately did NOT change

| item | why |
|---|---|
| output CSV and PNG filenames | renaming would mean regenerating everything downstream for no analytical gain |
| superseded script names | `PAPER_CORRECTIONS.md` refers to them by those names |
| `PAPER_CORRECTIONS.md` numbering | its entries describe what 10b, 15b and 16 did wrong; those files still carry those names |
| `main.tex` | it never referenced script names, so the renumbering could not affect it |
| `reorganize_repo.ps1` | left in the root — check whether it is superseded before deleting |
| `results/phase*` folder names | phase grouping still matches the narrative in `pipeline_map.md` |

---

## 8. Tools used

Kept in `tools/`, all dry-run by default.

| script | what it did |
|---|---|
| `restructure.ps1` | 70 actions: marked and moved superseded scripts, archived outputs, pruned backups |
| `renumber.ps1` | 49 actions: two-pass rename via staging names, plus cross-reference rewriting |
| `fix_docstrings.py` | 23 changes: bare tokens and stale phrases the rename could not catch |
| `show_structure.ps1` | reports the layout |
| `show_clutter.ps1` | reports backups, stray images, orphaned outputs |

The two-pass rename was necessary because several new names collided with
existing old ones — `01_build_catalog` becomes `02_build_catalog` while
`02_apply_redshift_cut` still exists. Everything moved to `__staging__*` first.

Each operation was committed separately, so any of them can be reverted alone:

```
Restructure after pipeline audit
Renumber pipeline scripts in execution order
Update Readme, run_pipeline and docstring references
Rebuild RUN_ORDER and pipeline_map for the new numbering
```