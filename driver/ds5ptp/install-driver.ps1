$ErrorActionPreference = "Stop"
$package = Join-Path $PSScriptRoot "package"
$installLog = Join-Path $package "install-driver.log"

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "PowerShell 7 or newer is required. Run this script with pwsh."
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $pwsh = Join-Path $PSHOME "pwsh.exe"
    if (Test-Path -LiteralPath $installLog) {
        Remove-Item -LiteralPath $installLog -Force
    }
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $process = Start-Process -FilePath $pwsh -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    if (Test-Path -LiteralPath $installLog) {
        Get-Content -LiteralPath $installLog
    }
    exit $process.ExitCode
}

Start-Transcript -LiteralPath $installLog -Force | Out-Null
$certificate = Join-Path $package "DS5VibeHubTestDriver.cer"
$inf = Join-Path $package "DS5VirtualPrecisionTouchpad.inf"
$devcon = "${env:ProgramFiles(x86)}\Windows Kits\10\Tools\10.0.26100.0\x64\devcon.exe"
$hardwareId = "Root\DS5VibeHubTouchpad"

foreach ($file in @($certificate, $inf, $devcon)) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Required install file is missing: $file. Run build-driver.ps1 first."
    }
}

Import-Certificate -FilePath $certificate -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
Import-Certificate -FilePath $certificate -CertStoreLocation Cert:\LocalMachine\TrustedPublisher | Out-Null

& bcdedit.exe /set testsigning on
if ($LASTEXITCODE -ne 0) {
    throw "Could not enable Windows test-signing mode. Disable Secure Boot if BCDEdit reports that the value is protected."
}

$deviceMatches = @((& $devcon findall $hardwareId 2>$null) | Where-Object {
    $_ -match '^ROOT\\HIDCLASS\\[^ ]+\s+:'
})
if ($deviceMatches.Count -gt 0) {
    Write-Host "Updating existing virtual touchpad device(s): $($deviceMatches.Count)"
    & $devcon update $inf $hardwareId
} else {
    Write-Host "Creating virtual touchpad device: $hardwareId"
    & $devcon install $inf $hardwareId
}
if ($LASTEXITCODE -notin @(0, 1)) {
    throw "DevCon failed with exit code $LASTEXITCODE"
}

Write-Host "The test-signed driver package is installed."
Write-Host "Restart Windows to enter test-signing mode, then restart the DS5 bridge."
Stop-Transcript | Out-Null
