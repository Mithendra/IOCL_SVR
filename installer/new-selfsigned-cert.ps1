<#
.SYNOPSIS
  Create a self-signed code-signing certificate for SVR IOCL Station and print
  everything needed to build with it and to trust it on a station PC.

.DESCRIPTION
  The $0 signing path. A self-signed cert removes the "Unknown publisher"
  SmartScreen warning ONLY on machines where the cert is installed into
  Trusted Root + Trusted Publishers - which is fine for a single on-prem
  dealership where the deployer controls every target PC. It buys no
  SmartScreen reputation and is worthless if the app is ever distributed
  off-network; for that, use Azure Trusted Signing or a CA cert instead.

  This script:
    1. creates a 5-year CodeSigning cert in Cert:\CurrentUser\My
    2. exports  <OutDir>\svr-codesign.cer  (public, to trust on station PCs)
       and      <OutDir>\svr-codesign.pfx  (private, KEEP SECRET, never commit)
    3. prints the thumbprint + the exact build-time env vars + the elevated
       commands to trust it on a station PC

.PARAMETER OutDir
  Where to write the .cer / .pfx. Default: installer\ (both are git-ignored -
  see .gitignore).

.PARAMETER PfxPassword
  Password for the exported .pfx. Prompted (secure) if omitted.

.PARAMETER Subject
  Cert subject. Default "CN=SVR Indian Oil Service Station".
#>
[CmdletBinding()]
param(
  [string]$OutDir = $PSScriptRoot,
  [System.Security.SecureString]$PfxPassword,
  [string]$Subject = "CN=SVR Indian Oil Service Station"
)

$ErrorActionPreference = "Stop"

if (-not $PfxPassword) {
  $PfxPassword = Read-Host -AsSecureString "Password for the exported .pfx"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$cer = Join-Path $OutDir "svr-codesign.cer"
$pfx = Join-Path $OutDir "svr-codesign.pfx"

Write-Host "Creating self-signed CodeSigning cert: $Subject"
$cert = New-SelfSignedCertificate `
  -Type CodeSigningCert `
  -Subject $Subject `
  -CertStoreLocation "Cert:\CurrentUser\My" `
  -KeyUsage DigitalSignature `
  -KeyExportPolicy Exportable `
  -KeyAlgorithm RSA -KeyLength 3072 `
  -HashAlgorithm SHA256 `
  -NotAfter (Get-Date).AddYears(5)

Export-Certificate -Cert $cert -FilePath $cer -Force | Out-Null
Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $PfxPassword -Force | Out-Null

$thumb = $cert.Thumbprint
Write-Host ""
Write-Host "Created:"
Write-Host "  $cer   (public - copy to station PCs to trust)"
Write-Host "  $pfx   (PRIVATE - keep secret, do NOT commit)"
Write-Host "  Thumbprint: $thumb"
Write-Host ""
Write-Host "--- Build a signed installer (from the repo root) -------------------"
Write-Host '  $env:SVR_SIGN_METHOD          = "store"'
Write-Host '  $env:SVR_SIGN_CERT_USER_STORE = "1"      # cert is in CurrentUser\My'
Write-Host "  `$env:SVR_SIGN_CERT_SHA1       = `"$thumb`""
Write-Host "  installer\build-all.ps1"
Write-Host "  installer\verify-signatures.ps1          # expect Valid"
Write-Host ""
Write-Host "  (or sign with the .pfx instead:)"
Write-Host '  $env:SVR_SIGN_METHOD   = "pfx"'
Write-Host "  `$env:CSC_LINK          = `"$pfx`""
Write-Host '  $env:CSC_KEY_PASSWORD  = "<the pfx password>"'
Write-Host ""
Write-Host "--- Trust it on each station PC (elevated PowerShell) ---------------"
Write-Host "  certutil -addstore -f Root            `"$([IO.Path]::GetFileName($cer))`""
Write-Host "  certutil -addstore -f TrustedPublisher `"$([IO.Path]::GetFileName($cer))`""
Write-Host ""
Write-Host "After that, the signed installer runs with no 'Unknown publisher' prompt on that PC."
