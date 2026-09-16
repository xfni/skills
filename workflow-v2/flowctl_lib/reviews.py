import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

from .artifacts import read_artifact as verify_artifact
from .errors import FlowctlError
from .state import commit_state, locked_state, reject_if_paused


REPORT_BEGIN = "FLOW_REVIEW_REPORT_BEGIN"
REPORT_END = "FLOW_REVIEW_REPORT_END"
ERROR_BEGIN = "FLOW_REVIEW_ERROR_BEGIN"
ERROR_END = "FLOW_REVIEW_ERROR_END"
RUN_ERROR_CODES = {
    "SDK_UNAVAILABLE",
    "CREDENTIAL_UNAVAILABLE",
    "DNS_ERROR",
    "CONNECTION_ERROR",
    "TLS_ERROR",
    "PROCESS_TIMEOUT",
    "BRIDGE_ERROR",
    "BACKEND_UNAVAILABLE",
    "RESPONSES_UNAVAILABLE",
    "PROCESS_UNAVAILABLE",
    "BACKEND_PROCESS_FAILURE",
    "UNKNOWN_BACKEND_FAILURE",
}
RETRYABLE_PROCESS_CLASSIFICATIONS = {"RUN_ERROR", "PROTOCOL_ERROR"}
UNCLASSIFIED_LIMIT = 2

# Content identities, independent of installation path. Update only with reviewed
# adapter changes. No caller/state/manifest may supply or extend this registry.
TRUSTED_ADAPTER_DIGESTS = {
    'cursor': frozenset({'172131cafcc03f17450a7dd098d3e1a13b8b6105ee9288144cc5f32f47b26c5a'}),
    'ibrain': frozenset({'1f6b9c10035cb7a773407dac05f3024403da10f6d8a1fc19d31e0d854d987175'}),
}


def trusted_adapter_source(runner_path, backend):
    from .review_package import read_regular
    path = Path(runner_path).absolute()
    raw = read_regular(path.parent, Path(path.name))
    if hashlib.sha256(raw).hexdigest() not in TRUSTED_ADAPTER_DIGESTS.get(backend, ()):
        raise FlowctlError('UNTRUSTED_REVIEW_ADAPTER')
    return raw.decode('utf-8')


def _eligible(item):
    return item.get("eligible", True)


def has_passed_review(state, artifact_key, backend, digest):
    """A lane label is not evidence: require its current terminal receipt."""
    lane = state.get('reviews', {}).get('lanes', {}).get(artifact_key, {}).get(backend, {})
    attempt = state.get('reviews', {}).get('attempts', {}).get(lane.get('attempt_id'), {})
    carried = backend == 'gpt' and lane.get('carried_forward') and attempt.get('invalidated_by') == artifact_key
    bound_digest = lane.get('digest') if carried else digest
    if not (lane.get('status') == attempt.get('status') == 'PASSED'
            and lane.get('digest') == attempt.get('artifact_digest') == bound_digest
            and attempt.get('backend') == backend and attempt.get('artifact_key') == artifact_key
            and attempt.get('classification') == 'REVIEW_RESULT' and (_eligible(attempt) or carried)):
        return False
    if backend in {'cursor', 'ibrain'} and attempt.get('execution_assurance') != 'CONTROLLER_EXECUTED':
        return False
    try:
        raw = Path(attempt['report_path']).read_bytes()
    except (KeyError, OSError):
        return False
    return 'sha256:' + hashlib.sha256(raw).hexdigest() == attempt.get('report_digest')


def reject_if_unclassified_exhausted(state, artifact_key, artifact_digest):
    counts = {}
    for item in state["reviews"]["attempts"].values():
        if (item.get("artifact_key") == artifact_key
                and item.get("artifact_digest") == artifact_digest
                and item.get("classification") == "UNCLASSIFIED"
                and _eligible(item)):
            backend = item.get("backend")
            counts[backend] = counts.get(backend, 0) + 1
    exhausted = {backend: count for backend, count in counts.items() if count >= UNCLASSIFIED_LIMIT}
    if exhausted:
        raise FlowctlError("UNCLASSIFIED_RETRY_EXHAUSTED", attempts=exhausted)


