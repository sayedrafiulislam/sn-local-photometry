# Local B–V Aperture Photometry of CSP Type Ia Supernova Host Galaxies

This repository contains the data pipeline for a thesis project extending the local
aperture photometry methodology of Kelsey et al. (2021, MNRAS 501, 4861) from
rest-frame U−R colour to observer-frame B−V colour, using imaging from the Carnegie
Supernova Project (CSP-I and CSP-II) of Type Ia supernova host galaxies.

Kelsey et al. measure host-galaxy colour and stellar mass in a local aperture
centred on the supernova, at a fixed physical radius, and relate these to SN Ia
standardisation residuals. This project builds the equivalent local photometry
pipeline for CSP imaging, using B and V band data from the 1 m Swope and 2.5 m
du Pont telescopes at Las Campanas Observatory, and justifies an aperture radius
for this sample via curve-of-growth analysis rather than adopting Kelsey et al.'s
radius directly.

## Pipeline overview

The pipeline is organised into numbered phases, each producing an auditable,
versioned output rather than overwriting previous results. Where objects or
images are excluded at any stage, the exclusion is logged with a reason rather
than silently dropped.

| Phase | Description | Key scripts |
|---|---|---|
| 0 | U−R → B−V substitution rationale | — (methodological discussion only) |
| 1 | PSF FWHM measurement / seeing floor | `06_measure_psf_fwhm.py`, `05_flag_image_quality.py`, `06_clean_group_summary.py` |
| 2 | Redshift compilation via NED | `02_build_catalog.py`, `04_apply_redshift_cut.py` |
| 3 | SN sky coordinate resolution | `10_fetch_sn_coordinates.py`, `11_spotcheck_sn_coordinates.py` |
| 4 | Curve-of-growth aperture design | `07_aperture_floor_per_object.py`, `10_curve_of_growth.py`, `11_local_color_vs_radius.py`, `12_color_scatter_vs_radius.py`, `14_color_scatter_paired_bootstrap.py` |
| 5 | Zero-point calibration | `15_apply_zero_points.py`, `16_flag_low_flux_colors.py` |

`scripts/diagnostics/` contains one-off visual and statistical sanity checks
generated while developing the pipeline (e.g. plotting flagged images, checking
outlier objects). These aren't part of the linear pipeline but are kept for
transparency and reproducibility of the decisions made along the way.

`scripts/archive/` contains one superseded script (`13_color_scatter_bootstrap.py`),
kept rather than deleted because it documents a real methodological correction:
an initial per-radius-independent bootstrap test was replaced by a paired
bootstrap (`14_color_scatter_paired_bootstrap.py`) that properly accounts for
the same objects appearing at every aperture radius. See the paper's Section on
curve-of-growth aperture design for the full reasoning.

## Current status

- 266/338 objects have a NED-resolved redshift
- PSF seeing characterised per telescope/filter, with 20/715 images excluded and
  logged (defocus, satellite/cosmic-ray trail contamination, host-galaxy
  substructure misidentified as stellar sources)
- Fiducial local aperture radius: **5.0 kpc**, justified via a paired-bootstrap
  significance test on local colour scatter across the sample as a function of
  aperture radius
- 98 objects with a calibrated local B−V colour at the fiducial aperture,
  median B−V = 0.73 mag

See `results/` for the full data products at each stage, and the accompanying
paper (`paper/main.tex`) for the complete methodology and results write-up.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Data availability

Raw CSP FITS imaging is not included in this repository (~total size is
prohibitive for version control) and is expected to sit in a separate local
directory, referenced by an absolute path at the top of each script. Update the
`FITS_DIR` variable in each script if running on a different machine. The
supervisor-provided zero-point calibration files (`data/*.dat`) and the
intermediate/final data products in `results/` are included, since these are
small and are the actual auditable outputs of the pipeline.

## Reproducing the pipeline

Scripts are numbered in pipeline order and are intended to be run sequentially
from the repository root, e.g.:

```powershell
python scripts\02_build_catalog.py
python scripts\04_apply_redshift_cut.py
python scripts\06_measure_psf_fwhm.py
...
```

Each script prints its progress and writes its output to `results/`, generally
without overwriting the previous script's output, so intermediate stages can be
inspected independently.

## Author

Rafid — graduate thesis project.

## Primary reference

Kelsey, L., Sullivan, M., Smith, M., et al. 2021, MNRAS, 501, 4861,
"The effect of environment on Type Ia supernovae in the Dark Energy Survey
three-year cosmological sample"
