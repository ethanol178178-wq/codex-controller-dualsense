# DS5 Codex hook migration (reviewable and reversible)

This directory is a migration package only. Inspecting it does not modify the
active user configuration or stop any process.

## Why migrate

The current hook tables point into the Unicode workspace path. The current
Codex protocol exposes `commandWindows`, requires an explicit `async` field,
and reports hook trust per source path. A stable ASCII entry point under
`%USERPROFILE%\.codex\bin` removes the path and quoting variable. `PostToolUse`
is included to resolve any outstanding tool approval while retaining the
working state until the whole turn emits `Stop` or `task_complete`.

## Dry-run and install

From the project directory:

```powershell
.\hooks-migration\install-hooks-migration.ps1
.\hooks-migration\install-hooks-migration.ps1 -Apply
```

The first command validates paths and writes a generated draft in this
directory. `-Apply` copies `codex_hook.py` to
`%USERPROFILE%\.codex\bin\ds5vibehub-hook.py`, retaining a timestamped backup.
It makes the default hook log `%USERPROFILE%\.codex\codex-hooks.log`. It never
edits `%USERPROFILE%\.codex\config.toml`.

Review `config.hooks.ascii.generated.toml`, then merge those hook tables into
the user config while Codex is closed. Do not paste template placeholders.
The generated command uses `command` and `commandWindows`, `async = false`,
and `timeoutSec = 5`.

## Exact state cleanup

First preview the narrowly-scoped cleanup:

```powershell
.\hooks-migration\clean-hook-state.ps1
```

Only table headers matching
`[hooks.state.'...hooks.json:...']` are selected. The script leaves all
`config.toml:*` trust records, project trust, and `hooks.json.disabled` alone.
After closing every Codex Desktop/app-server instance and making a backup,
apply it:

```powershell
.\hooks-migration\clean-hook-state.ps1 -Apply
```

The script writes a timestamped `config.toml.before-ds5-hook-state-cleanup.*`
backup next to the config and requires a fresh Codex process. Because the
stable command has a new source/hash, open `/hooks` in a new session, review
all six entries, and trust them. Verify `hooks/list` reports `trusted`, with
empty `warnings` and `errors`, before testing a real turn.

## Rollback

The stable copy can be restored without deleting anything:

```powershell
.\hooks-migration\rollback-stable-hook.ps1
```

Pass `-BackupPath` when more than one backup exists. To roll back config state,
restore the exact `config.toml.before-ds5-hook-state-cleanup.*` backup while
Codex is closed, then restart it. Do not run a broad recursive delete in the
user profile.

## Acceptance evidence

Record the initial size/time of `%USERPROFILE%\.codex\codex-hooks.log` and the
bridge `/api/status` hook counter. In a new session, expect `UserPromptSubmit`
or `PreToolUse` to make the bridge `working`, `PermissionRequest` to make it
`approval`, `PreToolUse`/`PostToolUse` after approval to return to `working`,
`PostToolUse` to remain `working`, and only `Stop`/`task_complete` to settle
`idle`. The log must contain a new
`origin = codex-hook-command` entry for each event; host `hook/started` alone
is not proof that a command ran.

Acceptance evidence must be sanitized before it leaves the internal review
environment. Keep only event names, state transitions, counters, timings and
anonymous identifiers. Remove API keys, bridge tokens, user names, absolute
paths, device serial numbers, MAC addresses, and raw session/request/tool IDs
from screenshots, copied JSON and log excerpts. Do not attach the generated
`bridge.token`, Codex configuration, session JSONL files or local databases.
