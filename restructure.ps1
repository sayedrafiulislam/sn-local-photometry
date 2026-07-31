# restructure.ps1
#
# One-off repository reorganisation after the pipeline audit.
#
#   - marks every superseded script and moves it to scripts\superseded
#   - promotes 09b/09c/09d from diagnostics to the pipeline
#   - retires 09e as RETRACTED
#   - archives outputs that no current script reads
#   - moves bulky diagnostic images out of the results folders
#   - prunes redundant backup generations, keeping the oldest of each group
#   - tidies the repository root
#
# DRY RUN BY DEFAULT.
#
#     powershell -ExecutionPolicy Bypass -File .\restructure.ps1
#     powershell -ExecutionPolicy Bypass -File .\restructure.ps1 -Execute
#
# Safe to re-run: every action checks the source exists first.

param([switch]$Execute)

$RepoRoot = "D:\Thesis\My Work\sn-local-photometry"

if (-not (Test-Path -LiteralPath $RepoRoot)) {
    Write-Host "Repository not found: $RepoRoot" -ForegroundColor Red
    exit 1
}
Set-Location -LiteralPath $RepoRoot

if ($Execute) {
    $mode = "EXECUTING - changes are being applied"
    $modeColour = "Red"
} else {
    $mode = "DRY RUN - nothing will change"
    $modeColour = "Cyan"
}

Write-Host ""
Write-Host "=== $mode ===" -ForegroundColor $modeColour

$Global:ActionCount = 0

function Invoke-Action {
    param(
        [string]$Verb,
        [string]$From,
        [string]$To
    )

    if (-not (Test-Path -LiteralPath $From)) { return }

    $Global:ActionCount = $Global:ActionCount + 1
    Write-Host ("{0,-8} {1}" -f $Verb, $From) -ForegroundColor Yellow
    if ($To -ne "") {
        Write-Host ("         -> {0}" -f $To) -ForegroundColor DarkGray
    }

    if (-not $Execute) { return }

    if ($Verb -eq "DELETE") {
        Remove-Item -LiteralPath $From -Force -Recurse
        return
    }

    $parent = Split-Path -Path $To -Parent
    if ($parent -ne "" -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Move-Item -LiteralPath $From -Destination $To -Force
}

# --------------------------------------------------------------- new folders

Write-Host ""
Write-Host "--- creating folders ---" -ForegroundColor Cyan

$newFolders = @(
    "scripts\superseded",
    "results\archive",
    "results\diagnostics",
    "results\phase0_catalog",
    "tools"
)

foreach ($folder in $newFolders) {
    if (Test-Path -LiteralPath $folder) {
        Write-Host ("EXISTS   {0}" -f $folder) -ForegroundColor DarkGray
    } else {
        Write-Host ("CREATE   {0}" -f $folder) -ForegroundColor Yellow
        if ($Execute) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }
    }
}

# ------------------------------------------------- superseded scripts (list)
# Each entry: source path, then destination filename inside scripts\superseded

Write-Host ""
Write-Host "--- marking superseded scripts ---" -ForegroundColor Cyan

$supersededMap = @(
    @("scripts\10_curve_of_growth_SUPERSEDED.py.py",       "10_curve_of_growth_SUPERSEDED.py"),
    @("scripts\05_flag_image_quality.py",                  "05_flag_image_quality_SUPERSEDED.py"),
    @("scripts\06_clean_group_summary.py",                 "06_clean_group_summary_SUPERSEDED.py"),
    @("scripts\07_aperture_floor_per_object.py",           "07_aperture_floor_per_object_SUPERSEDED.py"),
    @("scripts\10_curve_of_growth.py",                     "10_curve_of_growth_SUPERSEDED.py"),
    @("scripts\10b_curve_of_growth_annulus_test.py",       "10b_curve_of_growth_annulus_test_SUPERSEDED.py"),
    @("scripts\11_local_color_vs_radius.py",               "11_local_color_vs_radius_SUPERSEDED.py"),
    @("scripts\12_color_scatter_vs_radius.py",             "12_color_scatter_vs_radius_SUPERSEDED.py"),
    @("scripts\13_color_scatter_bootstrap.py",             "13_color_scatter_bootstrap_SUPERSEDED.py"),
    @("scripts\14_color_scatter_paired_bootstrap.py",      "14_color_scatter_paired_bootstrap_SUPERSEDED.py"),
    @("scripts\15_apply_zero_points.py",                   "15_apply_zero_points_SUPERSEDED.py"),
    @("scripts\15b_apply_galactic_extinction.py",          "15b_apply_galactic_extinction_SUPERSEDED.py"),
    @("scripts\16_flag_low_flux_colors.py",                "16_flag_low_flux_colors_SUPERSEDED.py"),
    @("scripts\16b_flag_unreliable_colors.py",             "16b_flag_unreliable_colors_SUPERSEDED.py"),
    @("scripts\17_plot_final_bv_distribution.py",          "17_plot_final_bv_distribution_SUPERSEDED.py"),
    @("scripts\18_color_scatter_corrected.py",             "18_color_scatter_corrected_SUPERSEDED.py")
)

