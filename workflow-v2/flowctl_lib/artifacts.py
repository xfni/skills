import hashlib
import json
from pathlib import Path
import re

from .errors import FlowctlError
from .integration_results import validate_integration_results, validate_plan_integration_scenarios


BODY_BEGIN = "--- FLOW BODY BEGIN ---"
BODY_END = "--- FLOW BODY END ---"
INTEGRITY_BEGIN = "--- FLOW INTEGRITY BEGIN ---"
INTEGRITY_END = "--- FLOW INTEGRITY END ---"
APPROVAL_BEGIN = "--- FLOW APPROVAL BEGIN ---"
APPROVAL_END = "--- FLOW APPROVAL END ---"
MARKERS = (BODY_BEGIN, BODY_END, INTEGRITY_BEGIN, INTEGRITY_END, APPROVAL_BEGIN, APPROVAL_END)
KINDS = ("requirement", "intent", "roadmap", "spec", "plan", "code", "integration")
APPROVED_STATUSES = {
    "APPROVED", "APPROVED_WITH_DEFECT", "CONFIRMED", "READY_FOR_INTENT",
    "COMPLETE", "COMPLETE_WITH_DEFECT", "PASSED",
}
APPROVAL_BY_KIND = {
    "requirement": {"APPROVED", "READY_FOR_INTENT"},
    "intent": {"APPROVED", "CONFIRMED"},
    "roadmap": {"APPROVED", "APPROVED_WITH_DEFECT"},
    "spec": {"APPROVED", "APPROVED_WITH_DEFECT"},
    "plan": {"APPROVED", "APPROVED_WITH_DEFECT"},
    "code": {"APPROVED", "COMPLETE", "COMPLETE_WITH_DEFECT"},
    "integration": {"PASSED", "COMPLETE_WITH_DEFECT"},
}


def _fields(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z0-9_.-]*):\s*(.*?)\s*$", line)
        if match:
            key = match.group(1).lower().replace("-", "_")
            value = match.group(2).strip().strip("`").strip()
            result.setdefault(key, []).append(value)
    return result


def _one(fields, key, required=False):
    values = fields.get(key, [])
    if required and len(values) != 1:
        raise FlowctlError("INVALID_FIELD_COUNT", f"{key} must occur exactly once", field=key, count=len(values))
    if len(values) > 1:
        raise FlowctlError("INVALID_FIELD_COUNT", f"{key} must occur at most once", field=key, count=len(values))
    return values[0] if values else None


def _split_regions(text):
    for marker in MARKERS:
        if text.count(marker) != 1:
            raise FlowctlError("INVALID_ARTIFACT_REGIONS", f"{marker} must occur exactly once")
    try:
        before, rest = text.split(BODY_BEGIN + "\n", 1)
        body, rest = rest.split(BODY_END + "\n", 1)
        between, rest = rest.split(INTEGRITY_BEGIN + "\n", 1)
        integrity, rest = rest.split(INTEGRITY_END + "\n", 1)
        between_approval, rest = rest.split(APPROVAL_BEGIN + "\n", 1)
        approval, after = rest.split(APPROVAL_END, 1)
    except ValueError as exc:
        raise FlowctlError("INVALID_ARTIFACT_REGIONS", "regions are missing, malformed, or out of order") from exc
    if before.strip() or between.strip() or between_approval.strip() or after.strip():
        raise FlowctlError("INVALID_ARTIFACT_REGIONS", "unexpected bytes outside or between regions")
    if not body.endswith("\n") or body.endswith("\n\n"):
        raise FlowctlError("NON_CANONICAL_BODY_END", "body must end in exactly one LF")
    return body, integrity, approval


