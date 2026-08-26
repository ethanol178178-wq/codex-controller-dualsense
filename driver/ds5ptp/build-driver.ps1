$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "PowerShell 7 or newer is required. Run this script with pwsh."
}

$driverRoot = $PSScriptRoot
$workspaceRoot = Split-Path (Split-Path $driverRoot -Parent) -Parent
$msbuild = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
$inf2cat = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.26100.0\x86\Inf2Cat.exe"
$signtool = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
$project = Join-Path $driverRoot "ds5ptp.vcxproj"
$builtDll = Join-Path $driverRoot "bin\x64\Release\DS5VirtualPrecisionTouchpad.dll"
$package = Join-Path $driverRoot "package"
$subject = "CN=DS5 Vibe Hub Test Driver"

foreach ($tool in @($msbuild, $inf2cat, $signtool)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        throw "Required build tool is missing: $tool"
    }
}

& $msbuild $project /p:Configuration=Release /p:Platform=x64 /m
if ($LASTEXITCODE -ne 0) {
    throw "Driver build failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $package) {
    $resolvedPackage = (Resolve-Path -LiteralPath $package).Path
    if (-not $resolvedPackage.StartsWith($driverRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clear package path outside the driver directory: $resolvedPackage"
    }
    Remove-Item -LiteralPath $resolvedPackage -Recurse -Force
}
New-Item -ItemType Directory -Path $package | Out-Null
Copy-Item -LiteralPath $builtDll -Destination $package
Copy-Item -LiteralPath (Join-Path $driverRoot "DS5VirtualPrecisionTouchpad.inf") -Destination $package

& $inf2cat "/driver:$package" /os:10_X64 /verbose
if ($LASTEXITCODE -ne 0) {
    throw "Inf2Cat failed with exit code $LASTEXITCODE"
}

$certificate = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object Subject -eq $subject |
    Where-Object NotAfter -gt (Get-Date).AddDays(1) |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1
if (-not $certificate) {
    $certificate = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $subject `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(3)
}

$cerPath = Join-Path $package "DS5VibeHubTestDriver.cer"
Export-Certificate -Cert $certificate -FilePath $cerPath -Force | Out-Null
foreach ($file in @(
    (Join-Path $package "DS5VirtualPrecisionTouchpad.dll"),
    (Join-Path $package "DS5VirtualPrecisionTouchpad.cat")
)) {
    & $signtool sign /sha1 $certificate.Thumbprint /s My /fd SHA256 $file
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool failed for $file with exit code $LASTEXITCODE"
    }
}

Write-Host "Built and test-signed package: $package"
Write-Host "Certificate thumbprint: $($certificate.Thumbprint)"
