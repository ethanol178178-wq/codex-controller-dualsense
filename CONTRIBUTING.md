# Contributing

Thanks for helping improve Codex Controller for DualSense.

## Before opening an issue

- Confirm the problem occurs on the latest release.
- Use a USB data cable; Bluetooth is not currently supported.
- Check the Device page for service and controller status.
- Do not post bridge tokens, Codex content, local paths, or personal mappings.

## Development setup

Use Windows 11, Python 3.10 or newer, Node.js for the JavaScript syntax check,
and a DualSense controller for hardware validation.

Run the development service with:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-admin.ps1
```

## Required checks

```powershell
python -m unittest discover -s . -p "test*.py" -v
python -m py_compile bridge.py approval_detection.py approval_watcher.py codex_hook.py launcher.py serve_ui.py
node --check app.js
```

Changes affecting HID input, lighting, haptics, adaptive triggers, startup, or
the installer should also be tested on a real Windows computer with a
DualSense connected over USB.

## Pull requests

- Keep changes focused and describe the user-visible behavior.
- Add or update tests for behavior changes.
- Preserve `LICENSE`, `NOTICE.md`, and `THIRD_PARTY_NOTICES.md`.
- Do not commit build outputs, local logs, tokens, mappings, or machine-specific
  Codex configuration.
- Update `CHANGELOG.md` when the change should appear in release notes.

The optional virtual touchpad driver contains separately licensed code. Keep
its source notices intact when editing or redistributing that directory.
