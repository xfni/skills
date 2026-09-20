"""Read-only continuation observation for the dev-run Stop hook."""
import hashlib
import json
import os
from pathlib import Path
import stat
import errno

from .errors import FlowctlError


MAX_STATE_BYTES = 8 * 1024 * 1024
STAGES = {
    "flow-requirement", "flow-intent", "flow-roadmap", "flow-spec",
    "flow-plan", "flow-code", "flow-integration",
}
SIGNALS = {None, "FLOW_RUN_ROUTE_BACK", "FLOW_RUN_RESUMED"}
ACTION_PREFIXES = (
    "produce:", "review:", "revise:", "repair:", "approve:",
    "handoff:", "inspect:", "execute:",
)


def _read_state(path):
    path = Path(path).expanduser()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise FlowctlError("CONTINUATION_STATE_SYMLINK", path=str(path)) from exc
        raise FlowctlError("CONTINUATION_STATE_UNREADABLE", path=str(path)) from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise FlowctlError("CONTINUATION_STATE_NOT_REGULAR", path=str(path))
        if info.st_size > MAX_STATE_BYTES:
            raise FlowctlError("CONTINUATION_STATE_TOO_LARGE", size=info.st_size)
        raw = os.read(descriptor, MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES:
            raise FlowctlError("CONTINUATION_STATE_TOO_LARGE", size=len(raw))
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FlowctlError("CONTINUATION_STATE_INVALID", path=str(path)) from exc
    finally:
        os.close(descriptor)
    if not isinstance(value, dict):
        raise FlowctlError("CONTINUATION_STATE_INVALID", path=str(path))
    return path.resolve(), value


def _unknown(stage=None, milestone=None, action=None, revision=None):
    return _result("ALLOW_STOP", "UNKNOWN", stage, milestone, action, revision, None)


def _result(decision, reason, stage, milestone, action, revision, fingerprint):
    messages = {
        "ACTIONABLE": "Continue the admitted dev-run loop from the current controller facts.",
        "HUMAN_WAIT": "The workflow is waiting for a human decision.",
        "BLOCKED": "The workflow has a recorded blocker.",
        "COMPLETE": "The workflow is complete.",
        "INACTIVE": "The workflow has no pending action.",
        "UNKNOWN": "Continuation cannot be determined safely.",
    }
    return {"ok": True, "continuation": {
        "decision": decision, "reason_code": reason, "stage": stage,
        "milestone_id": milestone, "pending_action": action,
        "state_revision": revision, "progress_fingerprint": fingerprint,
        "continuation_reason": messages[reason],
    }}


def _nullable(value, expected):
    return value if value is None or type(value) is expected else ...


def _all_typed(mapping, schema):
    projected = {name: _nullable(mapping.get(name), expected) for name, expected in schema.items()}
    if any(value is ... for value in projected.values()):
        raise ValueError("invalid projected field type")
    return projected


def _artifact_projection(state, stage, milestone):
    kind = stage.removeprefix("flow-")
    key = kind if kind in {"requirement", "intent", "roadmap"} else f"{kind}:{milestone}"
    artifacts = state.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts")
    artifact = artifacts.get(key)
    if artifact is None:
        return key, None, [], None
    if not isinstance(artifact, dict):
        raise ValueError("artifact")
    approval = artifact.get("approval")
    if not isinstance(approval, dict):
        raise ValueError("approval")
    projected = _all_typed(artifact, {
        "type": str, "digest": str, "revision": int, "milestone_id": str,
    })
    projected["key"] = key
    projected["approval"] = _all_typed(approval, {
        "valid": bool, "status": str, "approved_revision": str,
        "approved_digest": str, "confirmer": str,
    })
    attempts = []
    reviews = state.get("reviews", {})
    if reviews is not None and not isinstance(reviews, dict):
        raise ValueError("reviews")
    raw_attempts = (reviews or {}).get("attempts", {})
    if not isinstance(raw_attempts, dict):
        raise ValueError("attempts")
    for item in raw_attempts.values():
        if not isinstance(item, dict):
            raise ValueError("attempt")
        if item.get("artifact_key") != key or item.get("artifact_digest") != artifact.get("digest"):
            continue
        eligible = item.get("eligible", True)
        revoked = item.get("revoked", False)
        if type(eligible) is not bool or type(revoked) is not bool:
            raise ValueError("review bool")
        attempt = {name: _nullable(item.get(name), str) for name in (
            "attempt_id", "backend", "status", "classification", "artifact_digest",
            "snapshot_digest", "invalidated_by",
        )}
        if any(value is ... for value in attempt.values()):
            raise ValueError("review type")
        attempt.update(eligible=eligible, revoked=revoked)
        attempts.append(attempt)
    attempts.sort(key=lambda item: item.get("attempt_id") or "")
    snapshots = state.get("snapshots", {})
    if snapshots is not None and not isinstance(snapshots, dict):
        raise ValueError("snapshots")
    snapshot = (snapshots or {}).get(key)
    if snapshot is not None:
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("untracked", {}), dict):
            raise ValueError("snapshot")
        if not all(type(name) is str and type(digest) is str
                   for name, digest in snapshot.get("untracked", {}).items()):
            raise ValueError("snapshot untracked")
        snapshot = _all_typed(snapshot, {
            "snapshot_digest": str, "head": str, "status_digest": str,
            "tracked_diff_digest": str, "untracked": dict, "evidence_exclusion": str,
        })
    return key, projected, attempts, snapshot


