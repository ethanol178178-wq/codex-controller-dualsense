"""Installed entry point for the DualSense Codex controller.

The same executable starts the background bridge, opens the control center,
registers login startup, and stops the service. Development runs use this file
directly; PyInstaller turns it into ``DualSenseCodex.exe``.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import bridge
import serve_ui


APP_NAME = "DualSense Codex"
APP_URL = "http://127.0.0.1:4173/"
STATUS_URL = "http://127.0.0.1:37845/api/status"
TASK_NAME = "DualSense Codex"
LEGACY_TASK_NAME = "DualSense Vibe Hub"
SERVICE_MUTEX_NAME = "Local\\DualSenseCodexServiceV1"
STOP_EVENT_NAME = "Local\\DualSenseCodexStopV1"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
CREATE_NO_WINDOW = 0x08000000


def runtime_command(*arguments: str) -> list[str]:
    """Return a command that re-enters this launcher in source or frozen form."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, str(Path(__file__).resolve()), *arguments]


def service_status(timeout: float = 0.7) -> dict[str, object] | None:
    """Read the local bridge status without accepting a remote endpoint."""
    try:
        with urlopen(STATUS_URL, timeout=timeout) as response:
            payload = json.loads(response.read(65536).decode("utf-8"))
        return payload if isinstance(payload, dict) and payload.get("ok") is True else None
    except (OSError, URLError, ValueError):
        return None


def is_administrator() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def elevate(arguments: list[str]) -> bool:
    """Start the installed/source launcher elevated through the normal UAC flow."""
    command = runtime_command(*arguments)
    executable = command[0]
    parameters = subprocess.list2cmdline(command[1:])
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        str(Path(executable).resolve().parent),
        0,
    )
    return int(result) > 32


def acquire_service_mutex() -> wintypes.HANDLE | None:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, SERVICE_MUTEX_NAME)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create service mutex")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return handle


def create_stop_event() -> wintypes.HANDLE:
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateEventW.restype = wintypes.HANDLE
    handle = kernel32.CreateEventW(None, True, False, STOP_EVENT_NAME)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create service stop event")
    return handle


def signal_stop_event() -> bool:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenEventW.restype = wintypes.HANDLE
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, False, STOP_EVENT_NAME)
    if not handle:
        return service_status() is None
    try:
        if not kernel32.SetEvent(handle):
            raise OSError(ctypes.get_last_error(), "Could not signal service stop event")
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if service_status(timeout=0.25) is None:
                return True
            time.sleep(0.2)
        return False
    finally:
        kernel32.CloseHandle(handle)


def _component_runner(
    name: str,
    target: object,
    stop_event: threading.Event,
    failures: list[str],
) -> None:
    try:
        target(stop_event)  # type: ignore[operator]
    except BaseException as error:  # Keep the companion component from becoming orphaned.
        failures.append(f"{name}: {error}")
        stop_event.set()


def run_service() -> int:
    """Run the bridge and allowlisted control-center server as one service."""
    if service_status() is not None:
        return 0
    if not is_administrator():
        return 0 if elevate(["--service"]) else 1

    mutex = acquire_service_mutex()
    if mutex is None:
        return 0
    named_stop = create_stop_event()
    stop_event = threading.Event()
    failures: list[str] = []
    threads = [
        threading.Thread(
            target=_component_runner,
            args=("control center", serve_ui.main, stop_event, failures),
            name="dualsense-ui",
        ),
        threading.Thread(
            target=_component_runner,
            args=("controller bridge", bridge.main, stop_event, failures),
            name="dualsense-bridge",
        ),
    ]
    for thread in threads:
        thread.start()
    try:
        while not stop_event.is_set():
            result = ctypes.windll.kernel32.WaitForSingleObject(named_stop, 250)
            if result == WAIT_OBJECT_0:
                stop_event.set()
            elif result != WAIT_TIMEOUT:
                failures.append(f"stop event wait failed: {result}")
                stop_event.set()
    finally:
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5.0)
        ctypes.windll.kernel32.CloseHandle(named_stop)
        ctypes.windll.kernel32.CloseHandle(mutex)
    return 1 if failures else 0


def start_service(open_page: bool = True) -> int:
    """Ensure the background service is online, then optionally open its UI."""
    if service_status() is None:
        if is_administrator():
            creation_flags = CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.Popen(
                runtime_command("--service"),
                cwd=str(Path(sys.executable).resolve().parent),
                creationflags=creation_flags,
            )
        elif not elevate(["--service"]):
            return 1
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline and service_status(timeout=0.3) is None:
            time.sleep(0.2)
    if service_status() is None:
        return 1
    if open_page:
        webbrowser.open(APP_URL)
    return 0


def run_schtasks(*arguments: str, allow_missing: bool = False) -> bool:
    completed = subprocess.run(
        ["schtasks.exe", *arguments],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    return completed.returncode == 0 or allow_missing


def install_startup() -> int:
    """Register one per-user, elevated login task for the installed executable."""
    if not getattr(sys, "frozen", False):
        print("Startup registration is supported by the packaged executable only.")
        return 2
    if not is_administrator():
        return 0 if elevate(["--install-startup"]) else 1
    run_schtasks("/Delete", "/TN", LEGACY_TASK_NAME, "/F", allow_missing=True)
    run_schtasks("/Delete", "/TN", TASK_NAME, "/F", allow_missing=True)
    action = f'"{sys.executable}" --service'
    created = run_schtasks(
        "/Create",
        "/TN",
        TASK_NAME,
        "/SC",
        "ONLOGON",
        "/TR",
        action,
        "/RL",
        "HIGHEST",
        "/F",
    )
    if not created:
        return 1
    run_schtasks("/Run", "/TN", TASK_NAME)
    return 0


def uninstall_startup() -> int:
    if not is_administrator():
        return 0 if elevate(["--uninstall-startup"]) else 1
    return 0 if run_schtasks("/Delete", "/TN", TASK_NAME, "/F", allow_missing=True) else 1


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--service", action="store_true", help="run the background service")
    action.add_argument("--stop", action="store_true", help="stop the packaged service")
    action.add_argument("--status", action="store_true", help="show service status as JSON")
    action.add_argument("--install-startup", action="store_true", help="install login startup")
    action.add_argument("--uninstall-startup", action="store_true", help="remove login startup")
    parser.add_argument("--no-open", action="store_true", help="do not open the control center")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = parse_args(arguments)
    if options.service:
        return run_service()
    if options.stop:
        return 0 if signal_stop_event() else 1
    if options.status:
        print(json.dumps(service_status() or {"ok": False}, ensure_ascii=False))
        return 0
    if options.install_startup:
        return install_startup()
    if options.uninstall_startup:
        return uninstall_startup()
    return start_service(open_page=not options.no_open)


if __name__ == "__main__":
    raise SystemExit(main())