def begin_review(state_path, backend, stage, artifact_key, model, effort, expected_state_revision):
    if backend not in {"gpt", "cursor", "ibrain", "consistency"}:
        raise FlowctlError("INVALID_REVIEW_BACKEND")
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        if stage != state["current_stage"]:
            raise FlowctlError("STAGE_MISMATCH", expected=state["current_stage"], actual=stage)
        artifact = state["artifacts"].get(artifact_key)
        if not artifact:
            raise FlowctlError("ARTIFACT_NOT_REGISTERED", artifact_key=artifact_key)
        if stage != f"flow-{artifact['type']}":
            raise FlowctlError("REVIEW_ARTIFACT_STAGE_MISMATCH")
        current = verify_artifact(artifact["path"], expected_type=artifact["type"], expected_issue=state["issue_id"])
        if current["digest"] != artifact["digest"]:
            raise FlowctlError("ARTIFACT_DRIFT", artifact_key=artifact_key)
        reject_if_unclassified_exhausted(state, artifact_key, artifact["digest"])
        open_attempts = [
            item for item in state["reviews"]["attempts"].values()
            if item.get("artifact_key") == artifact_key and item.get("backend") == backend
            and item.get("status") == "STARTED" and _eligible(item)
        ]
        if open_attempts:
            raise FlowctlError(
                "REVIEW_ATTEMPT_IN_PROGRESS",
                attempt_ids=[item["attempt_id"] for item in open_attempts],
            )
        lanes = state.setdefault("reviews", {}).setdefault("lanes", {}).setdefault(artifact_key, {})
        if backend in {"cursor", "ibrain", "consistency"}:
            if lanes.get("gpt", {}).get("status") != "PASSED":
                raise FlowctlError("GPT_REVIEW_REQUIRED")
        if backend == "cursor":
            runtime_failures = sum(
                1 for item in state["reviews"]["attempts"].values()
                if item.get("artifact_key") == artifact_key and item.get("backend") == "cursor"
                and item.get("classification") in RETRYABLE_PROCESS_CLASSIFICATIONS and _eligible(item)
                and item.get("artifact_digest") == artifact["digest"]
            )
            if runtime_failures >= 2:
                raise FlowctlError("CURSOR_RETRY_EXHAUSTED", attempts=runtime_failures)
        elif backend == "ibrain":
            if model != "glm-5.3":
                raise FlowctlError("IBRAIN_MODEL_REQUIRED")
            cursor_failures = _runtime_failure_count_for(state, artifact_key, "cursor", artifact["digest"])
            if cursor_failures < 2 and not lanes.get("ibrain_activated"):
                raise FlowctlError("CURSOR_RETRY_REQUIRED", attempts=cursor_failures)
            if _runtime_failure_count_for(state, artifact_key, "ibrain", artifact["digest"]) >= 2:
                raise FlowctlError("IBRAIN_RETRY_EXHAUSTED")
            lanes["ibrain_activated"] = True
        elif backend == "consistency":
            if model != "gpt-6-astra" or effort != "medium":
                raise FlowctlError("CONSISTENCY_MODEL_REQUIRED")
            external_pass = any(
                lanes.get(name, {}).get("status") == "PASSED"
                and lanes.get(name, {}).get("digest") == artifact["digest"]
                for name in ("cursor", "ibrain")
            )
            external_exhausted = (
                (lanes.get('ibrain_activated') or
                 _runtime_failure_count_for(state, artifact_key, "cursor", artifact["digest"]) >= 2)
                and _runtime_failure_count_for(state, artifact_key, "ibrain", artifact["digest"]) >= 2
            )
            if not external_pass and not external_exhausted:
                raise FlowctlError("EXTERNAL_REVIEW_REQUIRED")
            if lanes.get("consistency_attempts", 0) >= 3:
                raise FlowctlError("CONSISTENCY_CYCLE_LIMIT")
        latest_lane = lanes.get(backend)
        if (backend != "gpt" and latest_lane
                and latest_lane.get("classification") == "REVIEW_RESULT"
                and latest_lane.get("digest") == artifact["digest"]):
            latest_attempt = state['reviews']['attempts'].get(latest_lane.get('attempt_id'), {})
            passed = has_passed_review(state, artifact_key, backend, artifact["digest"])
            if passed or _requires_repair(latest_attempt):
                code = "REVIEW_ALREADY_PASSED" if passed else "ARTIFACT_REVISION_REQUIRED"
                raise FlowctlError(code)
        completed_cycles = sum(
            1 for item in state["reviews"]["attempts"].values()
            if item.get("artifact_key") == artifact_key and item.get("backend") == backend
            and item.get("classification") == "REVIEW_RESULT"
        )
        if completed_cycles >= 3:
            raise FlowctlError("REVIEW_CYCLE_LIMIT", cycles=completed_cycles)
        attempt_id = f"review-{uuid.uuid4()}"
        attempt = {
            "attempt_id": attempt_id, "backend": backend, "stage": stage,
            "artifact_key": artifact_key, "artifact_digest": artifact["digest"],
            "artifact_revision": artifact["revision"], "model": model, "effort": effort,
            "status": "STARTED", "classification": None,
            "started_state_revision": expected_state_revision + 1,
            "eligible": True,
        }
        if artifact["type"] == "code":
            from .snapshot import verify_recorded_snapshot
            snapshot = verify_recorded_snapshot(state, artifact_key)
            attempt["snapshot_digest"] = snapshot["snapshot_digest"]
        state["reviews"]["attempts"][attempt_id] = attempt
        state["pending_action"] = f"review:{backend}:await-result"
        state = commit_state(state_path, state, "REVIEW_STARTED", attempt)
        return {**attempt, "state_revision": state["state_revision"]}


def _runtime_failure_count_for(state, artifact_key, backend, artifact_digest):
    return sum(
        1 for item in state["reviews"]["attempts"].values()
        if item.get("artifact_key") == artifact_key
        and item.get("backend") == backend
        and item.get("classification") in RETRYABLE_PROCESS_CLASSIFICATIONS and _eligible(item)
        and item.get("artifact_digest") == artifact_digest
    )


def _runtime_failure_count(state, attempt):
    return sum(
        1 for item in state["reviews"]["attempts"].values()
        if item.get("artifact_key") == attempt["artifact_key"]
        and item.get("backend") == attempt["backend"]
        and item.get("classification") in RETRYABLE_PROCESS_CLASSIFICATIONS and _eligible(item)
        and item.get("artifact_digest") == attempt["artifact_digest"]
    )


