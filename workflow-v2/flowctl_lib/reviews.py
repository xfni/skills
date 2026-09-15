import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

from .artifacts import verify_artifact
from .errors import FlowctlError
from .state import audit_state, commit_state, locked_state, reject_if_paused


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
}
UNCLASSIFIED_LIMIT = 2


def _eligible(item):
    return item.get("eligible", True)


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
        audit_state(state)
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
                and item.get("classification") == "RUN_ERROR" and _eligible(item)
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
                _runtime_failure_count_for(state, artifact_key, "cursor", artifact["digest"]) >= 2
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
            if latest_lane.get("status") in {"PASSED", "FAILED", "INCOMPLETE"}:
                code = "REVIEW_ALREADY_PASSED" if latest_lane.get("status") == "PASSED" else "ARTIFACT_REVISION_REQUIRED"
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
        and item.get("classification") == "RUN_ERROR" and _eligible(item)
        and item.get("artifact_digest") == artifact_digest
    )


def _runtime_failure_count(state, attempt):
    return sum(
        1 for item in state["reviews"]["attempts"].values()
        if item.get("artifact_key") == attempt["artifact_key"]
        and item.get("backend") == attempt["backend"]
        and item.get("classification") == "RUN_ERROR" and _eligible(item)
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
        _verify_attempt_snapshot(state, attempt)
        stdout, stderr = _sanitize(stdout), _sanitize(stderr)
        evidence = {
            "schema_version": 1, "attempt_id": attempt_id,
            "artifact_digest": attempt["artifact_digest"], "exit_code": exit_code,
            "timed_out": timed_out, "classification": classification,
            "reason": reason, "stdout": stdout, "stderr": stderr,
        }
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
        if classification == "UNCLASSIFIED":
            state["pending_action"] = (
                "blocked:review:unclassified"
                if attempt["unclassified_count"] >= UNCLASSIFIED_LIMIT
                else f"review:{attempt['backend']}:retry"
            )
        elif attempt["retry_count"] < 2:
            state["pending_action"] = f"review:{attempt['backend']}:retry"
        elif attempt["backend"] == "cursor":
            state["pending_action"] = "review:ibrain"
        elif attempt["backend"] == "ibrain":
            state["pending_action"] = "review:consistency"
        else:
            state["pending_action"] = f"handoff:{state['current_stage'].removeprefix('flow-')}:with-defect"
        state = commit_state(state_path, state, "REVIEW_PROCESS_RECORDED", {
            "attempt_id": attempt_id, "classification": classification,
            "reason": reason, "retry_count": attempt["retry_count"],
            "unclassified_count": attempt["unclassified_count"],
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
    if (report.get("status") not in {"PASSED", "FAILED", "INCOMPLETE"}
            or not isinstance(report.get("findings"), list)):
        raise FlowctlError("MALFORMED_REVIEW_REPORT")
    if report.get("reviewed_digest") != digest:
        raise FlowctlError("REVIEW_BINDING_MISMATCH")
    return report


def run_external_review(state_path, backend, artifact_key, prompt_path, runner_path, model, effort,
                        timeout_seconds, expected_state_revision):
    from .state import load_state

    state = load_state(state_path)
    artifact = state["artifacts"].get(artifact_key)
    if not artifact:
        raise FlowctlError("ARTIFACT_NOT_REGISTERED", artifact_key=artifact_key)
    try:
        prompt = Path(prompt_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FlowctlError("REVIEW_PROMPT_UNAVAILABLE") from exc
    if artifact["path"] not in prompt or artifact["digest"] not in prompt:
        raise FlowctlError("REVIEW_PROMPT_BINDING_MISMATCH")
    attempt = begin_review(
        state_path, backend, state["current_stage"], artifact_key, model, effort,
        expected_state_revision,
    )
    command = [
        sys.executable, str(runner_path), state["worktree_path"], str(prompt_path),
        "--model", model, "--timeout-seconds", str(timeout_seconds),
    ]
    if backend == "cursor":
        command.extend(["--effort", effort])
    timed_out = False
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds + 30)
        exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out, exit_code = True, None
        stdout, stderr = exc.stdout or "", exc.stderr or ""
    stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
    stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
    evidence_path = Path(state_path).parent / "reviews" / f"{attempt['attempt_id']}.json"
    try:
        report = _extract_json_report(stdout, attempt["artifact_digest"])
    except FlowctlError as exc:
        combined_output = stdout + "\n" + stderr
        terminal_like = _contains_terminal_json(combined_output) or _contains_terminal_fragment(combined_output)
        if exit_code == 0 or terminal_like:
            return record_process_result(
                state_path, attempt["attempt_id"], 2, stdout,
                f"terminal report extraction rejected: {exc.code}", False,
                attempt["state_revision"], evidence_path,
                forced_classification="UNCLASSIFIED",
                forced_reason="INVALID_TERMINAL_REVIEW_REPORT",
            )
    else:
        report_path = evidence_path.with_suffix(".report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            return submit_review(
                state_path, attempt["attempt_id"], report_path,
                attempt["state_revision"], controller_executed=True,
            )
        except FlowctlError as exc:
            return record_process_result(
                state_path, attempt["attempt_id"], 2, stdout,
                f"terminal report rejected: {exc.code}", False,
                attempt["state_revision"], evidence_path,
                forced_classification="UNCLASSIFIED",
                forced_reason="INVALID_TERMINAL_REVIEW_REPORT",
            )
    return record_process_result(
        state_path, attempt["attempt_id"], exit_code, stdout, stderr, timed_out,
        attempt["state_revision"], evidence_path,
    )


def run_cursor_review(state_path, artifact_key, prompt_path, runner_path, model, effort,
                      timeout_seconds, expected_state_revision):
    return run_external_review(
        state_path, "cursor", artifact_key, prompt_path, runner_path, model, effort,
        timeout_seconds, expected_state_revision,
    )


def run_ibrain_review(state_path, artifact_key, prompt_path, runner_path,
                      timeout_seconds, expected_state_revision):
    return run_external_review(
        state_path, "ibrain", artifact_key, prompt_path, runner_path, "glm-5.3", "medium",
        timeout_seconds, expected_state_revision,
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


def submit_review(state_path, attempt_id, report_path, expected_state_revision, controller_executed=False):
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        attempt = state["reviews"]["attempts"].get(attempt_id)
        if not attempt:
            raise FlowctlError("REVIEW_ATTEMPT_NOT_FOUND")
        _validate_open_attempt(state, attempt)
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
            report_bytes = Path(report_path).read_bytes()
            report = json.loads(report_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise FlowctlError("INVALID_REVIEW_REPORT") from exc
        if report.get("status") not in {"PASSED", "FAILED", "INCOMPLETE"}:
            raise FlowctlError("INVALID_REVIEW_REPORT")
        if report.get("reviewed_digest") != attempt["artifact_digest"] or not isinstance(report.get("findings"), list):
            raise FlowctlError("REVIEW_BINDING_MISMATCH")
        for finding in report["findings"]:
            required = {"id", "severity", "summary", "blocking_status", "recurrence_key", "evidence"}
            if not isinstance(finding, dict) or not required.issubset(finding):
                raise FlowctlError("INVALID_REVIEW_FINDING")
            if finding["severity"] not in {"BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"}:
                raise FlowctlError("INVALID_REVIEW_FINDING")
            if finding["blocking_status"] not in {"BLOCKING", "NON_BLOCKING"}:
                raise FlowctlError("INVALID_REVIEW_FINDING")
        has_blocking = any(item["blocking_status"] == "BLOCKING" for item in report["findings"])
        if (report["status"] == "PASSED" and has_blocking) or (report["status"] == "FAILED" and not has_blocking):
            raise FlowctlError("INCONSISTENT_REVIEW_STATUS")
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
        if attempt["status"] == "PASSED":
            if attempt["backend"] == "gpt":
                state["pending_action"] = "review:cursor"
            elif attempt["backend"] in {"cursor", "ibrain"}:
                state["pending_action"] = "review:consistency"
            else:
                state["pending_action"] = f"handoff:{state['current_stage'].removeprefix('flow-')}"
        elif attempt["status"] == "FAILED":
            lanes["repair_backend"] = attempt["backend"]
            state["pending_action"] = f"revise:{state['current_stage'].removeprefix('flow-')}"
        elif attempt["unclassified_count"] >= UNCLASSIFIED_LIMIT:
            state["pending_action"] = "blocked:review:unclassified"
        else:
            state["pending_action"] = f"review:{attempt['backend']}:retry"
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
        return "UNCLASSIFIED", "UNKNOWN_FAILURE"
    code = error.get("code")
    if error.get("schema_version") == 1 and code in RUN_ERROR_CODES:
        return "RUN_ERROR", code
    if isinstance(code, str):
        return "UNCLASSIFIED", code
    return "UNCLASSIFIED", "UNKNOWN_FAILURE"


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
