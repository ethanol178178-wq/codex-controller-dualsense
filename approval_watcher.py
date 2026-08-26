"""Compatibility watcher for Codex approval records in session JSONL files.

Some Codex Desktop builds do not dispatch PermissionRequest lifecycle hooks.
This process forwards only structured escalated exec calls and their matching
outputs to the already-running DS5 bridge. It exits automatically once a
bridge with the native structured fallback is running.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from approval_detection import has_escalated_shell_request


BRIDGE_STATUS_URL = "http://127.0.0.1:37845/api/status"
BRIDGE_HOOK_URL = "http://127.0.0.1:37845/api/codex-hook"
BRIDGE_TOKEN_PATH = os.environ.get("DS5VIBEHUB_TOKEN_PATH", "").strip() or os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.dirname(os.path.abspath(__file__))),
    "DS5VibeHub",
    "bridge.token",
)
SESSION_ROOT = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
POLL_SECONDS = 0.25
SUPPORTED_BRIDGE_BUILDS = {
    "structured-approval-fallback-v3",
    "turn-boundary-state-v4",
    "adaptive-triggers-v5",
    "adaptive-trigger-weapon-v7",
    "adaptive-trigger-recoil-v8",
    "adaptive-trigger-recoil-v9",
    "adaptive-trigger-mapping-gate-v10",
    "adaptive-trigger-firmware-gate-v11",
    "adaptive-trigger-haptic-priority-v12",
    "codex-state-correctness-v13",
    "hid-shutdown-safety-v14",
    "local-api-security-v15",
}
LOG_PATH = os.path.join(os.environ.get("TEMP", os.getcwd()), "ds5vibehub-approval-watcher.log")


def log(message: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as stream:
            stream.write(f"{time.time():.3f} {message}\n")
    except OSError:
        pass


def acquire_single_instance() -> object | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, "Local\\DS5VibeHubApprovalWatcherV1")
    if not handle or ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def bridge_build() -> str:
    try:
        with urlopen(BRIDGE_STATUS_URL, timeout=0.5) as response:
            payload = json.loads(response.read(65536).decode("utf-8"))
        return str(payload.get("build", "")) if isinstance(payload, dict) else ""
    except (OSError, URLError, ValueError):
        return ""


def bridge_token() -> str:
    try:
        with open(BRIDGE_TOKEN_PATH, "r", encoding="ascii") as stream:
            return stream.read(256).strip()
    except OSError:
        return ""


def anonymous_identifier(value: object, secret: str = "") -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    encoded = normalized.encode("utf-8", errors="replace")
    digest = (
        hmac.new(secret.encode("ascii", errors="ignore"), encoded, hashlib.sha256).hexdigest()
        if secret
        else hashlib.sha256(encoded).hexdigest()
    )[:24]
    return f"anon-{digest}"


def forward(event: str, session_id: str, call_id: str) -> bool:
    token = bridge_token()
    anonymous_session_id = anonymous_identifier(session_id, token)
    anonymous_call_id = anonymous_identifier(call_id, token)
    payload = {
        "event": event,
        # Mark this as an independent structured source. The running v2
        # bridge then suppresses its own generic JSONL fallback for the same
        # record instead of immediately overwriting approval yellow with
        # working red.
        "origin": "approval-watcher",
        "sessionId": anonymous_session_id,
        "requestKey": anonymous_call_id,
        "toolName": "exec",
        "sentAt": time.time(),
    }
    request = Request(
        BRIDGE_HOOK_URL,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-DS5VibeHub-Token": token,
        },
    )
    try:
        with urlopen(request, timeout=0.8) as response:
            response_payload = json.loads(response.read(65536).decode("utf-8"))
        codex = response_payload.get("codex", {}) if isinstance(response_payload, dict) else {}
        log(
            f"forwarded event={event} session={anonymous_session_id} call={anonymous_call_id} "
            f"state={codex.get('state')} pending={codex.get('pendingRequests')} "
            f"applied={codex.get('lastAppliedState')}"
        )
        return True
    except (OSError, URLError, ValueError) as error:
        log(f"bridge-error event={event} call={anonymous_call_id} error={error}")
        return False


def consume(path: str, offsets: dict[str, int], pending: set[tuple[str, str]]) -> None:
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    offset = offsets.setdefault(path, size)
    if size < offset:
        offset = 0
    if size == offset:
        return
    try:
        with open(path, "rb") as stream:
            stream.seek(offset)
            chunk = stream.read(size - offset)
    except OSError:
        return
    complete_through = chunk.rfind(b"\n")
    if complete_through < 0:
        return
    chunk = chunk[:complete_through + 1]
    offsets[path] = offset + complete_through + 1
    session_id = os.path.basename(path)[:128]
    for raw_line in chunk.splitlines():
        try:
            record = json.loads(raw_line.decode("utf-8", errors="replace"))
        except (TypeError, ValueError):
            continue
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict):
            continue
        event_type = str(payload.get("type", ""))
        call_id = str(payload.get("call_id", "")).strip()
        key = (session_id, call_id)
        if (
            event_type == "custom_tool_call"
            and str(payload.get("name", "")).strip() == "exec"
            and call_id
            and has_escalated_shell_request(str(payload.get("input", "")))
        ):
            if key not in pending and forward("PermissionRequest", session_id, call_id):
                pending.add(key)
        elif event_type == "custom_tool_call_output" and call_id and key in pending:
            if forward("PreToolUse", session_id, call_id):
                pending.discard(key)


def main() -> int:
    mutex = acquire_single_instance()
    if mutex is None:
        return 0
    log(f"started pid={os.getpid()}")
    offsets: dict[str, int] = {}
    pending: set[tuple[str, str]] = set()
    while True:
        if bridge_build() in SUPPORTED_BRIDGE_BUILDS:
            log("stopped reason=structured-fallback-active")
            return 0
        try:
            files: list[str] = []
            if os.path.isdir(SESSION_ROOT):
                for root, _dirs, names in os.walk(SESSION_ROOT):
                    files.extend(
                        os.path.join(root, name) for name in names if name.endswith(".jsonl")
                    )
            files.sort(key=os.path.getmtime, reverse=True)
            for path in files[:8]:
                consume(path, offsets, pending)
        except OSError as error:
            log(f"scan-error error={error}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
