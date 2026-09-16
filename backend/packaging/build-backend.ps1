<#
.SYNOPSIS
  Freeze the SVR-IOCL backend into backend/packaging/dist/svr-backend/ with PyInstaller.

.DESCRIPTION
  1. Picks a Python: backend/.venv if present, else whatever `python` is on PATH.
  2. Installs the build/runtime deps (svr-backend[build,win]).
  3. Runs PyInstaller against packaging/svr_backend.spec (one-dir, three exes).
  4. Smoke-tests the frozen svr-backend.exe (migrate builds a fresh DB; serve --help).

  The resulting dist/svr-backend/ folder is what the Electron installer bundles as
  resources/backend/ (frontend/package.json > build.extraResources).

.PARAMETER SkipInstall
  Don't touch pip - assume PyInstaller + deps are already in the chosen env.
#>
param(
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$backendDir = Split-Path -Parent $PSScriptRoot   # ...\backend
$packagingDir = $PSScriptRoot
Push-Location $backendDir
try {
  $venvPy = Join-Path $backendDir ".venv\Scripts\python.exe"
  $py = if (Test-Path $venvPy) { $venvPy } else { "python" }
  Write-Host "Python: $py"
  & $py --version

  if (-not $SkipInstall) {
    Write-Host "Installing build dependencies (svr-backend[build,win]) ..."
    & $py -m pip install --upgrade pip
    & $py -m pip install -e ".[build,win]"
    # pip is a native exe, so a failure here does NOT trip $ErrorActionPreference.
    # This bit me on the 0.1.2 build: a running dev backend held
    # .venv\Scripts\svr-backend.exe, so pip uninstalled svr-backend and then
    # could not reinstall it (WinError 32). The build carried on, PyInstaller's
    # collect_submodules("svr_backend") found nothing, and the freeze only failed
    # 3 minutes later at the smoke test with "No module named 'svr_backend'" -
    # an error that points nowhere near the real cause.
    if ($LASTEXITCODE -ne 0) {
      throw "pip install -e .[build,win] failed ($LASTEXITCODE) - the frozen exe would be missing svr_backend. If this is WinError 32, a running svr-backend.exe or python.exe is holding the venv; stop it and re-run."
    }
  }

  # Prove the package is importable and the module graph is whole BEFORE spending
  # three minutes freezing it. Same reason: fail where the cause is visible.
  Write-Host "Checking svr_backend is importable in the build env ..."
  & $py -c "import svr_backend, svr_backend.app; from PyInstaller.utils.hooks import collect_submodules as c; m = c('svr_backend'); assert len(m) > 40, 'only %d svr_backend submodules collected' % len(m); print('svr_backend OK - %d submodules' % len(m))"
  if ($LASTEXITCODE -ne 0) { throw "svr_backend is not importable in $py - fix the env before freezing" }

  # Clean previous output so a stale exe can never ship.
  foreach ($d in @("build", "dist")) {
    $p = Join-Path $packagingDir $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
  }

  Write-Host "Running PyInstaller ..."
  & $py -m PyInstaller --clean --noconfirm (Join-Path $packagingDir "svr_backend.spec") `
    --distpath (Join-Path $packagingDir "dist") `
    --workpath (Join-Path $packagingDir "build")

  $distRoot = Join-Path $packagingDir "dist\svr-backend"
  $svrBackend = Join-Path $distRoot "svr-backend.exe"
  $ourExes = @("svr-backend.exe", "svr-backend-service.exe", "svr-scheduler-service.exe")
  foreach ($exe in $ourExes) {
    $p = Join-Path $distRoot $exe
    if (-not (Test-Path $p)) { throw "expected $exe missing from $distRoot" }
  }

  # --- code-sign our 3 exes ------------------------------------------------------
  # electron-builder signs the Electron app + installer but never sees inside
  # extraResources, so the frozen backend exes are signed here. No-ops with no
  # cert configured (installer/sign.ps1). tesseract.exe is left as its publisher
  # shipped it.
  $signPs1 = Join-Path $backendDir "..\installer\sign.ps1" | Resolve-Path
  $exePaths = $ourExes | ForEach-Object { Join-Path $distRoot $_ }
  & $signPs1 -Path $exePaths

  # --- smoke -----------------------------------------------------------------
  $smokeDb = Join-Path $env:TEMP "svr-freeze-smoke.sqlite"
  if (Test-Path $smokeDb) { Remove-Item -Force $smokeDb }
  Write-Host "Smoke: migrate -> $smokeDb"
  & $svrBackend migrate --db $smokeDb
  if ($LASTEXITCODE -ne 0) { throw "svr-backend.exe migrate failed ($LASTEXITCODE)" }
  Write-Host "Smoke: serve --help"
  & $svrBackend serve --help | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "svr-backend.exe serve --help failed ($LASTEXITCODE)" }
  # Force the whole app graph (every router + starlette/anyio/pydantic/cryptography/
  # argon2) to import inside the frozen exe - catches a missing hidden-import here,
  # at build time, instead of as a dead backend on the station PC.
  Write-Host "Smoke: selfcheck (full app import)"
  & $svrBackend selfcheck
  if ($LASTEXITCODE -ne 0) { throw "svr-backend.exe selfcheck failed ($LASTEXITCODE)" }
  Remove-Item -Force $smokeDb -ErrorAction SilentlyContinue

  Write-Host ""
  Write-Host "OK - frozen backend at: $distRoot"
}
finally {
  Pop-Location
}
