# Changelog

All notable changes to this project are documented here.

## [0.2.4] - 2026-08-27

### Added

- Device-centred **Codex Controller** interface with three clear areas:
  Controller, Experience, and Device.
- Direct button selection from the DualSense diagram before changing a
  mapping.
- Collapsible full mapping list and reliability labels for every action.
- Codex realtime voice toggle, hold-to-dictate, smart delete, focus, review,
  conversation navigation, and scroll workflows.
- Codex status lighting, double-soft haptic feedback, and adaptive trigger
  controls.
- Portable ZIP and Traditional Chinese Windows installer builds.
- Login startup support, persistent mappings, local API authorization, and
  privacy-safe Codex status events.
- Automated tests for mapping, capture, status lights, touchpad gestures,
  adaptive triggers, privacy, and launcher behavior.

### Changed

- Replaced the former multi-dashboard layout with a device-first workflow.
- Removed Codex Micro as a standalone mode while retaining its useful
  automatic status behavior.
- Moved advanced lighting, trigger, touchpad, and diagnostic controls out of
  the primary mapping workflow.

### Known limitations

- USB only; Bluetooth is not supported.
- Release binaries are not code-signed and may trigger Windows SmartScreen.
- The optional virtual Precision Touchpad driver requires Windows test-signing
  mode and is intended for advanced testing.
