<#
.SYNOPSIS
  Uninstall-time teardown for SVR IOCL Station. Runs elevated from the NSIS
  customUnInstall hook (frontend/build/installer.nsh); safe to re-run by hand
  from an elevated PowerShell.

.DESCRIPTION
  Idempotent. It:
    - removes both Windows Services, force-killing a stuck service process so the
      delete cannot get left "marked for deletion";
    - removes the auto-start shortcut from EVERY user's Startup folder plus the
      all-users Startup (the uninstaller often runs as a different account than
      the one that actually uses the app - a per-user-only removal leaves the app
      auto-launching after uninstall);
    - clears the machine env vars that point into the now-deleted install dir
      (SVR_TESSERACT_CMD / SVR_TESSDATA_PREFIX - SDD ADR-6).

  Deliberately KEPT: C:\ProgramData\SVR-IOCL (SQLite DB, nightly backups, logs -
  business records) and SVR_DATA_DIR / SVR_DB_PATH / SVR_LOG_DIR / SVR_FIELD_KEY
  (losing the Fernet key would make encrypted employee bank fields unreadable on
  reinstall). A reinstall resumes cleanly.

  Exit code: 0 = clean; 3 = something could not be fully removed (e.g. a service
  is "marked for deletion" pending a reboot) - the NSIS hook surfaces this.

.PARAMETER InstallDir
  Root of the installed app (holds resources\backend\ with the service exes).
#>
param(
  [string]$InstallDir = (Split-Path -Parent $PSScriptRoot),
  [string]$DataDir     = "$env:ProgramData\SVR-IOCL"
)

# Best-effort: never let a teardown hiccup block the uninstaller.
$ErrorActionPreference = "Continue"
$problems = @()

Write-Host "SVR IOCL Station - uninstall teardown"

$backendDir  = Join-Path $InstallDir "resources\backend"
$serviceExes = [ordered]@{
  "SVR-IOCL-Backend"   = (Join-Path $backendDir "svr-backend-service.exe")
  "SVR-IOCL-Scheduler" = (Join-Path $backendDir "svr-scheduler-service.exe")
}

function Wait-Stopped([string]$Name, [int]$TimeoutSec = 20) {
  for ($i = 0; $i -lt $TimeoutSec; $i++) {
    $s = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $s -or $s.Status -eq "Stopped") { return }
    Start-Sleep -Seconds 1
  }
}

function Remove-SvrService([string]$Name, [string]$Exe) {
  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if (-not $svc) { Write-Host "  $Name not present - ok."; return }

  if ($svc.Status -ne "Stopped") {
    Write-Host "  stopping $Name ..."
    Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
    Wait-Stopped $Name 20
  }

  # Still not stopped -> kill the process, so `remove` / `sc delete` below take
  # effect immediately instead of leaving the service marked for deletion.
  $still = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if ($still -and $still.Status -ne "Stopped") {
    $procId = (Get-CimInstance Win32_Service -Filter "Name='$Name'" -ErrorAction SilentlyContinue).ProcessId
    if ($procId) {
      Write-Host "  $Name did not stop - killing PID $procId ..."
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
      Wait-Stopped $Name 10
    }
  }

  if (Test-Path $Exe) { & $Exe remove 2>&1 | Out-Null }        # pywin32 self-deregister
  if (Get-Service -Name $Name -ErrorAction SilentlyContinue) {
    & sc.exe delete $Name 2>&1 | Out-Null                      # fallback / be sure
  }

  Start-Sleep -Seconds 1
  if (Get-Service -Name $Name -ErrorAction SilentlyContinue) {
    Write-Warning "  $Name still registered (marked for deletion - a reboot completes it)."
    $script:problems += "$Name not fully removed (reboot pending)"
  }
  else {
    Write-Host "  $Name removed."
  }
}

foreach ($name in $serviceExes.Keys) { Remove-SvrService $name $serviceExes[$name] }

# --- auto-start shortcut, for EVERY user + all-users --------------------------
$shortcutName = "SVR IOCL Station.lnk"
$startupDirs  = New-Object System.Collections.Generic.List[string]
$usersRoot = Split-Path -Parent ([Environment]::GetFolderPath("UserProfile"))   # C:\Users
if (Test-Path $usersRoot) {
  Get-ChildItem $usersRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $startupDirs.Add((Join-Path $_.FullName "AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"))
  }
}
$startupDirs.Add([Environment]::GetFolderPath("CommonStartup"))   # all-users
$startupDirs.Add([Environment]::GetFolderPath("Startup"))         # whoever runs this

$removed = 0
foreach ($d in ($startupDirs | Select-Object -Unique)) {
  if (-not $d) { continue }
  $lnk = Join-Path $d $shortcutName
  if (Test-Path $lnk) {
    Remove-Item -Force $lnk -ErrorAction SilentlyContinue
    if (-not (Test-Path $lnk)) { $removed++ } else { $script:problems += "shortcut left at $lnk" }
  }
}
Write-Host "  removed $removed Startup shortcut(s)."

# --- machine env vars that point into the deleted InstallDir (SDD ADR-6) ------
foreach ($stale in @("SVR_TESSERACT_CMD", "SVR_TESSDATA_PREFIX")) {
  if ([Environment]::GetEnvironmentVariable($stale, "Machine")) {
    [Environment]::SetEnvironmentVariable($stale, $null, "Machine")
    Remove-Item "Env:$stale" -ErrorAction SilentlyContinue
    Write-Host "  cleared machine env $stale."
  }
}

Write-Host "  keeping data tree at $DataDir plus SVR_FIELD_KEY / SVR_DATA_DIR / SVR_DB_PATH / SVR_LOG_DIR."

if ($problems.Count -gt 0) {
  Write-Warning ("Teardown incomplete: " + ($problems -join "; "))
  exit 3
}
Write-Host "Done - teardown clean."
exit 0
