"""Forward a native Codex hook event to the local DualSense bridge.

Codex passes the lifecycle name as the first command argument in addition to
the JSON hook payload on stdin.  Older configurations relied on a
``hook_event_name`` field that is not guaranteed to be present, which made the
bridge reject otherwise valid hook invocations.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


BRIDGE_URL = "http://127.0.0.1:37845/api/codex-hook"
BRIDGE_TOKEN_PATH = os.environ.get("DS5VIBEHUB_TOKEN_PATH", "").strip() or os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.dirname(os.path.abspath(__file__))),
    "DS5VibeHub",
    "bridge.token",
)
# Codex supplies CODEX_HOME to hook commands in some hosts but not all. Use
# it first, then USERPROFILE, so diagnostics always land beside the active
# config instead of an administrator/system profile.
_CODEX_HOME = os.environ.get("CODEX_HOME", "").strip()
_USER_HOME = os.environ.get("USERPROFILE", "").strip() or os.path.expanduser("~")
_HOOK_HOME = _CODEX_HOME or os.path.join(_USER_HOME, ".codex")
_EXPLICIT_LOG_PATH = os.environ.get("DS5VIBEHUB_HOOK_LOG", "").strip()
LOG_PATH = _EXPLICIT_LOG_PATH or os.path.join(_HOOK_HOME, "codex-hooks.log")
FALLBACK_LOG_PATHS = tuple(
    path for path in (
        LOG_PATH,
        os.path.join(os.environ.get("TEMP", ""), "ds5vibehub-codex-hooks.log"),
        os.path.join(os.environ.get("TMP", ""), "ds5vibehub-codex-hooks.log"),
    ) if path
)


def log_entry(entry: dict[str, object]) -> None:
    """Write a bounded, non-sensitive execution trace for troubleshooting."""
    line = json.dumps({"at": time.time(), **entry}, separators=(",", ":")) + "\n"
    for path in FALLBACK_LOG_PATHS:
        try:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "a", encoding="utf-8") as stream:
                stream.write(line)
            return
        except OSError:
            continue


def anonymous_identifier(value: object, fallback: str = "", secret: str = "") -> str:
    """Return a stable identifier without exposing the source value."""
    normalized = str(value or "").strip()
    if not normalized:
        return fallback
    encoded = normalized.encode("utf-8", errors="replace")
    digest = (
        hmac.new(secret.encode("ascii", errors="ignore"), encoded, hashlib.sha256).hexdigest()
        if secret
        else hashlib.sha256(encoded).hexdigest()
    )[:24]
    return f"anon-{digest}"


def bridge_token() -> str:
    try:
        with open(BRIDGE_TOKEN_PATH, "r", encoding="ascii") as stream:
            return stream.read(256).strip()
    except OSError:
        return ""


def first_value(payload: dict[str, object], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def fallback_session_id(payload: dict[str, object], secret: str = "") -> str:
    """Derive a stable anonymous session key without forwarding local paths."""
    context = first_value(
        payload,
        "transcript_path", "transcriptPath", "session_file", "sessionFile",
        "cwd", "current_dir", "currentDir", "workspace", "workspace_root", "workspaceRoot",
    )
    if not context:
        return "codex-default"
    return anonymous_identifier(context, "codex-default", secret)


def build_bridge_payload(hook: dict[str, object], fallback_event: str) -> dict[str, object]:
    token = bridge_token()
    event = first_value(hook, "hook_event_name", "event") or fallback_event
    raw_session_id = first_value(
        hook,
        "session_id", "sessionId", "thread_id", "threadId", "conversation_id", "conversationId",
        "run_id", "runId",
    )
    session_id = anonymous_identifier(raw_session_id, secret=token) or fallback_session_id(hook, token)

    def anonymous_value(*names: str) -> str:
        return anonymous_identifier(first_value(hook, *names), secret=token)

    return {
        "event": event,
        "origin": "codex-hook-command",
        "argvEvent": fallback_event[:64] or None,
        "processId": os.getpid(),
        "sessionId": session_id[:128],
        "turnId": anonymous_value("turn_id", "turnId"),
        "toolUseId": anonymous_value("tool_use_id", "toolUseId"),
        "requestKey": anonymous_value(
            "permission_request_id", "permissionRequestId", "request_id", "requestId",
            "tool_use_id", "toolUseId", "turn_id", "turnId", "run_id", "runId",
        ),
        "runId": anonymous_value("run_id", "runId", "run_id_suffix", "runIdSuffix"),
        "toolName": first_value(hook, "tool_name", "toolName")[:128],
        "sentAt": time.time(),
    }


def main() -> int:
    fallback_event = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    # Keep this first record before touching stdin. If the command runner
    # starts the process but leaves stdin open, the later read can block until
    # the hook timeout; this record lets us distinguish that from a launch
    # failure without recording prompt contents.
    log_entry({
        "phase": "startup",
        "event": fallback_event,
        "processId": os.getpid(),
    })
    try:
        raw_input = sys.stdin.read()
        log_entry({
            "phase": "stdin-read",
            "event": fallback_event,
            "processId": os.getpid(),
            "chars": len(raw_input),
            "bytes": len(raw_input.encode("utf-8", errors="replace")),
        })
        hook = json.loads(raw_input) if raw_input.strip() else {}
    except (json.JSONDecodeError, OSError) as error:
        log_entry({"result": "invalid-json", "event": fallback_event, "error": str(error)})
        return 0
    if not isinstance(hook, dict):
        log_entry({"result": "invalid-payload", "event": fallback_event})
        return 0

    payload = build_bridge_payload(hook, fallback_event)
    event = str(payload["event"])
    session_id = str(payload["sessionId"])
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        BRIDGE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DS5VibeHub-Token": bridge_token(),
        },
    )
    log_entry({
        "phase": "bridge-request",
        "event": event,
        "processId": os.getpid(),
        "sessionId": session_id[:128],
        "payloadBytes": len(body),
    })
    try:
        with urlopen(request, timeout=0.8) as response:
            response.read(256)
            log_entry({
                "phase": "bridge-response",
                "result": "ok",
                "event": event,
                "argvEvent": fallback_event[:64] or None,
                "origin": "codex-hook-command",
                "processId": os.getpid(),
                "sessionId": session_id[:128],
                "status": response.status,
            })
    except (OSError, URLError) as error:
        log_entry({
            "phase": "bridge-error",
            "result": "bridge-error",
            "event": event,
            "sessionId": session_id[:128],
            "error": str(error),
        })
        # Status lighting must never block or fail a Codex task.
        return 0
    log_entry({"phase": "complete", "event": event, "processId": os.getpid()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
