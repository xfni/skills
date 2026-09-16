import re

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
    if (not isinstance(contract, dict) or set(contract) != {"schema_version", "scenarios"}
            or contract.get("schema_version") != 1 or not isinstance(contract.get("scenarios"), list)
            or not contract["scenarios"]):
        raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")
    seen = set()
    for scenario in contract["scenarios"]:
        if not isinstance(scenario, dict) or set(scenario) != {"scenario_id", "production_dependency"}:
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")
        scenario_id = scenario.get("scenario_id")
        if (not isinstance(scenario_id, str)
                or re.fullmatch(r"TESTCASE-[A-Za-z0-9][A-Za-z0-9._-]*", scenario_id) is None
                or scenario_id in seen):
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")
        seen.add(scenario_id)
        dependency = scenario.get("production_dependency")
        if not isinstance(dependency, dict) or type(dependency.get("required")) is not bool:
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS", scenario_id=scenario_id)
        expected = PLAN_TRACE_FIELDS if dependency["required"] else {"required"}
        if set(dependency) not in (expected, expected | {'replay_manifest_digest'}):
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS", scenario_id=scenario_id)
        if 'replay_manifest_digest' in dependency and (not dependency['required'] or not _valid_digest(dependency['replay_manifest_digest'])):
            raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS", scenario_id=scenario_id)
        if dependency["required"]:
            for field in PLAN_TRACE_FIELDS - {"required"}:
                if not isinstance(dependency[field], str) or not dependency[field].strip():
                    raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS", field=field)
    return contract


def require_integration_results(artifact, plan):
    if plan is None:
        raise FlowctlError('INTEGRATION_PLAN_BINDING_MISMATCH')
    result = artifact.get('integration_results')
    if result is None:
        if plan.get('integration_scenarios') is not None:
            raise FlowctlError('INTEGRATION_RESULTS_REQUIRED')
        return
    validate_integration_results_against_plan(result, plan)


def validate_production_replay_gap(gap):
    if not isinstance(gap, dict) or set(gap) != GAP_FIELDS:
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    if gap.get("type") != "PRODUCTION_REPLAY_GAP" or gap.get("status") != "OPEN":
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    scenario_ids = gap.get("scenario_ids")
    if (not isinstance(scenario_ids, list) or len(scenario_ids) != 1
            or not isinstance(scenario_ids[0], str) or not scenario_ids[0].strip()):
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    for field in ("missing_assurance", "reason", "owner", "remediation"):
        if not isinstance(gap.get(field), str) or not gap[field].strip():
            raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP", field=field)
    if (not _valid_digest(gap.get("plan_digest")) or type(gap.get("plan_revision")) is not int
            or gap["plan_revision"] < 1):
        raise FlowctlError("INVALID_PRODUCTION_REPLAY_GAP")
    return gap


def validate_integration_results(result):
    required = {
        "status", "executed_count", "skipped_count", "gaps", "warnings",
        "plan_digest", "plan_revision", "scenarios",
    }
    if not isinstance(result, dict) or set(result) != required:
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    if (result.get("status") not in AGGREGATE_STATUSES
            or not _valid_digest(result.get("plan_digest"))
            or type(result.get("plan_revision")) is not int or result["plan_revision"] < 1):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    if not isinstance(result.get("scenarios"), list) or not result["scenarios"]:
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    seen = set()
    statuses = []
    for scenario in result["scenarios"]:
        if not isinstance(scenario, dict) or set(scenario) != {"scenario_id", "status"}:
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
    if (type(result.get("executed_count")) is not int or result["executed_count"] != executed_count
            or type(result.get("skipped_count")) is not int
            or result["skipped_count"] != len(skipped_ids)):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    expected_warnings = ["ZERO_EXECUTED_SCENARIOS"] if skipped_ids and not executed_count else []
    if result.get("warnings") != expected_warnings:
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    if not isinstance(result.get("gaps"), list) or len(result["gaps"]) != len(skipped_ids):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    gap_ids = []
    for gap in result["gaps"]:
        validate_production_replay_gap(gap)
        if (gap["plan_digest"] != result["plan_digest"]
                or gap["plan_revision"] != result["plan_revision"]):
            raise FlowctlError("INVALID_INTEGRATION_RESULTS")
        gap_ids.extend(gap["scenario_ids"])
    if gap_ids != skipped_ids:
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")

    if "FAILED" in statuses:
        expected_status = "FAILED"
    elif "BLOCKED" in statuses:
        expected_status = "BLOCKED"
    elif skipped_ids:
        expected_status = "COMPLETE_WITH_DEFECT"
    else:
        expected_status = "PASSED"
    if result["status"] != expected_status:
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    if result["status"] == "PASSED" and (not executed_count or result["gaps"] or result["warnings"]):
        raise FlowctlError("INVALID_INTEGRATION_RESULTS")
    return result


