<#
.SYNOPSIS
  Post-install setup for SVR IOCL Station. Runs elevated - the NSIS installer invokes
  it from the customInstall hook (frontend/build/installer.nsh); it can also be re-run
  by hand as Administrator.

.DESCRIPTION
  1. Creates the data + per-component log tree under C:\ProgramData\SVR-IOCL (SDD 14.3).
  2. Persists SVR_* config as *machine* environment variables so the Windows Services
     (started by the SCM, not by this script) actually see them. Generates a Fernet
     field-encryption key once (SDD 13.3) if none is set.
  3. Applies SQLite migrations via the frozen svr-backend.exe.
  4. Registers + starts the two Windows Services (Automatic start).
  5. Adds the Electron frontend as a per-user Startup-folder shortcut (SDD 19 item 23).

.PARAMETER InstallDir
  Root of the installed app. Contains the Electron exe, resources\backend\ (the frozen
  backend), and installer\ (this script). Defaults to this script's parent's parent.

.PARAMETER DataDir
  Where the SQLite DB, backups and logs live. Defaults to C:\ProgramData\SVR-IOCL.
#>
param(
  [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
  [string]$DataDir     = "$env:ProgramData\SVR-IOCL"
)

$ErrorActionPreference = "Stop"

Write-Host "SVR IOCL Station - first-run setup"
Write-Host "  InstallDir = $InstallDir"
Write-Host "  DataDir    = $DataDir"

# --- locate the frozen backend --------------------------------------------------
# Installed layout: <InstallDir>\resources\backend\svr-backend*.exe
# Dev fallback: console scripts on PATH (pip install -e ".[dev,win]").
$backendDir     = Join-Path $InstallDir "resources\backend"
$svrBackend     = Join-Path $backendDir "svr-backend.exe"
$backendSvcExe  = Join-Path $backendDir "svr-backend-service.exe"
$schedSvcExe    = Join-Path $backendDir "svr-scheduler-service.exe"
$frozen = Test-Path $svrBackend
if (-not $frozen) {
  Write-Warning "Frozen backend not found at $backendDir - falling back to PATH console scripts (dev)."
  $svrBackend    = "svr-backend"     # not a real console script; see migrate call below
  $backendSvcExe = $null
  $schedSvcExe   = $null
}

# --- 1. data + log tree -------------------------------------------------------
$logDir    = Join-Path $DataDir "logs"
$backupDir = Join-Path $DataDir "backups"
New-Item -ItemType Directory -Force -Path $DataDir, $logDir, $backupDir | Out-Null
foreach ($f in @(
    "backend-service.log", "scheduler.log", "database.log",
    "frontend.log", "email-integration.log", "ocr-processing.log")) {
  $p = Join-Path $logDir $f
  if (-not (Test-Path $p)) { New-Item -ItemType File -Path $p | Out-Null }
}

# --- 2. machine-wide config -------------------------------------------------------
function Set-MachineEnv([string]$Name, [string]$Value) {
  [Environment]::SetEnvironmentVariable($Name, $Value, "Machine")
  Set-Item -Path "Env:$Name" -Value $Value   # so this process (migrations below) sees it too
  Write-Host "  $Name = $Value"
}

$dbPath = Join-Path $DataDir "svr.sqlite"
Set-MachineEnv "SVR_DATA_DIR" $DataDir
Set-MachineEnv "SVR_DB_PATH"  $dbPath
Set-MachineEnv "SVR_LOG_DIR"  $logDir

# Bundled Tesseract (SDD ADR-6). Point the backend at the copy electron-builder
# shipped under resources\tesseract\ so Scan/Upload needs no separate install.
$tessExe  = Join-Path $InstallDir "resources\tesseract\tesseract.exe"
$tessData = Join-Path $InstallDir "resources\tesseract\tessdata"
if (Test-Path $tessExe) {
  Set-MachineEnv "SVR_TESSERACT_CMD"   $tessExe
  Set-MachineEnv "SVR_TESSDATA_PREFIX" $tessData
} else {
  Write-Warning "Bundled Tesseract not found at $tessExe - OCR (Scan/Upload) will be unavailable until reinstalled with it."
}

# Fernet key for field encryption at rest (SDD 13.3). Generate once, then leave alone
# - regenerating would orphan every previously-encrypted employee bank field.
$existingKey = [Environment]::GetEnvironmentVariable("SVR_FIELD_KEY", "Machine")
if ([string]::IsNullOrWhiteSpace($existingKey)) {
  if ($frozen) {
    $key = (& $svrBackend gen-key).Trim()
  } else {
    # dev fallback: 32 random bytes, urlsafe-base64 (a valid Fernet key)
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $key = [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
  }
  Set-MachineEnv "SVR_FIELD_KEY" $key
  Write-Host "  SVR_FIELD_KEY generated (kept for the life of the install)."
} else {
  Set-Item -Path "Env:SVR_FIELD_KEY" -Value $existingKey
  Write-Host "  SVR_FIELD_KEY already set - keeping it."
}

# --- 3. migrations -------------------------------------------------------------
Write-Host "Applying migrations ..."
if ($frozen) {
  $migOut = & $svrBackend migrate 2>&1
} else {
  $migOut = & "svr-migrate" 2>&1
}
$migOut | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) { throw "migrations failed (exit $LASTEXITCODE)" }

# Fresh DB -> no users exist yet (prod migrate does not seed demo accounts).
# Someone must create the first Owner before anyone can log in.
if (($migOut -join "`n") -match 'Applied [1-9]') {
  $createUser = if ($frozen) { "`"$svrBackend`" create-user" } else { "svr-create-user" }
  Write-Host ""
  Write-Host "  ===================================================================="
  Write-Host "  NEXT STEP - create the first Owner account (nobody can log in yet):"
  Write-Host ""
  Write-Host "     $createUser --role Owner --name `"<Full Name>`" --login <login>"
  Write-Host ""
  Write-Host "  Run it from an elevated PowerShell; it prompts for the password."
  Write-Host "  ===================================================================="
  Write-Host ""
}

# --- 4. Windows Services ------------------------------------------------------
$svcWarnings = @()
function Register-Service([string]$Exe, [string]$Name, [string]$Module) {
  if ($Exe) {
    Write-Host "Registering $Name (Automatic) from $Exe ..."
    & $Exe --startup auto install
    & $Exe start
  } else {
    # dev fallback - pywin32 self-registration from an installed package
    $py = "python"
    Write-Host "Registering $Name (Automatic) via $py -m $Module ..."
    & $py -m $Module --startup auto install
    & $py -m $Module start
  }
  if ($LASTEXITCODE -ne 0) { $script:svcWarnings += "$Name (install/start exit $LASTEXITCODE)" }
}

Register-Service $backendSvcExe "SVR-IOCL-Backend"   "svr_backend.services.backend_service"
Register-Service $schedSvcExe   "SVR-IOCL-Scheduler" "svr_backend.services.scheduler_service"

# --- 5. frontend Startup shortcut (per-user, not a service) -----------------
$exe = Join-Path $InstallDir "SVR IOCL Station.exe"
if (Test-Path $exe) {
  $startup = [Environment]::GetFolderPath("Startup")
  $lnk = Join-Path $startup "SVR IOCL Station.lnk"
  $ws = New-Object -ComObject WScript.Shell
  $s = $ws.CreateShortcut($lnk)
  $s.TargetPath = $exe
  $s.WorkingDirectory = $InstallDir
  $s.Save()
  Write-Host "Startup shortcut -> $lnk"
} else {
  Write-Warning "Frontend exe not found at $exe - skipping Startup shortcut."
}

if ($svcWarnings.Count -gt 0) {
  Write-Warning ("Service setup issues: " + ($svcWarnings -join "; "))
  Write-Warning "Check services.msc for SVR-IOCL-Backend and SVR-IOCL-Scheduler."
  exit 3
}
Write-Host "Done. services.msc should show SVR-IOCL-Backend and SVR-IOCL-Scheduler (Running / Automatic)."
