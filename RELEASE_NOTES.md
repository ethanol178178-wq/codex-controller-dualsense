# Codex Controller for DualSense 0.2.4

This is the first GitHub public beta of the device-centred Codex Controller.

## Download

- **Windows installer:** `DualSense-Codex-Setup-0.2.4.exe`
- **Portable version:** `DualSense-Codex-Portable-0.2.4.zip`
- **Checksums:** `SHA256SUMS-0.2.4.txt`

## Highlights

- Connect a DualSense over USB and control Codex without reaching for the
  keyboard.
- Toggle Codex realtime voice with MIC or hold L2 for dictation.
- Send, cancel, delete, navigate conversations, scroll, and focus Codex from
  the controller.
- Click buttons directly on the controller diagram to change mappings.
- Follow Codex state through the light bar and optional haptic feedback.
- Configure adaptive triggers and experimental touchpad gestures.

## Installation

For most users, run the installer and leave login startup enabled. For a
no-install test, extract the portable ZIP and run `DualSenseCodex.exe`.

The binaries are not code-signed. Windows SmartScreen may display a warning.
Verify the SHA-256 checksum before choosing to run the file.

## Code signing policy

Version 0.2.4 is unsigned and was not signed by SignPath. Future releases will
follow the repository's [`CODE_SIGNING_POLICY.md`](CODE_SIGNING_POLICY.md) and
will be labelled as signed only after the downloadable files pass signature and
timestamp verification.

Free code signing provided by [SignPath.io](https://signpath.io/), certificate
by [SignPath Foundation](https://signpath.org/).

## Requirements and known limitations

- Windows 11 x64, Codex Desktop, and a DualSense connected by USB.
- Bluetooth is not supported.
- The optional virtual Precision Touchpad driver is not installed by the main
  installer and requires Windows test-signing mode.
- This is an independent community project, not an official Sony or OpenAI
  product.

See `README.md`, `CHANGELOG.md`, `PRIVACY.md`, and `THIRD_PARTY_NOTICES.md` for
complete documentation and attribution.
