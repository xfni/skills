import json
import copy
from pathlib import Path

from .artifacts import KINDS, verify_artifact
from .errors import FlowctlError
from .integration_results import validate_integration_results_against_plan
from .state import DEPENDENCIES, ORDER, artifact_key, commit_state, locked_state, validate_approval_authority
from .snapshot import capture_snapshot


def _review_eligible_after_resume(attempt, artifact, recorded_snapshot=None, actual_snapshot=None):
    if not artifact or artifact["digest"] != attempt.get("artifact_digest"):
        return False
    if artifact["type"] != "code":
        return True
    return bool(
        recorded_snapshot and actual_snapshot and attempt.get("snapshot_digest")
        and recorded_snapshot.get("snapshot_digest") == actual_snapshot.get("snapshot_digest")
        and attempt.get("snapshot_digest") == recorded_snapshot.get("snapshot_digest")
    )


def _production_replay_gaps(artifacts):
    gaps = []
    for key, artifact in artifacts.items():
        if artifact.get("type") != "integration" or not artifact.get("integration_results"):
            continue
        for gap in artifact["integration_results"]["gaps"]:
            gaps.append({**gap, "artifact_key": key})
    return gaps


def _integration_result_valid(artifact, artifacts, state=None):
    result = artifact.get("integration_results")
    milestone = artifact.get("milestone_id")
    plan = artifacts.get(f"plan:{milestone}") if milestone else None
    if not plan:
        return False
    if result is None:
        return plan.get('integration_scenarios') is None
    try:
        validate_integration_results_against_plan(result, plan)
    except FlowctlError:
        return False
    if result["skipped_count"] or result["gaps"]:
        if state is None:
            return True
        replay = state.get("authorizations", {}).get("production_replay", {})
        return (
            replay.get("status") == "GRANTED"
            and replay.get("decision") == "SKIP_PRODUCTION_REPLAY"
            and replay.get("mode") == "SKIP_PRODUCTION_REPLAY"
        )
    return True


def _infer_key(path):
    prefix = path.name.split("_", 1)[0]
    return prefix if prefix in KINDS else None


