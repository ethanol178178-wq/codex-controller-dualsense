param(
  [switch]$Elevated
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$adminRole = [Security.Principal.WindowsBuiltInRole]::Administrator
$currentShell = (Get-Process -Id $PID).Path
if ([IO.Path]::GetFileName($currentShell) -notin @('powershell.exe', 'pwsh.exe')) {
  throw 'Windows PowerShell or PowerShell 7 is required.'
}
if (-not $principal.IsInRole($adminRole)) {
  # Re-enter this same script through UAC, then let the elevated child do the
  # process ownership check and restart. Nothing else is stopped.
  $elevatedProcess = Start-Process -FilePath $currentShell -Verb RunAs -Wait -PassThru -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $MyInvocation.MyCommand.Path + '"'), '-Elevated'
  )
  if ($elevatedProcess.ExitCode -ne 0) { throw "Elevated bridge restart failed with exit code $($elevatedProcess.ExitCode)" }
  exit 0
}

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UserProfileDir = [Environment]::GetFolderPath('UserProfile')
$PythonCandidates = @(
  $env:DS5VIBEHUB_PYTHON
  (Join-Path $UserProfileDir '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
  ((Get-Command python.exe -ErrorAction SilentlyContinue).Source)
)
$Python = $PythonCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
$Bridge = Join-Path $ProjectDir 'bridge.py'
$Marker = Join-Path $ProjectDir 'bridge-restart-admin.result.json'

function Test-BridgeProcessOwner {
  param(
    [Parameter(Mandatory)][int]$CandidatePid,
    [Parameter(Mandatory)][string]$ExpectedBridge
  )

  try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $CandidatePid" -ErrorAction Stop
  } catch {
    return $false
  }
  if (-not $process -or -not $process.ExecutablePath -or -not $process.CommandLine) {
    return $false
  }
  $executableName = [IO.Path]::GetFileName([string]$process.ExecutablePath)
  $isPython = $executableName -in @('python.exe', 'pythonw.exe')
  $ownsBridge = ([string]$process.CommandLine).IndexOf(
    $ExpectedBridge, [StringComparison]::OrdinalIgnoreCase
  ) -ge 0
  return $isPython -and $ownsBridge
}

if (-not $Python) { throw 'Python runtime not found. Set DS5VIBEHUB_PYTHON or add python.exe to PATH.' }
if (-not (Test-Path -LiteralPath $Bridge)) { throw "Bridge not found: $Bridge" }

$listenerPids = @()
for ($attempt = 0; $attempt -lt 3; $attempt++) {
  $listeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 37845 -State Listen -ErrorAction SilentlyContinue)
  $listenerPids = @($listeners | ForEach-Object { [int]$_.OwningProcess } | Sort-Object -Unique)
  $unexpectedPids = @($listenerPids | Where-Object { -not (Test-BridgeProcessOwner -CandidatePid $_ -ExpectedBridge $Bridge) })
  if ($unexpectedPids.Count -ne 0) {
    throw "Port 37845 is owned by a non-bridge process; refusing to stop PID(s): $($unexpectedPids -join ', ')"
  }
  foreach ($ownerPid in $listenerPids) {
    # Every PID above was verified against this project's absolute bridge path.
    Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Milliseconds 700
  $remaining = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 37845 -State Listen -ErrorAction SilentlyContinue)
  if ($remaining.Count -eq 0) { break }
}
$remaining = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 37845 -State Listen -ErrorAction SilentlyContinue)
if ($remaining.Count -ne 0) {
  throw "Could not clear existing bridge listeners: $(@($remaining | ForEach-Object OwningProcess) -join ', ')"
}

$startInfo = [Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $Python
$startInfo.Arguments = '-B "' + $Bridge + '"'
$startInfo.WorkingDirectory = $ProjectDir
$startInfo.UseShellExecute = $true
$startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
$proc = [Diagnostics.Process]::Start($startInfo)
Start-Sleep -Seconds 2
$listen = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 37845 -State Listen -ErrorAction SilentlyContinue)
$result = [ordered]@{
  elevated = $true
  bridgePid = $proc.Id
  listenerPids = @($listen | ForEach-Object OwningProcess)
  at = (Get-Date).ToUniversalTime().ToString('o')
}
[IO.File]::WriteAllText($Marker, ($result | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
if ($listen.Count -ne 1 -or $listen[0].OwningProcess -ne $proc.Id) { throw 'Bridge did not bind exactly to 127.0.0.1:37845' }

# Keep the elevated launcher alive for the lifetime of the bridge. In the
# Codex Desktop process tree, an orphaned elevated child can otherwise be
# reclaimed shortly after this script exits even though it bound correctly.
$proc.WaitForExit()
exit $proc.ExitCode
