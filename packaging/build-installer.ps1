param(
  [string]$Version = (Get-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'VERSION') -Raw).Trim()
)

$ErrorActionPreference = 'Stop'
$PortableRoot = Join-Path $PSScriptRoot 'dist\DualSenseCodex'
if (-not (Test-Path -LiteralPath $PortableRoot -PathType Container)) {
  throw 'Portable output directory was not found. Build or restore the portable artifact first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PortableRoot 'DualSenseCodex.exe') -PathType Leaf)) {
  throw 'DualSenseCodex.exe was not found in the portable output directory.'
}

$CompilerCandidates = @(
  (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
  (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
  (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
  ((Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source)
)
$Compiler = $CompilerCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $Compiler) {
  throw 'Inno Setup 6 was not found.'
}

& $Compiler ("/DMyAppVersion={0}" -f $Version) (Join-Path $PSScriptRoot 'DualSenseCodex.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }

$InstallerPath = Join-Path $PSScriptRoot ("output\DualSense-Codex-Setup-{0}.exe" -f $Version)
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
  throw "Installer output was not found: $InstallerPath"
}
$InstallerPath