def _unclassified_failure_count(state, attempt):
    return sum(
        1 for item in state["reviews"]["attempts"].values()
        if item.get("artifact_key") == attempt["artifact_key"]
        and item.get("backend") == attempt["backend"]
        and item.get("classification") == "UNCLASSIFIED" and _eligible(item)
        and item.get("artifact_digest") == attempt["artifact_digest"]
    )


def _requires_repair(attempt):
    return attempt.get('status') == 'FAILED' or (
        attempt.get('status') == 'INCOMPLETE' and
        any(finding.get('blocking_status') == 'BLOCKING' for finding in attempt.get('findings', [])))


def next_review_action(state, artifact_key):
    """One local review dependency order for registration, results and resume."""
    artifact = state['artifacts'][artifact_key]
    kind, digest = artifact['type'], artifact['digest']
    lanes = state.get('reviews', {}).get('lanes', {}).get(artifact_key, {})
    attempts = state.get('reviews', {}).get('attempts', {})
    current = [a for a in attempts.values() if a.get('artifact_key') == artifact_key
               and a.get('artifact_digest') == digest and _eligible(a)]
    for attempt in current:
        if attempt.get('status') == 'STARTED':
            return f"review:{attempt['backend']}:await-result"
    try:
        reject_if_unclassified_exhausted(state, artifact_key, digest)
    except FlowctlError:
        return 'blocked:review:unclassified'
    for backend in ('gpt', 'cursor', 'ibrain', 'consistency'):
        lane = lanes.get(backend, {})
        if lane.get('digest') == digest and _requires_repair(attempts.get(lane.get('attempt_id'), {})):
            return 'revise:' + kind
    if kind == 'code' and artifact_key not in state.get('snapshots', {}):
        return 'snapshot:capture'
    if not has_passed_review(state, artifact_key, 'gpt', digest):
        backend = 'gpt'
    elif not any(has_passed_review(state, artifact_key, name, digest) for name in ('cursor', 'ibrain')):
        if _runtime_failure_count_for(state, artifact_key, 'cursor', digest) >= 2 or lanes.get('ibrain_activated'):
            backend = 'ibrain' if _runtime_failure_count_for(state, artifact_key, 'ibrain', digest) < 2 else 'consistency'
        else:
            backend = 'cursor'
    else:
        backend = 'consistency'
    if backend == 'consistency' and has_passed_review(state, artifact_key, backend, digest):
        return ('handoff:' if artifact['approval']['valid'] else 'approve:') + kind
    cycles = sum(a.get('artifact_key') == artifact_key and a.get('backend') == backend
                 and a.get('classification') == 'REVIEW_RESULT' for a in attempts.values())
    if cycles >= 3 or backend == 'consistency' and lanes.get('consistency_attempts', 0) >= 3:
        return 'blocked:review:cycle-limit'
    retry = any(a.get('backend') == backend and a.get('status') == 'INCOMPLETE' for a in current)
    return f"review:{backend}" + (':retry' if retry else '')


def record_process_result(state_path, attempt_id, exit_code, stdout, stderr, timed_out,
                          expected_state_revision, evidence_path,
                          forced_classification=None, forced_reason=None):
    if forced_classification:
        classification, reason = forced_classification, forced_reason
    else:
        classification, reason = classify_process(exit_code, stdout, stderr, timed_out)
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        attempt = state["reviews"]["attempts"].get(attempt_id)
        if not attempt:
            raise FlowctlError("REVIEW_ATTEMPT_NOT_FOUND")
        _validate_open_attempt(state, attempt)
        # A terminal ambiguity cannot approve or degrade. Record it even when
        # the guard that failed was snapshot validation; later attempts recheck.
        if forced_classification != 'UNCLASSIFIED':
            _verify_attempt_snapshot(state, attempt)
        stdout, stderr = _sanitize(stdout), _sanitize(stderr)
        evidence = {
            "schema_version": 1, "attempt_id": attempt_id,
            "artifact_digest": attempt["artifact_digest"], "exit_code": exit_code,
            "timed_out": timed_out, "classification": classification,
            "reason": reason, "stdout": stdout, "stderr": stderr,
        }
        evidence['exploration'] = _exploration_evidence(stderr, attempt.get('review_manifest', {}))
        if attempt.get('binding_id'):
            for channel in ('stdout', 'stderr'):
                output = evidence.pop(channel)
                evidence[channel + '_digest'] = 'sha256:' + hashlib.sha256(output.encode('utf-8')).hexdigest()
        evidence_path = Path(evidence_path).expanduser().resolve()
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        attempt.update({
            "status": "INCOMPLETE" if classification != "REVIEW_RESULT" else "FAILED",
            "classification": classification, "failure_reason": reason,
            "exit_code": exit_code, "timed_out": timed_out,
            "evidence_path": str(evidence_path),
            "evidence_digest": "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "execution_assurance": "CONTROLLER_EXECUTED",
            "completed_state_revision": expected_state_revision + 1,
        })
        attempt["retry_count"] = _runtime_failure_count(state, attempt)
        attempt["unclassified_count"] = _unclassified_failure_count(state, attempt)
        state["pending_action"] = next_review_action(state, attempt['artifact_key'])
        state = commit_state(state_path, state, "REVIEW_PROCESS_RECORDED", {
            "attempt_id": attempt_id, "classification": classification,
            "reason": reason, "retry_count": attempt["retry_count"],
            "unclassified_count": attempt["unclassified_count"],
        })
        return {**attempt, "state_revision": state["state_revision"]}


