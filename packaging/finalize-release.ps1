param(
  [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content -LiteralPath (Join-Path $ProjectDir 'VERSION') -Raw).Trim()
$PortableRoot = Join-Path $PSScriptRoot 'dist\DualSenseCodex'
if (-not (Test-Path -LiteralPath $PortableRoot -PathType Container)) {
  throw 'Portable output directory was not found.'
}

$PortableZip = Join-Path $PSScriptRoot ("DualSense-Codex-Portable-{0}.zip" -f $Version)
if (Test-Path -LiteralPath $PortableZip) { Remove-Item -LiteralPath $PortableZip -Force }
Compress-Archive -Path (Join-Path $PortableRoot '*') -DestinationPath $PortableZip -CompressionLevel Optimal

$InstallerPath = if ($SkipInstaller) { $null } else { Join-Path $PSScriptRoot ("output\DualSense-Codex-Setup-{0}.exe" -f $Version) }
$ReleaseArtifacts = @($PortableZip)
if ($InstallerPath) { $ReleaseArtifacts += $InstallerPath }

$ChecksumPath = Join-Path $PSScriptRoot ("SHA256SUMS-{0}.txt" -f $Version)
$ChecksumLines = foreach ($Artifact in $ReleaseArtifacts) {
  if (-not (Test-Path -LiteralPath $Artifact -PathType Leaf)) {
    throw "Release artifact was not found: $Artifact"
  }
  $Hash = (Get-FileHash -LiteralPath $Artifact -Algorithm SHA256).Hash.ToLowerInvariant()
  "{0}  {1}" -f $Hash, (Split-Path $Artifact -Leaf)
}
Set-Content -LiteralPath $ChecksumPath -Value $ChecksumLines -Encoding ascii

[pscustomobject]@{
  Version = $Version
  Portable = $PortableZip
  Installer = $InstallerPath
  Checksums = $ChecksumPath
}
