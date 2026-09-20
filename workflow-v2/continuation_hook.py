#!/usr/bin/env python3
"""Bounded, fail-open Codex Stop Hook for an explicitly activated dev-run turn."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import re

from flowctl_lib.continuation import inspect_continuation, _read_state


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
REASONS = {"complete", "human_wait", "blocked", "explicit_stop", "goal_pause", "budget_limit"}
MAX_RUNTIME_BYTES = 1024 * 1024


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _dirs():
    for name in ("turns", "owners", "continuations"):
        path = RUNTIME / name
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)


def _paths(session_id=None, state=None):
    result = {}
    if session_id:
        digest = _hash(session_id)
        result.update(marker=RUNTIME / "turns" / f"{digest}.json",
                      owner=RUNTIME / "owners" / f"{digest}.json",
                      owner_lock=RUNTIME / "owners" / f"{digest}.lock")
    if state:
        digest = _hash(str(Path(state).resolve()))
        result.update(sidecar=RUNTIME / "continuations" / f"{digest}.json",
                      controller_lock=RUNTIME / "continuations" / f"{digest}.lock")
    return result


def _read(path):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RUNTIME_BYTES:
            return None
        raw = os.read(descriptor, MAX_RUNTIME_BYTES + 1)
        if len(raw) > MAX_RUNTIME_BYTES:
            return None
        value = json.loads(raw.decode("utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _nonempty(value):
    return type(value) is str and bool(value)


def _valid_marker(value, session=None):
    return bool(value and value.get("schema_version") == 1
                and _nonempty(value.get("session_id"))
                and _nonempty(value.get("turn_id"))
                and _nonempty(value.get("cwd"))
                and (session is None or value.get("session_id") == session))


def _valid_owner(value, session=None):
    return bool(value and value.get("schema_version") == 1
                and _nonempty(value.get("session_id"))
                and _nonempty(value.get("controller_path"))
                and _nonempty(value.get("sidecar_path"))
                and type(value.get("generation")) is int and value["generation"] > 0
                and (session is None or value.get("session_id") == session))


def _valid_sidecar(value):
    if not (value and value.get("schema_version") == 1
            and all(_nonempty(value.get(name)) for name in (
                "controller_path", "worktree_path", "issue_id", "owner_session_id", "activation_turn_id"
            ))
            and type(value.get("generation")) is int and value["generation"] > 0
            and type(value.get("active")) is bool
            and type(value.get("max_nudges")) is int and 1 <= value["max_nudges"] <= 8
            and type(value.get("nudge_count")) is int and 0 <= value["nudge_count"] <= value["max_nudges"]
            and isinstance(value.get("nudged_fingerprints"), list)
            and len(value["nudged_fingerprints"]) <= value["max_nudges"]
            and all(type(item) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", item)
                    for item in value["nudged_fingerprints"])
            and _nonempty(value.get("last_reason_code"))):
        return False
    return (value["nudge_count"] == len(value["nudged_fingerprints"])
            and len(value["nudged_fingerprints"]) == len(set(value["nudged_fingerprints"])))


def _identity(owner, sidecar, session, state, sidecar_path, generation=None, turn=None,
              issue_id=None, worktree_path=None):
    expected_generation = owner.get("generation") if generation is None else generation
    return bool(_valid_owner(owner, session) and _valid_sidecar(sidecar)
                and owner["controller_path"] == state
                and owner["sidecar_path"] == str(sidecar_path.resolve())
                and owner["generation"] == expected_generation
                and sidecar["controller_path"] == state
                and sidecar["owner_session_id"] == session
                and sidecar["generation"] == expected_generation
                and (turn is None or sidecar["activation_turn_id"] == turn)
                and (issue_id is None or sidecar["issue_id"] == issue_id)
                and (worktree_path is None
                     or Path(sidecar["worktree_path"]).resolve() == Path(worktree_path).resolve()))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    os.chmod(path, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _inside(cwd, worktree):
    try:
        Path(cwd).resolve().relative_to(Path(worktree).resolve())
        return True
    except (OSError, ValueError):
        return False


def marker(event):
    session, turn, cwd = event.get("session_id"), event.get("turn_id"), event.get("cwd")
    if not all(type(item) is str and item for item in (session, turn, cwd)):
        return
    _dirs()
    _write(_paths(session_id=session)["marker"], {
        "schema_version": 1, "session_id": session, "turn_id": turn,
        "cwd": str(Path(cwd).resolve()),
    })


def activate(state, session, max_nudges=4, replace_owner=False, reason=None):
    if not 1 <= max_nudges <= 8:
        raise ValueError("INVALID_NUDGE_BUDGET")
    _dirs()
    supplied_state = Path(state).expanduser()
    observation = inspect_continuation(supplied_state)["continuation"]
    if observation["decision"] != "CONTINUE":
        raise ValueError("CONTINUATION_NOT_ACTIONABLE")
    state_path, controller = _read_state(supplied_state)
    state = str(state_path)
    paths = _paths(session, state)
    current_marker = _read(paths["marker"])
    if (not _valid_marker(current_marker, session)
            or not _inside(current_marker.get("cwd", ""), controller.get("worktree_path", ""))):
        raise ValueError("TURN_MARKER_REQUIRED")
    turn = current_marker["turn_id"]
    with _lock(paths["owner_lock"]):
        owner = _read(paths["owner"])
        if owner and not _valid_owner(owner, session):
            paths["owner"].unlink(missing_ok=True)
            owner = None
        if owner and owner.get("controller_path") != state:
            old_paths = {**paths, **_paths(state=owner["controller_path"])}
            old_sidecar = _read(old_paths["sidecar"])
            try:
                _, old_controller = _read_state(owner["controller_path"])
            except Exception:
                old_controller = None
            if (not old_controller or not _identity(
                    owner, old_sidecar, session, owner["controller_path"], old_paths["sidecar"],
                    issue_id=old_controller.get("issue_id"), worktree_path=old_controller.get("worktree_path"))
                    or old_sidecar.get("active") is not True):
                paths["owner"].unlink(missing_ok=True)
                owner = None
        if owner and owner.get("controller_path") != state:
            if not replace_owner:
                raise ValueError("OWNER_CONFLICT")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("REPLACE_REASON_REQUIRED")
            # The session lock serializes owner publication. Close A before
            # acquiring B's controller lock; never hold two controller locks.
            old_state = owner["controller_path"]
            old_paths = {**paths, **_paths(state=old_state)}
            with _lock(old_paths["controller_lock"]):
                old_sidecar = _read(old_paths["sidecar"])
                if (old_sidecar and old_sidecar.get("owner_session_id") == session
                        and old_sidecar.get("generation") == owner.get("generation")):
                    old_sidecar["active"] = False
                    old_sidecar["last_reason_code"] = "explicit_stop"
                    _write(old_paths["sidecar"], old_sidecar)
        with _lock(paths["controller_lock"]):
            sidecar = _read(paths["sidecar"])
            if sidecar and not _valid_sidecar(sidecar):
                raise ValueError("SIDECAR_INVALID")
            if (sidecar and sidecar.get("active") is True
                    and sidecar.get("owner_session_id") != session):
                if not replace_owner:
                    raise ValueError("OWNER_CONFLICT")
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError("REPLACE_REASON_REQUIRED")
                sidecar["active"] = False
                sidecar["last_reason_code"] = "explicit_stop"
                _write(paths["sidecar"], sidecar)
            if (owner and sidecar and _identity(
                    owner, sidecar, session, state, paths["sidecar"], turn=turn,
                    issue_id=controller["issue_id"], worktree_path=controller["worktree_path"])
                    and sidecar.get("active") is True):
                return {**sidecar, "ok": True, "turn_id": turn}
            generation = (sidecar.get("generation", 0) if sidecar else 0) + 1
            record = {
                "schema_version": 1, "controller_path": state,
                "worktree_path": str(Path(controller["worktree_path"]).resolve()),
                "issue_id": controller["issue_id"], "owner_session_id": session,
                "activation_turn_id": turn, "generation": generation, "active": True,
                "max_nudges": max_nudges, "nudge_count": 0,
                "nudged_fingerprints": [], "last_reason_code": observation["reason_code"],
            }
            if replace_owner:
                record["replace_reason_digest"] = "sha256:" + hashlib.sha256(reason.strip().encode()).hexdigest()
            _write(paths["sidecar"], record)
            _write(paths["owner"], {
                "schema_version": 1, "session_id": session, "controller_path": state,
                "sidecar_path": str(paths["sidecar"].resolve()), "generation": generation,
            })
            return {**record, "ok": True, "turn_id": turn}


def _deactivate_locked(paths, session, state, generation, reason, issue_id=None, worktree_path=None):
    owner, sidecar = _read(paths["owner"]), _read(paths["sidecar"])
    if not _identity(owner, sidecar, session, state, paths["sidecar"], generation=generation,
                     issue_id=issue_id, worktree_path=worktree_path):
        return False
    sidecar["active"] = False
    sidecar["last_reason_code"] = reason
    _write(paths["sidecar"], sidecar)
    current = _read(paths["owner"])
    if current and current.get("generation") == generation and current.get("controller_path") == state:
        paths["owner"].unlink(missing_ok=True)
    return True


def deactivate(state, session, generation, reason):
    if reason not in REASONS:
        raise ValueError("INVALID_DEACTIVATION_REASON")
    state_path, controller = _read_state(Path(state).expanduser())
    state = str(state_path)
    paths = _paths(session, state)
    with _lock(paths["owner_lock"]):
        with _lock(paths["controller_lock"]):
            changed = _deactivate_locked(
                paths, session, state, generation, reason,
                controller["issue_id"], controller["worktree_path"],
            )
    return {"ok": True, "deactivated": changed, "generation": generation}


def stop(event):
    session, turn, cwd = event.get("session_id"), event.get("turn_id"), event.get("cwd")
    if not all(type(item) is str and item for item in (session, turn, cwd)):
        return None
    _dirs()
    session_paths = _paths(session_id=session)
    with _lock(session_paths["owner_lock"]):
        owner = _read(session_paths["owner"])
        if not _valid_owner(owner, session):
            session_paths["owner"].unlink(missing_ok=True)
            return None
        state = owner.get("controller_path")
        try:
            _, controller = _read_state(state)
        except Exception:
            session_paths["owner"].unlink(missing_ok=True)
            return None
        paths = {**session_paths, **_paths(state=state)}
        with _lock(paths["controller_lock"]):
            sidecar = _read(paths["sidecar"])
            if (not _identity(
                    owner, sidecar, session, state, paths["sidecar"],
                    issue_id=controller.get("issue_id"), worktree_path=controller.get("worktree_path"))
                    or sidecar.get("active") is not True
                    or not _inside(cwd, sidecar.get("worktree_path", ""))):
                session_paths["owner"].unlink(missing_ok=True)
                return None
            generation = sidecar["generation"]
            if sidecar.get("activation_turn_id") != turn:
                _deactivate_locked(paths, session, state, generation, "explicit_stop",
                                   controller["issue_id"], controller["worktree_path"])
                return None
    try:
        process = subprocess.run(
            [sys.executable, str(ROOT / "flowctl.py"), "continuation", "inspect", "--state", state],
            text=True, capture_output=True, timeout=2, check=False,
        )
        payload = json.loads(process.stdout)
        if process.returncode or payload.get("ok") is not True:
            raise ValueError("inspection failed")
        observation = payload["continuation"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError):
        observation = {"decision": "ALLOW_STOP", "reason_code": "UNKNOWN"}
    with _lock(session_paths["owner_lock"]):
        owner = _read(session_paths["owner"])
        with _lock(paths["controller_lock"]):
            current = _read(paths["sidecar"])
            if (not _identity(
                    owner, current, session, state, paths["sidecar"], generation, turn,
                    controller["issue_id"], controller["worktree_path"])
                    or current.get("active") is not True):
                return None
            if observation.get("decision") != "CONTINUE":
                _deactivate_locked(
                    paths, session, state, generation, observation.get("reason_code", "UNKNOWN").lower(),
                    controller["issue_id"], controller["worktree_path"],
                )
                return None
            fingerprint = observation.get("progress_fingerprint")
            if (not fingerprint or fingerprint in current["nudged_fingerprints"]
                    or current["nudge_count"] >= current["max_nudges"]):
                _deactivate_locked(paths, session, state, generation, "budget_limit",
                                   controller["issue_id"], controller["worktree_path"])
                return None
            current["nudged_fingerprints"].append(fingerprint)
            current["nudge_count"] += 1
            current["last_reason_code"] = observation["reason_code"]
            _write(paths["sidecar"], current)
    return {"decision": "block", "reason": (
        "Re-read the current Flow controller and continue the admitted dev-run main loop. "
        "Reuse or wait for existing workers. Record facts before claiming progress, and stop at "
        "a human gate, real blocker, completion, permission boundary, or exhausted budget."
    )}


def hook():
    try:
        event = json.load(sys.stdin)
        name = event.get("hook_event_name") or event.get("event_name")
        if name == "UserPromptSubmit":
            marker(event)
            return None
        if name == "Stop":
            return stop(event)
    except Exception:
        return None
    return None


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hook")
    active = commands.add_parser("activate")
    active.add_argument("--state", required=True)
    active.add_argument("--session-id", required=True)
    active.add_argument("--max-nudges", type=int, default=4)
    active.add_argument("--replace-owner", action="store_true")
    active.add_argument("--reason")
    inactive = commands.add_parser("deactivate")
    inactive.add_argument("--state", required=True)
    inactive.add_argument("--session-id", required=True)
    inactive.add_argument("--generation", required=True, type=int)
    inactive.add_argument("--reason", required=True, choices=sorted(REASONS))
    args = parser.parse_args(argv)
    try:
        if args.command == "hook":
            result = hook()
        elif args.command == "activate":
            result = activate(args.state, args.session_id, args.max_nudges, args.replace_owner, args.reason)
        else:
            result = deactivate(args.state, args.session_id, args.generation, args.reason)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": str(exc)}}))
        return 2
    if result:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
