# Local B–V Aperture Photometry of CSP Type Ia Supernova Host Galaxies

Data pipeline for a thesis project extending the local aperture photometry
methodology of Kelsey et al. (2021, MNRAS 501, 4861) from rest-frame U−R colour
to observer-frame B−V, using Carnegie Supernova Project (CSP-I and CSP-II)
imaging of Type Ia supernova host galaxies.

Kelsey et al. measure host colour and stellar mass in a fixed physical aperture
centred on the supernova and relate these to SN Ia standardisation residuals.
This project builds the equivalent local photometry for CSP imaging in B and V
from the 1 m Swope and 2.5 m du Pont telescopes at Las Campanas, and tests the
aperture radius directly rather than adopting one from the literature.

## Results

| | |
|---|---|
| final sample | **85 host galaxies** (CSP-II only — see below) |
| median local B−V at 5.0 kpc | **0.649 mag**, 95% CI [0.590, 0.706] |
| 16th–84th percentile | 0.448 – 0.898 mag |
| robust scatter (σ_MAD) | 0.267 mag |
| median per-object uncertainty | 0.109 mag (a lower bound) |
| aperture radius test | **0 of 18 radii significant**, smallest q = 0.665 |
| offset–colour effect | **+0.022 mag**, p = 0.001 |

**The catalogue is CSP-II only.** The supplied zero-point files cover CSP-II and
do not cover CSP-I: of the 209 objects with a local colour at the fiducial
radius, 90 CSP-I objects have no zero point and 111 of 112 CSP-II objects do.
This is a cut by survey campaign rather than by data quality and is the largest
single reduction in the sample.

**A new result.** Local colours measured in apertures that reach the host's
inner regions are systematically redder by 0.022 mag (95% interval 0.014–0.033).
The effect scales with the supernova's projected galactocentric distance and is
significant at p = 0.001 against a permutation null that breaks the pairing
between colour profiles and offsets.

**A withdrawn result.** An earlier version reported significantly elevated
colour scatter across 1.5–4.5 kpc. Three statistical errors produced it: a
reference radius selected from the data, a 68 per cent interval used as a
significance threshold, and 18 comparisons with no multiplicity correction.
Corrected, no radius differs significantly from the pre-specified reference.
See `PAPER_CORRECTIONS.md`.

## Reproducing the pipeline

Scripts are numbered **00 to 22 in true execution order**. The number is the run
order — no letter suffixes, no exceptions. See `NUMBERING.md` for the map from
the previous scheme and `RUN_ORDER.md` for what each step reads and writes.

```powershell
.\run_pipeline.ps1 -DryRun      # print the commands
.\run_pipeline.ps1              # run everything
.\run_pipeline.ps1 -Phase 4     # one phase
.\run_pipeline.ps1 -SkipSlow    # skip steps 06 and 13
```

Or run steps individually from the repository root:

```powershell
python scripts\00_inspect_headers.py
python scripts\01_audit_plate_scales.py
...
```

| Phase | Steps | What it does |
|---|---|---|
| 0 | 00–01 | read every FITS header; audit the plate scales |
| 1 | 02–05 | catalogue, NED redshifts, observation epochs |
| 2 | 06–09 | seeing per frame, quality flags, aperture floor |
| 3 | 10–12 | SN positions, verification, host offsets |
| 4 | 13–14 | curve-of-growth photometry, local colour |
| 5 | 15–16 | the offset–colour result and its permutation null |
| 6 | 17–22 | zero points, quality cuts, extinction, figures |

**`ANNULUS_TAG = "ann20-30"` must match across steps 13, 14, 17, 18 and 21.**
Step 21 verifies this against the `annulus_tag` column in its input and refuses
to run on a mismatch.

## Repository layout

```
scripts/              steps 00-22, the reproduction path
scripts/superseded/   earlier versions, kept as the audit trail
scripts/diagnostics/  read-only checks, not part of the pipeline
results/              outputs by phase
results/archive/      outputs no current script reads
results/diagnostics/  visual inspection images
paper/                main.tex
tools/                repository maintenance scripts
data/                 supervisor-provided zero-point files
```

`scripts/superseded/` holds sixteen files under their original names. They are
retained rather than deleted because they document errors that were found and
corrected, and `PAPER_CORRECTIONS.md` refers to them by their original numbers.

## Conventions

Established during a script-by-script audit of the whole pipeline, which
produced 54 corrections and replaced eight scripts:

- **Never overwrite.** Existing outputs are renamed `*.bak_YYYYmmdd_HHMMSS`.
- **Provenance travels with the data.** Outputs carry an `annulus_tag` column,
  not just a tag in the filename.
- **Flag, never drop.** Exclusions are logged with a reason. Step 14 checksums
  its sample funnel and fails loudly if objects go unaccounted for.
- **No absolute thresholds.** Every cut is expressed relative to something the
  object itself supplies. The opposite error was found six times independently.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r Requirements.txt
```

## Data availability

Raw CSP FITS imaging is not in this repository — too large for version control —
and is expected in a separate local directory referenced by `FITS_DIR` at the
top of each script, or by `-DataDir` in `run_pipeline.ps1`.

The supervisor-provided zero-point files (`data/*.dat`) and all intermediate and
final products in `results/` are included, since they are small and are the
auditable outputs of the pipeline.

Galactic extinction (step 19) additionally requires the SFD98 dust maps and the
`sfdmap` package.

## Documentation

| file | contents |
|---|---|
| `NUMBERING.md` | step numbers and the map from the old scheme |
| `RUN_ORDER.md` | dependencies, inputs and outputs per step |
| `pipeline_map.md` | narrative account of what was built and why |
| `PAPER_CORRECTIONS.md` | 54 corrections found during the audit |
| `SUPERVISOR_QUESTIONS.md` | open questions, with evidence attached |
| `AUDIT_SUMMARY.md` | overview of the audit and its findings |

## Author

Rafid — graduate thesis project.

## Primary reference

Kelsey, L., Sullivan, M., Smith, M., et al. 2021, MNRAS, 501, 4861,
"The effect of environment on Type Ia supernovae in the Dark Energy Survey
three-year cosmological sample"