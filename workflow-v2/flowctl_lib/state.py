from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import re

from .artifacts import verify_artifact, read_artifact, is_reviewable_artifact
from .errors import FlowctlError


STAGE_BY_KIND = {kind: f"flow-{kind}" for kind in ("requirement", "intent", "roadmap", "spec", "plan", "code", "integration")}
ORDER = tuple(STAGE_BY_KIND)
DEPENDENCIES = {
    "requirement": (),
    "intent": ("requirement",),
    "roadmap": ("requirement", "intent"),
    "spec": ("requirement", "intent", "roadmap"),
    "plan": ("requirement", "intent", "roadmap", "spec"),
    "code": ("requirement", "intent", "roadmap", "spec", "plan"),
    "integration": ("requirement", "intent", "roadmap", "spec", "plan", "code"),
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def initialize_state(path, issue_id, repo_root, branch, run_id=None,
                     stage='flow-requirement', milestone=None):
    resolved = Path(path).expanduser().resolve()
    lock_path = resolved.with_suffix(resolved.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _initialize_state_locked(resolved, issue_id, repo_root, branch, run_id, stage, milestone)


def _initialize_state_locked(path, issue_id, repo_root, branch, run_id=None,
                             stage='flow-requirement', milestone=None):
    _recover_transaction(path)
    if not re.fullmatch(r"[A-Z][A-Z0-9]+-[1-9][0-9]*", issue_id):
        raise FlowctlError("INVALID_ISSUE_ID", issue_id=issue_id)
    if issue_id.lower() not in branch.lower():
        raise FlowctlError("BRANCH_ISSUE_MISMATCH", issue_id=issue_id, branch=branch)
    path = Path(path).expanduser().resolve()
    if path.exists():
        state = load_state(path)
        if state["issue_id"] != issue_id:
            raise FlowctlError("ISSUE_MISMATCH")
        expected_root = str(Path(repo_root).expanduser().resolve())
        if (state["repo_root"] != expected_root
                or state["worktree_path"] != expected_root
                or state["branch"] != branch):
            raise FlowctlError(
                "CONTROLLER_ADMISSION_MISMATCH",
                expected_repo=expected_root, actual_repo=state["repo_root"],
                expected_worktree=expected_root, actual_worktree=state["worktree_path"],
                expected_branch=branch, actual_branch=state["branch"],
            )
        return _migrate_state_locked(path, state)
    if stage not in STAGE_BY_KIND.values():
        raise FlowctlError('INVALID_ENTRY_STAGE', stage=stage)
    if stage in {'flow-spec', 'flow-plan', 'flow-code', 'flow-integration'} and not milestone:
        raise FlowctlError('MILESTONE_REQUIRED', stage=stage)
    now = utc_now()
    state = {
        "schema_version": 1,
        "issue_id": issue_id,
        "issue_provenance": "HUMAN_PROVIDED",
        "run_id": run_id or f"run-{issue_id.lower()}",
        "controller_path": str(path),
        "state_revision": 0,
        "repo_root": str(Path(repo_root).expanduser().resolve()),
        "worktree_path": str(Path(repo_root).expanduser().resolve()),
        "branch": branch,
        "current_stage": stage,
        "pending_action": 'produce:' + stage.removeprefix('flow-'),
        "artifacts": {},
        "reviews": {"attempts": {}, "lanes": {}},
        "snapshots": {},
        "coder_agent": {},
        "open_gaps": [],
        "target_milestones": [],
        "milestones": {},
        "active_milestone": milestone,
        "invalidations": [],
        "invalidated_checkpoints": {},
        "artifact_high_water": {},
        "route_back_context": None,
        "created_at": now,
        "updated_at": now,
        "event_head": None,
    }
    from .authorizations import migrate_state

    state, _ = migrate_state(state)
    _atomic_json(path, state)
    return state


def load_state(path):
    try:
        path = Path(path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise FlowctlError("CONTROLLER_NOT_FOUND", path=str(path)) from exc
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FlowctlError("INVALID_CONTROLLER") from exc
    required = {"issue_id", "run_id", "repo_root", "worktree_path", "branch", "current_stage", "pending_action", "artifacts", "reviews"}
    if (state.get("schema_version") not in {1, 2} or not isinstance(state.get("state_revision"), int)
            or not required.issubset(state)):
        raise FlowctlError("INVALID_CONTROLLER")
    if state['schema_version'] == 2 and not isinstance(state.get('authorizations'), dict):
        raise FlowctlError('INVALID_CONTROLLER')
    return state


def _migrate_state_locked(path, state):
    from .authorizations import migrate_state

    migrated, changed = migrate_state(state)
    if not changed:
        return migrated
    return commit_state(path, migrated, "STATE_SCHEMA_MIGRATED", {
        "from_schema_version": 1,
        "to_schema_version": 2,
    })


def read_consistent_state(path):
    path = Path(path).expanduser().resolve()
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        _recover_transaction(path)
        return _migrate_state_locked(path, load_state(path))


def validate_admission(state):
    """Revalidate worktree and branch facts at every controlled stage entry."""
    import subprocess

    worktree = Path(state["worktree_path"]).resolve()
    if not worktree.is_dir():
        raise FlowctlError("WORKTREE_NOT_FOUND", path=str(worktree))
    facts = {}
    for name, command in {
        "root": ["git", "rev-parse", "--show-toplevel"],
        "branch": ["git", "branch", "--show-current"],
    }.items():
        result = subprocess.run(command, cwd=worktree, text=True, capture_output=True)
        if result.returncode:
            raise FlowctlError("INVALID_WORKTREE", operation=name, stderr=result.stderr.strip())
        facts[name] = result.stdout.strip()
    if Path(facts["root"]).resolve() != worktree:
        raise FlowctlError("WORKTREE_MISMATCH", expected=str(worktree), actual=facts["root"])
    if facts["branch"] != state["branch"]:
        raise FlowctlError("BRANCH_MISMATCH", expected=state["branch"], actual=facts["branch"])
    return {"worktree_path": str(worktree), "branch": facts["branch"]}


def audit_state(state):
    """Recompute every registered artifact and reject a stale controller."""
    from .authorizations import validate_authorizations
    if state.get('schema_version') == 2 and not validate_authorizations(state.get('authorizations')):
        raise FlowctlError('INVALID_CONTROLLER')
    verified = {}
    for key, recorded in state.get("artifacts", {}).items():
        current = verify_artifact(
            recorded["path"], expected_type=recorded["type"],
            expected_issue=state["issue_id"], expected_milestone=recorded.get("milestone_id"),
        )
        if current["digest"] != recorded["digest"] or current["revision"] != recorded["revision"]:
            raise FlowctlError("ARTIFACT_DRIFT", artifact_key=key)
        if not current["approval"]["valid"]:
            raise FlowctlError("APPROVAL_STALE", artifact_key=key)
        verified[key] = current
    for key, current in verified.items():
        validate_upstream({**state, "artifacts": verified}, current, strict=True)
        validate_approval_authority({**state, "artifacts": verified}, current, strict=True)
    events_path = Path(state["worktree_path"]) / ".ai" / "issue" / state["issue_id"] / "flow-events.jsonl"
    controller_events = Path(state.get("controller_path", events_path.with_name("flow-state.json"))).with_name("flow-events.jsonl")
    if controller_events.exists():
        previous = None
        expected_seq = 1
        for line in controller_events.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FlowctlError("INVALID_EVENT_LOG") from exc
            digest = event.pop("event_digest", None)
            canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            actual = "sha256:" + hashlib.sha256(canonical).hexdigest()
            if event.get("seq") != expected_seq or event.get("previous_event_digest") != previous or digest != actual:
                raise FlowctlError("INVALID_EVENT_LOG", seq=event.get("seq"))
            previous, expected_seq = digest, expected_seq + 1
        if previous != state.get("event_head") or expected_seq - 1 != state["state_revision"]:
            raise FlowctlError("EVENT_STATE_MISMATCH")
    elif state["state_revision"]:
        raise FlowctlError("EVENT_STATE_MISMATCH")
    return {"artifact_count": len(verified), "verified_keys": sorted(verified), "event_head": state.get("event_head")}


def reject_if_paused(state):
    signal = state.get("pending_signal", {}).get("signal")
    if signal in {"FLOW_RUN_HUMAN_GATE", "FLOW_RUN_BLOCKED"}:
        raise FlowctlError("FLOW_PAUSED", signal=signal)


@contextmanager
def locked_state(path, expected_revision):
    path = Path(path).expanduser().resolve()
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        _recover_transaction(path)
        state = load_state(path)
        if state["state_revision"] != expected_revision:
            raise FlowctlError(
                "STATE_CONFLICT", expected_revision=expected_revision,
                actual_revision=state["state_revision"],
            )
        state = _migrate_state_locked(path, state)
        yield state


def commit_state(path, state, event_type, event_data):
    path = Path(path).expanduser().resolve()
    state["state_revision"] += 1
    state["updated_at"] = utc_now()
    event = {
        "seq": state["state_revision"],
        "at": state["updated_at"],
        "event": event_type,
        "previous_event_digest": state.get("event_head"),
        **event_data,
    }
    canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    event["event_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    state["event_head"] = event["event_digest"]
    events_path = path.with_name("flow-events.jsonl")
    transaction_path = path.with_suffix(path.suffix + ".txn.json")
    event_log_offset = events_path.stat().st_size if events_path.exists() else 0
    _atomic_json(transaction_path, {
        "state": state, "event": event, "event_log_offset": event_log_offset,
    })
    _append_event_once(events_path, event)
    _atomic_json(path, state)
    transaction_path.unlink()
    _fsync_directory(transaction_path.parent)
    return state


def _append_event_once(events_path, event):
    events_path = Path(events_path)
    existing_last = None
    if events_path.exists():
        lines = events_path.read_text(encoding="utf-8").splitlines()
        if lines:
            try:
                existing_last = json.loads(lines[-1])
            except json.JSONDecodeError as exc:
                raise FlowctlError("INVALID_EVENT_LOG") from exc
    if existing_last and existing_last.get("event_digest") == event["event_digest"]:
        return
    if existing_last and existing_last.get("seq", 0) >= event["seq"]:
        raise FlowctlError("EVENT_SEQUENCE_CONFLICT")
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _recover_transaction(path):
    path = Path(path).expanduser().resolve()
    transaction_path = path.with_suffix(path.suffix + ".txn.json")
    if not transaction_path.exists():
        return
    try:
        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
        state, event = transaction["state"], transaction["event"]
        event_log_offset = transaction["event_log_offset"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise FlowctlError("INVALID_TRANSACTION_JOURNAL") from exc
    events_path = path.with_name("flow-events.jsonl")
    _recover_event_append(events_path, event, event_log_offset)
    current_revision = -1
    if path.exists():
        try:
            current_revision = json.loads(path.read_text(encoding="utf-8")).get("state_revision", -1)
        except (OSError, json.JSONDecodeError):
            current_revision = -1
    if current_revision <= state["state_revision"]:
        _atomic_json(path, state)
    transaction_path.unlink()
    _fsync_directory(transaction_path.parent)


def _recover_event_append(events_path, event, offset):
    events_path = Path(events_path)
    if not isinstance(offset, int) or offset < 0:
        raise FlowctlError("INVALID_TRANSACTION_JOURNAL")
    expected = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    current = events_path.read_bytes() if events_path.exists() else b""
    if len(current) < offset:
        raise FlowctlError("EVENT_LOG_TRUNCATED", expected_offset=offset, actual_size=len(current))
    tail = current[offset:]
    if tail == expected:
        return
    if tail and not expected.startswith(tail):
        raise FlowctlError("EVENT_TAIL_CONFLICT")
    with events_path.open("r+b" if events_path.exists() else "w+b") as handle:
        handle.truncate(offset)
        handle.seek(offset)
        handle.write(expected)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(events_path.parent)


def _fsync_directory(path):
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def artifact_key(kind, milestone=None):
    return f"{kind}:{milestone}" if milestone and kind in {"spec", "plan", "code", "integration"} else kind


def _dependency_key(kind, dependency, milestone):
    if dependency in {"spec", "plan", "code", "integration"}:
        return artifact_key(dependency, milestone)
    return dependency


def validate_upstream(state, artifact, strict=False):
    kind = artifact["type"]
    if not strict:
        # Bind inputs that actually exist. Missing historical documents and
        # model-authored tuples are not an admission failure at arbitrary entry.
        for dependency in DEPENDENCIES[kind]:
            key = _dependency_key(kind, dependency, artifact['milestone_id'])
            registered = state['artifacts'].get(key)
            if registered:
                claimed = artifact['upstream'].get(dependency)
                if claimed and (claimed.get('digest') != registered['digest']
                                or claimed.get('revision') != registered['revision']):
                    artifact.setdefault('warnings', []).append('UPSTREAM_BINDING_CHANGED:' + key)
            else:
                artifact.setdefault('warnings', []).append('HISTORICAL_INPUT_UNAVAILABLE:' + key)
        return
    for dependency in DEPENDENCIES[kind]:
        key = _dependency_key(kind, dependency, artifact["milestone_id"])
        registered = state["artifacts"].get(key)
        claimed = artifact["upstream"].get(dependency)
        if not registered or not claimed:
            raise FlowctlError("UPSTREAM_REQUIRED", artifact=kind, dependency=key)
        try:
            current = verify_artifact(
                registered["path"], expected_type=registered["type"],
                expected_issue=state["issue_id"], expected_milestone=registered.get("milestone_id"),
            )
        except (FlowctlError, OSError) as exc:
            raise FlowctlError("UPSTREAM_DRIFT", dependency=key) from exc
        if current["digest"] != registered["digest"] or current["revision"] != registered["revision"]:
            raise FlowctlError("UPSTREAM_DRIFT", dependency=key)
        if claimed["digest"] != registered["digest"] or claimed["revision"] != registered["revision"]:
            raise FlowctlError("UPSTREAM_BINDING_MISMATCH", artifact=kind, dependency=key)


def validate_approval_authority(state, artifact, strict=False):
    approval = artifact["approval"]
    if artifact["type"] == "requirement":
        if approval['valid'] and approval["confirmer"] != "HUMAN":
            raise FlowctlError("HUMAN_REQUIREMENT_APPROVAL_REQUIRED")
        return
    if not strict:
        # Requirement human approval is the product gate; downstream authored
        # approval tuples are not proof of reviewer execution.
        if not approval.get('confirmer'):
            approval['confirmer'] = 'ORCHESTRATED'
        return
    if approval["confirmer"] == "HUMAN":
        return
    if approval["confirmer"] != "ORCHESTRATED":
        raise FlowctlError("INVALID_APPROVAL_AUTHORITY")
    requirement = state["artifacts"].get("requirement")
    if not requirement:
        raise FlowctlError("UPSTREAM_REQUIRED", dependency="requirement")
    try:
        approved_requirement_revision = int(approval["requirement_revision"])
    except (TypeError, ValueError) as exc:
        raise FlowctlError("INVALID_ORCHESTRATED_APPROVAL") from exc
    if (approval["controller_run_id"] != state["run_id"]
            or approved_requirement_revision != requirement["revision"]
            or approval["requirement_digest"] != requirement["digest"]
            or not approval["scope_binding"]):
        raise FlowctlError("INVALID_ORCHESTRATED_APPROVAL")



def reconcile_requirement_route(state, artifacts):
    """Clear a stale route only for an approved replacement of its tombstone."""
    context = state.get('route_back_context')
    if not context or context.get('owner_stage') != 'flow-requirement':
        return False
    replacement = artifacts.get('requirement')
    tombstone = state.get('invalidated_checkpoints', {}).get('requirement')
    if not (replacement and tombstone
            and replacement['digest'] != tombstone['digest']
            and replacement['revision'] > tombstone['revision']
            and replacement['approval']['valid']
            and replacement['approval']['confirmer'] == 'HUMAN'):
        return False
    state['route_back_context'] = None
    return True


def register_artifact(state_path, path, kind, milestone, expected_state_revision, disposition_path=None):
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        artifact = read_artifact(path, expected_type=kind, expected_issue=state["issue_id"], expected_milestone=milestone)
        if not is_reviewable_artifact(artifact):
            raise FlowctlError("APPROVAL_STALE", artifact=str(path))
        validate_upstream(state, artifact)
        validate_approval_authority(state, artifact)
        if kind == 'integration':
            from .integration_results import require_integration_results
            require_integration_results(artifact, state['artifacts'].get(f"plan:{artifact['milestone_id']}"))
        if kind in {"spec", "plan", "code", "integration"}:
            active = state.get("active_milestone")
            if state.get("target_milestones") and artifact["milestone_id"] != active:
                raise FlowctlError("MILESTONE_NOT_ACTIVE", expected=active, actual=artifact["milestone_id"])
        key = artifact_key(kind, milestone or artifact["milestone_id"])
        high_water = state.setdefault("artifact_high_water", {}).get(key)
        if high_water:
            artifact['revision'] = max(artifact['revision'], high_water['revision'] +
                (artifact['digest'] != high_water['digest']))
        tombstone = state.get("invalidated_checkpoints", {}).get(key)
        if tombstone and artifact['digest'] == tombstone['digest']:
            raise FlowctlError(
                "INVALIDATED_REVISION_REUSED", artifact_key=key,
                invalidated_revision=tombstone["revision"], candidate_revision=artifact["revision"],
            )
        if tombstone:
            artifact['revision'] = max(artifact['revision'], tombstone['revision'] + 1)
        current = state["artifacts"].get(key)
        if kind == 'integration':
            from .integration_results import validate_result_replacement
            validate_result_replacement(current, artifact)
        if current and all(current.get(field) == artifact.get(field) for field in ("path", "revision", "digest")):
            if kind == 'requirement' and reconcile_requirement_route(state, {key: artifact}):
                state['artifacts'][key] = artifact
                if state['current_stage'] == 'flow-requirement':
                    state['pending_action'] = 'handoff:requirement'
                return commit_state(state_path, state, 'ROUTE_BACK_RECONCILED', {
                    'artifact_key': key, 'digest': artifact['digest'],
                    'revision': artifact['revision'], 'owner_stage': 'flow-requirement',
                })
            if current['approval'] == artifact['approval'] and disposition_path is None:
                return state
            state['artifacts'][key] = artifact
            from .dispositions import apply_disposition
            apply_disposition(state, key, disposition_path)
            if kind in {'spec', 'plan', 'code'} and STAGE_BY_KIND[kind] == state['current_stage']:
                from .reviews import next_review_action
                state['pending_action'] = next_review_action(state, key)
            return commit_state(state_path, state, 'ARTIFACT_APPROVAL_UPDATED', {
                'artifact_key': key, 'digest': artifact['digest'], 'status': artifact['approval']['status'],
            })
        if current and artifact['digest'] != current['digest']:
            artifact['revision'] = max(artifact['revision'], current['revision'] + 1)

        # Registration records bytes, not semantic withdrawal. Old receipts and
        # their snapshots remain available; matching is checked when consumed.
        if current:
            state.setdefault('artifact_history', []).append({'artifact_key': key, 'artifact': current})
        invalidated = []
        invalidated_reviews = []
        state["artifacts"][key] = artifact
        from .reviews import reconcile_review_occupancy
        released_reviews = reconcile_review_occupancy(state)
        from .dispositions import apply_disposition
        apply_disposition(state, key, disposition_path)
        state.setdefault("artifact_high_water", {})[key] = {
            "revision": artifact["revision"], "digest": artifact["digest"],
        }
        route_context = state.get("route_back_context")
        if (route_context and route_context.get("owner_stage") == STAGE_BY_KIND[kind]
                and (not route_context.get("milestone_id")
                     or route_context.get("milestone_id") == artifact.get("milestone_id"))):
            state["route_back_context"] = None
        if kind == "roadmap" and artifact.get("target_milestones"):
            state["target_milestones"] = artifact["target_milestones"]
            state["milestones"] = {
                item: state.get('milestones', {}).get(item, {"status": "pending", "dependencies": artifact["milestone_dependencies"].get(item, [])})
                for item in artifact["target_milestones"]
            }
        if STAGE_BY_KIND[kind] != state['current_stage']:
            pass  # Supplementary registration never relocates execution.
        elif kind in {'spec', 'plan', 'code'}:
            from .reviews import next_review_action
            state['pending_action'] = next_review_action(state, key)
        else:
            state['pending_action'] = f'handoff:{kind}'
        return commit_state(state_path, state, "ARTIFACT_REGISTERED", {
            "artifact_key": key, "revision": artifact["revision"], "digest": artifact["digest"],
            "invalidated_artifacts": invalidated, "invalidated_reviews": invalidated_reviews,
            "released_review_occupancy": released_reviews,
        })


def record_runtime_goal(state_path, payload_path, expected_state_revision):
    """Record caller-observed runtime context; never create a Goal or approve Flow."""
    try:
        payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
        goal = payload.get("goal") if isinstance(payload, dict) else None
        if (not isinstance(goal, dict)
                or any(not isinstance(goal.get(key), str) or not goal[key].strip()
                       for key in ("threadId", "objective", "status"))
                or type(goal.get("createdAt")) is not int or goal["createdAt"] < 0):
            raise ValueError("invalid runtime context")
        reference = {key: goal[key] for key in ("threadId", "createdAt", "objective", "status")}
    except (OSError, ValueError, TypeError):
        raise FlowctlError("INVALID_RUNTIME_GOAL") from None
    with locked_state(state_path, expected_state_revision) as state:
        prior = state.get("runtime_goal")
        if prior == reference:
            return state
        if prior and any(prior.get(key) != reference[key]
                         for key in ("threadId", "createdAt", "objective")):
            state.setdefault("runtime_goal_history", []).append(prior)
        state["runtime_goal"] = reference
        return commit_state(state_path, state, "RUNTIME_GOAL_RECORDED", {"runtime_goal": reference})


CODER_FIELDS = {
    "coder_thread_id", "coder_model", "coder_effort", "active_task",
    "completed_tasks", "last_checkpoint", "replacement_generation",
    "replacement_reason", "prior_coder_thread_id",
}


def update_coder_state(state_path, payload_path, expected_state_revision):
    try:
        payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowctlError("INVALID_CODER_STATE") from exc
    if not isinstance(payload, dict) or not set(payload).issubset(CODER_FIELDS):
        raise FlowctlError("INVALID_CODER_STATE")
    if "completed_tasks" in payload and not (
        isinstance(payload["completed_tasks"], list)
        and all(isinstance(item, str) for item in payload["completed_tasks"])
    ):
        raise FlowctlError("INVALID_CODER_STATE")
    if "replacement_generation" in payload and (
        not isinstance(payload["replacement_generation"], int) or payload["replacement_generation"] < 0
    ):
        raise FlowctlError("INVALID_CODER_STATE")
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        if state["current_stage"] != "flow-code":
            raise FlowctlError("STAGE_MISMATCH", expected="flow-code", actual=state["current_stage"])
        prior = state.get("coder_agent", {})
        generation = payload.get("replacement_generation", prior.get("replacement_generation", 0))
        if generation < prior.get("replacement_generation", 0):
            raise FlowctlError("CODER_GENERATION_REGRESSION")
        state["coder_agent"] = {**prior, **payload}
        return commit_state(state_path, state, "CODER_STATE_UPDATED", {
            "active_task": state["coder_agent"].get("active_task"),
            "completed_tasks": state["coder_agent"].get("completed_tasks", []),
            "replacement_generation": generation,
        })