def repair_review_attempt(state_path, attempt_id, repair_kind, expected_state_revision):
    """Reclassify only known legacy bridge failures; never manufactures a review pass."""
    repairs = {
        "unknown_backend_failure": (
            {"UNKNOWN_FAILURE", "BACKEND_TERMINAL_FAILURE"},
            "RUN_ERROR", "UNKNOWN_BACKEND_FAILURE",
        ),
        "duplicate_identical_frames": (
            {"INVALID_TERMINAL_REVIEW_REPORT"},
            "PROTOCOL_ERROR", "INVALID_TERMINAL_REVIEW_REPORT",
        ),
    }
    if repair_kind not in repairs:
        raise FlowctlError("INVALID_REVIEW_REPAIR_KIND")
    allowed_reasons, classification, reason = repairs[repair_kind]
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        attempt = state["reviews"]["attempts"].get(attempt_id)
        if (not attempt or attempt.get("backend") not in {"cursor", "ibrain"}
                or attempt.get("classification") != "UNCLASSIFIED"
                or attempt.get("status") != "INCOMPLETE"
                or attempt.get("execution_assurance") != "CONTROLLER_EXECUTED"
                or attempt.get("failure_reason") not in allowed_reasons
                or not _eligible(attempt)):
            raise FlowctlError("REVIEW_REPAIR_NOT_ALLOWED")
        if repair_kind == "duplicate_identical_frames" and attempt["backend"] != "ibrain":
            raise FlowctlError("REVIEW_REPAIR_NOT_ALLOWED")
        evidence_path = Path(attempt.get("evidence_path", ""))
        try:
            evidence_bytes = evidence_path.read_bytes()
            evidence = json.loads(evidence_bytes)
        except (OSError, json.JSONDecodeError) as exc:
            raise FlowctlError("REVIEW_REPAIR_EVIDENCE_INVALID") from exc
        if ("sha256:" + hashlib.sha256(evidence_bytes).hexdigest() != attempt.get("evidence_digest")
                or evidence.get("attempt_id") != attempt_id
                or evidence.get("classification") != "UNCLASSIFIED"
                or evidence.get("reason") != attempt.get("failure_reason")):
            raise FlowctlError("REVIEW_REPAIR_EVIDENCE_INVALID")
        if repair_kind == "unknown_backend_failure" and evidence.get("exit_code") in {None, 0}:
            raise FlowctlError("REVIEW_REPAIR_NOT_ALLOWED")
        artifact = state["artifacts"].get(attempt["artifact_key"])
        if not artifact or artifact["digest"] != attempt["artifact_digest"]:
            raise FlowctlError("ARTIFACT_DRIFT")
        previous = {
            "classification": attempt["classification"],
            "failure_reason": attempt["failure_reason"],
        }
        if repair_kind == 'duplicate_identical_frames':
            # Preserve the old classification/evidence. This is an audited
            # operator-attested bridge diagnosis, never a recovered PASS.
            attempt['eligible'] = False
            attempt['ineligibility_reason'] = 'LEGACY_IBRAIN_FRAME_BUG'
        else:
            attempt["classification"] = classification
            attempt["failure_reason"] = reason
        attempt["repair"] = {
            "kind": repair_kind,
            "previous_classification": previous["classification"],
            "previous_failure_reason": previous["failure_reason"],
            "evidence_digest": attempt["evidence_digest"],
        }
        attempt["retry_count"] = _runtime_failure_count(state, attempt)
        attempt["unclassified_count"] = _unclassified_failure_count(state, attempt)
        if attempt["retry_count"] < 2:
            state["pending_action"] = f"review:{attempt['backend']}:retry"
        elif attempt["backend"] == "cursor":
            state["pending_action"] = "review:ibrain"
        else:
            state["pending_action"] = "review:consistency"
        event = ('LEGACY_REVIEW_ATTEMPT_INVALIDATED' if repair_kind == 'duplicate_identical_frames'
                 else 'REVIEW_CLASSIFICATION_REPAIRED')
        state = commit_state(state_path, state, event, {
            "attempt_id": attempt_id,
            "repair_kind": repair_kind,
            "previous_classification": previous["classification"],
            "previous_failure_reason": previous["failure_reason"],
            "classification": classification,
            "reason": reason,
            "evidence_digest": attempt["evidence_digest"],
            "eligible": attempt.get('eligible', True),
            "repair_assurance": ('OPERATOR_ATTESTED_BRIDGE_BUG' if repair_kind == 'duplicate_identical_frames'
                                 else 'CONTROLLER_EVIDENCE_CHECKED'),
        })
        return {**attempt, "state_revision": state["state_revision"]}


