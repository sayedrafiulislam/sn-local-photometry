<#
.SYNOPSIS
    Runs the SN local photometry pipeline in the corrected order.

.DESCRIPTION
    Scripts are numbered 00 to 22 in TRUE execution order. The number is the
    run order -- there are no letter suffixes and no exceptions. See
    NUMBERING.md for the mapping from the old numbering.

    Phases group the steps for convenience only; the numbers are authoritative.

.PARAMETER DataDir
    Directory containing the CSP FITS frames.

.PARAMETER Phase
    Which phase to run: All, 0, 1, 2, 3, 4, 5, 6. Default All.

.PARAMETER SkipSlow
    Skips steps 06 and 13, which open every FITS file and take a long time.
    Useful when only downstream logic has changed.

.PARAMETER SkipNetwork
    Skips steps 02, 03 and 10, which query NED.

.PARAMETER DryRun
    Prints the commands without executing them.

.EXAMPLE
    .\run_pipeline.ps1 -Phase 4
    .\run_pipeline.ps1 -SkipSlow
    .\run_pipeline.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [string]$DataDir = "D:\Thesis\pd\CSPAll",
    [ValidateSet("All", "0", "1", "2", "3", "4", "5", "6")]
    [string]$Phase = "All",
    [switch]$SkipSlow,
    [switch]$SkipNetwork,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$S  = Join-Path $Root "scripts"
$R  = Join-Path $Root "results"
$P0 = Join-Path $R "phase0_catalog"
$P1 = Join-Path $R "phase1_psf"
$P4 = Join-Path $R "phase4_aperture"
$P5 = Join-Path $R "phase5_calibration"

$script:StepNumber = 0