def verify_artifact(path, expected_type=None, expected_issue=None, expected_milestone=None):
    path = Path(path).expanduser().resolve(strict=True)
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FlowctlError("UTF8_BOM_FORBIDDEN")
    if b"\r" in raw:
        raise FlowctlError("NON_CANONICAL_LINE_ENDINGS", "only LF line endings are accepted")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FlowctlError("INVALID_UTF8") from exc
    body, integrity_text, approval_text = _split_regions(text)
    body_fields = _fields(body)
    integrity_fields = _fields(integrity_text)
    approval_fields = _fields(approval_text)

    revision_text = _one(body_fields, "content_revision", required=True)
    try:
        revision = int(revision_text)
    except ValueError as exc:
        raise FlowctlError("INVALID_CONTENT_REVISION") from exc
    if revision < 1:
        raise FlowctlError("INVALID_CONTENT_REVISION")

    digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    declared_digest = _one(integrity_fields, "content_digest", required=True)
    if declared_digest != digest:
        raise FlowctlError("DIGEST_MISMATCH", expected=declared_digest, actual=digest)

    artifact_type = _one(body_fields, "artifact_type") or _one(body_fields, "flow_step") or expected_type
    if artifact_type not in KINDS:
        raise FlowctlError("INVALID_ARTIFACT_TYPE", artifact_type=artifact_type)
    if expected_type and artifact_type != expected_type:
        raise FlowctlError("ARTIFACT_TYPE_MISMATCH", expected=expected_type, actual=artifact_type)
    issue_id = _one(body_fields, "issue_id")
    if expected_issue and issue_id != expected_issue:
        raise FlowctlError("ISSUE_MISMATCH", expected=expected_issue, actual=issue_id)
    milestone = _one(body_fields, "milestone_id")
    if expected_milestone and milestone != expected_milestone:
        raise FlowctlError("MILESTONE_MISMATCH", expected=expected_milestone, actual=milestone)

    approved_revision_text = _one(approval_fields, "approved_revision")
    try:
        approved_revision = int(approved_revision_text) if approved_revision_text is not None else None
    except ValueError:
        approved_revision = None
    approved_digest = _one(approval_fields, "approved_digest")
    approval_status = _one(approval_fields, "status")
    approval_valid = approved_revision == revision and approved_digest == digest and approval_status in APPROVED_STATUSES
    if approval_status not in APPROVAL_BY_KIND[artifact_type]:
        approval_valid = False

    integration_scenarios = None
    integration_scenarios_text = _one(body_fields, "integration_scenarios")
    if artifact_type == "plan":
        if integration_scenarios_text is not None:
            try:
                integration_scenarios = json.loads(integration_scenarios_text)
            except json.JSONDecodeError as exc:
                raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS") from exc
            validate_plan_integration_scenarios(integration_scenarios)
    elif integration_scenarios_text is not None:
        raise FlowctlError("INVALID_PLAN_INTEGRATION_SCENARIOS")

    integration_results = None
    integration_results_text = _one(body_fields, "integration_results")
    if integration_results_text is not None:
        if artifact_type != "integration":
            raise FlowctlError("INVALID_INTEGRATION_RESULTS")
        try:
            integration_results = json.loads(integration_results_text)
        except json.JSONDecodeError as exc:
            raise FlowctlError("INVALID_INTEGRATION_RESULTS") from exc
        validate_integration_results(integration_results)
        if (integration_results["status"] != _one(body_fields, "status")
                or integration_results["status"] != approval_status):
            raise FlowctlError("INTEGRATION_STATUS_MISMATCH")
    elif artifact_type == "integration" and approval_status == "COMPLETE_WITH_DEFECT":
        approval_valid = False

    upstream = {}
    for kind in KINDS:
        upstream_digest = _one(body_fields, f"{kind}_digest")
        upstream_revision = _one(body_fields, f"{kind}_revision")
        if upstream_digest or upstream_revision:
            try:
                parsed_revision = int(upstream_revision) if upstream_revision else None
            except ValueError as exc:
                raise FlowctlError("INVALID_UPSTREAM_REVISION", artifact=kind) from exc
            upstream[kind] = {"digest": upstream_digest, "revision": parsed_revision}
    if integration_results is not None:
        plan_binding = upstream.get("plan")
        if (not plan_binding or integration_results["plan_digest"] != plan_binding["digest"]
                or integration_results["plan_revision"] != plan_binding["revision"]):
            raise FlowctlError("INTEGRATION_PLAN_BINDING_MISMATCH")

    target_milestones = None
    milestone_dependencies = None
    if artifact_type == "roadmap":
        targets_text = _one(body_fields, "target_milestones")
        dependencies_text = _one(body_fields, "milestone_dependencies")
        if targets_text is None or dependencies_text is None:
            raise FlowctlError("MILESTONE_GRAPH_REQUIRED")
        if targets_text is not None or dependencies_text is not None:
            try:
                target_milestones = json.loads(targets_text)
                milestone_dependencies = json.loads(dependencies_text or "{}")
            except json.JSONDecodeError as exc:
                raise FlowctlError("INVALID_MILESTONE_GRAPH") from exc
            if (not isinstance(target_milestones, list) or not target_milestones
                    or len(set(target_milestones)) != len(target_milestones)
                    or not all(isinstance(item, str) and item for item in target_milestones)
                    or not isinstance(milestone_dependencies, dict)):
                raise FlowctlError("INVALID_MILESTONE_GRAPH")
            for target in target_milestones:
                dependencies = milestone_dependencies.get(target, [])
                if (not isinstance(dependencies, list) or not all(item in target_milestones for item in dependencies)
                        or target in dependencies):
                    raise FlowctlError("INVALID_MILESTONE_GRAPH", milestone=target)
            unknown = set(milestone_dependencies) - set(target_milestones)
            if unknown:
                raise FlowctlError("INVALID_MILESTONE_GRAPH", unknown=sorted(unknown))

    return {
        "path": str(path),
        "type": artifact_type,
        "issue_id": issue_id,
        "milestone_id": milestone,
        "revision": revision,
        "digest": digest,
        "body_status": _one(body_fields, "status"),
        "upstream": upstream,
        "target_milestones": target_milestones,
        "milestone_dependencies": milestone_dependencies,
        "integration_scenarios": integration_scenarios,
        "integration_results": integration_results,
        "approval": {
            "valid": approval_valid,
            "status": approval_status,
            "approved_revision": approved_revision,
            "approved_digest": approved_digest,
            "confirmer": _one(approval_fields, "confirmer"),
            "controller_run_id": _one(approval_fields, "controller_run_id"),
            "requirement_revision": _one(approval_fields, "requirement_revision"),
            "requirement_digest": _one(approval_fields, "requirement_digest"),
            "scope_binding": _one(approval_fields, "scope_binding"),
        },
    }
