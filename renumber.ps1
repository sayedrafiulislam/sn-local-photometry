# renumber.ps1
#
# Renumbers the pipeline scripts 00..22 in true execution order and rewrites
# every cross-reference inside the .py files so nothing points at an old name.
#
# Run AFTER restructure.ps1.
#
#     powershell -ExecutionPolicy Bypass -File .\renumber.ps1
#     powershell -ExecutionPolicy Bypass -File .\renumber.ps1 -Execute
#
# The rename happens in two passes via temporary names, because several new
# names collide with existing old ones (01_build_catalog -> 02_build_catalog
# while 02_apply_redshift_cut still exists).
#
# Superseded scripts keep their original names. That is the audit trail.

param([switch]$Execute)

$RepoRoot = "D:\Thesis\My Work\sn-local-photometry"

if (-not (Test-Path -LiteralPath $RepoRoot)) {
    Write-Host "Repository not found: $RepoRoot" -ForegroundColor Red
    exit 1
}
Set-Location -LiteralPath $RepoRoot

if ($Execute) {
    $mode = "EXECUTING"
    $modeColour = "Red"
} else {
    $mode = "DRY RUN - nothing will change"
    $modeColour = "Cyan"
}

Write-Host ""
Write-Host "=== $mode ===" -ForegroundColor $modeColour

# old filename, new filename, one-line description
$MAP = @(
    @("00_inspect_headers.py",                        "00_inspect_headers.py",              "read every FITS header"),
    @("00b_plate_scale_audit.py",                     "01_audit_plate_scales.py",           "three plate scales, not one"),
    @("01_build_catalog.py",                          "02_build_catalog.py",                "filenames plus NED redshifts"),
    @("01b_retry_failed_ned.py",                      "03_retry_failed_ned.py",             "alternative name conventions"),
    @("02_apply_redshift_cut.py",                     "04_apply_redshift_cut.py",           "338 to 266 objects"),
    @("03_get_positions_and_epochs.py",               "05_get_positions_and_epochs.py",     "observation dates from headers"),
    @("04_measure_psf_fwhm.py",                       "06_measure_psf_fwhm.py",             "seeing, measured per frame"),
    @("05b_flag_image_quality_corrected.py",          "07_flag_image_quality.py",           "quality cuts scaled per frame"),
    @("06b_psf_summary_corrected.py",                 "08_summarise_psf.py",                "PSF summary - paper Table 2"),
    @("07b_aperture_floor_per_object_corrected.py",   "09_aperture_floor_per_object.py",    "smallest trustworthy radius"),
    @("08_fetch_sn_coordinates.py",                   "10_fetch_sn_coordinates.py",         "SN positions from NED"),
    @("09_spotcheck_sn_coordinates.py",               "11_spotcheck_sn_coordinates.py",     "visual position check"),
    @("09b_verify_sn_positions.py",                   "12_verify_sn_positions.py",          "NED types and host offsets"),
    @("10c_curve_of_growth_final.py",                 "13_curve_of_growth.py",              "the core photometry"),
    @("11b_local_color_vs_radius_corrected.py",       "14_local_colour_vs_radius.py",       "brightness into colour"),
    @("09c_nuclear_contamination_test.py",            "15_offset_colour_test.py",           "offset-dependent reddening"),
    @("09d_nuclear_contamination_permutation.py",     "16_offset_colour_permutation.py",    "permutation null for it"),
    @("15c_apply_zero_points_corrected.py",           "17_apply_zero_points.py",            "counts into magnitudes"),
    @("16c_flag_unreliable_colors.py",                "18_flag_unreliable_colours.py",      "two quality criteria"),
    @("15d_apply_galactic_extinction_corrected.py",   "19_apply_galactic_extinction.py",    "Milky Way dust"),
    @("17b_plot_final_bv_distribution_corrected.py",  "20_plot_bv_distribution.py",         "paper Figure 2"),
    @("18b_color_scatter_corrected.py",               "21_colour_scatter_vs_radius.py",     "paper Figure 3"),
    @("19_annulus_sensitivity_driver.py",             "22_annulus_sensitivity.py",          "independent cross-check")
)

$Global:ActionCount = 0

