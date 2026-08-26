[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Apply,
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"
$UserProfilePath = [Environment]::GetFolderPath("UserProfile")
if ([string]::IsNullOrWhiteSpace($UserProfilePath)) { $UserProfilePath = $env:USERPROFILE }
$CodexHomePath = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $UserProfilePath ".codex" }
if ([string]::IsNullOrWhiteSpace($ConfigPath)) { $ConfigPath = Join-Path $CodexHomePath "config.toml" }
$ConfigFull = [IO.Path]::GetFullPath($ConfigPath)
$HomeFull = [IO.Path]::GetFullPath($CodexHomePath).TrimEnd("\")
if ((Split-Path -Leaf $ConfigFull) -ne "config.toml" -or
    (Split-Path -Leaf (Split-Path -Parent $ConfigFull)) -ne ".codex" -or
    -not $ConfigFull.StartsWith($HomeFull + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to edit a file outside CODEX_HOME\config.toml: $ConfigFull"
}
if (-not (Test-Path -LiteralPath $ConfigFull -PathType Leaf)) { throw "Config file not found: $ConfigFull" }

$text = [IO.File]::ReadAllText($ConfigFull, [Text.UTF8Encoding]::new($false))
$headerPattern = "(?m)^\[hooks\.state\.'[^']*hooks\.json:[^']*'\]\r?\n"
$headers = [Regex]::Matches($text, $headerPattern)
if ($headers.Count -eq 0) {
    Write-Output "No legacy hooks.json state tables found in $ConfigFull"
    return
}

# Remove only each matching table through the next TOML table header.
$ranges = @()
foreach ($header in $headers) {
    $after = $header.Index + $header.Length
    $next = [Regex]::Match($text.Substring($after), "(?m)^\[")
    $end = if ($next.Success) { $after + $next.Index } else { $text.Length }
    $ranges += ,@($header.Index, $end)
}
$clean = $text
for ($index = $ranges.Count - 1; $index -ge 0; $index--) {
    $range = $ranges[$index]
    $clean = $clean.Remove([int]$range[0], [int]($range[1] - $range[0]))
}

Write-Output "Legacy tables to remove: $($headers.Count)"
foreach ($header in $headers) { Write-Output ("  " + $header.Value.Trim()) }
if (-not $Apply) {
    Write-Output "DRY RUN: config.toml was not changed. Re-run with -Apply after closing Codex and taking a backup."
    return
}
if (-not $PSCmdlet.ShouldProcess($ConfigFull, "remove only hooks.json trust-state tables")) { return }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$ConfigFull.before-ds5-hook-state-cleanup.$stamp.bak"
Copy-Item -LiteralPath $ConfigFull -Destination $backup -Force
[IO.File]::WriteAllText($ConfigFull, $clean, [Text.UTF8Encoding]::new($false))
Write-Output "Backup: $backup"
Write-Output "Updated: $ConfigFull"
Write-Output "A fresh Codex process is required; this script does not stop processes."
