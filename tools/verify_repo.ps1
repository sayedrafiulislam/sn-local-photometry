# verify_repo.ps1
#
# Checks that every expected file exists and reports which pipeline steps have
# outputs older than their inputs, i.e. which need re-running.
#
#     powershell -ExecutionPolicy Bypass -File .\tools\verify_repo.ps1
#
# Read-only. Changes nothing.

Set-Location "D:\Thesis\My Work\sn-local-photometry"
$R  = "results"
$P0 = "$R\phase0_catalog"
$P1 = "$R\phase1_psf"
$P4 = "$R\phase4_aperture"
$P5 = "$R\phase5_calibration"

$missing = 0
$stale   = 0

function Check-File {
    param([string]$Path, [string]$Label)
    if (Test-Path -LiteralPath $Path) {
        Write-Host ("  OK    {0}" -f $Label) -ForegroundColor Green
    } else {
        Write-Host ("  MISS  {0}" -f $Label) -ForegroundColor Red
        Write-Host ("          expected at {0}" -f $Path) -ForegroundColor DarkGray
        $script:missing++
    }
}

function Check-Fresh {
    param([string]$Num, [string]$Name, [string]$Output, [string[]]$Inputs)

    if (-not (Test-Path -LiteralPath $Output)) {
        Write-Host ("  NOT RUN  [{0}] {1}" -f $Num, $Name) -ForegroundColor Red
        Write-Host ("             no {0}" -f (Split-Path $Output -Leaf)) -ForegroundColor DarkGray
        $script:missing++
        return
    }

    $outTime = (Get-Item -LiteralPath $Output).LastWriteTime
    $newer = @()
    foreach ($i in $Inputs) {
        if (Test-Path -LiteralPath $i) {
            $t = (Get-Item -LiteralPath $i).LastWriteTime
            if ($t -gt $outTime) { $newer += (Split-Path $i -Leaf) }
        }
    }

    if ($newer.Count -gt 0) {
        Write-Host ("  STALE    [{0}] {1}" -f $Num, $Name) -ForegroundColor Yellow
        Write-Host ("             newer input: {0}" -f ($newer -join ", ")) -ForegroundColor DarkGray
        $script:stale++
    } else {
        Write-Host ("  fresh    [{0}] {1}   {2:yyyy-MM-dd HH:mm}" -f $Num, $Name, $outTime) -ForegroundColor Green
    }
}

# ==========================================================================
Write-Host "`n===== PIPELINE SCRIPTS (00-22) =====" -ForegroundColor Cyan

$expected = @(
    "00_inspect_headers.py",
    "01_audit_plate_scales.py",
    "02_build_catalog.py",
    "03_retry_failed_ned.py",
    "04_apply_redshift_cut.py",
    "05_get_positions_and_epochs.py",
    "06_measure_psf_fwhm.py",
    "07_flag_image_quality.py",
    "08_summarise_psf.py",
    "09_aperture_floor_per_object.py",
    "10_fetch_sn_coordinates.py",
    "11_spotcheck_sn_coordinates.py",
    "12_verify_sn_positions.py",
    "13_curve_of_growth.py",
    "14_local_colour_vs_radius.py",
    "15_offset_colour_test.py",
    "16_offset_colour_permutation.py",
    "17_apply_zero_points.py",
    "18_flag_unreliable_colours.py",
    "19_apply_galactic_extinction.py",
    "20_plot_bv_distribution.py",
    "21_colour_scatter_vs_radius.py",
    "22_annulus_sensitivity.py"
)
foreach ($s in $expected) { Check-File "scripts\$s" $s }

$extra = Get-ChildItem "scripts" -Filter "*.py" -File -ErrorAction SilentlyContinue |
         Where-Object { $expected -notcontains $_.Name }
if ($extra) {
    Write-Host "`n  Unexpected files loose in scripts\ :" -ForegroundColor Yellow
    $extra | ForEach-Object { Write-Host ("    {0}" -f $_.Name) -ForegroundColor Yellow }
}

# ==========================================================================
Write-Host "`n===== DOCUMENTS =====" -ForegroundColor Cyan
@(
    "Readme.md", "NUMBERING.md", "RENAME_LOG.md", "RUN_ORDER.md",
    "pipeline_map.md", "PAPER_CORRECTIONS.md", "SUPERVISOR_QUESTIONS.md",
    "AUDIT_SUMMARY.md", ".gitignore", "run_pipeline.ps1",
    "paper\main.tex"
) | ForEach-Object { Check-File $_ $_ }

Write-Host "`n===== TOOLS =====" -ForegroundColor Cyan
@("tools\show_structure.ps1", "tools\show_clutter.ps1",
  "tools\fix_docstrings.py") | ForEach-Object { Check-File $_ $_ }

# ==========================================================================
Write-Host "`n===== FOLDERS =====" -ForegroundColor Cyan
@("scripts\superseded", "scripts\diagnostics", "results\archive",
  "results\diagnostics", $P0, $P1, $P4, $P5, "data") |
  ForEach-Object { Check-File $_ $_ }

