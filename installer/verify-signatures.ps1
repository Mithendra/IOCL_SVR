<#
.SYNOPSIS
  Report the Authenticode status of the built installer and the frozen backend
  exes. Informational by default; a gate with -RequireSigned.

.DESCRIPTION
  Run after installer\build-all.ps1. Checks:
    - installer\output\SVR-IOCL-Station-Setup-*.exe
    - backend\packaging\dist\svr-backend\svr-backend*.exe  (the 3 we build)

  With no cert configured every line will read "NotSigned" - that is expected
  until code-signing is switched on (see installer\README.md).

.PARAMETER RequireSigned
  Exit 1 if any checked file is not "Valid". Use this in a release pipeline once
  a cert is in place.
#>
[CmdletBinding()]
param(
  [switch]$RequireSigned
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

$targets = @()
$targets += Get-ChildItem (Join-Path $repo "installer\output") -Filter "SVR-IOCL-Station-Setup-*.exe" -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty FullName
$distRoot = Join-Path $repo "backend\packaging\dist\svr-backend"
foreach ($e in "svr-backend.exe", "svr-backend-service.exe", "svr-scheduler-service.exe") {
  $p = Join-Path $distRoot $e
  if (Test-Path $p) { $targets += $p }
}

if (-not $targets) {
  Write-Warning "Nothing to check - run installer\build-all.ps1 first."
  exit 0
}

& (Join-Path $PSScriptRoot "sign.ps1") -Verify -RequireSigned:$RequireSigned -Path $targets
exit $LASTEXITCODE
