# fix_stale_notes.ps1
#
# After renumber.ps1, three docstring passages still give instructions that
# point at scripts which no longer exist. They were not caught by the automatic
# rewrite because they name SUPERSEDED scripts, and those deliberately keep
# their original names.
#
# Historical statements ("Supersedes 10b_...") are correct and left alone.
# Only live instructions are fixed.
#
#     powershell -ExecutionPolicy Bypass -File .\fix_stale_notes.ps1
#     powershell -ExecutionPolicy Bypass -File .\fix_stale_notes.ps1 -Execute

param([switch]$Execute)

$RepoRoot = "D:\Thesis\My Work\sn-local-photometry"
Set-Location -LiteralPath $RepoRoot

if ($Execute) { $mode = "EXECUTING"; $colour = "Red" }
else          { $mode = "DRY RUN - nothing will change"; $colour = "Cyan" }

Write-Host ""
Write-Host "=== $mode ===" -ForegroundColor $colour

# file, old text, new text, why
$FIXES = @(

  @("scripts\17_apply_zero_points.py",
    "Named 15c because 15b is already taken by 15b_apply_galactic_extinction.py.",
    "Runs at step 17. Its output feeds step 18 (quality flags), which feeds step`r`n19 (Galactic extinction).",
    "obsolete naming rationale"),

  @("scripts\17_apply_zero_points.py",
    "Run 16_flag_low_flux_colors.py, then 15b_apply_galactic_extinction.py --`r`n  in that order, despite the numbering.",
    "Next: 18_flag_unreliable_colours.py, then 19_apply_galactic_extinction.py.",
    "points at superseded scripts"),

  @("scripts\18_flag_unreliable_colours.py",
    "*** 15b_apply_galactic_extinction.py currently filters on flag_low_flux and`r`n*** must be changed to flag_exclude, or the new criteria will have no effect.",
    "*** Downstream steps 19 and 20 filter on flag_exclude. flag_low_flux is`r`n*** retained in the output for comparison only and must not be filtered on.",
    "warning already acted on"),

  @("scripts\18_flag_unreliable_colours.py",
    "IMPORTANT: filter downstream on ``flag_exclude``, not ``flag_low_flux``.`r`n15b_apply_galactic_extinction.py currently filters on flag_low_flux and MUST be`r`nupdated, or the calibration criterion will have no effect on the final sample.",
    "IMPORTANT: filter downstream on ``flag_exclude``, not ``flag_low_flux``.`r`nSteps 19 and 20 already do. flag_low_flux is retained for comparison only.",
    "warning already acted on")
)

$applied = 0
$notFound = 0

foreach ($fix in $FIXES) {
    $path = $fix[0]
    $old  = $fix[1]
    $new  = $fix[2]
    $why  = $fix[3]

    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host ("MISSING  {0}" -f $path) -ForegroundColor Red
        continue
    }

    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8

    # try CRLF first, then LF, since the file may use either
    $oldLF = $old.Replace("`r`n", "`n")
    $newLF = $new.Replace("`r`n", "`n")

    if ($text.Contains($old)) {
        $text = $text.Replace($old, $new)
        $hit = $true
    } elseif ($text.Contains($oldLF)) {
        $text = $text.Replace($oldLF, $newLF)
        $hit = $true
    } else {
        $hit = $false
    }

    if ($hit) {
        $applied = $applied + 1
        Write-Host ("FIX      {0}" -f (Split-Path $path -Leaf)) -ForegroundColor Yellow
        Write-Host ("           {0}" -f $why) -ForegroundColor DarkGray
        if ($Execute) {
            Set-Content -LiteralPath $path -Value $text -Encoding UTF8 -NoNewline
        }
    } else {
        $notFound = $notFound + 1
        Write-Host ("SKIP     {0}  ({1})" -f (Split-Path $path -Leaf), $why) -ForegroundColor DarkGray
        Write-Host  "           text not found - already fixed, or wording differs" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host ("=== {0} : {1} applied, {2} not found ===" -f $mode, $applied, $notFound) -ForegroundColor $colour

if (-not $Execute) {
    Write-Host "Re-run with  -Execute  to apply."
} else {
    Write-Host ""
    Write-Host "Verify what remains:" -ForegroundColor Green
    Write-Host '  Select-String -Path .\scripts\*.py -Pattern "\d\d[b-e]_"'
    Write-Host ""
    Write-Host "Expect exactly three hits, all of them correct history:" -ForegroundColor Green
    Write-Host "  13_curve_of_growth.py        Supersedes 10b_..."
    Write-Host "  18_flag_unreliable_colours   Supersedes 16_... and 16b_..."
    Write-Host "  19_apply_galactic_extinction Supersedes 15b_..."
}
Write-Host ""