# --------------------------------------------------------------- pre-flight

Write-Host ""
Write-Host "--- checking which scripts are present ---" -ForegroundColor Cyan

$present = @()
$missing = @()

foreach ($row in $MAP) {
    $src = Join-Path "scripts" $row[0]
    if (Test-Path -LiteralPath $src) {
        $present = $present + ,$row
    } else {
        $missing = $missing + $row[0]
    }
}

Write-Host ("found   {0} of {1}" -f $present.Count, $MAP.Count) -ForegroundColor Green
if ($missing.Count -gt 0) {
    Write-Host ("missing {0}:" -f $missing.Count) -ForegroundColor Yellow
    foreach ($m in $missing) { Write-Host ("          {0}" -f $m) -ForegroundColor Yellow }
    Write-Host "        (run restructure.ps1 first if these should exist)" -ForegroundColor DarkGray
}

# ------------------------------------------------------- pass 1: to temp

Write-Host ""
Write-Host "--- pass 1: staging ---" -ForegroundColor Cyan

foreach ($row in $present) {
    $src = Join-Path "scripts" $row[0]
    $tmp = Join-Path "scripts" ("__staging__" + $row[1])
    Write-Host ("STAGE    {0}" -f $row[0]) -ForegroundColor DarkGray
    $Global:ActionCount = $Global:ActionCount + 1
    if ($Execute) { Move-Item -LiteralPath $src -Destination $tmp -Force }
}

# ------------------------------------------------------ pass 2: to final

Write-Host ""
Write-Host "--- pass 2: final names ---" -ForegroundColor Cyan

foreach ($row in $present) {
    $tmp = Join-Path "scripts" ("__staging__" + $row[1])
    $dst = Join-Path "scripts" $row[1]
    Write-Host ("{0,-46} -> {1}" -f $row[0], $row[1]) -ForegroundColor Yellow
    if ($Execute) { Move-Item -LiteralPath $tmp -Destination $dst -Force }
}

# ------------------------------------------- rewrite cross-references

Write-Host ""
Write-Host "--- rewriting references inside .py files ---" -ForegroundColor Cyan

# Longest names first, so that e.g. 15c_apply_zero_points_corrected.py is
# replaced before any shorter substring of it could match.
$replacements = @()
foreach ($row in $MAP) {
    $replacements = $replacements + ,@($row[0], $row[1])
}
$replacements = $replacements | Sort-Object { - $_[0].Length }

$pyFiles = Get-ChildItem -Path "scripts" -Filter "*.py" -File -Recurse |
           Where-Object { $_.DirectoryName -notmatch "\\superseded$" }

$changedCount = 0
foreach ($f in $pyFiles) {
    $text = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    $orig = $text
    $hits = @()
    foreach ($pair in $replacements) {
        $old = $pair[0]
        $new = $pair[1]
        if ($old -eq $new) { continue }
        if ($text.Contains($old)) {
            $text = $text.Replace($old, $new)
            $hits = $hits + ("{0} -> {1}" -f $old, $new)
        }
    }
    if ($text -ne $orig) {
        $changedCount = $changedCount + 1
        Write-Host ("EDIT     {0}" -f $f.Name) -ForegroundColor Yellow
        foreach ($h in $hits) { Write-Host ("           {0}" -f $h) -ForegroundColor DarkGray }
        $Global:ActionCount = $Global:ActionCount + 1
        if ($Execute) {
            Set-Content -LiteralPath $f.FullName -Value $text -Encoding UTF8 -NoNewline
        }
    }
}
if ($changedCount -eq 0) { Write-Host "no cross-references found" -ForegroundColor DarkGray }

# ------------------------------------- also fix references in diagnostics

Write-Host ""
Write-Host "--- rewriting references in tools and docs ---" -ForegroundColor Cyan

$docFiles = @()
foreach ($pattern in @("*.md", "*.ps1")) {
    $docFiles = $docFiles + (Get-ChildItem -Path "." -Filter $pattern -File -Recurse -ErrorAction SilentlyContinue |
                             Where-Object { $_.FullName -notmatch "\\(\.venv|venv|\.git)\\" })
}