$sup = (Get-ChildItem "scripts\superseded" -Filter "*.py" -ErrorAction SilentlyContinue).Count
$dia = (Get-ChildItem "scripts\diagnostics" -Filter "*.py" -ErrorAction SilentlyContinue).Count
Write-Host ("`n  superseded scripts : {0}   (expected 16)" -f $sup) -ForegroundColor $(if($sup -eq 16){'Green'}else{'Yellow'})
Write-Host ("  diagnostic scripts : {0}" -f $dia) -ForegroundColor Gray

# ==========================================================================
Write-Host "`n===== OUTPUTS: WHICH STEPS NEED RE-RUNNING =====" -ForegroundColor Cyan

Check-Fresh "00" "Inspect headers"       "$R\header_summary_full.csv" @()
Check-Fresh "01" "Audit plate scales"    "$R\plate_scale_status.csv"  @("$R\header_summary_full.csv")
Check-Fresh "02" "Build catalogue"       "$R\sn_catalog_v2.csv"       @()
Check-Fresh "04" "Redshift cut"          "$R\sn_catalog_final.csv"    @("$R\sn_catalog_v2.csv")
Check-Fresh "05" "Positions and epochs"  "$P0\positions_epochs.csv"   @()
Check-Fresh "06" "PSF FWHM per star"     "$P1\psf_fwhm_per_star.csv"  @()
Check-Fresh "07" "Image quality flags"   "$P1\image_quality_flags_corrected.csv" @("$P1\psf_fwhm_per_star.csv")
Check-Fresh "08" "PSF summary (Table 2)" "$P1\psf_fwhm_summary_corrected.csv"    @("$P1\psf_fwhm_per_star.csv")
Check-Fresh "09" "Aperture floor"        "$P4\aperture_floor_per_object_corrected.csv" @("$P1\psf_fwhm_summary_corrected.csv", "$R\sn_catalog_final.csv")
Check-Fresh "10" "SN coordinates"        "$R\sn_coordinates.csv"      @("$R\sn_catalog_final.csv")
Check-Fresh "12" "Verify positions"      "$R\sn_position_verification.csv" @("$R\sn_coordinates.csv")
Check-Fresh "13" "Curve of growth"       "$P4\curve_of_growth_ann20-30.csv" @("$P4\aperture_floor_per_object_corrected.csv", "$R\sn_coordinates.csv")
Check-Fresh "14" "Local colour"          "$P4\local_color_vs_radius_ann20-30.csv" @("$P4\curve_of_growth_ann20-30.csv")
Check-Fresh "15" "Offset-colour test"    "$P4\nuclear_contamination_ann20-30_per_object.csv" @("$P4\local_color_vs_radius_ann20-30.csv", "$R\sn_position_verification.csv")
Check-Fresh "16" "Permutation null"      "$P4\nuclear_permutation_ann20-30_results.csv"      @("$P4\local_color_vs_radius_ann20-30.csv", "$R\sn_position_verification.csv")
Check-Fresh "17" "Zero points"           "$P5\calibrated_color_5kpc.csv"        @("$P4\curve_of_growth_ann20-30.csv", "data\B_ZP_dup.dat", "data\V_ZP_dup.dat")
Check-Fresh "18" "Quality flags"         "$P5\calibrated_color_5kpc_flagged.csv" @("$P5\calibrated_color_5kpc.csv")
Check-Fresh "19" "Galactic extinction"   "$P5\calibrated_color_5kpc_dered.csv"   @("$P5\calibrated_color_5kpc_flagged.csv")
Check-Fresh "20" "B-V figure"            "$P5\bv_distribution.png"               @("$P5\calibrated_color_5kpc_dered.csv")
Check-Fresh "21" "Scatter figure"        "$P4\color_scatter_corrected.png"       @("$P4\local_color_vs_radius_ann20-30.csv", "$P5\calibrated_color_5kpc_flagged.csv")
Check-Fresh "22" "Annulus sensitivity"   "$P4\annulus_sensitivity_summary.csv"   @("$P4\curve_of_growth_ann20-30.csv")

# ==========================================================================
Write-Host "`n===== FIGURES FOR THE PAPER =====" -ForegroundColor Cyan
@(
  @("$P5\bv_distribution.png",        "Figure 2 - B-V distribution"),
  @("$P4\color_scatter_corrected.png","Figure 3 - scatter vs radius"),
  @("$P4\nuclear_contamination_ann20-30_profiles.png", "offset-colour profiles"),
  @("$P4\nuclear_permutation_ann20-30_null.png",       "permutation null")
) | ForEach-Object { Check-File $_[0] $_[1] }

Write-Host "`n  main.tex needs bv_distribution.png and color_scatter_corrected.png" -ForegroundColor DarkYellow
Write-Host "  copied into paper\ , or the \includegraphics paths adjusted." -ForegroundColor DarkYellow

# ==========================================================================
Write-Host "`n===== SUMMARY =====" -ForegroundColor Cyan
if ($missing -eq 0 -and $stale -eq 0) {
    Write-Host "  Everything present and up to date." -ForegroundColor Green
} else {
    if ($missing -gt 0) { Write-Host ("  {0} missing or never run" -f $missing) -ForegroundColor Red }
    if ($stale   -gt 0) { Write-Host ("  {0} stale - output older than its input" -f $stale) -ForegroundColor Yellow }
}
Write-Host ""