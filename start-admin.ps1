$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$UserProfileDir = [Environment]::GetFolderPath("UserProfile")
$PythonCandidates = @(
  $env:DS5VIBEHUB_PYTHON
  (Join-Path $UserProfileDir ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
  ((Get-Command python.exe -ErrorAction SilentlyContinue).Source)
)
$Python = $PythonCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
$Bridge = Join-Path $ProjectDir "bridge.py"
$ApprovalWatcher = Join-Path $ProjectDir "approval_watcher.py"
$WebServer = Join-Path $ProjectDir "serve_ui.py"
$WebLog = Join-Path $ProjectDir "web-server.log"
$BridgeLog = Join-Path $ProjectDir "bridge-admin.log"
$WebErr = Join-Path $ProjectDir "web-server.err"

if (-not $Python) { throw "Python runtime not found. Set DS5VIBEHUB_PYTHON or add python.exe to PATH." }

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
  $executableName = [IO.Path]::GetFileName([string]$process.ExecutablePath)
  if ($executableName -notin @('python.exe', 'pythonw.exe')) {
    return $false
  }
  $commandLine = [string]$process.CommandLine
  if ($Port -eq 37845) {
    return $commandLine.IndexOf($Bridge, [StringComparison]::OrdinalIgnoreCase) -ge 0
  }
  if ($Port -eq 4173) {
    return $commandLine.IndexOf($WebServer, [StringComparison]::OrdinalIgnoreCase) -ge 0
  }
  return $false
}

$StartBridge = $true
$StartWeb = $true

# Reuse listeners whose command line proves that they belong to this project.
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
  if ($listenerPids.Count -gt 1) {
    throw "Port $port has multiple project listeners; stop them explicitly before starting."
  }
  if ($port -eq 37845 -and $listenerPids.Count -eq 1) { $StartBridge = $false }
  if ($port -eq 4173 -and $listenerPids.Count -eq 1) { $StartWeb = $false }
}

# The bridge needs elevation for reliable HID output and SendInput into elevated apps.
if ($StartBridge) {
  $bridgeArgs = @('-B', ('"' + $Bridge + '"'))
  Start-Process -FilePath $Python -ArgumentList $bridgeArgs -WorkingDirectory $ProjectDir -Verb RunAs -WindowStyle Hidden | Out-Null
}

# Some Codex Desktop builds do not emit PermissionRequest hooks. This
# unprivileged watcher forwards only structured require_escalated calls to the
# bridge and exits automatically once the bridge's built-in v3 fallback runs.
if ($StartBridge -and (Test-Path -LiteralPath $ApprovalWatcher)) {
  Start-Process -FilePath $Python -ArgumentList @('-B', ('"' + $ApprovalWatcher + '"')) -WorkingDirectory $ProjectDir -WindowStyle Hidden | Out-Null
}

Start-Sleep -Milliseconds 700

# Serve only the allowlisted UI assets on the stable browser port.
$webArgs = @('-B', ('"' + $WebServer + '"'))
if ($StartWeb) {
  Start-Process -FilePath $Python -ArgumentList $webArgs -WorkingDirectory $ProjectDir -WindowStyle Hidden -RedirectStandardOutput $WebLog -RedirectStandardError $WebErr | Out-Null
}

Start-Sleep -Seconds 1
$bridge = Invoke-RestMethod "http://127.0.0.1:37845/api/status"
$page = Invoke-WebRequest "http://127.0.0.1:4173/" -UseBasicParsing
[pscustomobject]@{
  Bridge = "http://127.0.0.1:37845"
  Web = "http://127.0.0.1:4173/"
  BridgeOk = [bool]$bridge.ok
  WebStatus = [int]$page.StatusCode
  Controller = [bool]$bridge.input.connected
  CodexHooks = [int]$bridge.codex.hookCount
}
