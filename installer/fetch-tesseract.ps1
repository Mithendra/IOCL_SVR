<#
.SYNOPSIS
  Populate installer\vendor\tesseract\ with the portable Tesseract payload the
  Electron installer bundles as resources\tesseract\ (SDD ADR-6).

.DESCRIPTION
  The ~30 MB Tesseract binary + language data is third-party redistributable and
  is NOT committed to git (installer\vendor\ is git-ignored). This script stages
  it before a build:

    1. If installer\vendor\tesseract\tesseract.exe already exists -> no-op
       (pass -Force to re-stage).
    2. Otherwise obtain the UB Mannheim Windows build, VERIFY its SHA-256 against
       the pin below, extract it with 7-Zip, and copy out only:
         tesseract.exe, its runtime *.dll, tessdata\eng.traineddata,
         tessdata\osd.traineddata, and the Apache-2.0 LICENSE.

  Air-gapped / no 7-Zip: download the setup .exe yourself, then either point
  -SourcePath at it (7-Zip still required to unpack an NSIS exe) or hand-place the
  five items above under installer\vendor\tesseract\ and this script is happy.

.PARAMETER Force
  Re-stage even if tesseract.exe is already present.

.PARAMETER SourcePath
  Path to an already-downloaded tesseract-ocr-w64-setup-*.exe (skips the download;
  the SHA-256 pin is still checked unless -SkipHashCheck).

.PARAMETER SkipHashCheck
  Escape hatch for a source whose hash is not yet pinned. Prints the actual hash
  so it can be pinned in this file.
#>
param(
  [switch]$Force,
  [string]$SourcePath,
  [switch]$SkipHashCheck
)

$ErrorActionPreference = "Stop"

# --- the pin (bump deliberately; SDD ADR-6) ---------------------------------
$TesseractVersion = "5.3.3.20231005"
$SetupUrl  = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-$TesseractVersion.exe"
# TODO(packaging session): replace with the real SHA-256 the first successful
# download prints, then commit. Until then callers must pass -SkipHashCheck.
$SetupSha256 = "REPLACE_WITH_PINNED_SHA256"

$vendorDir = Join-Path $PSScriptRoot "vendor\tesseract"
$tessExe   = Join-Path $vendorDir "tesseract.exe"

$needed = @(
  "tesseract.exe",
  "tessdata\eng.traineddata",
  "tessdata\osd.traineddata"
)

function Test-VendorComplete {
  foreach ($rel in $needed) {
    if (-not (Test-Path (Join-Path $vendorDir $rel))) { return $false }
  }
  return $true
}

if ((Test-VendorComplete) -and -not $Force) {
  Write-Host "Tesseract vendor payload already staged at $vendorDir - nothing to do."
  Write-Host "  (pass -Force to re-stage)"
  exit 0
}

New-Item -ItemType Directory -Force -Path $vendorDir | Out-Null

# --- locate 7-Zip (needed to unpack the NSIS setup exe) --------------------
$sevenZip = $null
foreach ($cand in @(
    "7z",
    "$env:ProgramFiles\7-Zip\7z.exe",
    "${env:ProgramFiles(x86)}\7-Zip\7z.exe")) {
  $cmd = Get-Command $cand -ErrorAction SilentlyContinue
  if ($cmd) { $sevenZip = $cmd.Source; break }
}
if (-not $sevenZip) {
  throw @"
7-Zip not found. Install it (winget install 7zip.7zip) or hand-place these
files under $vendorDir and re-run:
  $($needed -join "`n  ")
  LICENSE   (Tesseract's Apache-2.0 license text)
"@
}

# --- obtain the setup exe -------------------------------------------------------
$work = Join-Path $env:TEMP "svr-tesseract-stage"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$setupExe = if ($SourcePath) { (Resolve-Path $SourcePath).Path } else { Join-Path $work "tesseract-setup.exe" }

if (-not $SourcePath) {
  Write-Host "Downloading Tesseract $TesseractVersion ..."
  Write-Host "  $SetupUrl"
  Invoke-WebRequest -Uri $SetupUrl -OutFile $setupExe -UseBasicParsing
}

# --- verify the pin ----------------------------------------------------------
$actual = (Get-FileHash -Algorithm SHA256 -Path $setupExe).Hash.ToLower()
if ($SkipHashCheck -or $SetupSha256 -eq "REPLACE_WITH_PINNED_SHA256") {
  Write-Warning "SHA-256 not verified. Actual hash of $([IO.Path]::GetFileName($setupExe)):"
  Write-Warning "  $actual"
  Write-Warning "Pin this in fetch-tesseract.ps1 (`$SetupSha256`) and drop -SkipHashCheck."
} elseif ($actual -ne $SetupSha256.ToLower()) {
  throw "SHA-256 mismatch. expected $SetupSha256, got $actual - refusing to use this file."
} else {
  Write-Host "SHA-256 OK ($actual)."
}

# --- extract + copy out just what we ship ------------------------------------
$extract = Join-Path $work "extract"
if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
Write-Host "Extracting with $sevenZip ..."
& $sevenZip x -y "-o$extract" $setupExe | Out-Null
if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed ($LASTEXITCODE)" }

$srcExe = Get-ChildItem -Path $extract -Recurse -Filter "tesseract.exe" | Select-Object -First 1
if (-not $srcExe) { throw "tesseract.exe not found in the extracted setup" }
$srcRoot = $srcExe.Directory.FullName

# clear stale payload, then copy fresh
Get-ChildItem -Path $vendorDir -Force | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $vendorDir "tessdata") | Out-Null

Copy-Item (Join-Path $srcRoot "tesseract.exe") $vendorDir
Get-ChildItem -Path $srcRoot -Filter "*.dll" | ForEach-Object { Copy-Item $_.FullName $vendorDir }

foreach ($lang in @("eng.traineddata", "osd.traineddata")) {
  $hit = Get-ChildItem -Path $extract -Recurse -Filter $lang | Select-Object -First 1
  if (-not $hit) { throw "$lang not found in the extracted setup" }
  Copy-Item $hit.FullName (Join-Path $vendorDir "tessdata")
}

$license = Get-ChildItem -Path $extract -Recurse -Include "LICENSE", "LICENSE.txt", "COPYING" -File |
  Select-Object -First 1
if ($license) {
  Copy-Item $license.FullName (Join-Path $vendorDir "LICENSE")
} else {
  Write-Warning "No LICENSE file found in the setup - add Tesseract's Apache-2.0 text to $vendorDir\LICENSE by hand."
}

Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue

if (-not (Test-VendorComplete)) { throw "staging finished but $vendorDir is still incomplete" }
$size = [math]::Round(((Get-ChildItem $vendorDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "OK - Tesseract $TesseractVersion staged at $vendorDir ($size MB)."
