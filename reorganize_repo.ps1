# reorganize_repo.ps1
#
# Run this from your repo root (D:\Thesis\My Work\sn-local-photometry)
# to reorganize scripts\ into the structure described in README.md:
# creates scripts\diagnostics\ and scripts\archive\, then moves the
# relevant files into them. Main numbered pipeline scripts (00-16,
# excluding 13 which is archived) stay directly in scripts\.
#
# Safe to run more than once -- uses -ErrorAction SilentlyContinue so
# it won't fail if a file has already been moved.

Write-Host "Creating subfolders..."
New-Item -ItemType Directory -Path "scripts\diagnostics" -Force | Out-Null
New-Item -ItemType Directory -Path "scripts\archive" -Force | Out-Null
New-Item -ItemType Directory -Path "paper" -Force | Out-Null

Write-Host "Moving diagnostic scripts..."
$diagnostics = @(
    "check_per_file_summary.py",
    "check_swo_tail.py",
    "plot_flagged_swo.py",
    "check_aperture_floor_outliers.py",
    "check_curve_shapes.py",
    "check_aperture_overlay.py",
    "check_color_shapes.py",
    "check_color_outliers.py"
)
foreach ($f in $diagnostics) {
    $src = "scripts\$f"
    if (Test-Path $src) {
        Move-Item -Path $src -Destination "scripts\diagnostics\$f" -Force -ErrorAction SilentlyContinue
        Write-Host "  moved $f"
    } else {
        Write-Host "  [skip] not found: $f"
    }
}

Write-Host "Archiving superseded script..."
$archiveSrc = "scripts\13_color_scatter_bootstrap.py"
if (Test-Path $archiveSrc) {
    Move-Item -Path $archiveSrc -Destination "scripts\archive\13_color_scatter_bootstrap.py" -Force -ErrorAction SilentlyContinue
    Write-Host "  moved 13_color_scatter_bootstrap.py"
} else {
    Write-Host "  [skip] not found: 13_color_scatter_bootstrap.py"
}

Write-Host ""
Write-Host "Done. Current scripts\ layout:"
Get-ChildItem -Path "scripts" -Recurse -File | Select-Object FullName