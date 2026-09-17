import json
import copy
from pathlib import Path
from .artifacts import KINDS, read_artifact as verify_artifact, is_reviewable_artifact
from .errors import FlowctlError
from .integration_results import validate_integration_results_against_plan
from .state import ORDER, artifact_key, commit_state, locked_state, validate_approval_authority, reconcile_requirement_route
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



def _integration_result_valid(artifact, artifacts, state=None):
    result = artifact.get("integration_results")
    milestone = artifact.get("milestone_id")
    plan = artifacts.get(f"plan:{milestone}") if milestone else None
    if not plan:
        if result is None:
            return False
        from .integration_results import validate_integration_results
        try:
            validate_integration_results(result)
        except FlowctlError:
            return False
        return True
    if result is None:
        return not plan.get('integration_contract_present') and plan.get('integration_scenarios') is None
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
    try:
        return verify_artifact(path)['type']
    except (FlowctlError, OSError):
        return None


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
    # Discovery establishes available inputs, not a complete historical proof.
    # Content/review receipts are checked at the actual stage handoff.
    return True


def resume_flow(issue_id, repo_root, inputs_path=None, controller=None):
    if controller is None:
        try:
            from .state import load_state
            controller = load_state(Path(repo_root) / '.ai' / 'issue' / issue_id / 'flow-state.json')
        except (FlowctlError, OSError, ValueError):
            controller = {}
    if (controller.get('issue_id') != issue_id
            or Path(controller.get('worktree_path', '')).resolve() != Path(repo_root).resolve()):
        controller = {}
    initial_discovery = (not controller.get('artifacts')
                         and not controller.get('invalidated_checkpoints')
                         and controller.get('current_stage', 'flow-requirement') == 'flow-requirement')
    candidates = (_candidate_map(issue_id, repo_root, inputs_path)
                  if inputs_path or not controller or initial_discovery else {})
    for key, recorded in controller.get('artifacts', {}).items():
        if inputs_path and (key in candidates or key.partition(':')[0] in candidates):
            continue  # An explicit replacement for this key remains authoritative.
        path = recorded.get('path')
        if isinstance(path, str) and path not in candidates.setdefault(key, []):
            candidates[key].append(path)
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
            if not is_reviewable_artifact(artifact) or not _deps_satisfied(artifact, valid):
                invalid.append({"path": artifact["path"], "code": "UNBOUND_ARTIFACT"})
                continue
            if artifact["type"] == "integration" and not _integration_result_valid(artifact, valid):
                invalid.append({"path": artifact["path"], "code": "INVALID_INTEGRATION_PLAN_BINDING"})
                continue
            current = valid.get(actual_key)
            if current and current["revision"] == artifact["revision"] and current["digest"] != artifact["digest"]:
                selected = controller.get('artifacts', {}).get(actual_key, {})
                if selected.get('path') == artifact['path'] and selected.get('digest') == artifact['digest']:
                    valid[actual_key] = artifact
                    continue
                if selected.get('path') == current['path'] and selected.get('digest') == current['digest']:
                    continue
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


def _restore_current_code_gpt_lane(state):
    """Rebuild a lost index from exact, revalidated receipts; no new review."""
    from .reviews import has_passed_review
    for key, artifact in state['artifacts'].items():
        if artifact['type'] != 'code' or not has_passed_review(state, key, 'gpt', artifact['digest']):
            continue
        attempts = [a for a in state['reviews']['attempts'].values()
                    if a.get('artifact_key') == key and a.get('backend') == 'gpt'
                    and a.get('artifact_digest') == artifact['digest']
                    and a.get('invalidated_by') in {None, 'resume', key}]
        if not attempts or any(a.get('status') == 'STARTED' for a in attempts):
            continue
        latest = max(attempts, key=lambda a: a.get('completed_state_revision', 0))
        candidate = {'status': latest.get('status'), 'digest': artifact['digest'],
                     'attempt_id': latest['attempt_id'], 'classification': latest.get('classification')}
        probe = {**state, 'reviews': {**state['reviews'], 'lanes': {
            key: {'gpt': candidate}}}}
        if has_passed_review(probe, key, 'gpt', artifact['digest']):
            state['reviews']['lanes'].setdefault(key, {})['gpt'] = candidate



