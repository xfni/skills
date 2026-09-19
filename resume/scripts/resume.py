#!/usr/bin/env python3
"""Read-only helpers for selecting the primary Codex session."""

import argparse
import json
import os
from pathlib import Path
import shlex
import sys


class ResumeError(RuntimeError):
    """Raised when session metadata cannot identify one primary session."""


def _read_first_payload(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    return None
                payload = record.get("payload")
                return payload if isinstance(payload, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return None


def _is_primary(payload: dict, thread_id: str) -> bool:
    session_id = payload.get("session_id")
    return (
        payload.get("id") == thread_id
        and isinstance(session_id, str)
        and bool(session_id)
        and payload.get("thread_source") == "user"
        and payload.get("source") == "cli"
    )


def resolve_session_file(sessions_root: Path, thread_id: str) -> tuple[Path, dict]:
    """Return the sole primary session matching ``thread_id``."""
    matches = []
    for path in sorted(sessions_root.rglob("*.jsonl")):
        if not path.is_file():
            continue
        payload = _read_first_payload(path)
        if payload is not None and _is_primary(payload, thread_id):
            matches.append((path, payload))

    if len(matches) != 1:
        candidate_paths = ", ".join(str(path) for path, _ in matches) or "<none>"
        raise ResumeError(
            f"expected exactly one primary session for {thread_id!r}; "
            f"found {len(matches)} ({candidate_paths})"
        )
    return matches[0]


def _skip_javascript_string(source: str, index: int) -> int:
    quote = source[index]
    index += 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
        elif source[index] == quote:
            return index + 1
        else:
            index += 1
    return index


def _is_regex_start(source: str, index: int) -> bool:
    previous = index - 1
    while previous >= 0 and source[previous].isspace():
        previous -= 1
    if (
        previous > 0
        and source[previous] in "+-"
        and source[previous - 1] == source[previous]
    ):
        return False
    if previous < 0 or source[previous] in "([{:;,=!?&|+-*%^~<>":
        return True
    if not (source[previous].isalnum() or source[previous] in "_$"):
        return False
    word_end = previous + 1
    while previous >= 0 and (source[previous].isalnum() or source[previous] in "_$"):
        previous -= 1
    return source[previous + 1:word_end] in {
        "await",
        "case",
        "delete",
        "do",
        "else",
        "in",
        "instanceof",
        "new",
        "of",
        "return",
        "throw",
        "typeof",
        "void",
        "yield",
    }


def _skip_javascript_regex(source: str, index: int) -> int:
    in_character_class = False
    index += 1
    while index < len(source):
        character = source[index]
        if character == "\\":
            index += 2
            continue
        if character in "\r\n":
            return index
        if character == "[":
            in_character_class = True
        elif character == "]":
            in_character_class = False
        elif character == "/" and not in_character_class:
            index += 1
            while index < len(source) and source[index].isalpha():
                index += 1
            return index
        index += 1
    return index


def _json_object_end(source: str, index: int) -> int | None:
    depth = 0
    in_string = False
    while index < len(source):
        character = source[index]
        if in_string:
            if character == "\\":
                index += 2
                continue
            if character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _literal_exec_options(source: str):
    marker = "tools.exec_command"
    index = 0
    while index < len(source):
        character = source[index]
        if character in "'\"`":
            index = _skip_javascript_string(source, index)
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            index = len(source) if newline == -1 else newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end == -1 else end + 2
            continue
        if character == "/" and _is_regex_start(source, index):
            index = _skip_javascript_regex(source, index)
            continue
        if not source.startswith(marker, index):
            index += 1
            continue
        if index and (source[index - 1].isalnum() or source[index - 1] in "_$."):
            index += len(marker)
            continue

        argument_start = index + len(marker)
        while argument_start < len(source) and source[argument_start].isspace():
            argument_start += 1
        if argument_start >= len(source) or source[argument_start] != "(":
            index += len(marker)
            continue
        argument_start += 1
        while argument_start < len(source) and source[argument_start].isspace():
            argument_start += 1
        if argument_start >= len(source) or source[argument_start] != "{":
            index += len(marker)
            continue

        object_end = _json_object_end(source, argument_start)
        if object_end is None:
            index += len(marker)
            continue
        call_end = object_end
        while call_end < len(source) and source[call_end].isspace():
            call_end += 1
        if call_end >= len(source) or source[call_end] != ")":
            index = object_end
            continue
        try:
            options = json.loads(source[argument_start:object_end])
        except json.JSONDecodeError:
            index = call_end + 1
            continue
        if isinstance(options, dict):
            yield options
        index = call_end + 1


def _existing_directory(value: object) -> tuple[Path, Path] | None:
    if not isinstance(value, str):
        return None
    try:
        path = Path(value)
        if not path.is_absolute() or not path.is_dir():
            return None
        return path, path.resolve()
    except (OSError, ValueError):
        return None


def _append_directory(
    directories: list[Path], seen: set[Path], value: object, primary_cwd: Path
) -> None:
    directory = _existing_directory(value)
    if directory is None:
        return
    path, canonical_path = directory
    try:
        primary_path = primary_cwd.resolve()
    except OSError:
        primary_path = primary_cwd
    try:
        codex_home = (Path.home() / ".codex").resolve()
        is_codex_runtime_directory = canonical_path.is_relative_to(codex_home)
    except OSError:
        is_codex_runtime_directory = False
    if (
        canonical_path == primary_path
        or canonical_path in seen
        or is_codex_runtime_directory
    ):
        return
    seen.add(canonical_path)
    directories.append(path)


def _add_directories_from_command(command: object) -> list[str]:
    if not isinstance(command, str):
        return []
    try:
        arguments = shlex.split(command)
    except ValueError:
        return []
    if len(arguments) < 2 or arguments[:2] != ["codex", "resume"]:
        return []

    directories = []
    for index, argument in enumerate(arguments):
        if argument == "--add-dir" and index + 1 < len(arguments):
            directories.append(arguments[index + 1])
        elif argument.startswith("--add-dir="):
            directories.append(argument.removeprefix("--add-dir="))
    return directories


def directories_from_session(session_file: Path, primary_cwd: Path) -> list[Path]:
    """Return existing literal directory arguments from executed exec records."""
    directories: list[Path] = []
    seen: set[Path] = set()
    try:
        with session_file.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except (KeyError, TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                    continue
                payload = record["payload"]
                if record.get("type") == "response_item":
                    item = payload.get("item", payload)
                else:
                    item = payload.get("item")
                if (
                    not isinstance(item, dict)
                    or item.get("type") != "custom_tool_call"
                    or item.get("name") != "exec"
                    or not isinstance(item.get("input"), str)
                ):
                    continue
                for options in _literal_exec_options(item["input"]):
                    _append_directory(directories, seen, options.get("workdir"), primary_cwd)
                    for directory in _add_directories_from_command(options.get("cmd")):
                        _append_directory(directories, seen, directory, primary_cwd)
    except (OSError, UnicodeError):
        return directories
    return directories


def _quote_argument(value: str) -> str:
    if any(character in value for character in ("\n", "\r", "\0")):
        raise ResumeError("newline, carriage return, or NUL cannot be rendered safely")
    for raw, escaped in (("\\", "\\\\"), ('"', '\\"'), ("$", "\\$"), ("`", "\\`")):
        value = value.replace(raw, escaped)
    return f'"{value}"'


def render_command(primary_cwd: Path, session_id: str, added_dirs: list[Path]) -> str:
    """Render a copyable command without executing it."""
    if _existing_directory(str(primary_cwd)) is None:
        raise ResumeError(f"primary cwd must be an existing absolute directory: {str(primary_cwd)!r}")
    if not session_id or session_id.startswith("-"):
        raise ResumeError("session_id must be nonempty and must not be an option")
    cd_line = f"cd -- {_quote_argument(str(primary_cwd))}"
    resume_lines = [f"codex resume {_quote_argument(session_id)}"]
    resume_lines.extend(f"  --add-dir {_quote_argument(str(path))}" for path in added_dirs)
    return cd_line + "\n" + " \\\n".join(resume_lines)


def _selection(value: str, count: int) -> list[int]:
    try:
        selected = [int(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise ResumeError("directory selection must be comma-separated numbers") from error
    if not selected or any(number < 1 or number > count for number in selected):
        raise ResumeError("directory selection is outside the candidate range")
    return list(dict.fromkeys(number - 1 for number in selected))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--list-candidates", action="store_true")
    parser.add_argument("--include")
    arguments = parser.parse_args([] if argv is None else argv)
    try:
        thread_id = os.environ.get("CODEX_THREAD_ID")
        if not thread_id:
            raise ResumeError("CODEX_THREAD_ID is required to identify the current session")
        session_file, payload = resolve_session_file(
            Path.home() / ".codex" / "sessions", thread_id
        )
        directory = _existing_directory(payload.get("cwd"))
        if directory is None:
            raise ResumeError(f"primary session cwd must be an existing absolute directory: {session_file}")
        primary_cwd, _ = directory
        candidates = directories_from_session(session_file, primary_cwd)
        if arguments.list_candidates:
            print("当前会话已添加目录：不可获取；以下为历史工作候选：")
            for index, candidate in enumerate(candidates, start=1):
                print(f"{index}. [历史工作目录] {candidate}")
            return 0
        if arguments.include is not None:
            candidates = [candidates[index] for index in _selection(arguments.include, len(candidates))]
        elif len(candidates) > 1:
            raise ResumeError(
                "multiple directory candidates found; run with --list-candidates, "
                "then rerun with --include 1,3"
            )
        command = render_command(
            primary_cwd,
            payload["session_id"],
            candidates,
        )
    except ResumeError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
