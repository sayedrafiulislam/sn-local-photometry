<#
.SYNOPSIS
    Runs the SN local photometry pipeline in the corrected order.

.DESCRIPTION
    The script numbering is not the run order. This driver encodes the real
    dependency chain documented in RUN_ORDER.md:

        00 -> 00b -> 01 -> 02 -> 04 -> 05b -> 06b -> 08 -> 07b
           -> 10 -> 10b -> 11 -> 18 -> 19 -> 15 -> 16 -> 15b -> 17

    Departures from the numbering, and why:
      - There is no script 03.
      - 08 (SN coordinates) runs before 07b, because 10 needs both and 07b
        does not depend on coordinates.
      - 15b runs after 16, because it requires the flag_low_flux column that
        16 creates. The "b" suffix is misleading.
      - 05b, 06b and 07b supersede 05, 06 and 07.
      - 12, 13 and 14 are superseded by 18 and are not run.

.PARAMETER DataDir
    Directory containing the CSP FITS frames.

.PARAMETER Phase
    Which phase to run: All, 0, 1, 2, 3, 4, 5. Default All.

.PARAMETER SkipSlow
    Skip scripts 04 and 10, which reopen every FITS file and take a long time.
    Useful when only downstream logic has changed.

.PARAMETER DryRun
    Print the commands without executing them.

.EXAMPLE
    .\run_pipeline.ps1 -Phase 2
    .\run_pipeline.ps1 -SkipSlow
    .\run_pipeline.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [string]$DataDir = "D:\Thesis\pd\CSPAll",
    [ValidateSet("All", "0", "1", "2", "3", "4", "5")]
    [string]$Phase = "All",
    [switch]$SkipSlow,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Always operate from the repository root. Scripts 00-02 take command-line
# arguments and resolve relative paths against the working directory, so
# running from scripts\ silently creates a second results\ tree.
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$S = Join-Path $Root "scripts"
$R = Join-Path $Root "results"
$P1 = Join-Path $R "phase1_psf"
$P4 = Join-Path $R "phase4_aperture"
$P5 = Join-Path $R "phase5_calibration"

$script:StepNumber = 0

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Script,
        [string[]]$Arguments = @(),
        [switch]$Slow,
        [switch]$Diagnostic,
        [string]$Note
    )

    $script:StepNumber++
    $tag = if ($Diagnostic) { "diagnostic" } elseif ($Slow) { "SLOW" } else { "" }

    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host ("[{0,2}] {1} {2}" -f $script:StepNumber, $Name, $(if ($tag) { "($tag)" } else { "" })) -ForegroundColor Cyan
    if ($Note) { Write-Host "     $Note" -ForegroundColor DarkYellow }
    Write-Host ("=" * 78) -ForegroundColor DarkGray

    $path = Join-Path $S $Script
    if (-not (Test-Path $path)) {
        Write-Host "     SKIPPED - $Script not found" -ForegroundColor Red
        return
    }

    if ($Slow -and $SkipSlow) {
        Write-Host "     SKIPPED - -SkipSlow was specified" -ForegroundColor Yellow
        return
    }

    $cmd = "python `"$path`" " + ($Arguments -join " ")
    if ($DryRun) {
        Write-Host "     $cmd" -ForegroundColor DarkGray
        return
    }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & python $path @Arguments
    $sw.Stop()

    if ($LASTEXITCODE -ne 0) {
        throw "$Script exited with code $LASTEXITCODE. Pipeline halted."
    }
    Write-Host ("     done in {0:n1}s" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
}

function Test-Phase { param([string]$N) return ($Phase -eq "All" -or $Phase -eq $N) }

Write-Host "Repository root: $Root"
Write-Host "FITS directory : $DataDir"
Write-Host "Phase          : $Phase"
if ($SkipSlow) { Write-Host "Skipping slow steps (04, 10)" -ForegroundColor Yellow }
if ($DryRun) { Write-Host "DRY RUN - nothing will be executed" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# Phase 0 - Reconnaissance
# ---------------------------------------------------------------------------
if (Test-Phase "0") {
    Invoke-Step -Name "Inspect FITS headers" -Script "00_inspect_headers.py" `
        -Note "Do NOT pass --limit. The original limited run sampled only du Pont frames and produced the single-plate-scale assumption (C2)." `
        -Arguments @("--data-dir", "`"$DataDir`"", "--out-csv", "`"$R\header_summary_full.csv`"")

    Invoke-Step -Name "Plate scale audit" -Script "01_audit_plate_scales.py" -Diagnostic `
        -Arguments @("--summary-csv", "`"$R\header_summary_full.csv`"",
                     "--catalog-csv", "`"$P5\calibrated_color_5kpc_flagged.csv`"",
                     "--out-csv", "`"$R\plate_scale_status.csv`"")
}