function Invoke-Step {
    param(
        [string]$Num,
        [string]$Name,
        [string]$Script,
        [string[]]$Arguments = @(),
        [switch]$Slow,
        [switch]$Network,
        [string]$Note
    )

    $script:StepNumber++

    $tags = @()
    if ($Slow)    { $tags += "SLOW" }
    if ($Network) { $tags += "NET" }
    $tag = if ($tags.Count -gt 0) { " (" + ($tags -join ", ") + ")" } else { "" }

    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor DarkGray
    Write-Host ("[{0}] {1}{2}" -f $Num, $Name, $tag) -ForegroundColor Cyan
    if ($Note) { Write-Host ("      " + $Note) -ForegroundColor DarkYellow }
    Write-Host ("=" * 78) -ForegroundColor DarkGray

    $path = Join-Path $S $Script
    if (-not (Test-Path $path)) {
        Write-Host "      SKIPPED - $Script not found" -ForegroundColor Red
        return
    }
    if ($Slow -and $SkipSlow) {
        Write-Host "      SKIPPED - SkipSlow was specified" -ForegroundColor Yellow
        return
    }
    if ($Network -and $SkipNetwork) {
        Write-Host "      SKIPPED - SkipNetwork was specified" -ForegroundColor Yellow
        return
    }

    $cmd = "python `"$path`" " + ($Arguments -join " ")
    if ($DryRun) {
        Write-Host "      $cmd" -ForegroundColor DarkGray
        return
    }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & python $path @Arguments
    $sw.Stop()

    if ($LASTEXITCODE -ne 0) {
        throw "Step $Num exited with code $LASTEXITCODE. Pipeline halted."
    }
    Write-Host ("      done in {0:mm\:ss}" -f $sw.Elapsed) -ForegroundColor Green
}

function Test-Phase { param([string]$N) return ($Phase -eq "All" -or $Phase -eq $N) }

Write-Host ""
Write-Host "Repository  : $Root"
Write-Host "FITS        : $DataDir"
Write-Host "Phase       : $Phase"
if ($SkipSlow)    { Write-Host "Skipping slow steps (06, 13)"   -ForegroundColor Yellow }
if ($SkipNetwork) { Write-Host "Skipping network steps (02, 03, 10)" -ForegroundColor Yellow }
if ($DryRun)      { Write-Host "DRY RUN - nothing will be executed"  -ForegroundColor Yellow }

# --------------------------------------------------------------------------
# Phase 0 - Reconnaissance
# --------------------------------------------------------------------------
if (Test-Phase "0") {

    Invoke-Step -Num "00" -Name "Inspect FITS headers" `
        -Script "00_inspect_headers.py" -Slow `
        -Note "Runs over ALL frames. An earlier limited run sampled only du Pont files and produced the single-plate-scale error." `
        -Arguments @("--data-dir", "`"$DataDir`"", "--out-csv", "`"$R\header_summary_full.csv`"")

    Invoke-Step -Num "01" -Name "Audit plate scales" `
        -Script "01_audit_plate_scales.py" `
        -Note "Three scales exist: 0.230, 0.430 and 0.159 arcsec/pixel." `
        -Arguments @("--summary-csv", "`"$R\header_summary_full.csv`"",
                     "--out-csv", "`"$R\plate_scale_status.csv`"")
}

# --------------------------------------------------------------------------
# Phase 1 - Catalogue, redshifts and epochs
# --------------------------------------------------------------------------
if (Test-Phase "1") {

    Invoke-Step -Num "02" -Name "Build catalogue and query NED" `
        -Script "02_build_catalog.py" -Network `
        -Arguments @("--data-dir", "`"$DataDir`"", "--out-csv", "`"$R\sn_catalog_v2.csv`"")

    Invoke-Step -Num "03" -Name "Retry failed NED queries" `
        -Script "03_retry_failed_ned.py" -Network `
        -Note "Only informative when NED's name-checker was previously unhealthy." `
        -Arguments @("--log-csv", "`"$R\excluded_objects_log.csv`"",
                     "--out-csv", "`"$R\ned_retry_results.csv`"")

    Invoke-Step -Num "04" -Name "Apply redshift cut" `
        -Script "04_apply_redshift_cut.py" `
        -Note "338 objects in, 266 out." `
        -Arguments @("--in-csv", "`"$R\sn_catalog_v2.csv`"",
                     "--out-csv", "`"$R\sn_catalog_final.csv`"",
                     "--excluded-csv", "`"$R\excluded_objects_log.csv`"")

    Invoke-Step -Num "05" -Name "Observation dates and positions" `
        -Script "05_get_positions_and_epochs.py" `
        -Note "Use --skip-ned: steps 02 and 10 already fetch redshifts and positions. Only the epochs are new, and they address the SN-light question." `
        -Arguments @("--data-dir", "`"$DataDir`"",
                     "--out-csv", "`"$P0\positions_epochs.csv`"", "--skip-ned")
}

# --------------------------------------------------------------------------
# Phase 2 - Image quality
# --------------------------------------------------------------------------
if (Test-Phase "2") {

    Invoke-Step -Num "06" -Name "Measure PSF FWHM per star" `
        -Script "06_measure_psf_fwhm.py" -Slow `
        -Note "Opens every FITS file. Everything after this works from the per-star table."

    Invoke-Step -Num "07" -Name "Flag image quality" `
        -Script "07_flag_image_quality.py" `
        -Note "Thresholds scaled to each frame's own plate scale; rejects sub-half-median detections (cosmic rays)." `
        -Arguments @("--per-star", "`"$P1\psf_fwhm_per_star.csv`"",
                     "--header-summary", "`"$R\header_summary_full.csv`"",
                     "--out-flags", "`"$P1\image_quality_flags_corrected.csv`"",
                     "--out-excluded", "`"$P1\excluded_images_phase1_corrected.csv`"")

    Invoke-Step -Num "08" -Name "Summarise PSF (paper Table 2)" `
        -Script "08_summarise_psf.py" `
        -Note "Cluster bootstrap over images, not stars: ~24 stars in one frame share an atmosphere." `
        -Arguments @("--per-star", "`"$P1\psf_fwhm_per_star.csv`"",
                     "--header-summary", "`"$R\header_summary_full.csv`"",
                     "--excluded", "`"$P1\excluded_images_phase1_corrected.csv`"",
                     "--out-csv", "`"$P1\psf_fwhm_summary_corrected.csv`"")

    Invoke-Step -Num "09" -Name "Aperture floor per object" `
        -Script "09_aperture_floor_per_object.py" `
        -Note "Reads the per-star table directly, so the plate-scale correction propagates." `
        -Arguments @("--per-star", "`"$P1\psf_fwhm_per_star.csv`"",
                     "--header-summary", "`"$R\header_summary_full.csv`"",
                     "--flags", "`"$P1\image_quality_flags_corrected.csv`"",
                     "--redshifts", "`"$R\sn_catalog_final.csv`"",
                     "--out-csv", "`"$P4\aperture_floor_per_object_corrected.csv`"")
}

# --------------------------------------------------------------------------
# Phase 3 - Supernova positions
# --------------------------------------------------------------------------
if (Test-Phase "3") {

    Invoke-Step -Num "10" -Name "Fetch SN coordinates from NED" `
        -Script "10_fetch_sn_coordinates.py" -Network

    Invoke-Step -Num "11" -Name "Spot-check SN positions" `
        -Script "11_spotcheck_sn_coordinates.py" `
        -Note "Optional. Writes inspection PNGs only."

    Invoke-Step -Num "12" -Name "Verify SN positions and offsets" `
        -Script "12_verify_sn_positions.py" -Network `
        -Note "Confirms all 266 are NED type SN, and measures the offset to each host centre. REQUIRED by steps 15 and 16."
}

# --------------------------------------------------------------------------
# Phase 4 - Photometry and colour
# --------------------------------------------------------------------------
if (Test-Phase "4") {

    Invoke-Step -Num "13" -Name "Curve of growth" `
        -Script "13_curve_of_growth.py" -Slow `
        -Note "The core measurement. Three annulus settings, per-file plate scales, aperture and annulus guards. 541 object-images."

    Invoke-Step -Num "14" -Name "Local colour versus radius" `
        -Script "14_local_colour_vs_radius.py" `
        -Note "du Pont only. Check the funnel prints 266 of 266."
}

# --------------------------------------------------------------------------
# Phase 5 - The offset-colour result
# --------------------------------------------------------------------------
if (Test-Phase "5") {

    $pos = Join-Path $R "sn_position_verification.csv"
    $col = Join-Path $P4 "local_color_vs_radius_ann20-30.csv"

    Invoke-Step -Num "15" -Name "Offset-colour test" `
        -Script "15_offset_colour_test.py" `
        -Note "Within-object design. Runs AFTER step 14 despite its number in the old scheme." `
        -Arguments @("--colors", "`"$col`"", "--positions", "`"$pos`"",
                     "--out-prefix", "`"$P4\nuclear_contamination_ann20-30`"")

    Invoke-Step -Num "16" -Name "Offset-colour permutation null" `
        -Script "16_offset_colour_permutation.py" `
        -Note "Shuffles the pairing between profiles and offsets, 5000 times." `
        -Arguments @("--colors", "`"$col`"", "--positions", "`"$pos`"",
                     "--out-prefix", "`"$P4\nuclear_permutation_ann20-30`"")
}

# --------------------------------------------------------------------------
# Phase 6 - Calibration and results
# --------------------------------------------------------------------------
if (Test-Phase "6") {

    Invoke-Step -Num "17" -Name "Apply zero points" `
        -Script "17_apply_zero_points.py" `
        -Note "Watch the epoch crosstab: the supplied zero points cover CSP-II only."

    Invoke-Step -Num "18" -Name "Flag unreliable colours" `
        -Script "18_flag_unreliable_colours.py" `
        -Note "Two criteria: background fraction, and the object's own quoted uncertainty."

    Invoke-Step -Num "19" -Name "Apply Galactic extinction" `
        -Script "19_apply_galactic_extinction.py" `
        -Note "Requires the SFD maps and the sfdmap package. Filters on flag_exclude."

    Invoke-Step -Num "20" -Name "Plot B-V distribution (paper Figure 2)" `
        -Script "20_plot_bv_distribution.py" `
        -Note "Plots the DEREDDENED colours."

    Invoke-Step -Num "21" -Name "Colour scatter versus radius (paper Figure 3)" `
        -Script "21_colour_scatter_vs_radius.py" `
        -Note "Pre-specified 4 kpc reference, 95 per cent intervals, BH-FDR."

    Invoke-Step -Num "22" -Name "Annulus sensitivity" `
        -Script "22_annulus_sensitivity.py" `
        -Note "Independent cross-check. Reimplements steps 14 and 21 rather than importing them -- do not refactor."
}

Write-Host ""
Write-Host ("=" * 78) -ForegroundColor DarkGray
Write-Host ("Pipeline finished. {0} step(s)." -f $script:StepNumber) -ForegroundColor Green
Write-Host "See NUMBERING.md for the step map and RUN_ORDER.md for dependencies." -ForegroundColor DarkYellow
Write-Host ("=" * 78) -ForegroundColor DarkGray
Write-Host ""