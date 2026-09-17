import re
from pathlib import Path

from .errors import FlowctlError


SCENARIO_STATUSES = {"PASSED", "FAILED", "BLOCKED", "SKIPPED_AUTHORIZED_REPLAY"}
AGGREGATE_STATUSES = {"PASSED", "FAILED", "BLOCKED", "COMPLETE_WITH_DEFECT"}
GAP_FIELDS = {
    "type", "scenario_ids", "missing_assurance", "reason", "owner", "remediation", "status",
    "plan_digest", "plan_revision",
}
PLAN_TRACE_FIELDS = {"required", "reason", "missing_assurance", "owner", "remediation"}


def _valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def validate_plan_integration_scenarios(contract):
    if (not isinstance(contract, dict)
            or contract.get("schema_version") != 1 or not isinstance(contract.get("scenarios"), list)
            or not contract["scenarios"]):
        raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")
    seen = set()
    for scenario in contract["scenarios"]:
        if not isinstance(scenario, dict) or not {'scenario_id', 'production_dependency'}.issubset(scenario):
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")
        scenario_id = scenario.get("scenario_id")
        if (not isinstance(scenario_id, str)
                or not scenario_id.strip()
                or scenario_id in seen):
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")
        seen.add(scenario_id)
        dependency = scenario.get("production_dependency")
        if not isinstance(dependency, dict) or type(dependency.get("required")) is not bool:
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS", scenario_id=scenario_id)
    return contract


def require_integration_results(artifact, plan):
    result = artifact.get('integration_results')
    if result is None:
        raise FlowctlError('INTEGRATION_RESULTS_REQUIRED', action='repair',
                           missing=['terminal test result'], suggested_actions=['Record actual execution evidence; do not rebuild historical Plan'])
        return
    if plan is None:
        validate_integration_results(result)
    else:
        validate_integration_results_against_plan(result, plan)


def require_completion_evidence(artifact, worktree):
    """Check identity/readability, not whether execution proves coverage."""
    result = artifact.get('integration_results') or {}
    target = result.get('test_object') or artifact.get('upstream', {}).get('code', {}).get('digest')
    references = result.get('evidence')
    if not isinstance(target, str) or not target.strip():
        raise FlowctlError('INTEGRATION_TEST_OBJECT_REQUIRED', action='repair')
    if isinstance(references, str):
        references = [references]
    if not isinstance(references, list) or not references:
        raise FlowctlError('INTEGRATION_EXECUTION_EVIDENCE_REQUIRED', action='repair')
    for reference in references:
        try:
            if not isinstance(reference, str) or not reference.strip():
                raise ValueError('empty evidence')
            file = Path(reference)
            if not file.is_absolute():
                file = Path(worktree) / file
            file.read_bytes()
        except (OSError, ValueError, TypeError) as exc:
            raise FlowctlError('INTEGRATION_EXECUTION_EVIDENCE_REQUIRED', action='repair') from exc


def validate_result_replacement(previous, current):
    """A partial passing rerun cannot silently discard other known failures."""
    old = previous.get('integration_results') if previous else None
    new = current.get('integration_results')
    if not old or not new:
        return
    unresolved = {item['scenario_id'] for item in old['scenarios']
                  if item['status'] in {'FAILED', 'BLOCKED'}}
    unresolved.update(old.get('_unresolved_observations', []))
    resolved = {item['scenario_id'] for item in new['scenarios'] if item['status'] == 'PASSED'}
    if new.get('status') not in {'PASSED', 'COMPLETE_WITH_DEFECT'}:
        # Derived controller facts survive partial failure/startup reports;
        # incoming caller metadata cannot erase prior observations.
        new['_unresolved_observations'] = sorted(unresolved - resolved)
        return
    if not unresolved and old.get('status') not in {'FAILED', 'BLOCKED'}:
        return
    old_object = old.get('test_object') or previous.get('upstream', {}).get('code', {}).get('digest')
    new_object = new.get('test_object') or current.get('upstream', {}).get('code', {}).get('digest')
    if not old_object or not new_object or new.get('replaces') != previous['digest']:
        raise FlowctlError('INTEGRATION_REPLACEMENT_REFERENCE_REQUIRED', action='repair')
    if old_object != new_object and new.get('replaces_test_object') != old_object:
        raise FlowctlError('INTEGRATION_REPLACEMENT_OBJECT_MISMATCH', action='repair')
    if not unresolved and not new.get('resolution'):
        raise FlowctlError('INTEGRATION_UNRESOLVED_OBSERVATIONS', missing=['aggregate failure resolution'])
    if unresolved - resolved:
        raise FlowctlError('INTEGRATION_UNRESOLVED_OBSERVATIONS', missing=sorted(unresolved - resolved))
    new['_unresolved_observations'] = []


