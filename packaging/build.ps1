param(
  [switch]$SkipInstaller,
  [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $PSScriptRoot '.build'
$VenvDir = Join-Path $BuildRoot 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$Version = (Get-Content -LiteralPath (Join-Path $ProjectDir 'VERSION') -Raw).Trim()

$UserProfileDir = [Environment]::GetFolderPath('UserProfile')
$PythonCandidates = @(
  $env:DS5VIBEHUB_PYTHON
  (Join-Path $UserProfileDir '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
  ((Get-Command python.exe -ErrorAction SilentlyContinue).Source)
)
$Python = $PythonCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $Python) { throw 'Python 3.10 or newer was not found.' }

if ($Clean -and (Test-Path -LiteralPath $BuildRoot)) {
  $ResolvedBuildRoot = (Resolve-Path -LiteralPath $BuildRoot).Path
  $ResolvedPackagingRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
  if (-not $ResolvedBuildRoot.StartsWith($ResolvedPackagingRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to clean a path outside the packaging directory.'
  }
  Remove-Item -LiteralPath $ResolvedBuildRoot -Recurse -Force
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
  & $Python -m venv --without-pip $VenvDir
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the packaging Python environment.' }
}

& $Python -m pip --python $VenvPython install --disable-pip-version-check --upgrade 'pyinstaller==6.15.0'
if ($LASTEXITCODE -ne 0) { throw 'Could not install PyInstaller 6.15.0.' }
& $VenvPython -m PyInstaller --noconfirm --clean --distpath (Join-Path $PSScriptRoot 'dist') --workpath (Join-Path $BuildRoot 'pyinstaller') (Join-Path $PSScriptRoot 'DualSenseCodex.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$PortableZip = Join-Path $PSScriptRoot ("DualSense-Codex-Portable-{0}.zip" -f $Version)
if (Test-Path -LiteralPath $PortableZip) { Remove-Item -LiteralPath $PortableZip -Force }
$PortableRoot = Join-Path $PSScriptRoot 'dist\DualSenseCodex'
if (-not (Test-Path -LiteralPath $PortableRoot -PathType Container)) { throw 'Portable output directory was not found.' }
Compress-Archive -Path (Join-Path $PortableRoot '*') -DestinationPath $PortableZip -CompressionLevel Optimal

if (-not $SkipInstaller) {
  $CompilerCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    ((Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source)
  )
  $Compiler = $CompilerCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
  if (-not $Compiler) {
    throw 'Inno Setup 6 was not found. Install it or use -SkipInstaller.'
  }
  & $Compiler ("/DMyAppVersion={0}" -f $Version) (Join-Path $PSScriptRoot 'DualSenseCodex.iss')
  if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }
}

$InstallerPath = if ($SkipInstaller) { $null } else { Join-Path $PSScriptRoot ("output\DualSense-Codex-Setup-{0}.exe" -f $Version) }
$ChecksumPath = Join-Path $PSScriptRoot ("SHA256SUMS-{0}.txt" -f $Version)
$ReleaseArtifacts = @($PortableZip)
if ($InstallerPath) { $ReleaseArtifacts += $InstallerPath }
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