def _fingerprint(path, state, stage, milestone, action):
    key, artifact, attempts, snapshot = _artifact_projection(state, stage, milestone)
    signal = state.get("pending_signal")
    signal_projection = None if signal is None else _all_typed(signal, {
        "signal": str, "stage": str, "owner_stage": str, "next_stage": str, "gate": str,
    })
    coder = None
    if stage == "flow-code":
        raw = state.get("coder_agent", {})
        if not isinstance(raw, dict):
            raise ValueError("coder")
        completed = raw.get("completed_tasks")
        if completed is not None and (not isinstance(completed, list) or not all(isinstance(x, str) for x in completed)):
            raise ValueError("coder completed")
        coder = _all_typed(raw, {
            "coder_thread_id": str, "coder_model": str, "coder_effort": str,
            "active_task": str, "completed_tasks": list, "last_checkpoint": str,
            "replacement_generation": int,
        })
    projection = {
        "schema_version": 1, "controller_path": str(path),
        "issue_id": state["issue_id"], "run_id": state["run_id"],
        "stage": stage, "active_milestone": milestone, "pending_action": action,
        "pending_signal": signal_projection, "artifact_key": key, "artifact": artifact,
        "review_attempts": attempts, "snapshot": snapshot, "coder_agent": coder,
    }
    canonical = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def inspect_continuation(state_path):
    path, state = _read_state(state_path)
    stage, action = state.get("current_stage"), state.get("pending_action")
    milestone, revision = state.get("active_milestone"), state.get("state_revision")
    required_strings = (state.get("issue_id"), state.get("run_id"), state.get("controller_path"), state.get("worktree_path"))
    schema_version = state.get("schema_version")
    if (type(schema_version) is not int or schema_version not in {1, 2}
            or not all(type(item) is str and item for item in required_strings)
            or type(revision) is not int or revision < 0
            or Path(state.get("controller_path", "")).expanduser().resolve() != path):
        raise FlowctlError("CONTINUATION_STATE_SCHEMA_INVALID")
    if milestone is not None and type(milestone) is not str:
        return _unknown(stage, milestone, action, revision)
    if type(stage) is not str:
        return _unknown(stage, milestone, action, revision)
    if stage == "complete":
        return _result("ALLOW_STOP", "COMPLETE", stage, milestone, action, revision, None)
    signal = state.get("pending_signal")
    if signal is not None and not isinstance(signal, dict):
        return _unknown(stage, milestone, action, revision)
    signal_name = (signal or {}).get("signal")
    if signal_name is not None and type(signal_name) is not str:
        return _unknown(stage, milestone, action, revision)
    if signal_name in {"FLOW_RUN_HUMAN_GATE", "FLOW_ADMISSION_GATE"} or action == "human_gate":
        return _result("ALLOW_STOP", "HUMAN_WAIT", stage, milestone, action, revision, None)
    if signal_name in {"FLOW_RUN_BLOCKED", "FLOW_ADMISSION_BLOCKED"} or (isinstance(action, str) and (action == "blocked" or action.startswith("blocked:"))):
        return _result("ALLOW_STOP", "BLOCKED", stage, milestone, action, revision, None)
    if stage not in STAGES or signal_name not in SIGNALS:
        return _unknown(stage, milestone, action, revision)
    if action is None:
        return _result("ALLOW_STOP", "INACTIVE", stage, milestone, action, revision, None)
    actionable = isinstance(action, str) and (action in {"resume", "snapshot:capture"} or action.startswith(ACTION_PREFIXES))
    if not actionable:
        return _unknown(stage, milestone, action, revision)
    try:
        fingerprint = _fingerprint(path, state, stage, milestone, action)
    except (KeyError, TypeError, ValueError):
        return _unknown(stage, milestone, action, revision)
    return _result("CONTINUE", "ACTIONABLE", stage, milestone, action, revision, fingerprint)
