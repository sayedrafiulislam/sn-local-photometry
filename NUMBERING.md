# Script numbering

Scripts are numbered in **execution order**. The number is the run order;
there are no letter suffixes and no exceptions.

To reproduce every result, run 00 through 22 in sequence.

| # | script | was | what it does |
|---|---|---|---|
| 00 | `00_inspect_headers.py` | (unchanged) | read every FITS header |
| 01 | `01_audit_plate_scales.py` | 00b_plate_scale_audit.py | three plate scales, not one |
| 02 | `02_build_catalog.py` | 01_build_catalog.py | filenames plus NED redshifts |
| 03 | `03_retry_failed_ned.py` | 01b_retry_failed_ned.py | alternative name conventions |
| 04 | `04_apply_redshift_cut.py` | 02_apply_redshift_cut.py | 338 to 266 objects |
| 05 | `05_get_positions_and_epochs.py` | 03_get_positions_and_epochs.py | observation dates from headers |
| 06 | `06_measure_psf_fwhm.py` | 04_measure_psf_fwhm.py | seeing, measured per frame |
| 07 | `07_flag_image_quality.py` | 05b_flag_image_quality_corrected.py | quality cuts scaled per frame |
| 08 | `08_summarise_psf.py` | 06b_psf_summary_corrected.py | PSF summary - paper Table 2 |
| 09 | `09_aperture_floor_per_object.py` | 07b_aperture_floor_per_object_corrected.py | smallest trustworthy radius |
| 10 | `10_fetch_sn_coordinates.py` | 08_fetch_sn_coordinates.py | SN positions from NED |
| 11 | `11_spotcheck_sn_coordinates.py` | 09_spotcheck_sn_coordinates.py | visual position check |
| 12 | `12_verify_sn_positions.py` | 09b_verify_sn_positions.py | NED types and host offsets |
| 13 | `13_curve_of_growth.py` | 10c_curve_of_growth_final.py | the core photometry |
| 14 | `14_local_colour_vs_radius.py` | 11b_local_color_vs_radius_corrected.py | brightness into colour |
| 15 | `15_offset_colour_test.py` | 09c_nuclear_contamination_test.py | offset-dependent reddening |
| 16 | `16_offset_colour_permutation.py` | 09d_nuclear_contamination_permutation.py | permutation null for it |
| 17 | `17_apply_zero_points.py` | 15c_apply_zero_points_corrected.py | counts into magnitudes |
| 18 | `18_flag_unreliable_colours.py` | 16c_flag_unreliable_colors.py | two quality criteria |
| 19 | `19_apply_galactic_extinction.py` | 15d_apply_galactic_extinction_corrected.py | Milky Way dust |
| 20 | `20_plot_bv_distribution.py` | 17b_plot_final_bv_distribution_corrected.py | paper Figure 2 |
| 21 | `21_colour_scatter_vs_radius.py` | 18b_color_scatter_corrected.py | paper Figure 3 |
| 22 | `22_annulus_sensitivity.py` | 19_annulus_sensitivity_driver.py | independent cross-check |

## Notes

**Optional steps.** `11_spotcheck_sn_coordinates.py` writes only inspection
images. `22_annulus_sensitivity.py` is an independent cross-check that
nothing depends on, but it validates 14 and 21 and should be run last.

**Independent step.** `05_get_positions_and_epochs.py` reads only the FITS
directory and can run at any time. Use `--skip-ned`: steps 02 and 10
already fetch redshifts and positions, so only the observation dates are new.

**Configuration that must match across steps 13, 14, 17, 18 and 21:**

    ANNULUS_TAG = "ann20-30"

Step 21 verifies this against the `annulus_tag` column in its input and
refuses to run on a mismatch.

**Superseded scripts keep their original names** in `scripts/superseded/`.
Renumbering them would destroy the audit trail; the old numbers are how the
corrections log refers to them.

**Diagnostics** in `scripts/diagnostics/` are read-only checks. They are not
numbered because they are not part of the reproduction path.
