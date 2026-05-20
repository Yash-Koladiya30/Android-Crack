#requires -Version 5.1
<#
.SYNOPSIS
    Android-Crack dependency installer for Windows 11.

.DESCRIPTION
    Installs adb (Android platform-tools), scrcpy, nmap, and Python 3.11+
    via winget. Falls back to Chocolatey when available. Metasploit on
    Windows: links to the official installer (winget package not stable).

.PARAMETER Components
    Comma-separated subset of: python,adb,scrcpy,nmap,metasploit

.PARAMETER Interactive
    Prompt per component instead of bulk install.

.PARAMETER NonInteractive
    Suppress all prompts (assume yes).

.EXAMPLE
    Set-ExecutionPolicy -Scope Process Bypass
    .\install.ps1
    .\install.ps1 -Components adb,nmap,python
    .\install.ps1 -Interactive
#>

[CmdletBinding()]
param(
    [string]$Components = "",
    [switch]$Interactive,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"

function Test-Admin {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Warning "Run this script from an elevated PowerShell (Run as Administrator)."
    exit 2
}

function Want([string]$Name) {
    if ([string]::IsNullOrEmpty($Components)) { return $true }
    return ($Components.Split(',') -contains $Name)
}

function Confirm-Install([string]$Label) {
    if ($NonInteractive) { return $true }
    if (-not $Interactive) { return $true }
    $ans = Read-Host "Install $Label`? [Y/n]"
    return ([string]::IsNullOrEmpty($ans)) -or ($ans -match '^[yY]')
}

function Has-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function Has-Choco  { return [bool](Get-Command choco  -ErrorAction SilentlyContinue) }

function Install-Winget([string]$Id, [string]$Label) {
    Write-Host "[android-crack] winget install $Id ($Label)"
    winget install --silent --accept-source-agreements --accept-package-agreements --id $Id
}

function Install-Choco([string]$Pkg, [string]$Label) {
    Write-Host "[android-crack] choco install $Pkg ($Label)"
    choco install -y $Pkg
}

if (-not (Has-Winget) -and -not (Has-Choco)) {
    Write-Error @"
Neither winget nor Chocolatey is available.
Install one first:
  - winget ships with Windows 11 / App Installer (https://aka.ms/getwinget)
  - Chocolatey: https://chocolatey.org/install
"@
    exit 2
}

if (Want "python" -and (Confirm-Install "Python 3.11+")) {
    if (Has-Winget) { Install-Winget "Python.Python.3.12" "Python 3.12" }
    elseif (Has-Choco) { Install-Choco "python" "Python" }
}

if (Want "adb" -and (Confirm-Install "Android platform-tools (adb)")) {
    if (Has-Winget) { Install-Winget "Google.PlatformTools" "Android platform-tools" }
    elseif (Has-Choco) { Install-Choco "adb" "adb" }
}

if (Want "scrcpy" -and (Confirm-Install "scrcpy")) {
    if (Has-Winget) { Install-Winget "Genymobile.scrcpy" "scrcpy" }
    elseif (Has-Choco) { Install-Choco "scrcpy" "scrcpy" }
}

if (Want "nmap" -and (Confirm-Install "Nmap")) {
    if (Has-Winget) { Install-Winget "Insecure.Nmap" "Nmap" }
    elseif (Has-Choco) { Install-Choco "nmap" "Nmap" }
}

if (Want "metasploit" -and (Confirm-Install "Metasploit-Framework")) {
    Write-Host ""
    Write-Host "[android-crack] Metasploit on Windows is best installed via the official installer:"
    Write-Host "  https://www.metasploit.com/download"
    Write-Host "  (Antivirus may flag the payload generator. See docs for exceptions.)"
}

Write-Host ""
Write-Host "[android-crack] Dependencies attempted. Open a NEW PowerShell so PATH refreshes, then:"
Write-Host "  python -m venv .venv"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  pip install -e ."
Write-Host "  android-crack --i-have-authorization"