def reconcile_resume(state_path, discovery, expected_state_revision, disposition_path=None):
    """Atomically make the verified discovery chain the controller checkpoint."""
    with locked_state(state_path, expected_state_revision) as state:
        original_state = copy.deepcopy(state)
        if discovery["issue_id"] != state["issue_id"]:
            raise FlowctlError("ISSUE_MISMATCH")
        if state.get('pending_signal', {}).get('signal') in {'FLOW_RUN_HUMAN_GATE', 'FLOW_RUN_BLOCKED'}:
            if disposition_path is not None:
                from .state import reject_if_paused
                reject_if_paused(state)
            return state
        # Resume refreshes available facts. It does not choose a new stage or
        # reinterpret missing historical files as withdrawal of accepted work.
        for key, artifact in discovery['valid_artifacts'].items():
            tombstone = state.get('invalidated_checkpoints', {}).get(key)
            if tombstone and tombstone['digest'] == artifact['digest']:
                continue  # Explicit withdrawal cannot be undone by discovery.
            if artifact['type'] == 'integration' and not _integration_result_valid(artifact, discovery['valid_artifacts'], state):
                continue
            recorded = state['artifacts'].get(key)
            validate_approval_authority(state, artifact)
            high_water = state.setdefault('artifact_high_water', {}).get(key)
            if high_water:
                artifact['revision'] = max(artifact['revision'], high_water['revision'] +
                    (artifact['digest'] != high_water['digest']))
            if artifact['type'] == 'integration':
                from .integration_results import validate_result_replacement
                validate_result_replacement(recorded, artifact)
            if recorded and recorded['digest'] != artifact['digest']:
                state.setdefault('artifact_history', []).append({'artifact_key': key, 'artifact': recorded})
            state['artifacts'][key] = artifact
            state['artifact_high_water'][key] = {
                'revision': artifact['revision'], 'digest': artifact['digest']}
        if reconcile_requirement_route(state, state['artifacts']) and state['current_stage'] == 'flow-requirement':
            state['pending_action'] = 'handoff:requirement'
        _restore_current_code_gpt_lane(state)
        from .dispositions import apply_disposition
        apply_disposition(state, artifact_key(state['current_stage'].removeprefix('flow-'),
                                            state.get('active_milestone')), disposition_path)
        if state.get('pending_signal', {}).get('signal') not in {'FLOW_RUN_HUMAN_GATE', 'FLOW_RUN_BLOCKED'}:
            kind = state['current_stage'].removeprefix('flow-')
            key = artifact_key(kind, state.get('active_milestone'))
            if state.get('route_back_context'):
                state['pending_action'] = 'revise:' + kind
            elif kind in {'spec', 'plan', 'code'} and key in state['artifacts']:
                from .reviews import next_review_action
                state['pending_action'] = next_review_action(state, key)
            elif kind == 'integration':
                code_key = artifact_key('code', state.get('active_milestone'))
                recorded = state.get('snapshots', {}).get(code_key)
                code = state['artifacts'].get(code_key)
                if recorded and code:
                    actual = capture_snapshot(state['worktree_path'], code['path'] if recorded.get('evidence_exclusion') else None)
                    if actual['snapshot_digest'] != recorded['snapshot_digest']:
                        state['pending_action'] = 'inspect:integration-snapshot'
        if state == original_state:
            return state
        return commit_state(state_path, state, 'CHECKPOINT_RECONCILED', {
            'artifact_keys': sorted(discovery['valid_artifacts']),
            'position_preserved': True,
            'invalid_candidates': discovery['invalid_candidates'],
        })
