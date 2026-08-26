param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$TaskName = 'DualSense Vibe Hub'
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Watcher = Join-Path $ProjectDir 'device-autostart.ps1'

$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$PrincipalCheck = [Security.Principal.WindowsPrincipal]::new($Identity)
if (-not $PrincipalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  $Arguments = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
  if ($Remove) { $Arguments += '-Remove' }
  $Process = Start-Process -FilePath 'powershell.exe' -ArgumentList $Arguments -Verb RunAs -Wait -PassThru -WindowStyle Hidden
  exit $Process.ExitCode
}

if ($Remove) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Output 'DualSense Vibe Hub startup task removed.'
  exit 0
}

if (-not (Test-Path -LiteralPath $Watcher -PathType Leaf)) {
  throw "Device watcher not found: $Watcher"
}

$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$Arguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $Watcher + '"'
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Watches for a DualSense USB controller and starts the local controller services when it is connected.'

Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Output 'DualSense Vibe Hub will now start automatically after Windows sign-in.'
