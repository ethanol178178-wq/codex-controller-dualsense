[CmdletBinding(SupportsShouldProcess = $true)]
param([string]$BackupPath)

$ErrorActionPreference = "Stop"
$UserProfilePath = [Environment]::GetFolderPath("UserProfile")
if ([string]::IsNullOrWhiteSpace($UserProfilePath)) { $UserProfilePath = $env:USERPROFILE }
$CodexHomePath = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $UserProfilePath ".codex" }
$HomeFull = [IO.Path]::GetFullPath($CodexHomePath).TrimEnd("\")
$TargetPath = Join-Path $HomeFull "bin\ds5vibehub-hook.py"
if ([string]::IsNullOrWhiteSpace($BackupPath)) {
    $BackupPath = Get-ChildItem -LiteralPath (Join-Path $HomeFull "bin") -Filter "ds5vibehub-hook.py.bak.*" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if ([string]::IsNullOrWhiteSpace($BackupPath) -or -not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) {
    throw "No stable-hook backup was found. Pass -BackupPath explicitly."
}
$BackupFull = [IO.Path]::GetFullPath($BackupPath)
if (-not $BackupFull.StartsWith((Join-Path $HomeFull "bin\"), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to restore a backup outside CODEX_HOME\bin: $BackupFull"
}
if (-not $PSCmdlet.ShouldProcess($TargetPath, "restore $BackupFull")) { return }
Copy-Item -LiteralPath $BackupFull -Destination $TargetPath -Force
Write-Output "Restored: $TargetPath"
Write-Output "The user config was not changed. Re-run /hooks after restart if the command hash changed."
