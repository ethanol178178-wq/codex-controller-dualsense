# DS5 Virtual Precision Touchpad

This UMDF 2 virtual HID device turns bridge-generated four-contact gestures
into Windows Precision Touchpad input. It keeps Microsoft's MS-PL-licensed
`vhidmini2` request plumbing and adapts the five-contact descriptor, report
layout and PTPHQA feature data validated by the MIT-licensed
`PeronGH/BLE-PTP-PoC` project. The fifth report slot remains inactive while
the Bridge drives four contacts.

This is a development/test driver workflow. The repository does not ship a
production-signed DLL, CAT, or certificate.

## Prerequisites

Use an x64 Windows 11 development machine with:

- PowerShell 7 (`pwsh`)
- Visual Studio 2022 Build Tools with the Desktop C++ workload, MSVC v143,
  and the Windows SDK
- Windows 11 WDK `10.0.26100.0`, including MSBuild integration, Inf2Cat,
  SignTool, and DevCon
- Administrator rights for installation and removal

The scripts expect the standard Build Tools and WDK locations under
`%ProgramFiles(x86)%`. If Visual Studio or the WDK was installed elsewhere,
update the tool paths in the scripts or run the equivalent tools manually.

## Build a test-signed package

Run from the repository root in PowerShell 7:

```powershell
pwsh -NoProfile -File .\driver\ds5ptp\build-driver.ps1
```

The script builds `ds5ptp.vcxproj` as `Release|x64`, creates
`driver\ds5ptp\package`, copies the DLL and INF, runs Inf2Cat, then reuses or
creates a three-year self-signed certificate named
`CN=DS5 Vibe Hub Test Driver` in the current user's certificate store. It
exports `DS5VibeHubTestDriver.cer` and signs the DLL and CAT with that
certificate.

Expected package contents:

```text
driver/ds5ptp/package/
  DS5VirtualPrecisionTouchpad.dll
  DS5VirtualPrecisionTouchpad.inf
  DS5VirtualPrecisionTouchpad.cat
  DS5VibeHubTestDriver.cer
```

The generated `bin`, `obj`, and `package` directories are local build
artifacts and are excluded from the public source release.

## Install

Before installing, close the Bridge and any previous virtual touchpad test
instance. Run the following command from an elevated PowerShell 7 process, or
let the script request UAC elevation:

```powershell
pwsh -NoProfile -File .\driver\ds5ptp\install-driver.ps1
```

The script verifies the package files, imports the test certificate into
`LocalMachine\Root` and `LocalMachine\TrustedPublisher`, runs
`bcdedit.exe /set testsigning on`, and creates or updates the
`Root\DS5VibeHubTouchpad` virtual device with DevCon. It writes an installation
transcript to `driver\ds5ptp\package\install-driver.log`.

The script never restarts Windows. Restart Windows before testing the driver.
If Secure Boot prevents the test-signing setting, disable Secure Boot in
firmware only on a dedicated test machine, rerun the install script, and
restart Windows. Do not use this workflow on a managed or production machine.

## Verify

After the restart:

1. Confirm that Windows is in test-signing mode. The desktop watermark is expected.
2. Check device registration:

```powershell
& "${env:ProgramFiles(x86)}\Windows Kits\10\Tools\10.0.26100.0\x64\devcon.exe" findall Root\DS5VibeHubTouchpad
```

3. Start the Bridge and UI with `start-admin.ps1` from the repository root, or use the manual startup commands in the root README.
4. Open the Touchpad view. `/api/status` should report
   `touchpadGestures.driverAvailable = true` when the vendor HID channel is available.
5. Enable touchpad gestures and perform a horizontal swipe. The status should report
   `switchMode = touch-injection`; `driver-required` means the driver is not available
   and no keyboard fallback will be attempted.

## Uninstall and recovery

Remove the virtual device and matching machine-level test certificate with:

```powershell
pwsh -NoProfile -File .\driver\ds5ptp\uninstall-driver.ps1 -WhatIf
pwsh -NoProfile -File .\driver\ds5ptp\uninstall-driver.ps1
```

The first command is a read-only preview. Review every listed device and
certificate before running the second command.

The script removes matching `Root\DS5VibeHubTouchpad` devices and the test
certificate from `LocalMachine\Root` and `LocalMachine\TrustedPublisher`. It
leaves the current-user signing certificate and the source/build directories
alone.

If this machine does not need test-signing for any other driver, disable it in
the same operation:

```powershell
pwsh -NoProfile -File .\driver\ds5ptp\uninstall-driver.ps1 -DisableTestSigning
```

Restart Windows after cleanup. Do not use `-DisableTestSigning` on a machine
that still relies on another test-signed driver. The uninstall script does not
delete the generated package; remove those local files manually only after
confirming they are no longer needed.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `Required build tool is missing` | Install the exact WDK/Build Tools versions or update the paths at the top of `build-driver.ps1`. |
| `Inf2Cat failed` | Confirm the x64 package contains the INF and that the Windows SDK/WDK version matches the script. |
| `Could not enable Windows test-signing mode` | Check Secure Boot and organization policy; do not bypass a managed-device policy. |
| Certificate or INF missing during install | Run `build-driver.ps1` successfully first and inspect `driver\ds5ptp\package`. |
| DevCon cannot create/update the device | Run the install script elevated, inspect `install-driver.log`, and remove a stale device with `uninstall-driver.ps1` before retrying. |
| `driverAvailable` is false after reboot | Restart the Bridge, confirm the device exists with DevCon, and check the Bridge error state. |
| Swipe remains `driver-required` | The Bridge cannot open the vendor HID channel; reinstall the driver or use no-driver mode without touchpad gestures. |

## Technical details

The vendor output report is 50 bytes: report ID `0x09`, followed by the
49-byte payload of the normal Precision Touchpad input report. The driver
changes the report ID to `0x05` before submitting it to HIDClass.

The UMDF HID request plumbing is derived from Microsoft's Windows Driver
Samples `hid/vhidmini2` sample under the Microsoft Public License (MS-PL).
The Precision Touchpad descriptor, report layout, device capabilities, and
PTPHQA feature data are adapted from `PeronGH/BLE-PTP-PoC` under the MIT
License. See `THIRD_PARTY_NOTICES.md` for complete notices.
