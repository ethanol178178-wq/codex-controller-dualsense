"""Recognize approval-bearing shell calls without scanning arbitrary text."""

from __future__ import annotations


def _quoted_value(source: str, start: int) -> tuple[str, int] | None:
    if start >= len(source) or source[start] not in {"'", '"'}:
        return None
    quote = source[start]
    value: list[str] = []
    index = start + 1
    while index < len(source):
        character = source[index]
        if character == "\\" and index + 1 < len(source):
            value.append(source[index + 1])
            index += 2
            continue
        if character == quote:
            return "".join(value), index + 1
        value.append(character)
        index += 1
    return None


def _skip_quoted(source: str, start: int) -> int:
    quote = source[start]
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
        elif source[index] == quote:
            return index + 1
        else:
            index += 1
    return len(source)


def _skip_space_and_comments(source: str, start: int) -> int:
    index = start
    while index < len(source):
        if source[index].isspace():
            index += 1
        elif source.startswith("//", index):
            newline = source.find("\n", index + 2)
            index = len(source) if newline < 0 else newline + 1
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
        else:
            break
    return index


def has_escalated_shell_request(source: str) -> bool:
    """Return true only for a shell_command object's top-level option.

    Codex tool inputs are JavaScript. A raw regex misclassifies examples,
    patches, and nested scripts that merely contain the approval field. This
    scanner ignores quoted/template text and inspects only the actual options
    object passed to ``tools.shell_command``.
    """
    token = "tools.shell_command"
    index = 0
    while index < len(source):
        if source[index] in {"'", '"', "`"}:
            index = _skip_quoted(source, index)
            continue
        if source.startswith("//", index) or source.startswith("/*", index):
            index = _skip_space_and_comments(source, index)
            continue
        if not source.startswith(token, index):
            index += 1
            continue

        cursor = _skip_space_and_comments(source, index + len(token))
        if cursor >= len(source) or source[cursor] != "(":
            index += len(token)
            continue
        cursor = _skip_space_and_comments(source, cursor + 1)
        if cursor >= len(source) or source[cursor] != "{":
            index += len(token)
            continue

        depth = 1
        cursor += 1
        while cursor < len(source) and depth:
            cursor = _skip_space_and_comments(source, cursor)
            if cursor >= len(source):
                break
            character = source[cursor]
            if character in {"'", '"'}:
                parsed = _quoted_value(source, cursor)
                if parsed is None:
                    break
                key, after_key = parsed
                if depth == 1 and key == "sandbox_permissions":
                    value_start = _skip_space_and_comments(source, after_key)
                    if value_start < len(source) and source[value_start] == ":":
                        value_start = _skip_space_and_comments(source, value_start + 1)
                        value = _quoted_value(source, value_start)
                        if value is not None and value[0] == "require_escalated":
                            return True
                cursor = after_key
                continue
            if character == "`":
                cursor = _skip_quoted(source, cursor)
                continue
            if character == "{":
                depth += 1
                cursor += 1
                continue
            if character == "}":
                depth -= 1
                cursor += 1
                continue
            if depth == 1 and source.startswith("sandbox_permissions", cursor):
                end = cursor + len("sandbox_permissions")
                if end == len(source) or not (source[end].isalnum() or source[end] in "_$"):
                    value_start = _skip_space_and_comments(source, end)
                    if value_start < len(source) and source[value_start] == ":":
                        value_start = _skip_space_and_comments(source, value_start + 1)
                        value = _quoted_value(source, value_start)
                        if value is not None and value[0] == "require_escalated":
                            return True
                cursor = end
                continue
            cursor += 1
        index += len(token)
    return False
