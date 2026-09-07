<#
.SYNOPSIS
  One-shot local build of the SVR IOCL Station Windows installer.

.DESCRIPTION
  1. Stages the portable Tesseract -> installer/vendor/tesseract/ (SDD ADR-6)
  2. Freezes the Python backend  -> backend/packaging/dist/svr-backend/
  3. Packages the Electron app   -> installer/output/SVR-IOCL-Station-Setup-*.exe
     (electron-builder bundles the frozen backend as resources/backend/, the
     portable Tesseract as resources/tesseract/, and runs first-run.ps1 elevated
     on install - see frontend/build/installer.nsh).

  Prereqs: Python 3.11+ (a backend/.venv is used if present), Node 20+, 7-Zip
  (to stage Tesseract), and `npm ci` already run in frontend/.

.PARAMETER SkipBackendInstall
  Pass through to build-backend.ps1: assume PyInstaller + deps are already present.
#>
param(
  [switch]$SkipBackendInstall
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "== 1/3  Staging Tesseract =="
& (Join-Path $PSScriptRoot "fetch-tesseract.ps1")
$vendorExe = Join-Path $PSScriptRoot "vendor\tesseract\tesseract.exe"
if (-not (Test-Path $vendorExe)) {
  throw "Tesseract not staged at $vendorExe - see installer/fetch-tesseract.ps1 (SDD ADR-6)"
}

Write-Host ""
Write-Host "== 2/3  Freezing backend =="
& (Join-Path $repo "backend\packaging\build-backend.ps1") -SkipInstall:$SkipBackendInstall

Write-Host ""
Write-Host "== 3/3  Packaging Electron installer =="
Push-Location (Join-Path $repo "frontend")
try {
  if (-not (Test-Path "node_modules")) { throw "run 'npm ci' in frontend/ first" }
  & npm run dist
}
finally {
  Pop-Location
}

Write-Host ""
Get-ChildItem (Join-Path $repo "installer\output") -Filter *.exe | ForEach-Object {
  Write-Host "Installer: $($_.FullName)  ($([math]::Round($_.Length / 1MB, 1)) MB)"
}

Write-Host ""
Write-Host "== Signature check (informational) =="
& (Join-Path $PSScriptRoot "verify-signatures.ps1")