foreach ($pair in $supersededMap) {
    $src = $pair[0]
    $dst = Join-Path "scripts\superseded" $pair[1]
    Invoke-Action "RENAME" $src $dst
}

# scripts already carrying the tag but still sitting loose in scripts\
$alreadyTagged = Get-ChildItem -Path "scripts" -Filter "*_SUPERSEDED.py" -File -ErrorAction SilentlyContinue
foreach ($f in $alreadyTagged) {
    $dst = Join-Path "scripts\superseded" $f.Name
    Invoke-Action "MOVE" $f.FullName $dst
}

# 09e was retracted: fixed angular threshold across a factor of 37 in redshift
Invoke-Action "RENAME" "scripts\diagnostics\09e_verify_positions_in_pixels.py" "scripts\superseded\09e_verify_positions_in_pixels_RETRACTED.py"
Invoke-Action "RENAME" "scripts\09e_verify_positions_in_pixels.py"             "scripts\superseded\09e_verify_positions_in_pixels_RETRACTED.py"

# duplicate copy of script 13
Invoke-Action "DELETE" "scripts\archive\13_color_scatter_bootstrap.py" ""

# --------------------------- 09b/09c/09d are pipeline steps, not diagnostics

Write-Host ""
Write-Host "--- promoting 09b/09c/09d to the pipeline ---" -ForegroundColor Cyan

$promote = @(
    "09b_verify_sn_positions.py",
    "09c_nuclear_contamination_test.py",
    "09d_nuclear_contamination_permutation.py"
)

foreach ($name in $promote) {
    $src = Join-Path "scripts\diagnostics" $name
    $dst = Join-Path "scripts" $name
    Invoke-Action "MOVE" $src $dst
}

# ---------------------------------------------------------------- images

Write-Host ""
Write-Host "--- images folder ---" -ForegroundColor Cyan

Invoke-Action "MOVE" "images\redshift_distribution.png" "results\phase0_catalog\redshift_distribution.png"

# --------------------------- consolidate the current offset-colour outputs

Write-Host ""
Write-Host "--- consolidating offset-colour outputs ---" -ForegroundColor Cyan

$nuclear = Get-ChildItem -Path "results" -Filter "nuclear_*ann20-30*" -File -ErrorAction SilentlyContinue
foreach ($f in $nuclear) {
    $dst = Join-Path "results\phase4_aperture" $f.Name
    Invoke-Action "MOVE" $f.FullName $dst
}

# --------------------------------------------------- archive orphaned outputs

Write-Host ""
Write-Host "--- archiving outputs no current script reads ---" -ForegroundColor Cyan

$toArchive = @(
    # superseded by the tagged curve_of_growth_ann*.csv from 10c
    "results\phase4_aperture\curve_of_growth.csv",
    # scripts 12, 13, 14 - statistics superseded by 18b
    "results\phase4_aperture\color_scatter_summary.csv",
    "results\phase4_aperture\color_scatter_vs_radius.png",
    "results\phase4_aperture\color_scatter_bootstrap.csv",
    "results\phase4_aperture\color_scatter_bootstrap.png",
    "results\phase4_aperture\color_scatter_paired_bootstrap.csv",
    "results\phase4_aperture\color_scatter_paired_bootstrap.png",
    # pre-guard offset-colour run, replaced by the ann20-30 versions
    "results\phase4_aperture\nuclear_contamination_profiles.png",
    "results\phase4_aperture\nuclear_permutation_null.png",
    "results\phase4_aperture\nuclear_contamination_per_object.csv",
    "results\phase4_aperture\nuclear_permutation_results.csv",
    # superseded by 07b
    "results\phase4_aperture\aperture_floor_per_object.csv",
    # manual backups from before 10c and the annulus fix
    "results\phase4_aperture\local_color_vs_radius_pre_annulus_fix.csv",
    "results\phase4_aperture\local_color_vs_radius_pre10c.csv",
    "results\phase5_calibration\calibrated_color_5kpc_pre_annulus_fix.csv",
    # superseded by 05b / 06b
    "results\phase1_psf\psf_fwhm_summary.csv",
    "results\phase1_psf\psf_fwhm_summary_clean.csv",
    "results\phase1_psf\image_quality_flags.csv",
    "results\phase1_psf\excluded_images_phase1.csv",
    "results\phase1_psf\swo_tail_check.csv"
)

