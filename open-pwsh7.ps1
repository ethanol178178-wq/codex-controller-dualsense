$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -lt 7 -or $PSVersionTable.PSEdition -ne 'Core') {
  throw 'Run this launcher with PowerShell 7 (pwsh.exe).'
}

foreach ($target in @('Machine', 'User')) {
  $variables = [Environment]::GetEnvironmentVariables($target)
  foreach ($entry in $variables.GetEnumerator()) {
    if ($entry.Key -ne 'Path') {
      [Environment]::SetEnvironmentVariable([string]$entry.Key, [string]$entry.Value, 'Process')
    }
  }
}

$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path = @($machinePath, $userPath) | Where-Object { $_ } | Join-String -Separator ';'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pwsh = (Get-Process -Id $PID).Path
Start-Process -FilePath $pwsh -ArgumentList @('-NoLogo', '-NoProfile') -WorkingDirectory $projectDir
