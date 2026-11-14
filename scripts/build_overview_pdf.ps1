# Builds docs/Susanin_AI_overview.pdf from docs/overview/overview.html.
# Needs Microsoft Edge or Google Chrome.
#   powershell -ExecutionPolicy Bypass -File scripts\build_overview_pdf.ps1
# (This file is ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 without BOM.)
$repo = Split-Path -Parent $PSScriptRoot
$html = Join-Path $repo 'docs\overview\overview.html'
$pdf = Join-Path $repo 'docs\Susanin_AI_overview.pdf'
$browser = @(
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Google\Chrome\Application\chrome.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { Write-Error 'Edge or Chrome not found'; exit 1 }

$profileDir = Join-Path $env:TEMP 'susanin_pdf_profile'
$url = 'file:///' + ($html -replace '\\', '/')
$arguments = @('--headless=new', '--disable-gpu', '--no-pdf-header-footer',
               "--user-data-dir=$profileDir", "--print-to-pdf=$pdf", $url)
Start-Process -FilePath $browser -ArgumentList $arguments -Wait
if (Test-Path $pdf) { "Done: $pdf ($([math]::Round((Get-Item $pdf).Length / 1KB)) KB)" }
else { Write-Error 'PDF was not created'; exit 1 }
