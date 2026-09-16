import json
import hashlib
from pathlib import Path

from .artifacts import read_artifact as verify_artifact
from .errors import FlowctlError
from .state import commit_state, locked_state, reject_if_paused
from .snapshot import verify_recorded_snapshot
from .reviews import _unique_object, reject_if_unclassified_exhausted, has_passed_review, external_review_backends
from .integration_results import (
    validate_integration_results_against_plan,
    validate_production_replay_gap,
)


TRANSITIONS = {
    "flow-requirement": "flow-intent",
    "flow-intent": "flow-roadmap",
    "flow-roadmap": "flow-spec",
    "flow-spec": "flow-plan",
    "flow-plan": "flow-code",
    "flow-code": "flow-integration",
    "flow-integration": "complete",
}
REVIEWED_STAGES = {"flow-spec", "flow-plan", "flow-code"}


def _validate_handoff_gap(gap):
    if not isinstance(gap, dict):
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    if gap.get("type") == "PRODUCTION_REPLAY_GAP":
        replay_gap = dict(gap)
        artifact_key = replay_gap.pop("artifact_key", None)
        if artifact_key is not None and (not isinstance(artifact_key, str) or not artifact_key):
            raise FlowctlError("HANDOFF_SCHEMA_INVALID")
        validate_production_replay_gap(replay_gap)
        return
    if gap.get("type") == "EXTERNAL_REVIEW_GAP":
        if not isinstance(gap.get("artifact_key"), str) or not gap["artifact_key"]:
            raise FlowctlError("HANDOFF_SCHEMA_INVALID")
        return
    raise FlowctlError("HANDOFF_SCHEMA_INVALID")


def _read_handoff(path):
    try:
        data = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise FlowctlError("INVALID_HANDOFF_JSON") from exc
    if not isinstance(data, dict):
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    required = {
        "schema_version": int, "signal": str, "issue_id": str,
        "run_id": str, "from_stage": str, "next_stage": str, "artifact_key": str,
    }
    if set(required) - set(data):
        raise FlowctlError("HANDOFF_SCHEMA_INVALID", missing=sorted(set(required) - set(data)))
    if any(not isinstance(data[key], expected) for key, expected in required.items()):
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    if type(data["schema_version"]) is not int:
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    if data["schema_version"] != 1 or data["signal"] != "FLOW_RUN_HANDOFF":
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    if any(not data[key] for key in ("issue_id", "run_id", "artifact_key")):
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    if data["from_stage"] not in TRANSITIONS:
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    if data["next_stage"] not in {"auto", *TRANSITIONS.values()}:
        raise FlowctlError("HANDOFF_SCHEMA_INVALID")
    # Quality and gaps are derived from registered results, never from a
    # duplicate handoff declaration. Auxiliary fields do not authorize progress.
    return {key: data[key] for key in required}


def _attempt_evidence_current(attempt):
    path_value = attempt.get("report_path") or attempt.get("evidence_path")
    digest = attempt.get("report_digest") or attempt.get("evidence_digest")
    if not path_value or not digest:
        return False
    try:
        actual = "sha256:" + hashlib.sha256(Path(path_value).read_bytes()).hexdigest()
    except OSError:
        return False
    return actual == digest


def _attempt_boundary_current(attempt, artifact, snapshot_digest=None):
    if (not attempt.get("eligible", True)
            or attempt.get("artifact_digest") != artifact["digest"]
            or not _attempt_evidence_current(attempt)):
        return False
    if artifact["type"] == "code":
        return bool(snapshot_digest and attempt.get("snapshot_digest") == snapshot_digest)
    return True