foreach ($f in $docFiles) {
    if ($f.Name -eq "renumber.ps1") { continue }
    $text = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    $orig = $text
    foreach ($pair in $replacements) {
        if ($pair[0] -eq $pair[1]) { continue }
        $text = $text.Replace($pair[0], $pair[1])
    }
    if ($text -ne $orig) {
        Write-Host ("EDIT     {0}" -f $f.Name) -ForegroundColor Yellow
        $Global:ActionCount = $Global:ActionCount + 1
        if ($Execute) {
            Set-Content -LiteralPath $f.FullName -Value $text -Encoding UTF8 -NoNewline
        }
    }
}

# ------------------------------------------------------ write NUMBERING.md

Write-Host ""
Write-Host "--- writing NUMBERING.md ---" -ForegroundColor Cyan

$lines = @()
$lines = $lines + "# Script numbering"
$lines = $lines + ""
$lines = $lines + "Scripts are numbered in **execution order**. The number is the run order;"
$lines = $lines + "there are no letter suffixes and no exceptions."
$lines = $lines + ""
$lines = $lines + "To reproduce every result, run 00 through 22 in sequence."
$lines = $lines + ""
$lines = $lines + "| # | script | was | what it does |"
$lines = $lines + "|---|---|---|---|"

$i = 0
foreach ($row in $MAP) {
    $num = "{0:D2}" -f $i
    $wasName = $row[0]
    if ($row[0] -eq $row[1]) { $wasName = "(unchanged)" }
    $lines = $lines + ("| {0} | ``{1}`` | {2} | {3} |" -f $num, $row[1], $wasName, $row[2])
    $i = $i + 1
}

$lines = $lines + ""
$lines = $lines + "## Notes"
$lines = $lines + ""
$lines = $lines + "**Optional steps.** ``11_spotcheck_sn_coordinates.py`` writes only inspection"
$lines = $lines + "images. ``22_annulus_sensitivity.py`` is an independent cross-check that"
$lines = $lines + "nothing depends on, but it validates 14 and 21 and should be run last."
$lines = $lines + ""
$lines = $lines + "**Independent step.** ``05_get_positions_and_epochs.py`` reads only the FITS"
$lines = $lines + "directory and can run at any time. Use ``--skip-ned``: steps 02 and 10"
$lines = $lines + "already fetch redshifts and positions, so only the observation dates are new."
$lines = $lines + ""
$lines = $lines + "**Configuration that must match across steps 13, 14, 17, 18 and 21:**"
$lines = $lines + ""
$lines = $lines + '    ANNULUS_TAG = "ann20-30"'
$lines = $lines + ""
$lines = $lines + "Step 21 verifies this against the ``annulus_tag`` column in its input and"
$lines = $lines + "refuses to run on a mismatch."
$lines = $lines + ""
$lines = $lines + "**Superseded scripts keep their original names** in ``scripts/superseded/``."
$lines = $lines + "Renumbering them would destroy the audit trail; the old numbers are how the"
$lines = $lines + "corrections log refers to them."
$lines = $lines + ""
$lines = $lines + "**Diagnostics** in ``scripts/diagnostics/`` are read-only checks. They are not"
$lines = $lines + "numbered because they are not part of the reproduction path."

if ($Execute) {
    Set-Content -LiteralPath "NUMBERING.md" -Value ($lines -join "`r`n") -Encoding UTF8
    Write-Host "written" -ForegroundColor Green
} else {
    Write-Host "would write NUMBERING.md ({0} lines)" -ForegroundColor DarkGray
}

# ------------------------------------------------------------------ summary

Write-Host ""
Write-Host ("=== {0} : {1} action(s) ===" -f $mode, $Global:ActionCount) -ForegroundColor $modeColour

if (-not $Execute) {
    Write-Host "Re-run with  -Execute  to apply."
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Done. Next:" -ForegroundColor Green
    Write-Host "  git add -A"
    Write-Host "  git commit -m 'Renumber pipeline scripts in execution order'"
    Write-Host ""
    Write-Host "  Then verify nothing points at an old name:" -ForegroundColor Green
    Write-Host '    Select-String -Path .\scripts\*.py -Pattern "\d\d[b-e]_" | Select-Object -First 20'
    Write-Host ""
}