def validate_production_replay_gaps_against_plan(gaps, plan_artifact):
    contract = validate_plan_integration_scenarios(plan_artifact.get("integration_scenarios"))
    planned = {item["scenario_id"]: item["production_dependency"] for item in contract["scenarios"]}
    seen = set()
    for gap in gaps:
        validate_production_replay_gap(gap)
        scenario_id = gap["scenario_ids"][0]
        trace = planned.get(scenario_id)
        if not trace or not trace["required"] or scenario_id in seen:
            raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")
        seen.add(scenario_id)
        expected = {
            "type": "PRODUCTION_REPLAY_GAP",
            "scenario_ids": [scenario_id],
            "missing_assurance": trace["missing_assurance"],
            "reason": trace["reason"],
            "owner": trace["owner"],
            "remediation": trace["remediation"],
            "status": "OPEN",
            "plan_digest": plan_artifact["digest"],
            "plan_revision": plan_artifact["revision"],
        }
        if gap != expected:
            raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")
    return gaps


def validate_integration_results_against_plan(result, plan_artifact):
    validate_integration_results(result)
    contract = validate_plan_integration_scenarios(plan_artifact.get("integration_scenarios"))
    if (result["plan_digest"] != plan_artifact.get("digest")
            or result["plan_revision"] != plan_artifact.get("revision")):
        raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")
    expected = contract["scenarios"]
    if [item["scenario_id"] for item in result["scenarios"]] != [item["scenario_id"] for item in expected]:
        raise FlowctlError("INTEGRATION_SCENARIO_SET_MISMATCH")
    by_id = {item["scenario_id"]: item for item in expected}
    for scenario in result["scenarios"]:
        if (scenario["status"] == "SKIPPED_AUTHORIZED_REPLAY"
                and not by_id[scenario["scenario_id"]]["production_dependency"]["required"]):
            raise FlowctlError("PRODUCTION_REPLAY_SKIP_NOT_IN_PLAN")
    validate_production_replay_gaps_against_plan(result["gaps"], plan_artifact)
    return result


def aggregate_integration_results(scenarios: list[dict], plan_artifact_path) -> dict:
    from .artifacts import verify_artifact

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
    if set(supplied) != set(planned_ids):
        raise FlowctlError(
            "INTEGRATION_SCENARIO_SET_MISMATCH",
            missing=sorted(set(planned_ids) - set(supplied)),
            unexpected=sorted(set(supplied) - set(planned_ids)),
        )

    normalized = []
    for planned in contract["scenarios"]:
        scenario = supplied[planned["scenario_id"]]
        if scenario["status"] == "SKIPPED_AUTHORIZED_REPLAY":
            if scenario.get("replay_mode") != "SKIP_PRODUCTION_REPLAY":
                raise FlowctlError("UNAUTHORIZED_PRODUCTION_REPLAY_SKIP", scenario_id=planned["scenario_id"])
            if not planned["production_dependency"]["required"]:
                raise FlowctlError("PRODUCTION_REPLAY_SKIP_NOT_IN_PLAN", scenario_id=planned["scenario_id"])
        normalized.append({"scenario_id": planned["scenario_id"], "status": scenario["status"]})

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
            "missing_assurance": trace["missing_assurance"],
            "reason": trace["reason"],
            "owner": trace["owner"],
            "remediation": trace["remediation"],
            "status": "OPEN",
            "plan_digest": plan["digest"],
            "plan_revision": plan["revision"],
        })
    return validate_integration_results_against_plan(result, plan)
