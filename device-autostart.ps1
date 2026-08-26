$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $ProjectDir 'start-admin.ps1'
$LogPath = Join-Path $ProjectDir 'device-autostart.log'
$ControllerPattern = 'VID_054C&PID_0CE6'
$WasPresent = $false

function Write-WatcherLog([string]$Message) {
  $line = '{0:u} {1}' -f (Get-Date), $Message
  Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Test-ControllerPresent {
  return [bool](
    Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
      Where-Object { $_.InstanceId -like "*$ControllerPattern*" } |
      Select-Object -First 1
  )
}

function Test-BridgeOnline {
  try {
    $status = Invoke-RestMethod -Uri 'http://127.0.0.1:37845/api/status' -TimeoutSec 2
    return [bool]$status.ok
  } catch {
    return $false
  }
}

Write-WatcherLog 'DualSense device watcher started.'
while ($true) {
  try {
    $present = Test-ControllerPresent
    if ($present -and ((-not $WasPresent) -or (-not (Test-BridgeOnline)))) {
      Write-WatcherLog 'DualSense detected; starting controller services.'
      & $Launcher | Out-String | ForEach-Object { if ($_.Trim()) { Write-WatcherLog $_.Trim() } }
    }
    $WasPresent = $present
  } catch {
    Write-WatcherLog ("Watcher error: " + $_.Exception.Message)
  }
  Start-Sleep -Seconds 2
}