foreach ($p in $toArchive) {
    $dst = Join-Path "results\archive" (Split-Path -Path $p -Leaf)
    Invoke-Action "MOVE" $p $dst
}

# ------------------------------------------- bulky visual-inspection images

Write-Host ""
Write-Host "--- moving diagnostic images out of the results folders ---" -ForegroundColor Cyan

$toDiagnostics = @(
    "results\phase1_psf\diagnostic_ASAS14lq_V_comb_swo.png",
    "results\phase1_psf\diagnostic_ASAS14mw_V_comb_swo.png",
    "results\phase1_psf\diagnostic_SN07ol_V_comb_dup.png",
    "results\phase1_psf\diagnostic_SN2012fr_B_comb_dup.png",
    "results\phase4_aperture\spotcheck_ASAS14ad.png",
    "results\phase4_aperture\spotcheck_KISS13v.png",
    "results\phase4_aperture\spotcheck_SN2012fr.png",
    "results\phase4_aperture\aperture_overlay_ASAS14ad.png",
    "results\phase4_aperture\aperture_overlay_KISS13v.png",
    "results\phase4_aperture\cog_check_ASAS14ad.png",
    "results\phase4_aperture\cog_check_KISS13v.png",
    "results\phase4_aperture\cog_check_SN2012fr.png",
    "results\phase4_aperture\color_check_ASAS14ad.png",
    "results\phase4_aperture\color_check_KISS13v.png"
)

foreach ($p in $toDiagnostics) {
    $dst = Join-Path "results\diagnostics" (Split-Path -Path $p -Leaf)
    Invoke-Action "MOVE" $p $dst
}

# ------------------------------------------------------------------ backups
#
# Corrected scripts write *.bak_YYYYmmdd_HHMMSS and never delete. Several
# re-runs in one session leave multiple generations of the same file. Keep the
# OLDEST of each group - that is the pre-audit state, worth retaining until the
# paper is submitted - and drop the intermediate re-runs.

Write-Host ""
Write-Host "--- pruning backup generations ---" -ForegroundColor Cyan

$allBaks = Get-ChildItem -Recurse -File -Filter "*.bak_*" -ErrorAction SilentlyContinue
$baks = @()
foreach ($f in $allBaks) {
    if ($f.FullName -notmatch "\\\.?venv\\") { $baks = $baks + $f }
}

if ($baks.Count -gt 0) {
    $totalMB = [math]::Round((($baks | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
    Write-Host ("{0} backup files, {1} MB" -f $baks.Count, $totalMB) -ForegroundColor DarkGray

    $groups = $baks | Group-Object -Property { ($_.Name -split "\.bak_")[0] }
    foreach ($g in $groups) {
        $sorted = $g.Group | Sort-Object -Property LastWriteTime
        Write-Host ("KEEP     {0}" -f $sorted[0].Name) -ForegroundColor Green
        for ($i = 1; $i -lt $sorted.Count; $i++) {
            Invoke-Action "DELETE" $sorted[$i].FullName ""
        }
    }
} else {
    Write-Host "none found" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- root tidy

Write-Host ""
Write-Host "--- repository root ---" -ForegroundColor Cyan

Invoke-Action "MOVE" "show_structure.ps1" "tools\show_structure.ps1"
Invoke-Action "MOVE" "show_clutter.ps1"   "tools\show_clutter.ps1"
Invoke-Action "DELETE" "structure_audit.txt" ""

# NOTE: reorganize_repo.ps1 is deliberately NOT touched. Check what it does and
# remove it by hand if this script supersedes it.

# ------------------------------------------------------------------ summary

Write-Host ""
Write-Host ("=== {0} : {1} action(s) ===" -f $mode, $Global:ActionCount) -ForegroundColor $modeColour

if (-not $Execute) {
    Write-Host "Re-run with  -Execute  to apply."
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Done. Next:" -ForegroundColor Green
    Write-Host "  1. git add -A"
    Write-Host "     git commit -m 'Restructure after pipeline audit'"
    Write-Host "  2. powershell -ExecutionPolicy Bypass -File .\tools\show_structure.ps1"
    Write-Host ""
    Write-Host "  scripts\ should now hold only the reproduction path:" -ForegroundColor Green
    Write-Host "    00 00b 01 01b 02 03 04 05b 06b 07b 08 09 09b"
    Write-Host "    10c 11b 09c 09d 15c 16c 15d 17b 18b 19"
    Write-Host ""
}