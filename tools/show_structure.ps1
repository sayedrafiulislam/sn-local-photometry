<#
show_structure.ps1

Prints the project layout: folder tree, files grouped by folder, and totals
by file type. Excludes virtual environments and caches.

    powershell -ExecutionPolicy Bypass -File .\tools\show_structure.ps1

To capture it (note: PowerShell writes UTF-16 with '>'):

    powershell -ExecutionPolicy Bypass -File .\tools\show_structure.ps1 |
        Out-File -Encoding utf8 structure.txt
#>

Set-Location "D:\Thesis\My Work\sn-local-photometry"
$root = (Get-Location).Path + '\'

# .venv, venv, .git, __pycache__, checkpoints -- anywhere in the path
$EXCLUDE = '\\(\.venv|venv|\.git|__pycache__|\.ipynb_checkpoints)\\'

function Rel($p) { $p.Replace($root, '') }

Write-Host "`n=========== DIRECTORY TREE ===========" -ForegroundColor Cyan
Get-ChildItem -Recurse -Directory |
    Where-Object { $_.FullName -notmatch $EXCLUDE -and
                   $_.Name -notmatch '^(\.venv|venv|\.git|__pycache__)$' } |
    ForEach-Object { Rel $_.FullName } |
    Sort-Object

Write-Host "`n=========== FILES BY FOLDER ===========" -ForegroundColor Cyan
Get-ChildItem -Recurse -File |
    Where-Object { $_.FullName -notmatch $EXCLUDE } |
    Group-Object { Rel $_.DirectoryName } |
    Sort-Object Name |
    ForEach-Object {
        $label = if ($_.Name) { $_.Name } else { '<root>' }
        Write-Host "`n--- $label  ($($_.Count) files) ---" -ForegroundColor Yellow
        $_.Group | Sort-Object Name | ForEach-Object {
            "{0,-62} {1,9} KB  {2}" -f $_.Name,
                                       [math]::Round($_.Length / 1KB, 1),
                                       $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')
        }
    }

Write-Host "`n=========== TOTALS BY FILE TYPE ===========" -ForegroundColor Cyan
Get-ChildItem -Recurse -File |
    Where-Object { $_.FullName -notmatch $EXCLUDE } |
    Group-Object Extension |
    Sort-Object Count -Descending |
    Select-Object @{n = 'ext';   e = { if ($_.Name) { $_.Name } else { '(none)' } }},
                  Count,
                  @{n = 'MB';    e = { [math]::Round(($_.Group | Measure-Object Length -Sum).Sum / 1MB, 2) }} |
    Format-Table -AutoSize

$all = Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch $EXCLUDE }
Write-Host ("TOTAL: {0} files, {1} MB (excluding virtual environments)`n" -f `
            $all.Count, [math]::Round(($all | Measure-Object Length -Sum).Sum / 1MB, 1)) `
           -ForegroundColor Cyan