def _extract_framed_json(output, begin_marker, end_marker):
    if output.count(begin_marker) != 1 or output.count(end_marker) != 1:
        raise FlowctlError("INVALID_REVIEW_FRAME")
    start = output.index(begin_marker) + len(begin_marker)
    try:
        end = output.index(end_marker, start)
    except ValueError as exc:
        raise FlowctlError("INVALID_REVIEW_FRAME") from exc
    try:
        value = json.loads(output[start:end].strip(), object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FlowctlError("INVALID_REVIEW_FRAME") from exc
    if not isinstance(value, dict):
        raise FlowctlError("INVALID_REVIEW_FRAME")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _extract_json_report(output, digest):
    try:
        report = _extract_framed_json(output, REPORT_BEGIN, REPORT_END)
    except FlowctlError as exc:
        raise FlowctlError("MALFORMED_REVIEW_REPORT")
    _validate_terminal_report(report, digest)
    return report


def _exploration_evidence(stderr, manifest):
    """Keep bounded local operation metadata, never file contents/vendor prose."""
    try:
        data = _extract_framed_json(stderr, 'FLOW_REVIEW_EXPLORATION_BEGIN', 'FLOW_REVIEW_EXPLORATION_END')
    except FlowctlError:
        return {'assurance':'UNAVAILABLE', 'calls':[]}
    if (data.get('schema_version') != 1 or data.get('assurance') != 'LOCAL_READ_TOOLS'
            or not isinstance(data.get('calls'), list) or len(data['calls']) > 256):
        return {'assurance':'UNAVAILABLE', 'calls':[]}
    import re
    available = {item['path']: item['digest'] for item in manifest.get('files', [])}
    calls = []
    for item in data['calls']:
        if (not isinstance(item, dict) or item.get('tool') not in {'list_files','read_file','search'}
                or not isinstance(item.get('result_digest'), str)
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', item['result_digest'])):
            return {'assurance':'UNAVAILABLE', 'calls':[]}
        entry = {'tool':item['tool'], 'result_digest':item['result_digest']}
        path = item.get('path')
        if isinstance(path, str) and path in available and item.get('source_digest') == available[path]:
            entry.update(path=path, source_digest=available[path])
        calls.append(entry)
    return {'assurance':'LOCAL_READ_TOOLS', 'calls':calls}


def _validate_terminal_report(report, digest):
    if not isinstance(report, dict):
        raise FlowctlError('INVALID_REVIEW_REPORT')
    status = report.get('status')
    if not isinstance(status, str) or status.upper() not in {'PASSED', 'FAILED', 'INCOMPLETE'}:
        raise FlowctlError('INVALID_REVIEW_REPORT')
    status = status.upper()
    findings = report.get('findings', [])
    if report.get('reviewed_digest', digest) != digest or not isinstance(findings, list):
        raise FlowctlError('REVIEW_BINDING_MISMATCH')
    normalized = []
    for index, finding in enumerate(findings, 1):
        if not isinstance(finding, dict) or not isinstance(finding.get('summary'), str) or not finding['summary'].strip():
            raise FlowctlError('INVALID_REVIEW_FINDING')
        severity = str(finding.get('severity', 'HIGH' if status == 'FAILED' else 'MEDIUM')).upper()
        if severity not in {'BLOCKER', 'HIGH', 'MEDIUM', 'LOW', 'INFO'}:
            severity = 'HIGH' if status == 'FAILED' else 'MEDIUM'
        blocking = finding.get('blocking_status')
        if blocking is None:
            blocking = 'BLOCKING' if status == 'FAILED' or severity in {'BLOCKER', 'HIGH'} else 'NON_BLOCKING'
        if blocking not in {'BLOCKING', 'NON_BLOCKING'}:
            raise FlowctlError('INVALID_REVIEW_FINDING')
        summary = finding['summary'].strip()
        normalized.append(dict(id=str(finding.get('id') or f'F-{index}'), severity=severity,
            summary=summary, blocking_status=blocking,
            recurrence_key=str(finding.get('recurrence_key') or hashlib.sha256(summary.encode()).hexdigest()[:16]),
            evidence=str(finding.get('evidence') or 'NOT_SUPPLIED')))
    has_blocking = any(item['blocking_status'] == 'BLOCKING' for item in normalized)
    if (status == 'PASSED' and has_blocking) or (status == 'FAILED' and not has_blocking):
        raise FlowctlError('INCONSISTENT_REVIEW_STATUS')
    # Metadata is generated here; auxiliary model prose is not persisted as a gate.
    report.clear()
    report.update(status=status, reviewed_digest=digest, findings=normalized)


def _redacted_terminal_report(report, digest):
    from .review_package import check_content
    _validate_terminal_report(report, digest)
    # Redact the complete field when sensitive syntax is present. Partial token
    # substitution can leak multiline values or an authorization scheme's tail.
    def redact(value):
        try:
            check_content(value.encode('utf-8'))
        except UnicodeError:
            raise FlowctlError('INVALID_REVIEW_REPORT') from None
        except FlowctlError as exc:
            if exc.code == 'REVIEW_SENSITIVE_CONTENT':
                return '[REDACTED]'
            raise
        return value
    redacted = {**report, 'findings': [{key: redact(value) for key, value in item.items()}
                                     for item in report['findings']]}
    _validate_terminal_report(redacted, digest)
    return redacted


def run_external_review(state_path, backend, artifact_key, prompt_path, runner_path, model, effort,
                        timeout_seconds, expected_state_revision, binding_id=None, manifest_path=None):
    from .state import load_state
    if manifest_path is not None:
        if binding_id is not None:
            raise FlowctlError('INVALID_REVIEW_MANIFEST')
        from .review_package import validate_review_manifest
        validated = validate_review_manifest(state_path, manifest_path, expected_state_revision)
        binding_id, expected_state_revision = validated['binding_id'], validated['state_revision']
    state = load_state(state_path)
    artifact = state["artifacts"].get(artifact_key)
    if not artifact:
        raise FlowctlError("ARTIFACT_NOT_REGISTERED", artifact_key=artifact_key)
    from .review_package import create_review_package, bind_package, consume_binding
    bindings = state['authorizations']['external_review']['bindings']
    selected = next((b for b in bindings if b['binding_id'] == binding_id), None) if binding_id else None
    if binding_id and (not selected or selected['status'] != 'BOUND' or 'input_manifest' not in selected):
        raise FlowctlError('AUTHORIZATION_BINDING_STALE')
    if not binding_id and any('input_manifest' in b and b.get('status') == 'BOUND' for b in bindings):
        raise FlowctlError('REVIEW_BINDING_REQUIRED')
    inputs = selected['input_manifest'] if selected else dict(backend=backend, stage=state['current_stage'],
        artifact_key=artifact_key, prompt_path=str(prompt_path), paths=[artifact['path']])
    if (inputs['backend'] != backend or inputs['stage'] != state['current_stage']
            or inputs['artifact_key'] != artifact_key or Path(inputs['prompt_path']).resolve() != Path(prompt_path).resolve()):
        raise FlowctlError('AUTHORIZATION_BINDING_STALE')
    package = create_review_package(state, **inputs)
    attempt = None
    failure_reason = None
    try:
        if selected and selected['package_digest'] != package.digest:
            raise FlowctlError('REVIEW_PACKAGE_DRIFT')
        attempt = begin_review(
            state_path, backend, state["current_stage"], artifact_key, model, effort,
            expected_state_revision,
        )
        with locked_state(state_path, attempt["state_revision"]) as current:
            fresh = create_review_package(current, **inputs)
            try:
                if fresh.digest != package.digest:
                    raise FlowctlError('REVIEW_PACKAGE_DRIFT')
            finally:
                fresh.cleanup()
            binding = next((item for item in current['authorizations']['external_review']['bindings']
                            if item['binding_id'] == binding_id), None) if binding_id else None
            if binding is None:
                binding = bind_package(current, package)
            consume_binding(current, package, binding["binding_id"])
            current["reviews"]["attempts"][attempt["attempt_id"]]["binding_id"] = binding["binding_id"]
            current['reviews']['attempts'][attempt['attempt_id']]['review_snapshot'] = package.source_snapshot
            current['reviews']['attempts'][attempt['attempt_id']]['review_manifest'] = package.manifest
            current = commit_state(state_path, current, "REVIEW_PACKAGE_CONSUMED", {
                "binding_id": binding["binding_id"], "package_digest": package.digest,
                "authorization_id": binding["authorization_id"],
                "authorization_revision": binding["authorization_revision"],
            })
            attempt["state_revision"] = current["state_revision"]
            exit_code, stdout, stderr, timed_out = _run_bound_package(
                package, runner_path, backend, model, effort, timeout_seconds)
            mutation_reason = None
            try:
                package.verify()
                package.verify_source(state['worktree_path'])
            except FlowctlError as exc:
                mutation_reason = exc.code
    except (FlowctlError, OSError, ValueError) as exc:
        if attempt is None:
            raise
        failure_reason = exc.code if isinstance(exc, FlowctlError) else 'BRIDGE_ERROR'
    finally:
        try:
            package.cleanup()
        except FlowctlError:
            if attempt is None:
                raise
            failure_reason = 'REVIEW_PACKAGE_CLEANUP_FAILED'
    if failure_reason:
        current = load_state(state_path)
        recorded = current['reviews']['attempts'].get(attempt['attempt_id'], {})
        if recorded.get('status') != 'STARTED' or not _eligible(recorded):
            # Another controller mutation already resolved/invalidated it.
            raise FlowctlError(failure_reason)
        record_process_result(
            state_path, attempt['attempt_id'], 2, '', '', False,
            current['state_revision'],
            Path(state_path).parent / 'reviews' / f"{attempt['attempt_id']}.json",
            forced_classification='UNCLASSIFIED', forced_reason=failure_reason,
        )
        raise FlowctlError(failure_reason)
    if mutation_reason:
        return record_process_result(
            state_path, attempt['attempt_id'], exit_code, '', '', timed_out,
            attempt['state_revision'],
            Path(state_path).parent / 'reviews' / f"{attempt['attempt_id']}.json",
            forced_classification='UNCLASSIFIED', forced_reason=mutation_reason,
        )
    stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
    stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
    evidence_path = Path(state_path).parent / "reviews" / f"{attempt['attempt_id']}.json"
    try:
        report = _extract_json_report(stdout, attempt["artifact_digest"])
        report = _redacted_terminal_report(report, attempt['artifact_digest'])
    except FlowctlError as exc:
        combined_output = stdout + "\n" + stderr
        terminal_like = _contains_terminal_json(combined_output) or _contains_terminal_fragment(combined_output)
        if exit_code == 0 and not terminal_like:
            return record_process_result(
                state_path, attempt["attempt_id"], exit_code, stdout,
                f"terminal report extraction rejected: {exc.code}", False,
                attempt["state_revision"], evidence_path,
                forced_classification="PROTOCOL_ERROR",
                forced_reason=(exc.code if exc.code == 'REVIEW_WORKTREE_MUTATED'
                               else "INVALID_TERMINAL_REVIEW_REPORT"),
            )
        if terminal_like:
            return record_process_result(
                state_path, attempt["attempt_id"], 2, stdout,
                f"terminal report extraction rejected: {exc.code}", False,
                attempt["state_revision"], evidence_path,
                forced_classification="UNCLASSIFIED",
                forced_reason="INVALID_TERMINAL_REVIEW_REPORT",
            )
    else:
        report_path = evidence_path.with_suffix(".report.json")
        if ERROR_BEGIN in stdout + stderr or ERROR_END in stdout + stderr:
            return record_process_result(state_path, attempt['attempt_id'], 2, stdout, stderr, False,
                attempt['state_revision'], evidence_path, forced_classification='UNCLASSIFIED',
                forced_reason='CONFLICTING_REVIEW_SIGNALS')
        try:
            return submit_review(
                state_path, attempt["attempt_id"], report_path,
                attempt["state_revision"], controller_executed=True,
                report_data=(json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode(),
                process_evidence={
                    'exit_code':exit_code, 'timed_out':timed_out,
                    'stdout_digest':'sha256:' + hashlib.sha256(stdout.encode()).hexdigest(),
                    'stderr_digest':'sha256:' + hashlib.sha256(stderr.encode()).hexdigest(),
                    'exploration':_exploration_evidence(stderr, package.manifest),
                },
            )
        except FlowctlError as exc:
            report_path.unlink(missing_ok=True)
            return record_process_result(
                state_path, attempt["attempt_id"], 2, stdout,
                f"terminal report rejected: {exc.code}", False,
                attempt["state_revision"], evidence_path,
                forced_classification="UNCLASSIFIED",
                forced_reason=(exc.code if exc.code == 'REVIEW_WORKTREE_MUTATED'
                               else "INVALID_TERMINAL_REVIEW_REPORT"),
            )
    return record_process_result(
        state_path, attempt["attempt_id"], exit_code, stdout, stderr, timed_out,
        attempt["state_revision"], evidence_path,
    )



def _run_bound_package(package, runner_path, backend, model, effort, timeout_seconds):
    from .review_package import validate_capabilities
    try:
        source = trusted_adapter_source(runner_path, backend)
        # Execute the captured, pinned bytes for BOTH checks and review. Isolated
        # Python prevents caller cwd/PYTHONPATH from replacing adapter imports.
        runtime = Path.home() / '.codex/runtime/cursor-review/bin/python'
        executable = str(runtime) if backend == 'cursor' and runtime.is_file() else sys.executable
        launcher = [executable, '-I', '-c', source]
        check = subprocess.run([*launcher, "--check-capabilities"],
                               text=True, capture_output=True, timeout=30)
        if check.returncode != 0:
            raise FlowctlError("BACKEND_UNAVAILABLE")
        validate_capabilities(json.loads(check.stdout))
    except (OSError, ValueError, subprocess.TimeoutExpired, FlowctlError):
        error = ERROR_BEGIN + '\n' + json.dumps({
            "schema_version": 1, "code": "BACKEND_UNAVAILABLE"}) + '\n' + ERROR_END
        return 2, "", error, False
    package.verify()
    command = [*launcher, str(package.request_path), '--workspace', str(package.workspace_path),
               '--expected-request-digest', package.digest,
               "--model", model, "--timeout-seconds", str(timeout_seconds)]
    if backend == "cursor":
        command.extend(["--effort", effort])
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds + 30)
        return result.returncode, result.stdout, result.stderr, False
    except subprocess.TimeoutExpired as exc:
        return None, exc.stdout or "", exc.stderr or "", True
    except OSError:
        error = ERROR_BEGIN + '\n' + json.dumps({
            "schema_version": 1, "code": "PROCESS_UNAVAILABLE"}) + '\n' + ERROR_END
        return 2, "", error, False


def run_cursor_review(state_path, artifact_key, prompt_path, runner_path, model, effort,
                      timeout_seconds, expected_state_revision, binding_id=None, manifest_path=None):
    return run_external_review(
        state_path, "cursor", artifact_key, prompt_path, runner_path, model, effort,
        timeout_seconds, expected_state_revision, binding_id, manifest_path,
    )


def run_ibrain_review(state_path, artifact_key, prompt_path, runner_path,
                      timeout_seconds, expected_state_revision, binding_id=None, manifest_path=None):
    return run_external_review(
        state_path, "ibrain", artifact_key, prompt_path, runner_path, "glm-5.3", "medium",
        timeout_seconds, expected_state_revision, binding_id, manifest_path,
    )


def _contains_terminal_json(output):
    decoder = json.JSONDecoder()
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and ("status" in value or "findings" in value):
            return True
    return False


def _contains_terminal_fragment(output):
    lowered = output.lower()
    if "finished without terminal report" in lowered:
        return True
    return "{" in output and ('"status"' in lowered or '"findings"' in lowered)


def submit_review(state_path, attempt_id, report_path, expected_state_revision, controller_executed=False,
                  report_data=None, process_evidence=None):
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        attempt = state["reviews"]["attempts"].get(attempt_id)
        if not attempt:
            raise FlowctlError("REVIEW_ATTEMPT_NOT_FOUND")
        _validate_open_attempt(state, attempt)
        if attempt.get('review_snapshot'):
            from .review_workspace import verify_review_snapshot
            verify_review_snapshot(state['worktree_path'], state_path, attempt['review_snapshot'])
        _verify_attempt_snapshot(state, attempt)
        if attempt["backend"] in {"cursor", "ibrain"} and not controller_executed:
            raise FlowctlError("EXTERNAL_CONTROLLER_EXECUTION_REQUIRED")
        artifact = state["artifacts"].get(attempt["artifact_key"])
        if not artifact:
            raise FlowctlError("ARTIFACT_NOT_REGISTERED")
        try:
            current = verify_artifact(artifact["path"], expected_type=artifact["type"], expected_issue=state["issue_id"])
        except (FlowctlError, OSError) as exc:
            raise FlowctlError("ARTIFACT_DRIFT") from exc
        if current["digest"] != attempt["artifact_digest"]:
            raise FlowctlError("ARTIFACT_DRIFT")
        try:
            if report_data is not None and not controller_executed:
                raise FlowctlError('EXTERNAL_CONTROLLER_EXECUTION_REQUIRED')
            report_bytes = report_data if report_data is not None else Path(report_path).read_bytes()
            report = json.loads(report_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise FlowctlError("INVALID_REVIEW_REPORT") from exc
        _validate_terminal_report(report, attempt['artifact_digest'])
        if report_data is not None:
            Path(report_path).parent.mkdir(parents=True, exist_ok=True)
            Path(report_path).write_bytes(report_bytes)
        if process_evidence is not None:
            if not controller_executed:
                raise FlowctlError('EXTERNAL_CONTROLLER_EXECUTION_REQUIRED')
            attempt['process_evidence'] = process_evidence
        attempt.update({
            "status": report["status"], "findings": report["findings"],
            "report_path": str(Path(report_path).resolve()),
            "report_digest": "sha256:" + hashlib.sha256(report_bytes).hexdigest(),
            "execution_assurance": "CONTROLLER_EXECUTED" if controller_executed else "CALLER_ATTESTED",
            "classification": (
                "REVIEW_RESULT"
                if report["status"] in {"PASSED", "FAILED"} or report["findings"]
                else "UNCLASSIFIED"
            ),
            "completed_state_revision": expected_state_revision + 1,
        })
        lanes = state.setdefault("reviews", {}).setdefault("lanes", {}).setdefault(attempt["artifact_key"], {})
        lanes[attempt["backend"]] = {
            "status": attempt["status"], "digest": attempt["artifact_digest"],
            "attempt_id": attempt_id, "classification": attempt["classification"],
        }
        if attempt["backend"] == "consistency":
            lanes["consistency_attempts"] = lanes.get("consistency_attempts", 0) + 1
        attempt["unclassified_count"] = _unclassified_failure_count(state, attempt)
        if _requires_repair(attempt):
            lanes["repair_backend"] = attempt["backend"]
        state['pending_action'] = next_review_action(state, attempt['artifact_key'])
        state = commit_state(state_path, state, "REVIEW_RECORDED", {
            "attempt_id": attempt_id, "status": attempt["status"],
            "classification": attempt["classification"], "report_digest": attempt["report_digest"],
        })
        return {**attempt, "state_revision": state["state_revision"]}


def classify_process(exit_code, stdout, stderr, timed_out):
    if timed_out:
        return "RUN_ERROR", "PROCESS_TIMEOUT"
    if exit_code == 0:
        return "REVIEW_RESULT", None
    try:
        error = _extract_framed_json(stdout + "\n" + stderr, ERROR_BEGIN, ERROR_END)
    except FlowctlError:
        return "RUN_ERROR", "UNKNOWN_BACKEND_FAILURE"
    code = error.get("code")
    if error.get("schema_version") == 1 and code in RUN_ERROR_CODES:
        return "RUN_ERROR", code
    if error.get("schema_version") == 1 and code == "PROTOCOL_ERROR":
        return "PROTOCOL_ERROR", code
    if isinstance(code, str):
        return "UNCLASSIFIED", code
    return "RUN_ERROR", "UNKNOWN_BACKEND_FAILURE"


def _sanitize(value):
    import re

    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    for pattern, replacement in (
        (r"(?i)(api[_-]?key|authorization|token|secret)(\s*[:=]\s*)([^\s,;]+)", r"\1\2[REDACTED]"),
        (r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]"),
    ):
        value = re.sub(pattern, replacement, value)
    return value


def _validate_open_attempt(state, attempt):
    if attempt.get("status") != "STARTED" or not _eligible(attempt):
        raise FlowctlError("REVIEW_ATTEMPT_TERMINAL")
    if attempt.get("stage") != state["current_stage"]:
        raise FlowctlError("REVIEW_STAGE_STALE")
    artifact = state["artifacts"].get(attempt["artifact_key"])
    if not artifact or artifact["digest"] != attempt["artifact_digest"]:
        raise FlowctlError("ARTIFACT_DRIFT")


def _verify_attempt_snapshot(state, attempt):
    expected = attempt.get("snapshot_digest")
    if expected is None:
        return
    from .snapshot import verify_recorded_snapshot
    current = verify_recorded_snapshot(state, attempt["artifact_key"])
    if current["snapshot_digest"] != expected:
        raise FlowctlError("CODE_SNAPSHOT_DRIFT")
