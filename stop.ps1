param(
  [switch]$Elevated
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$adminRole = [Security.Principal.WindowsBuiltInRole]::Administrator
$currentShell = (Get-Process -Id $PID).Path
if (-not $principal.IsInRole($adminRole)) {
  $elevatedProcess = Start-Process -FilePath $currentShell -Verb RunAs -Wait -PassThru -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $MyInvocation.MyCommand.Path + '"'), '-Elevated'
  )
  if ($elevatedProcess.ExitCode -ne 0) {
    throw "Elevated stop failed with exit code $($elevatedProcess.ExitCode)"
  }
  exit 0
}

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bridge = Join-Path $ProjectDir 'bridge.py'
$WebServer = Join-Path $ProjectDir 'serve_ui.py'
$ApprovalWatcher = Join-Path $ProjectDir 'approval_watcher.py'

function Test-ProjectListenerOwner {
  param(
    [Parameter(Mandatory)][int]$CandidatePid,
    [Parameter(Mandatory)][int]$Port
  )

  try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $CandidatePid" -ErrorAction Stop
  } catch {
    return $false
  }
  if (-not $process -or -not $process.ExecutablePath -or -not $process.CommandLine) {
    return $false
  }
  if ([IO.Path]::GetFileName([string]$process.ExecutablePath) -notin @('python.exe', 'pythonw.exe')) {
    return $false
  }
  $commandLine = [string]$process.CommandLine
  if ($Port -eq 37845) {
    return $commandLine.IndexOf($Bridge, [StringComparison]::OrdinalIgnoreCase) -ge 0
  }
  return $Port -eq 4173 -and $commandLine.IndexOf($WebServer, [StringComparison]::OrdinalIgnoreCase) -ge 0
}

$stopped = @()
foreach ($port in @(37845, 4173)) {
  $listenerPids = @(
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
      ForEach-Object { [int]$_.OwningProcess } |
      Sort-Object -Unique
  )
  $unexpectedPids = @(
    $listenerPids | Where-Object { -not (Test-ProjectListenerOwner -CandidatePid $_ -Port $port) }
  )
  if ($unexpectedPids.Count -ne 0) {
    throw "Port $port is owned by a non-project process; refusing to stop PID(s): $($unexpectedPids -join ', ')"
  }
  foreach ($ownerPid in $listenerPids) {
    Stop-Process -Id $ownerPid -Force -ErrorAction Stop
    $stopped += $ownerPid
  }
}

# The compatibility watcher has no listening port. Stop only a Python process
# whose command line contains this project's exact watcher path.
try {
  $watchers = @(
    Get-CimInstance Win32_Process -ErrorAction Stop |
      Where-Object {
        ([IO.Path]::GetFileName([string]$_.ExecutablePath) -in @('python.exe', 'pythonw.exe')) -and
        ([string]$_.CommandLine).IndexOf($ApprovalWatcher, [StringComparison]::OrdinalIgnoreCase) -ge 0
      }
  )
} catch {
  throw "Could not inspect the compatibility watcher process list: $($_.Exception.Message)"
}
foreach ($watcher in $watchers) {
  Stop-Process -Id ([int]$watcher.ProcessId) -Force -ErrorAction Stop
  $stopped += [int]$watcher.ProcessId
}

[pscustomobject]@{
  StoppedPids = @($stopped | Sort-Object -Unique)
  Bridge = 'http://127.0.0.1:37845'
  Web = 'http://127.0.0.1:4173/'
}