# ---------------------------------------------------------------------------
# Phase 1 - Catalogue and redshifts
# ---------------------------------------------------------------------------
if (Test-Phase "1") {
    Invoke-Step -Name "Build catalogue and query NED" -Script "02_build_catalog.py" `
        -Note "Queries NED for every unique object. Requires network." `
        -Arguments @("--data-dir", "`"$DataDir`"", "--out-csv", "`"$R\sn_catalog_v2.csv`"")

    Invoke-Step -Name "Split on redshift availability" -Script "04_apply_redshift_cut.py" `
        -Arguments @("--in-csv", "`"$R\sn_catalog_v2.csv`"",
                     "--out-csv", "`"$R\sn_catalog_final.csv`"",
                     "--excluded-csv", "`"$R\excluded_objects_log.csv`"")

    Invoke-Step -Name "Retry failed NED queries" -Script "03_retry_failed_ned.py" -Diagnostic `
        -Note "Only informative when NED's name-checker backend is healthy. If most results come back STILL_ERRORING, rerun later." `
        -Arguments @("--log-csv", "`"$R\excluded_objects_log.csv`"",
                     "--out-csv", "`"$R\ned_retry_results.csv`"")
}

# ---------------------------------------------------------------------------
# Phase 2 - PSF characterisation
# ---------------------------------------------------------------------------
if (Test-Phase "2") {
    Invoke-Step -Name "Measure PSF FWHM per star" -Script "06_measure_psf_fwhm.py" -Slow `
        -Note "Opens every FITS file. The only Phase 2 step that touches the images; everything after works from the per-star table."

    Invoke-Step -Name "Flag image quality (corrected)" -Script "07_flag_image_quality.py" `
        -Note "Supersedes 05. Applies per-frame plate scales and rejects sub-half-median detections (C6, C7)." `
        -Arguments @("--per-star", "`"$P1\psf_fwhm_per_star.csv`"",
                     "--header-summary", "`"$R\header_summary_full.csv`"",
                     "--out-flags", "`"$P1\image_quality_flags_corrected.csv`"",
                     "--out-excluded", "`"$P1\excluded_images_phase1_corrected.csv`"")

    Invoke-Step -Name "PSF summary table (corrected)" -Script "08_summarise_psf.py" `
        -Note "Supersedes 06. Produces Table 2 with a cluster-bootstrap uncertainty (C3)." `
        -Arguments @("--per-star", "`"$P1\psf_fwhm_per_star.csv`"",
                     "--header-summary", "`"$R\header_summary_full.csv`"",
                     "--excluded", "`"$P1\excluded_images_phase1_corrected.csv`"",
                     "--out-csv", "`"$P1\psf_fwhm_summary_corrected.csv`"")
}

# ---------------------------------------------------------------------------
# Phase 3 - Supernova positions
# ---------------------------------------------------------------------------
if (Test-Phase "3") {
    Invoke-Step -Name "Fetch SN coordinates from NED" -Script "10_fetch_sn_coordinates.py" `
        -Note "Runs before 07b/10. If SN masking in script 04 is ever enabled, this must move ahead of 04 (RUN_ORDER Issue 1)."

    Invoke-Step -Name "Spot-check SN positions" -Script "11_spotcheck_sn_coordinates.py" -Diagnostic `
        -Note "Writes PNG cutouts for visual confirmation that the SN lands on the host."
}

# ---------------------------------------------------------------------------
# Phase 4 - Aperture design and photometry
# ---------------------------------------------------------------------------
if (Test-Phase "4") {
    Invoke-Step -Name "Aperture floor per object (corrected)" -Script "09_aperture_floor_per_object.py" `
        -Note "Supersedes 07. Reads the per-star table directly rather than per_file_summary.csv, so the wrong plate scale does not propagate." `
        -Arguments @("--per-star", "`"$P1\psf_fwhm_per_star.csv`"",
                     "--header-summary", "`"$R\header_summary_full.csv`"",
                     "--flags", "`"$P1\image_quality_flags_corrected.csv`"",
                     "--redshifts", "`"$R\sn_catalog_final.csv`"",
                     "--out-csv", "`"$P4\aperture_floor_per_object_corrected.csv`"")

    Invoke-Step -Name "Curve of growth" -Script "10_curve_of_growth.py" -Slow `
        -Note "NOT YET AUDITED. Still reads aperture_floor_per_object.csv (uncorrected) and hard-codes PLATE_SCALE = 0.23. Repoint both before trusting the output."

    Invoke-Step -Name "Annulus sensitivity variants" -Script "10b_curve_of_growth_annulus_test.py" -Slow `
        -Note "NOT YET AUDITED."

    Invoke-Step -Name "Local colour vs radius" -Script "11_local_color_vs_radius.py" `
        -Note "NOT YET AUDITED. Restricts to du Pont frames, which is why the Swope plate-scale error never reaches the colours."

    Invoke-Step -Name "Colour scatter vs radius (corrected)" -Script "18_color_scatter_corrected.py" `
        -Note "NOT YET AUDITED. Supersedes 12, 13 and 14."

    Invoke-Step -Name "Annulus sensitivity driver" -Script "22_annulus_sensitivity.py" `
        -Note "NOT YET AUDITED."
}

# ---------------------------------------------------------------------------
# Phase 5 - Calibration
# ---------------------------------------------------------------------------
if (Test-Phase "5") {
    Invoke-Step -Name "Apply zero points" -Script "15_apply_zero_points.py" `
        -Note "NOT YET AUDITED. Reads curve_of_growth.csv directly rather than local_color_vs_radius.csv, so it performs its own extraction at the fiducial radius."

    Invoke-Step -Name "Flag low-flux colours" -Script "16_flag_low_flux_colors.py" `
        -Note "NOT YET AUDITED."

    Invoke-Step -Name "Apply Galactic extinction" -Script "15b_apply_galactic_extinction.py" `
        -Note "NOT YET AUDITED. Runs AFTER 16 despite the name, because it needs the flag_low_flux column."

    Invoke-Step -Name "Plot final B-V distribution" -Script "17_plot_final_bv_distribution.py" `
        -Note "WARNING (C8): reads calibrated_color_5kpc_flagged.csv, i.e. colours BEFORE extinction correction. The dereddened catalogue from 15b is currently read by nothing."
}

Write-Host ""
Write-Host ("=" * 78) -ForegroundColor DarkGray
Write-Host "Pipeline finished. $($script:StepNumber) steps." -ForegroundColor Green
Write-Host "Phases 4 and 5 are not yet audited - see the notes above and RUN_ORDER.md." -ForegroundColor DarkYellow
Write-Host ("=" * 78) -ForegroundColor DarkGray