def _candidate_map(issue_id, repo_root, inputs_path):
    if inputs_path:
        try:
            raw = json.loads(Path(inputs_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FlowctlError("INVALID_INPUT_MAP") from exc
        if not isinstance(raw, dict):
            raise FlowctlError("INVALID_INPUT_MAP")
        result = {}
        for key, value in raw.items():
            kind, separator, milestone = key.partition(":")
            if kind not in KINDS or (separator and (kind not in {"spec", "plan", "code", "integration"} or not milestone)):
                raise FlowctlError("INVALID_INPUT_KEY", key=key)
            values = [value] if isinstance(value, str) else value
            if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
                raise FlowctlError("INVALID_INPUT_PATHS", key=key)
            result[key] = values
        return result
    issue_dir = Path(repo_root) / ".ai" / "issue" / issue_id
    result = {}
    if issue_dir.is_dir():
        for path in sorted(issue_dir.glob("*.md")):
            inferred = _infer_key(path)
            if inferred:
                result.setdefault(inferred, []).append(str(path))
    return result


def _deps_satisfied(artifact, valid):
    for dependency in DEPENDENCIES[artifact["type"]]:
        key = artifact_key(dependency, artifact.get("milestone_id"))
        registered = valid.get(key)
        claimed = artifact["upstream"].get(dependency)
        if not registered or not claimed:
            return False
        if registered["digest"] != claimed["digest"] or registered["revision"] != claimed["revision"]:
            return False
    return True


def resume_flow(issue_id, repo_root, inputs_path=None):
    candidates = _candidate_map(issue_id, repo_root, inputs_path)
    parsed = []
    invalid = []
    for supplied_key, paths in candidates.items():
        expected_type, _, expected_milestone = supplied_key.partition(":")
        for candidate in paths:
            try:
                artifact = verify_artifact(
                    candidate, expected_type=expected_type, expected_issue=issue_id,
                    expected_milestone=expected_milestone or None,
                )
                parsed.append((supplied_key, artifact))
            except (FlowctlError, OSError) as exc:
                invalid.append({"path": str(candidate), "code": getattr(exc, "code", "ARTIFACT_UNAVAILABLE")})

    valid = {}
    for kind in ORDER:
        kind_candidates = [(key, item) for key, item in parsed if item["type"] == kind]
        for key, artifact in sorted(kind_candidates, key=lambda pair: pair[1]["revision"]):
            actual_key = artifact_key(kind, artifact.get("milestone_id"))
            if not artifact["approval"]["valid"] or not _deps_satisfied(artifact, valid):
                invalid.append({"path": artifact["path"], "code": "UNBOUND_ARTIFACT"})
                continue
            if artifact["type"] == "integration" and not _integration_result_valid(artifact, valid):
                invalid.append({"path": artifact["path"], "code": "INVALID_INTEGRATION_PLAN_BINDING"})
                continue
            current = valid.get(actual_key)
            if current and current["revision"] == artifact["revision"] and current["digest"] != artifact["digest"]:
                raise FlowctlError("AMBIGUOUS_CHECKPOINT", artifact_key=actual_key, revision=artifact["revision"])
            if not current or artifact["revision"] > current["revision"]:
                valid[actual_key] = artifact

    deepest = None
    for artifact in valid.values():
        if deepest is None or ORDER.index(artifact["type"]) > ORDER.index(deepest["type"]):
            deepest = artifact
    if deepest is None:
        deepest_stage = None
        next_stage = "flow-requirement"
    else:
        deepest_stage = f"flow-{deepest['type']}"
        index = ORDER.index(deepest["type"])
        next_stage = f"flow-{ORDER[index + 1]}" if index + 1 < len(ORDER) else None
    return {
        "ok": True,
        "issue_id": issue_id,
        "deepest_valid_stage": deepest_stage,
        "deepest_valid_artifact": deepest,
        "next_stage": next_stage,
        "valid_artifacts": valid,
        "invalid_candidates": invalid,
    }


def reconcile_resume(state_path, discovery, expected_state_revision):
    """Atomically make the verified discovery chain the controller checkpoint."""
    with locked_state(state_path, expected_state_revision) as state:
        from .replay import reject_unresolved_cleanup
        reject_unresolved_cleanup(state)
        original_state = copy.deepcopy(state)
        if discovery["issue_id"] != state["issue_id"]:
            raise FlowctlError("ISSUE_MISMATCH")
        route_context = state.get("route_back_context")
        pending_route_back = bool(route_context)
        if state.get("pending_signal", {}).get("signal") in {"FLOW_RUN_HUMAN_GATE", "FLOW_RUN_BLOCKED"}:
            return state
        route_owner_stage = route_context.get("owner_stage") if pending_route_back else None
        route_milestone = route_context.get("milestone_id") if pending_route_back else None
        artifacts = dict(discovery["valid_artifacts"])
        tombstones = state.get("invalidated_checkpoints", {})
        high_water_marks = dict(state.get("artifact_high_water", {}))
        for key, current in state.get("artifacts", {}).items():
            prior = high_water_marks.get(key)
            if not prior or current["revision"] > prior["revision"]:
                high_water_marks[key] = {"revision": current["revision"], "digest": current["digest"]}
        for kind in ORDER:
            for key, artifact in list(artifacts.items()):
                if artifact["type"] != kind:
                    continue
                high_water = high_water_marks.get(key)
                if high_water and artifact["revision"] < high_water["revision"]:
                    raise FlowctlError(
                        "CHECKPOINT_REVISION_ROLLBACK", artifact_key=key,
                        highest_revision=high_water["revision"], candidate_revision=artifact["revision"],
                    )
                if (high_water and artifact["revision"] == high_water["revision"]
                        and artifact["digest"] != high_water["digest"]):
                    raise FlowctlError("CHECKPOINT_HISTORY_CONFLICT", artifact_key=key)
                tombstone = tombstones.get(key)
                if tombstone and artifact["revision"] <= tombstone["revision"]:
                    artifacts.pop(key)
                    continue
                if not _deps_satisfied(artifact, artifacts):
                    artifacts.pop(key)
                    continue
                if artifact["type"] == "integration" and not _integration_result_valid(
                    artifact, artifacts, state,
                ):
                    artifacts.pop(key)
        for artifact in artifacts.values():
            validate_approval_authority({**state, "artifacts": artifacts}, artifact)
        keep_reviews = {}
        actual_snapshot = None
        for attempt_id, attempt in state["reviews"]["attempts"].items():
            artifact = artifacts.get(attempt.get("artifact_key"))
            recorded = state.get("snapshots", {}).get(attempt.get("artifact_key"))
            if artifact and artifact["type"] == "code" and recorded:
                if recorded and actual_snapshot is None:
                    actual_snapshot = capture_snapshot(state["worktree_path"])
            eligible = _review_eligible_after_resume(attempt, artifact, recorded, actual_snapshot)
            attempt["eligible"] = eligible
            if not attempt["eligible"]:
                attempt["invalidated_by"] = "resume"
            keep_reviews[attempt_id] = attempt
        state["artifacts"] = artifacts
        state["artifact_high_water"] = high_water_marks
        state["reviews"]["attempts"] = keep_reviews
        state["open_gaps"] = [
            gap for gap in state.get("open_gaps", [])
            if gap.get("type") != "PRODUCTION_REPLAY_GAP" or not gap.get("artifact_key")
        ] + _production_replay_gaps(artifacts)
        if not pending_route_back:
            state.pop("pending_signal", None)
        roadmap = artifacts.get("roadmap")
        if roadmap and roadmap.get("target_milestones"):
            state["target_milestones"] = roadmap["target_milestones"]
            state["milestones"] = {
                item: {"status": "pending", "dependencies": roadmap["milestone_dependencies"].get(item, [])}
                for item in roadmap["target_milestones"]
            }
            for key, item in artifacts.items():
                if item["type"] == "integration" and item.get("milestone_id") in state["milestones"]:
                    state["milestones"][item["milestone_id"]]["status"] = "completed"
        else:
            state["target_milestones"] = []
            state["milestones"] = {}
        state["active_milestone"] = None
        if state["milestones"]:
            ready = [
                item for item in state["target_milestones"]
                if state["milestones"][item]["status"] == "pending"
                and all(state["milestones"][dependency]["status"] == "completed"
                        for dependency in state["milestones"][item]["dependencies"])
            ]
            if ready:
                milestone = ready[0]
                state["active_milestone"] = milestone
                deepest = next(
                    (artifacts.get(f"{kind}:{milestone}") for kind in ("code", "plan", "spec")
                     if artifacts.get(f"{kind}:{milestone}")),
                    None,
                )
                if deepest is None:
                    state["current_stage"] = "flow-spec"
                    state["pending_action"] = "produce:spec"
                else:
                    key = artifact_key(deepest["type"], milestone)
                    state["current_stage"] = f"flow-{deepest['type']}"
                    passed_gpt = any(
                        item.get("artifact_key") == key and item.get("backend") == "gpt"
                        and item.get("status") == "PASSED" and item.get("classification") == "REVIEW_RESULT"
                        and item.get("eligible", True) for item in keep_reviews.values()
                    )
                    passed_cursor = any(
                        item.get("artifact_key") == key and item.get("backend") == "cursor"
                        and item.get("status") == "PASSED" and item.get("classification") == "REVIEW_RESULT"
                        and item.get("eligible", True) for item in keep_reviews.values()
                    )
                    state["pending_action"] = "review:gpt" if not passed_gpt else ("review:cursor" if not passed_cursor else f"handoff:{deepest['type']}")
            elif all(item["status"] == "completed" for item in state["milestones"].values()):
                state["current_stage"] = "complete"
                state["pending_action"] = None
            else:
                raise FlowctlError("MILESTONE_DEPENDENCY_DEADLOCK")
        else:
            deepest = None
            for artifact in artifacts.values():
                if deepest is None or ORDER.index(artifact["type"]) > ORDER.index(deepest["type"]):
                    deepest = artifact
            if deepest is None:
                state["current_stage"] = "flow-requirement"
                state["pending_action"] = "produce:requirement"
            else:
                state["current_stage"] = f"flow-{deepest['type']}"
                state["pending_action"] = f"handoff:{deepest['type']}"
        if pending_route_back:
            state["current_stage"] = route_owner_stage
            state["pending_action"] = f"revise:{route_owner_stage.removeprefix('flow-')}"
            if route_owner_stage.removeprefix("flow-") in {"spec", "plan", "code", "integration"}:
                if not route_milestone:
                    raise FlowctlError("MILESTONE_NOT_ACTIVE")
                state["active_milestone"] = route_milestone
        if state == original_state:
            return state
        return commit_state(state_path, state, "CHECKPOINT_RECONCILED", {
            "artifact_keys": sorted(artifacts),
            "deepest_valid_stage": discovery["deepest_valid_stage"],
            "invalid_candidate_count": len(discovery["invalid_candidates"]),
        })
