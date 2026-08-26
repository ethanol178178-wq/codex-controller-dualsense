param(
  [switch]$SkipInstaller,
  [switch]$SkipFinalize,
  [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $PSScriptRoot '.build'
$VenvDir = Join-Path $BuildRoot 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$Version = (Get-Content -LiteralPath (Join-Path $ProjectDir 'VERSION') -Raw).Trim()
if ($Version -notmatch '^\d+(\.\d+){0,3}$') {
  throw "VERSION must contain one to four numeric components: $Version"
}
$VersionParts = @($Version.Split('.') | ForEach-Object { [int]$_ })
while ($VersionParts.Count -lt 4) { $VersionParts += 0 }
$FourPartVersion = $VersionParts -join '.'
$VersionTuple = "({0}, {1}, {2}, {3})" -f $VersionParts[0], $VersionParts[1], $VersionParts[2], $VersionParts[3]

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

$VersionInfoPath = Join-Path $BuildRoot 'windows-version-info.txt'
$VersionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=$VersionTuple,
    prodvers=$VersionTuple,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Codex Controller for DualSense contributors'),
          StringStruct('FileDescription', 'DualSense controller integration for Codex Desktop'),
          StringStruct('FileVersion', '$FourPartVersion'),
          StringStruct('InternalName', 'DualSenseCodex'),
          StringStruct('LegalCopyright', 'Copyright (c) Codex Controller for DualSense contributors'),
          StringStruct('OriginalFilename', 'DualSenseCodex.exe'),
          StringStruct('ProductName', 'Codex Controller for DualSense'),
          StringStruct('ProductVersion', '$FourPartVersion')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
Set-Content -LiteralPath $VersionInfoPath -Value $VersionInfo -Encoding ascii
$env:DUALSENSE_CODEX_VERSION_FILE = $VersionInfoPath
& $VenvPython -m PyInstaller --noconfirm --clean --distpath (Join-Path $PSScriptRoot 'dist') --workpath (Join-Path $BuildRoot 'pyinstaller') (Join-Path $PSScriptRoot 'DualSenseCodex.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

if (-not $SkipInstaller) {
  & (Join-Path $PSScriptRoot 'build-installer.ps1') -Version $Version
}

if (-not $SkipFinalize) {
  & (Join-Path $PSScriptRoot 'finalize-release.ps1') -SkipInstaller:$SkipInstaller
}

[pscustomobject]@{
  Version = $Version
  PortableRoot = Join-Path $PSScriptRoot 'dist\DualSenseCodex'
  Installer = if ($SkipInstaller) { $null } else { Join-Path $PSScriptRoot ("output\DualSense-Codex-Setup-{0}.exe" -f $Version) }
  Finalized = -not $SkipFinalize
}
