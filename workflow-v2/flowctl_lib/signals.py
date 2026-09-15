import json
from pathlib import Path

from .errors import FlowctlError
from .state import ORDER, STAGE_BY_KIND, commit_state, locked_state


SIGNALS = {"FLOW_RUN_HUMAN_GATE", "FLOW_RUN_BLOCKED", "FLOW_RUN_ROUTE_BACK", "FLOW_RUN_RESUMED"}
COMMON = {"schema_version", "signal", "issue_id", "run_id", "stage", "cause", "evidence", "resume_condition"}
OPTIONAL = {"owner_stage", "next_stage", "gate"}


def _load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FlowctlError("INVALID_SIGNAL_JSON") from exc
    if (not isinstance(data, dict) or set(data) - (COMMON | OPTIONAL)
            or not COMMON.issubset(data) or data.get("schema_version") != 1
            or data.get("signal") not in SIGNALS):
        raise FlowctlError("SIGNAL_SCHEMA_INVALID")
    for key in COMMON - {"schema_version"}:
        if not isinstance(data[key], str) or not data[key]:
            raise FlowctlError("SIGNAL_SCHEMA_INVALID", field=key)
    return data


def _invalidate_from(state, stage):
    kind = stage.removeprefix("flow-")
    if kind not in ORDER:
        raise FlowctlError("INVALID_ROUTE_STAGE")
    start = ORDER.index(kind)
    milestone_local = kind in {"spec", "plan", "code", "integration"}
    milestone = state.get("active_milestone")
    removed = []
    tombstones = state.setdefault("invalidated_checkpoints", {})
    for key, artifact in list(state["artifacts"].items()):
        if ORDER.index(artifact["type"]) < start:
            continue
        if milestone_local and artifact["type"] in {"spec", "plan", "code", "integration"} and milestone and artifact.get("milestone_id") != milestone:
            continue
        removed.append(key)
        prior = tombstones.get(key)
        if not prior or artifact["revision"] >= prior["revision"]:
            tombstones[key] = {
                "revision": artifact["revision"], "digest": artifact["digest"],
                "invalidated_by": stage,
            }
        state["artifacts"].pop(key)
        state.get("snapshots", {}).pop(key, None)
    removed_set = set(removed)
    for attempt_id, attempt in state["reviews"]["attempts"].items():
        if attempt.get("artifact_key") in removed_set:
            attempt["eligible"] = False
            attempt["invalidated_by"] = stage
    state["open_gaps"] = [gap for gap in state.get("open_gaps", []) if gap.get("artifact_key") not in removed_set]
    if any(key.startswith("code:") for key in removed):
        state["coder_agent"] = {}
    if start <= ORDER.index("roadmap"):
        state["target_milestones"] = []
        state["milestones"] = {}
        state["active_milestone"] = None
    return removed


def record_signal(state_path, payload_path, expected_state_revision):
    payload = _load(payload_path)
    with locked_state(state_path, expected_state_revision) as state:
        if payload["issue_id"] != state["issue_id"]:
            raise FlowctlError("ISSUE_MISMATCH")
        if payload["run_id"] != state["run_id"]:
            raise FlowctlError("RUN_MISMATCH")
        if payload["stage"] != state["current_stage"]:
            raise FlowctlError("STAGE_MISMATCH", expected=state["current_stage"], actual=payload["stage"])
        paused = state.get("pending_signal", {}).get("signal")
        if paused in {"FLOW_RUN_HUMAN_GATE", "FLOW_RUN_BLOCKED"} and payload["signal"] != "FLOW_RUN_RESUMED":
            raise FlowctlError("FLOW_PAUSED", signal=paused)
        removed = []
        if payload["signal"] == "FLOW_RUN_RESUMED":
            if paused not in {"FLOW_RUN_HUMAN_GATE", "FLOW_RUN_BLOCKED"}:
                raise FlowctlError("FLOW_NOT_PAUSED")
            state.pop("pending_signal", None)
            state["pending_action"] = "resume"
        elif payload["signal"] == "FLOW_RUN_ROUTE_BACK":
            next_stage = payload.get("next_stage")
            if next_stage not in STAGE_BY_KIND.values():
                raise FlowctlError("SIGNAL_SCHEMA_INVALID", field="next_stage")
            current_kind = state["current_stage"].removeprefix("flow-")
            next_kind = next_stage.removeprefix("flow-")
            current_index = len(ORDER) if current_kind == "complete" else ORDER.index(current_kind)
            if ORDER.index(next_kind) >= current_index:
                raise FlowctlError("INVALID_ROUTE_STAGE")
            if payload.get("owner_stage") != next_stage:
                raise FlowctlError("ROUTE_OWNER_MISMATCH")
            if next_kind in {"spec", "plan", "code", "integration"} and not state.get("active_milestone"):
                raise FlowctlError("MILESTONE_NOT_ACTIVE")
            removed = _invalidate_from(state, next_stage)
            state["route_back_context"] = {
                "owner_stage": next_stage,
                "milestone_id": state.get("active_milestone"),
                "cause": payload["cause"],
                "evidence": payload["evidence"],
                "resume_condition": payload["resume_condition"],
            }
            state.setdefault("invalidations", []).append({
                "at_state_revision": expected_state_revision + 1,
                "cause": "route-back", "owner_stage": next_stage,
                "artifacts": removed,
            })
            state["current_stage"] = next_stage
            state["pending_action"] = f"revise:{next_kind}"
        elif payload["signal"] == "FLOW_RUN_HUMAN_GATE":
            if not payload.get("gate"):
                raise FlowctlError("SIGNAL_SCHEMA_INVALID", field="gate")
            state["pending_action"] = "human_gate"
        else:
            state["pending_action"] = "blocked"
        if payload["signal"] != "FLOW_RUN_RESUMED":
            state["pending_signal"] = payload
        state.setdefault("signal_history", []).append(payload)
        state = commit_state(state_path, state, "FLOW_SIGNAL_RECORDED", {
            "signal": payload["signal"], "stage": payload["stage"],
            "cause": payload["cause"], "invalidated_artifacts": removed,
        })
        return {"state_revision": state["state_revision"], "current_stage": state["current_stage"], "pending_action": state["pending_action"], "invalidated_artifacts": removed}
