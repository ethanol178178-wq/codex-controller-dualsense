[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$DisableTestSigning
)

$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "PowerShell 7 or newer is required. Run this script with pwsh."
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$adminRole = [Security.Principal.WindowsBuiltInRole]::Administrator
if (-not $principal.IsInRole($adminRole) -and -not $WhatIfPreference) {
    $pwsh = Join-Path $PSHOME "pwsh.exe"
    $arguments = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`""
    )
    if ($DisableTestSigning) { $arguments += "-DisableTestSigning" }
    $process = Start-Process -FilePath $pwsh -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}

$devcon = "${env:ProgramFiles(x86)}\Windows Kits\10\Tools\10.0.26100.0\x64\devcon.exe"
$hardwareId = "Root\DS5VibeHubTouchpad"
$certificateSubject = "CN=DS5 Vibe Hub Test Driver"

if (-not (Test-Path -LiteralPath $devcon)) {
    throw "DevCon is missing: $devcon. Install the Windows 11 WDK 10.0.26100.0 first."
}

$deviceLines = @(& $devcon findall $hardwareId 2>$null)
$instanceIds = @(
    $deviceLines |
        ForEach-Object {
            if ($_ -match '^([^ ]+)\s+:') { $matches[1] }
        } |
        Sort-Object -Unique
)

foreach ($instanceId in $instanceIds) {
    if ($PSCmdlet.ShouldProcess($instanceId, "Remove virtual touchpad device")) {
        & $devcon remove "@$instanceId"
        if ($LASTEXITCODE -notin @(0, 1)) {
            throw "DevCon could not remove $instanceId (exit code $LASTEXITCODE)."
        }
    }
}

foreach ($store in @("Root", "TrustedPublisher")) {
    $certificates = @(
        Get-ChildItem -Path "Cert:\LocalMachine\$store" -ErrorAction Stop |
            Where-Object Subject -eq $certificateSubject
    )
    foreach ($certificate in $certificates) {
        $target = "LocalMachine\$store\$($certificate.Thumbprint)"
        if ($PSCmdlet.ShouldProcess($target, "Remove DS5 Vibe Hub test certificate")) {
            Remove-Item -LiteralPath $certificate.PSPath -Force
        }
    }
}

if ($DisableTestSigning) {
    if ($PSCmdlet.ShouldProcess("Windows boot configuration", "Disable test-signing after restart")) {
        & bcdedit.exe /set testsigning off
        if ($LASTEXITCODE -ne 0) {
            throw "Could not disable Windows test-signing. Run 'bcdedit /enum {current}' and inspect it manually."
        }
        Write-Host "Windows test-signing will be disabled after the next restart."
    }
} else {
    Write-Host "Test-signing was left unchanged. Re-run with -DisableTestSigning when no other test driver needs it."
}

if ($instanceIds.Count -eq 0) {
    Write-Host "No DS5 virtual touchpad device was registered."
}
if ($WhatIfPreference) {
    Write-Host "Preview completed; no driver, certificate, or boot setting was changed."
} else {
    Write-Host "Driver cleanup completed. Restart Windows if the device or test-signing state is still visible."
}
