[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Apply,
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"

# Dry-run by default. This script never edits config.toml.
$MigrationDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $MigrationDir
$SourcePath = Join-Path $ProjectDir "codex_hook.py"
if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
    throw "Source hook was not found: $SourcePath"
}

$UserProfilePath = [Environment]::GetFolderPath("UserProfile")
if ([string]::IsNullOrWhiteSpace($UserProfilePath)) { $UserProfilePath = $env:USERPROFILE }
if ([string]::IsNullOrWhiteSpace($UserProfilePath)) { throw "Windows user profile could not be resolved." }

$CodexHomePath = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $UserProfilePath ".codex" }
$UserProfileFull = [IO.Path]::GetFullPath($UserProfilePath).TrimEnd("\")
$CodexHomeFull = [IO.Path]::GetFullPath($CodexHomePath).TrimEnd("\")
if ((Split-Path -Leaf $CodexHomeFull) -ne ".codex" -or
    -not $CodexHomeFull.StartsWith($UserProfileFull + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use a CODEX_HOME outside the current user's .codex directory: $CodexHomeFull"
}
if ($CodexHomeFull -match "[^\x00-\x7F]") { throw "CODEX_HOME must be an ASCII path for this migration." }

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $candidates = @(
        $env:DS5VIBEHUB_PYTHON,
        (Join-Path $UserProfileFull ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        ((Get-Command python.exe -ErrorAction SilentlyContinue).Source)
    )
    $PythonPath = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($PythonPath) -or -not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "A Python interpreter is required. Pass -PythonPath or set DS5VIBEHUB_PYTHON."
}
$PythonPath = [IO.Path]::GetFullPath($PythonPath)
if ($PythonPath -match "[^\x00-\x7F]") { throw "PythonPath must be an ASCII path." }

$TargetDir = Join-Path $CodexHomeFull "bin"
$TargetPath = Join-Path $TargetDir "ds5vibehub-hook.py"
$LogPath = Join-Path $CodexHomeFull "codex-hooks.log"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupPath = "$TargetPath.bak.$Timestamp"
$FragmentPath = Join-Path $MigrationDir "config.hooks.ascii.generated.toml"

$sourceText = Get-Content -LiteralPath $SourcePath -Raw -Encoding UTF8
if ($sourceText -notmatch "def main\(\)") { throw "The source hook does not look like codex_hook.py." }

# Keep the implementation identical, but make its default log location stable.
# The source already computes _HOOK_HOME from CODEX_HOME/USERPROFILE. Keep that
# fallback intact so an elevated hook cannot accidentally write to a relative
# path or a different profile.
$stableText = $sourceText
$stableReplacement = 'LOG_PATH = _EXPLICIT_LOG_PATH or os.path.join(_HOOK_HOME, "codex-hooks.log")' + [Environment]::NewLine
$stableText = [Regex]::Replace(
    $sourceText,
    '(?m)^LOG_PATH\s*=.*(?:\r?\n|$)',
    $stableReplacement,
    1
)
if ($stableText -eq $sourceText) { throw "Could not locate the source LOG_PATH block; refusing a partial copy." }

# Validate the generated copy before any install. Use AST parsing so this
# check does not create a __pycache__ artifact next to the temporary file.
$validationPath = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllText($validationPath, $stableText, [Text.UTF8Encoding]::new($false))
    $validationOutput = & $PythonPath -B -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" $validationPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        $details = ($validationOutput -join [Environment]::NewLine).Trim()
        throw "Generated stable hook failed Python syntax validation.$([Environment]::NewLine)$details"
    }
}
finally {
    Remove-Item -LiteralPath $validationPath -Force -ErrorAction SilentlyContinue
}

function New-CommandLine([string]$EventName) {
    if ($PythonPath.Contains("'")) { throw "PythonPath contains an unsupported apostrophe." }
    if ($TargetPath.Contains("'")) { throw "TargetPath contains an unsupported apostrophe." }
    return "`"$PythonPath`" -B `"$TargetPath`" $EventName"
}

$events = @(
    @{ Name = "UserPromptSubmit"; Matcher = $null; Status = "DS5: working" },
    @{ Name = "PreToolUse"; Matcher = ".*"; Status = "DS5: working" },
    @{ Name = "PermissionRequest"; Matcher = ".*"; Status = "DS5: waiting for approval" },
    @{ Name = "PostToolUse"; Matcher = ".*"; Status = "DS5: tool completed" },
    @{ Name = "Stop"; Matcher = $null; Status = "DS5: done" },
    @{ Name = "SubagentStop"; Matcher = ".*"; Status = "DS5: subagent done" }
)
$fragment = @(
    "# Generated draft; review with /hooks before applying."
    "# Windows uses commandWindows; command is retained for portability."
    ""
)
foreach ($entry in $events) {
    $fragment += "[[hooks.$($entry.Name)]]"
    if ($entry.Matcher) { $fragment += "matcher = '$($entry.Matcher)'" }
    $fragment += "[[hooks.$($entry.Name).hooks]]"
    $fragment += "type = 'command'"
    $fragment += "command = '$(New-CommandLine $entry.Name)'"
    $fragment += "commandWindows = '$(New-CommandLine $entry.Name)'"
    $fragment += "async = false"
    $fragment += "timeoutSec = 5"
    $fragment += "statusMessage = '$($entry.Status)'"
    $fragment += ""
}
[IO.File]::WriteAllText($FragmentPath, (($fragment -join "`r`n") + "`r`n"), [Text.UTF8Encoding]::new($false))

Write-Output "Stable target: $TargetPath"
Write-Output "Stable log:    $LogPath"
Write-Output "Config draft:  $FragmentPath"
Write-Output "Python:        $PythonPath"
if (-not $Apply) {
    Write-Output "DRY RUN: no file under CODEX_HOME was changed. Re-run with -Apply to install the stable copy."
    return
}
if (-not $PSCmdlet.ShouldProcess($TargetPath, "copy stable hook and retain a timestamped backup")) { return }
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
if (Test-Path -LiteralPath $TargetPath -PathType Leaf) {
    Copy-Item -LiteralPath $TargetPath -Destination $BackupPath -Force
    Write-Output "Previous stable hook backed up to: $BackupPath"
}
[IO.File]::WriteAllText($TargetPath, $stableText, [Text.UTF8Encoding]::new($false))
Write-Output "Installed stable hook: $TargetPath"
Write-Output "The user config was not modified. Merge the generated TOML only after reviewing it with /hooks."