def validate_production_replay_gap(gap):
    if not isinstance(gap, dict):
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    if gap.get("type") != "PRODUCTION_REPLAY_GAP" or gap.get("status") != "OPEN":
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    scenario_ids = gap.get("scenario_ids")
    if (not isinstance(scenario_ids, list) or len(scenario_ids) != 1
            or not isinstance(scenario_ids[0], str) or not scenario_ids[0].strip()):
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    return gap


def validate_integration_results(result):
    if not isinstance(result, dict) or not {'status', 'scenarios'}.issubset(result):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    result.setdefault('gaps', [])
    result.setdefault('warnings', [])
    if (result.get("status") not in AGGREGATE_STATUSES
            or (result.get('plan_digest') is not None and not _valid_digest(result['plan_digest']))
            or (result.get('plan_revision') is not None and
                (type(result['plan_revision']) is not int or result['plan_revision'] < 1))):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    if not isinstance(result.get("scenarios"), list) or not result["scenarios"]:
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    seen = set()
    statuses = []
    for scenario in result["scenarios"]:
        if not isinstance(scenario, dict) or not {'scenario_id', 'status'}.issubset(scenario):
            raise FlowctlError("INVALID_INTEGRATION_RESULTS")
        scenario_id, status = scenario.get("scenario_id"), scenario.get("status")
        if (not isinstance(scenario_id, str) or not scenario_id.strip()
                or scenario_id in seen or status not in SCENARIO_STATUSES):
            raise FlowctlError("INVALID_INTEGRATION_RESULTS")
        seen.add(scenario_id)
        statuses.append(status)

    skipped_ids = [
        scenario["scenario_id"] for scenario in result["scenarios"]
        if scenario["status"] == "SKIPPED_AUTHORIZED_REPLAY"
    ]
    executed_count = len(statuses) - len(skipped_ids)
    result['executed_count'] = executed_count
    result['skipped_count'] = len(skipped_ids)
    expected_warnings = ["ZERO_EXECUTED_SCENARIOS"] if skipped_ids and not executed_count else []
    result['warnings'] = expected_warnings
    if not isinstance(result.get("gaps"), list) or len(result["gaps"]) != len(skipped_ids):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    gap_ids = []
    for gap in result["gaps"]:
        validate_production_replay_gap(gap)
        gap.setdefault('plan_digest', result.get('plan_digest'))
        gap.setdefault('plan_revision', result.get('plan_revision'))
        if (gap['plan_digest'] != result.get('plan_digest')
                or gap['plan_revision'] != result.get('plan_revision')):
            raise FlowctlError("INVALID_INTEGRATION_RESULTS")
        gap_ids.extend(gap["scenario_ids"])
    if set(gap_ids) != set(skipped_ids) or len(gap_ids) != len(skipped_ids):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")

    if "FAILED" in statuses:
        expected_status = "FAILED"
    elif "BLOCKED" in statuses:
        expected_status = "BLOCKED"
    elif skipped_ids:
        expected_status = "COMPLETE_WITH_DEFECT"
    else:
        expected_status = "PASSED"
    # A known aggregate obstacle cannot disappear merely because a partial
    # list contains only passing observations.
    if result['status'] == 'FAILED':
        expected_status = 'FAILED'
    elif result['status'] == 'BLOCKED' and expected_status != 'FAILED':
        expected_status = 'BLOCKED'
    result['status'] = expected_status
    if result["status"] == "PASSED" and (not executed_count or result["gaps"] or result["warnings"]):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    return result


def validate_production_replay_gaps_against_plan(gaps, plan_artifact):
    contract = plan_artifact.get('integration_scenarios')
    try:
        validate_plan_integration_scenarios(contract)
    except FlowctlError:
        return gaps
    planned = {item["scenario_id"]: item["production_dependency"] for item in contract["scenarios"]}
    seen = set()
    for gap in gaps:
        validate_production_replay_gap(gap)
        scenario_id = gap["scenario_ids"][0]
        trace = planned.get(scenario_id)
        if not trace or not trace["required"] or scenario_id in seen:
            raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")
        seen.add(scenario_id)
        for field in PLAN_TRACE_FIELDS - {'required'}:
            gap.setdefault(field, trace.get(field, 'NOT_SUPPLIED'))
        # Explanatory text may evolve; scope and active skip permission remain
        # checked independently. Do not require verbatim Plan prose.
    return gaps