def accept_handoff(state_path, handoff_path, expected_state_revision):
    handoff = _read_handoff(handoff_path)
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        if handoff["issue_id"] != state["issue_id"]:
            raise FlowctlError("ISSUE_MISMATCH")
        if handoff["run_id"] != state["run_id"]:
            raise FlowctlError("RUN_MISMATCH")
        if handoff["from_stage"] != state["current_stage"]:
            raise FlowctlError("STAGE_MISMATCH", current=state["current_stage"])
        requested_next = handoff["next_stage"]
        expected_next = TRANSITIONS.get(handoff["from_stage"])
        artifact = state["artifacts"].get(handoff["artifact_key"])
        if not artifact:
            raise FlowctlError("ARTIFACT_NOT_REGISTERED")
        if handoff["from_stage"] != f"flow-{artifact['type']}":
            raise FlowctlError("HANDOFF_ARTIFACT_STAGE_MISMATCH")
        current = verify_artifact(artifact["path"], expected_type=artifact["type"], expected_issue=state["issue_id"])
        if current["digest"] != artifact["digest"] or not current["approval"]["valid"]:
            raise FlowctlError("ARTIFACT_DRIFT")
        snapshot_digest = None
        if handoff["from_stage"] == "flow-code":
            snapshot_digest = verify_recorded_snapshot(state, handoff["artifact_key"])["snapshot_digest"]
        completion_quality = "COMPLETE"
        if handoff["from_stage"] in REVIEWED_STAGES:
            reject_if_unclassified_exhausted(state, handoff["artifact_key"], artifact["digest"])
            lanes = state.get("reviews", {}).get("lanes", {}).get(handoff["artifact_key"], {})
            if not has_passed_review(state, handoff['artifact_key'], 'gpt', artifact['digest']):
                raise FlowctlError("GPT_REVIEW_REQUIRED")
            for backend in ("cursor", "ibrain"):
                external = lanes.get(backend, {})
                attempt = state['reviews']['attempts'].get(external.get('attempt_id'), {})
                superseded = (backend == 'cursor' and state['reviews'].get('external_backend') == 'ibrain'
                    and external.get('status') == 'INCOMPLETE'
                    and attempt.get('classification') == 'REVIEW_RESULT'
                    and not any(f.get('blocking_status') == 'BLOCKING' for f in attempt.get('findings', []))
                    and has_passed_review(state, handoff['artifact_key'], 'ibrain', artifact['digest']))
                if superseded:
                    continue  # Retain the old receipt; the selected lane provides current assurance.
                if external.get("digest") == artifact["digest"] and external.get("status") in {"FAILED", "INCOMPLETE"}:
                    code = "CURSOR_REVIEW_FAILED" if backend == "cursor" else "IBRAIN_REVIEW_FAILED"
                    raise FlowctlError(code)
            if not has_passed_review(state, handoff['artifact_key'], 'consistency', artifact['digest']):
                raise FlowctlError("CONSISTENCY_REVIEW_REQUIRED")
            open_external = [
                attempt for attempt in state["reviews"]["attempts"].values()
                if attempt.get("artifact_key") == handoff["artifact_key"]
                and attempt.get("backend") in {"cursor", "ibrain", "consistency"}
                and attempt.get("status") == "STARTED"
                and attempt.get("eligible", True)
            ]
            if open_external:
                raise FlowctlError("EXTERNAL_REVIEW_IN_PROGRESS")
            external_pass = any(
                has_passed_review(state, handoff['artifact_key'], name, artifact['digest'])
                for name in external_review_backends(state)
            )
            if not external_pass:
                cursor_failures = [
                    item for item in state["reviews"]["attempts"].values()
                    if item.get("artifact_key") == handoff["artifact_key"]
                    and item.get("backend") == "cursor"
                    and item.get("classification") in {"RUN_ERROR", "PROTOCOL_ERROR"}
                    and item.get("artifact_digest") == artifact["digest"] and item.get("eligible", True)
                ]
                ibrain_failures = [
                    item for item in state["reviews"]["attempts"].values()
                    if item.get("artifact_key") == handoff["artifact_key"]
                    and item.get("backend") == "ibrain"
                    and item.get("classification") in {"RUN_ERROR", "PROTOCOL_ERROR"}
                    and item.get("artifact_digest") == artifact["digest"] and item.get("eligible", True)
                ]
                fallback_active = state['reviews']['lanes'].get(handoff['artifact_key'], {}).get('ibrain_activated')
                if (len(cursor_failures) < 2 and not fallback_active) or len(ibrain_failures) < 2:
                    raise FlowctlError("EXTERNAL_REVIEW_REQUIRED")
                completion_quality = "COMPLETE_WITH_DEFECT"
                state.setdefault("open_gaps", []).append({
                    "type": "EXTERNAL_REVIEW_GAP", "artifact_key": handoff["artifact_key"],
                    "attempt_ids": [item["attempt_id"] for item in cursor_failures + ibrain_failures],
                    'status': 'OPEN', 'owner': handoff['from_stage'],
                    'missing_assurance': 'External independent review unavailable.',
                    'remediation': 'Rerun external review when a backend becomes available.',
                })
        if handoff["from_stage"] == "flow-roadmap":
            ready = _ready_milestones(state)
            if not ready:
                raise FlowctlError("NO_DEPENDENCY_READY_MILESTONE")
            state["active_milestone"] = ready[0]
            expected_next = "flow-spec"
        elif handoff["from_stage"] == "flow-integration":
            milestone = artifact.get("milestone_id")
            if not milestone or milestone != state.get("active_milestone"):
                raise FlowctlError("MILESTONE_NOT_ACTIVE")
            integration_results = current.get("integration_results")
            from .integration_results import require_integration_results
            require_integration_results(current, state.get('artifacts', {}).get(f'plan:{milestone}'))
            durable_gaps = list(state.get("open_gaps", []))
            if integration_results:
                plan = state.get("artifacts", {}).get(f"plan:{milestone}")
                if not plan:
                    raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")
                validate_integration_results_against_plan(integration_results, plan)
                scenario_quality = integration_results["status"]
                if scenario_quality == "COMPLETE_WITH_DEFECT":
                    replay = state.get("authorizations", {}).get("production_replay", {})
                    if (replay.get("status") != "GRANTED"
                            or replay.get("decision") != "SKIP_PRODUCTION_REPLAY"
                            or replay.get("mode") != "SKIP_PRODUCTION_REPLAY"):
                        raise FlowctlError("UNAUTHORIZED_PRODUCTION_REPLAY_SKIP")
                for gap in integration_results["gaps"]:
                    durable_gap = {**gap, "artifact_key": handoff["artifact_key"]}
                    if durable_gap not in durable_gaps:
                        durable_gaps.append(durable_gap)
            else:
                scenario_quality = current["approval"]["status"]
            expected_quality = "COMPLETE_WITH_DEFECT" if durable_gaps else scenario_quality
            state["open_gaps"] = durable_gaps
            completion_quality = expected_quality
            state["milestones"][milestone]["status"] = "completed"
            ready = _ready_milestones(state)
            if ready:
                state["active_milestone"] = ready[0]
                expected_next = "flow-spec"
            elif any(item["status"] == "pending" for item in state["milestones"].values()):
                raise FlowctlError("MILESTONE_DEPENDENCY_DEADLOCK")
            else:
                state["active_milestone"] = None
                expected_next = "complete"
        if requested_next not in {expected_next, "auto"}:
            raise FlowctlError("ILLEGAL_TRANSITION", expected=expected_next, actual=requested_next)
        state["current_stage"] = expected_next
        state["pending_action"] = None if expected_next == "complete" else f"produce:{expected_next.removeprefix('flow-')}"
        state.pop("pending_signal", None)
        state = commit_state(state_path, state, "HANDOFF_ACCEPTED", handoff)
        return {
            "ok": True, "state_revision": state["state_revision"],
            "current_stage": state["current_stage"], "next_action": state["pending_action"],
            "active_milestone": state.get("active_milestone"),
            "completion_quality": completion_quality,
            "stage_summary": {
                "stage": handoff["from_stage"], "status": "已完成",
                "milestone_id": artifact.get("milestone_id"),
                "result": "有条件通过" if completion_quality == "COMPLETE_WITH_DEFECT" or state.get("open_gaps") else "通过",
                "explanation": "交接已接受；遗留问题见 open_gaps" if state.get("open_gaps") else "交接已接受",
            },
            "open_gaps": state.get("open_gaps", []),
        }


def _ready_milestones(state):
    result = []
    milestones = state.get("milestones", {})
    for milestone in state.get("target_milestones", []):
        record = milestones[milestone]
        if record["status"] != "pending":
            continue
        if all(milestones[item]["status"] == "completed" for item in record.get("dependencies", [])):
            result.append(milestone)
    return result
