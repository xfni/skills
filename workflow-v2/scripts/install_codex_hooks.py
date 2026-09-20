#!/usr/bin/env python3
"""Merge the dev-run continuation hooks into an already deployed Codex home."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
try:
    import tomllib
except ImportError:  # Python 3.10 deployment environments use the compatible package.
    import tomli as tomllib


def _home(raw):
    if raw:
        return Path(raw).expanduser().resolve()
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".codex").resolve()


def _atomic_json(path, value):
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_shape(value):
    if not isinstance(value, dict):
        raise ValueError("HOOKS_JSON_INVALID")
    hooks = value.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("HOOKS_JSON_INVALID")
    for groups in hooks.values():
        if not isinstance(groups, list) or not all(isinstance(group, dict) for group in groups):
            raise ValueError("HOOKS_JSON_INVALID")
        for group in groups:
            handlers = group.get("hooks")
            if (not isinstance(handlers, list)
                    or not all(isinstance(handler, dict)
                               and handler.get("type") == "command"
                               and isinstance(handler.get("command"), str)
                               and bool(handler["command"])
                               for handler in handlers)):
                raise ValueError("HOOKS_JSON_INVALID")
    return hooks


def install(codex_home):
    codex_home = _home(codex_home)
    package = Path(__file__).resolve().parents[1]
    expected = (codex_home / "flow-v2").resolve()
    if package != expected:
        raise ValueError("INSTALLER_PACKAGE_ROOT_MISMATCH")
    helper = package / "continuation_hook.py"
    flowctl = package / "flowctl.py"
    if not helper.is_file() or not flowctl.is_file() or not (package / "flowctl_lib").is_dir():
        raise ValueError("FLOW_PACKAGE_NOT_DEPLOYED")
    path = codex_home / "hooks.json"
    if path.exists():
        try:
            value = json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("HOOKS_JSON_INVALID") from exc
    else:
        value = {"hooks": {}}
    hooks = _validate_shape(value)
    config = codex_home / "config.toml"
    warning = False
    if config.is_file():
        try:
            parsed = tomllib.loads(config.read_text())
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise ValueError("CONFIG_TOML_INVALID") from exc
        inline = parsed.get("hooks", {})
        if not isinstance(inline, dict):
            raise ValueError("CONFIG_TOML_INVALID")
        warning = any(name != "state" for name in inline)
    command = f"{shlex.quote(str(Path(sys.executable).resolve()))} {shlex.quote(str(helper.resolve()))} hook"
    handler = {"type": "command", "command": command, "timeout": 5}
    changed = False
    for event in ("UserPromptSubmit", "Stop"):
        groups = hooks.setdefault(event, [])
        found = False
        for group in groups:
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                raise ValueError("HOOKS_JSON_INVALID")
            for index, existing in enumerate(handlers):
                if isinstance(existing, dict) and existing.get("command") == command:
                    found = True
                    if existing != handler:
                        handlers[index] = dict(handler)
                        changed = True
        if not found:
            groups.append({"hooks": [dict(handler)]})
            changed = True
    backup = None
    if changed:
        codex_home.mkdir(parents=True, exist_ok=True)
        backup = path.with_name("hooks.json.flow-v2.bak")
        if path.exists():
            shutil.copy2(path, backup)
        else:
            backup.write_text('{"hooks": {}}\n')
        _atomic_json(path, value)
    return {"ok": True, "changed": changed, "hooks_path": str(path),
            "backup_path": str(backup) if backup else None,
            "warning": "INLINE_HOOK_WARNING" if warning else None,
            "next_action": "Start a new Codex session, run /hooks, review and trust the changed definitions."}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home")
    args = parser.parse_args(argv)
    try:
        result = install(args.codex_home)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": str(exc)}}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
