<#
show_clutter.ps1

Flags things that need a decision: backup files, stray images, scripts by
category, outputs no current script reads, and loose files in the root.
Read-only -- changes nothing.

    powershell -ExecutionPolicy Bypass -File .\tools\show_clutter.ps1
#>

Set-Location "D:\Thesis\My Work\sn-local-photometry"
$root = (Get-Location).Path + '\'

$EXCLUDE = '\\(\.venv|venv|\.git|__pycache__|\.ipynb_checkpoints)\\'

function Rel($p) { $p.Replace($root, '') }

# ------------------------------------------------------------------ backups
Write-Host "`n=========== BACKUPS (.bak_*) ===========" -ForegroundColor Yellow
$b = Get-ChildItem -Recurse -File -Filter '*.bak_*' -ErrorAction SilentlyContinue |
     Where-Object { $_.FullName -notmatch $EXCLUDE }
if ($b) {
    Write-Host ("{0} files, {1} MB" -f $b.Count,
                [math]::Round(($b | Measure-Object Length -Sum).Sum / 1MB, 1))
    $b | Group-Object { ($_.Name -split '\.bak_')[0] } | Sort-Object Name | ForEach-Object {
        Write-Host "  $($_.Name)  --  $($_.Count) generation(s)" -ForegroundColor DarkGray
        $_.Group | Sort-Object LastWriteTime | ForEach-Object {
            "    {0}   content dated {1}" -f (Rel $_.FullName),
                                             $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
        }
    }
} else {
    Write-Host "none" -ForegroundColor Green
}

# ------------------------------------------------------------------- images
Write-Host "`n=========== IMAGES, WHEREVER THEY LIVE ===========" -ForegroundColor Yellow
Get-ChildItem -Recurse -File -Include *.png, *.jpg, *.jpeg, *.pdf |
    Where-Object { $_.FullName -notmatch $EXCLUDE } |
    Sort-Object DirectoryName, Name |
    ForEach-Object {
        "{0,-72} {1,8} KB  {2}" -f (Rel $_.FullName),
                                   [math]::Round($_.Length / 1KB, 0),
                                   $_.LastWriteTime.ToString('yyyy-MM-dd')
    }

# ------------------------------------------------------------------ scripts
Write-Host "`n=========== SCRIPTS ===========" -ForegroundColor Yellow
Get-ChildItem -Recurse -File -Filter '*.py' |
    Where-Object { $_.FullName -notmatch $EXCLUDE } |
    ForEach-Object {
        $rel = Rel $_.FullName
        $tag = if     ($_.Name -match 'RETRACTED')            { 'RETRACTED' }
               elseif ($_.Name -match 'SUPERSEDED')           { 'superseded' }
               elseif ($rel   -match '^scripts\\diagnostics') { 'diagnostic' }
               elseif ($_.Name -match '^\d\d[b-e]_')          { 'CURRENT' }
               elseif ($_.Name -match '^\d\d_')               { 'CURRENT' }
               else                                           { '?' }
        [pscustomobject]@{ Tag = $tag; Path = $rel }
    } |
    Sort-Object Path |
    ForEach-Object {
        $colour = switch ($_.Tag) {
            'CURRENT'    { 'Green' }
            'diagnostic' { 'Gray' }
            default      { 'DarkGray' }
        }
        Write-Host ("{0,-11} {1}" -f $_.Tag, $_.Path) -ForegroundColor $colour
    }

# ---------------------------------------------------------- orphaned outputs
Write-Host "`n=========== OUTPUTS NO CURRENT SCRIPT READS ===========" -ForegroundColor Yellow

# Filename prefixes written by a script on the current reproduction path.
$currentPrefixes = @(
    'header_summary', 'plate_scale', 'sn_catalog', 'ned_retry', 'excluded_objects',
    'positions_epochs', 'redshift_distribution',
    'psf_fwhm_per_star', 'per_file_summary', 'psf_fwhm_summary_corrected',
    'image_quality_flags_corrected', 'excluded_images_phase1_corrected',
    'aperture_floor_per_object_corrected',
    'sn_coordinates', 'sn_position_verification', 'spotcheck_',
    'curve_of_growth_ann', 'annulus_setting_comparison', 'annulus_sensitivity',
    'local_color_vs_radius',
    'nuclear_contamination_ann', 'nuclear_permutation_ann',
    'calibrated_color_5kpc', 'bv_distribution', 'color_scatter_corrected'
)

$orphans = Get-ChildItem -Recurse -File -Include *.csv, *.png, *.txt |
    Where-Object { $_.FullName -notmatch $EXCLUDE } |
    Where-Object { (Rel $_.FullName) -match '^results\\' } |
    Where-Object { (Rel $_.FullName) -notmatch '^results\\(archive|diagnostics)\\' } |
    Where-Object { $_.Name -notmatch '\.bak_' } |
    Where-Object {
        $name = $_.Name
        $hit = $false
        foreach ($p in $currentPrefixes) {
            if ($name -like "$p*") { $hit = $true; break }
        }
        -not $hit
    }

if ($orphans) {
    $orphans | Sort-Object LastWriteTime | ForEach-Object {
        "{0,-70} {1}" -f (Rel $_.FullName), $_.LastWriteTime.ToString('yyyy-MM-dd')
    }
} else {
    Write-Host "none -- every output traces to a current script" -ForegroundColor Green
}

# --------------------------------------------------------------- root files
Write-Host "`n=========== LOOSE FILES IN ROOT ===========" -ForegroundColor Yellow
Get-ChildItem -File | Sort-Object Name | ForEach-Object {
    "{0,-40} {1,8} KB" -f $_.Name, [math]::Round($_.Length / 1KB, 1)
}

Write-Host ""