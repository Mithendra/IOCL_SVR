<#
.SYNOPSIS
  Authenticode-sign one or more files, using whichever mechanism the environment
  selects. Wired but DORMANT by default - with no cert configured it leaves files
  unsigned and exits 0, so an unsigned build still succeeds.

.DESCRIPTION
  Called from two places:
    - backend/packaging/build-backend.ps1  - signs the 3 frozen svr-backend*.exe
      (electron-builder never sees inside extraResources, so it can't sign them)
    - frontend/build/sign-hook.js           - electron-builder's win.sign hook,
      one call per PE it builds (app exe, uninstaller, NSIS installer)

  Mechanism = $env:SVR_SIGN_METHOD, one of:

    none                     (default) do nothing, exit 0
    pfx                      $env:CSC_LINK = path to .pfx, $env:CSC_KEY_PASSWORD
    store                    a cert already in the Windows cert store - hardware
                             token OR self-signed (see installer/new-selfsigned-cert.ps1).
                             $env:SVR_SIGN_CERT_SHA1  (thumbprint, preferred) or
                             $env:SVR_SIGN_CERT_SUBJECT (CN substring)
    azure-trusted-signing    $env:SVR_ATS_DLIB = path to Azure.CodeSigning.Dlib.dll,
                             $env:SVR_ATS_ENDPOINT, $env:SVR_ATS_ACCOUNT,
                             $env:SVR_ATS_CERT_PROFILE, plus AZURE_TENANT_ID /
                             AZURE_CLIENT_ID / AZURE_CLIENT_SECRET for auth.

  If SVR_SIGN_METHOD is unset it is inferred from whichever of the above is
  present, else 'none'.

  Timestamp URL: $env:SVR_SIGN_TIMESTAMP_URL (default http://timestamp.digicert.com).

.PARAMETER Path
  One or more files to sign (or to inspect, with -Verify).

.PARAMETER Verify
  Don't sign - just print each file's Authenticode status. Exit 1 if -RequireSigned
  and any file is not Valid.

.PARAMETER RequireSigned
  With -Verify, treat an unsigned / invalid file as a failure.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory, Position = 0)][string[]]$Path,
  [switch]$Verify,
  [switch]$RequireSigned
)

$ErrorActionPreference = "Stop"

function Resolve-Method {
  if ($env:SVR_SIGN_METHOD) { return $env:SVR_SIGN_METHOD.Trim().ToLower() }
  if ($env:CSC_LINK) { return "pfx" }
  if ($env:SVR_SIGN_CERT_SHA1 -or $env:SVR_SIGN_CERT_SUBJECT) { return "store" }
  if ($env:SVR_ATS_ENDPOINT -and $env:SVR_ATS_ACCOUNT) { return "azure-trusted-signing" }
  return "none"
}

function Find-SignTool {
  $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $roots = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "${env:ProgramFiles}\Windows Kits\10\bin")
  $hit = $roots | Where-Object { Test-Path $_ } | ForEach-Object {
    Get-ChildItem $_ -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -match '\\(x64|arm64)\\' }
  } | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $hit) { throw "signtool.exe not found. Install the Windows 10/11 SDK (Signing Tools) or add it to PATH." }
  return $hit.FullName
}

function Show-Status([string[]]$files) {
  $bad = 0
  foreach ($f in $files) {
    if (-not (Test-Path $f)) { Write-Host ("  {0,-10} {1}" -f "MISSING", $f); $bad++; continue }
    $s = Get-AuthenticodeSignature -FilePath $f
    Write-Host ("  {0,-10} {1}  {2}" -f $s.Status, (Split-Path $f -Leaf), $s.SignerCertificate.Subject)
    if ($s.Status -ne "Valid") { $bad++ }
  }
  return $bad
}

# --- verify-only ------------------------------------------------------------
if ($Verify) {
  Write-Host "Authenticode status:"
  $bad = Show-Status $Path
  if ($RequireSigned -and $bad -gt 0) { Write-Error "$bad file(s) not validly signed."; exit 1 }
  exit 0
}

# --- sign -----------------------------------------------------------------------
$method = Resolve-Method
if ($method -eq "none") {
  Write-Host "sign.ps1: SVR_SIGN_METHOD=none - leaving $($Path.Count) file(s) unsigned."
  Write-Host "          set SVR_SIGN_METHOD (+ credentials) to enable; see installer/README.md."
  exit 0
}

$ts = if ($env:SVR_SIGN_TIMESTAMP_URL) { $env:SVR_SIGN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
$signtool = Find-SignTool
Write-Host "sign.ps1: method=$method  signtool=$signtool  timestamp=$ts"

$common = @("sign", "/fd", "SHA256", "/tr", $ts, "/td", "SHA256", "/v")

switch ($method) {
  "pfx" {
    if (-not $env:CSC_LINK) { throw "method=pfx needs `$env:CSC_LINK (path to .pfx)" }
    $args = $common + @("/f", $env:CSC_LINK)
    if ($env:CSC_KEY_PASSWORD) { $args += @("/p", $env:CSC_KEY_PASSWORD) }
  }
  "store" {
    $args = $common + @("/sm")   # /sm = machine store; drop if the cert is in the user store
    if ($env:SVR_SIGN_CERT_SHA1) { $args += @("/sha1", ($env:SVR_SIGN_CERT_SHA1 -replace '\s', '')) }
    elseif ($env:SVR_SIGN_CERT_SUBJECT) { $args += @("/n", $env:SVR_SIGN_CERT_SUBJECT) }
    else { throw "method=store needs `$env:SVR_SIGN_CERT_SHA1 or `$env:SVR_SIGN_CERT_SUBJECT" }
    if ($env:SVR_SIGN_CERT_USER_STORE) { $args = $args | Where-Object { $_ -ne "/sm" } }
  }
  "azure-trusted-signing" {
    foreach ($v in "SVR_ATS_DLIB", "SVR_ATS_ENDPOINT", "SVR_ATS_ACCOUNT", "SVR_ATS_CERT_PROFILE") {
      if (-not (Get-Item "Env:$v" -ErrorAction SilentlyContinue)) { throw "method=azure-trusted-signing needs `$env:$v" }
    }
    if (-not (Test-Path $env:SVR_ATS_DLIB)) { throw "SVR_ATS_DLIB not found: $env:SVR_ATS_DLIB (install the Azure.CodeSigning.Dlib / trusted-signing dlib)" }
    $md = Join-Path $env:TEMP "svr-ats-metadata.json"
    @{
      Endpoint               = $env:SVR_ATS_ENDPOINT
      CodeSigningAccountName  = $env:SVR_ATS_ACCOUNT
      CertificateProfileName  = $env:SVR_ATS_CERT_PROFILE
    } | ConvertTo-Json | Set-Content -Path $md -Encoding utf8
    $args = $common + @("/dlib", $env:SVR_ATS_DLIB, "/dmdf", $md)
  }
  default { throw "unknown SVR_SIGN_METHOD '$method' (none|pfx|store|azure-trusted-signing)" }
}

foreach ($f in $Path) {
  if (-not (Test-Path $f)) { throw "file to sign not found: $f" }
  Write-Host "  signing $f"
  & $signtool @args $f
  if ($LASTEXITCODE -ne 0) { throw "signtool failed on $f (exit $LASTEXITCODE)" }
}

Write-Host "sign.ps1: signed $($Path.Count) file(s). Verifying ..."
$bad = Show-Status $Path
if ($bad -gt 0) { throw "post-sign verification found $bad unsigned/invalid file(s)" }