def validate_integration_results_against_plan(result, plan_artifact):
    result.setdefault('plan_digest', plan_artifact.get('digest'))
    result.setdefault('plan_revision', plan_artifact.get('revision'))
    for gap in result.get('gaps', []):
        if isinstance(gap, dict):
            if gap.get('plan_digest') is None:
                gap['plan_digest'] = result['plan_digest']
            if gap.get('plan_revision') is None:
                gap['plan_revision'] = result['plan_revision']
    validate_integration_results(result)
    contract = plan_artifact.get('integration_scenarios')
    try:
        validate_plan_integration_scenarios(contract)
    except FlowctlError:
        result.setdefault('warnings', []).append('PLAN_COVERAGE_CALLER_ATTESTED')
        return result
    if (result["plan_digest"] != plan_artifact.get("digest")
            or result["plan_revision"] != plan_artifact.get("revision")):
        raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")
    expected = contract["scenarios"]
    if not {item['scenario_id'] for item in expected}.issubset(
            {item['scenario_id'] for item in result['scenarios']}):
        result.setdefault('warnings', []).append('PLAN_COVERAGE_CALLER_ATTESTED')
    by_id = {item["scenario_id"]: item for item in expected}
    for scenario in result["scenarios"]:
        if (scenario["status"] == "SKIPPED_AUTHORIZED_REPLAY"
                and not by_id.get(scenario['scenario_id'], {}).get('production_dependency', {}).get('required')):
            raise FlowctlError("PRODUCTION_REPLAY_SKIP_NOT_IN_PLAN")
    validate_production_replay_gaps_against_plan(result["gaps"], plan_artifact)
    return result


def aggregate_integration_results(scenarios: list[dict], plan_artifact_path) -> dict:
    from .artifacts import read_artifact as verify_artifact

    plan = verify_artifact(plan_artifact_path, expected_type="plan")
    if not plan["approval"]["valid"]:
        raise FlowctlError("PLAN_APPROVAL_REQUIRED")
    if plan.get("integration_scenarios") is None:
        raise FlowctlError("PLAN_INTEGRATION_SCENARIOS_REQUIRED")
    contract = validate_plan_integration_scenarios(plan.get("integration_scenarios"))
    if not isinstance(scenarios, list) or not scenarios:
        raise FlowctlError("INTEGRATION_SCENARIOS_REQUIRED")
    supplied = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise FlowctlError("INVALID_INTEGRATION_SCENARIO")
        scenario_id, status = scenario.get("scenario_id"), scenario.get("status")
        if (not isinstance(scenario_id, str) or not scenario_id.strip()
                or scenario_id in supplied or status not in SCENARIO_STATUSES):
            raise FlowctlError("INVALID_INTEGRATION_SCENARIO", scenario_id=scenario_id)
        supplied[scenario_id] = scenario
    planned_ids = [item["scenario_id"] for item in contract["scenarios"]]
    if not set(planned_ids).issubset(supplied):
        raise FlowctlError(
            "INTEGRATION_SCENARIO_SET_MISMATCH",
            missing=sorted(set(planned_ids) - set(supplied)),
            unexpected=sorted(set(supplied) - set(planned_ids)),
        )

    normalized = []
    by_id = {item['scenario_id']: item for item in contract['scenarios']}
    for scenario_id in planned_ids + [item for item in supplied if item not in by_id]:
        scenario = supplied[scenario_id]
        if scenario["status"] == "SKIPPED_AUTHORIZED_REPLAY":
            if scenario.get("replay_mode") != "SKIP_PRODUCTION_REPLAY":
                raise FlowctlError('UNAUTHORIZED_PRODUCTION_REPLAY_SKIP', scenario_id=scenario_id)
            if not by_id.get(scenario_id, {}).get('production_dependency', {}).get('required'):
                raise FlowctlError('PRODUCTION_REPLAY_SKIP_NOT_IN_PLAN', scenario_id=scenario_id)
        normalized.append({'scenario_id': scenario_id, 'status': scenario['status']})

    statuses = [item["status"] for item in normalized]
    skipped_count = statuses.count("SKIPPED_AUTHORIZED_REPLAY")
    executed_count = len(statuses) - skipped_count
    if "FAILED" in statuses:
        aggregate_status = "FAILED"
    elif "BLOCKED" in statuses:
        aggregate_status = "BLOCKED"
    elif skipped_count:
        aggregate_status = "COMPLETE_WITH_DEFECT"
    else:
        aggregate_status = "PASSED"
    result = {
        "status": aggregate_status,
        "executed_count": executed_count,
        "skipped_count": skipped_count,
        "gaps": [],
        "warnings": ["ZERO_EXECUTED_SCENARIOS"] if skipped_count and not executed_count else [],
        "plan_digest": plan["digest"],
        "plan_revision": plan["revision"],
        "scenarios": normalized,
    }
    by_id = {item["scenario_id"]: item for item in contract["scenarios"]}
    for scenario in normalized:
        if scenario["status"] != "SKIPPED_AUTHORIZED_REPLAY":
            continue
        trace = by_id[scenario["scenario_id"]]["production_dependency"]
        result["gaps"].append({
            "type": "PRODUCTION_REPLAY_GAP",
            "scenario_ids": [scenario["scenario_id"]],
            "missing_assurance": trace.get('missing_assurance', 'NOT_SUPPLIED'),
            "reason": trace.get('reason', 'NOT_SUPPLIED'),
            "owner": trace.get('owner', 'NOT_SUPPLIED'),
            "remediation": trace.get('remediation', 'NOT_SUPPLIED'),
            "status": "OPEN",
            "plan_digest": plan["digest"],
            "plan_revision": plan["revision"],
        })
    return validate_integration_results_against_plan(result, plan)
