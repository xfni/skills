import argparse
import json
from pathlib import Path
import sys

from .artifacts import verify_artifact
from .authorizations import (
    EXTERNAL_REVIEW_STAGES,
    begin_authorization_amendment,
    decide_authorization,
)
from .errors import FlowctlError
from .handoff import accept_handoff
from .resume import reconcile_resume, resume_flow
from .reviews import begin_review, repair_review_attempt, run_cursor_review, run_ibrain_review, submit_review
from .snapshot import record_snapshot
from .signals import record_signal
from .state import audit_state, initialize_state, read_consistent_state, register_artifact, update_coder_state, validate_admission


def _parser():
    parser = argparse.ArgumentParser(prog="flowctl", description="Deterministic Flow v2 controller")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--issue", required=True)
    init.add_argument("--repo", required=True)
    init.add_argument("--branch", required=True)
    init.add_argument("--state")
    init.add_argument("--run-id")

    status = commands.add_parser("status")
    status.add_argument("--state", required=True)

    artifact = commands.add_parser("artifact")
    artifact_commands = artifact.add_subparsers(dest="artifact_command", required=True)
    verify = artifact_commands.add_parser("verify")
    verify.add_argument("--path", required=True)
    verify.add_argument("--type")
    verify.add_argument("--issue")
    verify.add_argument("--milestone")
    register = artifact_commands.add_parser("register")
    register.add_argument("--state", required=True)
    register.add_argument("--path", required=True)
    register.add_argument("--type", required=True)
    register.add_argument("--milestone")
    register.add_argument("--expected-revision", required=True, type=int)

    resume = commands.add_parser("resume")
    resume.add_argument("--issue", required=True)
    resume.add_argument("--repo", required=True)
    resume.add_argument("--inputs")
    resume.add_argument("--state", required=True)
    resume.add_argument("--expected-revision", required=True, type=int)

    review = commands.add_parser("review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    begin = review_commands.add_parser("begin")
    for option, required in (("state", True), ("backend", True), ("stage", True), ("artifact-key", True), ("model", True), ("effort", True)):
        begin.add_argument(f"--{option}", required=required)
    begin.add_argument("--expected-revision", required=True, type=int)
    submit = review_commands.add_parser("submit")
    submit.add_argument("--state", required=True)
    submit.add_argument("--attempt", required=True)
    submit.add_argument("--report", required=True)
    submit.add_argument("--expected-revision", required=True, type=int)
    cursor = review_commands.add_parser("cursor")
    cursor.add_argument("--state", required=True)
    cursor.add_argument("--artifact-key", required=True)
    cursor.add_argument("--prompt", required=True)
    cursor.add_argument("--runner", required=True)
    cursor.add_argument("--model", default="grok-4.6")
    cursor.add_argument("--effort", default="high")
    cursor.add_argument("--timeout-seconds", type=int, default=960)
    cursor.add_argument("--expected-revision", required=True, type=int)
    cursor_binding = cursor.add_mutually_exclusive_group()
    cursor_binding.add_argument('--binding-id')
    cursor_binding.add_argument('--manifest')
    ibrain = review_commands.add_parser("ibrain")
    ibrain.add_argument("--state", required=True)
    ibrain.add_argument("--artifact-key", required=True)
    ibrain.add_argument("--prompt", required=True)
    ibrain.add_argument("--runner", required=True)
    ibrain.add_argument("--timeout-seconds", type=int, default=960)
    ibrain.add_argument("--expected-revision", required=True, type=int)
    ibrain_binding = ibrain.add_mutually_exclusive_group()
    ibrain_binding.add_argument('--binding-id')
    ibrain_binding.add_argument('--manifest')
    repair = review_commands.add_parser("repair-classification")
    repair.add_argument("--state", required=True)
    repair.add_argument("--attempt", required=True)
    repair.add_argument(
        "--kind", required=True,
        choices=("unknown_backend_failure", "duplicate_identical_frames"),
    )
    repair.add_argument("--expected-revision", required=True, type=int)

    handoff = commands.add_parser("handoff")
    handoff_commands = handoff.add_subparsers(dest="handoff_command", required=True)
    accept = handoff_commands.add_parser("accept")
    accept.add_argument("--state", required=True)
    accept.add_argument("--handoff", required=True)
    accept.add_argument("--expected-revision", required=True, type=int)

    coder = commands.add_parser("coder")
    coder_commands = coder.add_subparsers(dest="coder_command", required=True)
    update = coder_commands.add_parser("update")
    update.add_argument("--state", required=True)
    update.add_argument("--payload", required=True)
    update.add_argument("--expected-revision", required=True, type=int)

    snapshot = commands.add_parser("snapshot")
    snapshot_commands = snapshot.add_subparsers(dest="snapshot_command", required=True)
    capture = snapshot_commands.add_parser("capture")
    capture.add_argument("--state", required=True)
    capture.add_argument("--artifact-key", required=True)
    capture.add_argument("--expected-revision", required=True, type=int)

    signal = commands.add_parser("signal")
    signal_commands = signal.add_subparsers(dest="signal_command", required=True)
    record = signal_commands.add_parser("record")
    record.add_argument("--state", required=True)
    record.add_argument("--payload", required=True)
    record.add_argument("--expected-revision", required=True, type=int)

    authorization = commands.add_parser("authorization")
    authorization_commands = authorization.add_subparsers(dest="authorization_command", required=True)
    validate = authorization_commands.add_parser('validate')
    validate.add_argument('--state', required=True)
    validate.add_argument('--kind', required=True, choices=('external_review', 'production_replay'))
    validate.add_argument('--manifest', required=True)
    validate.add_argument('--expected-revision', required=True, type=int)
    for name in ("decide", "amend"):
        command = authorization_commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--kind", required=True, choices=("external_review", "production_replay"))
        command.add_argument("--decision", required=True)
        command.add_argument("--expected-revision", required=True, type=int)
    replay = commands.add_parser('replay')
    replay_commands = replay.add_subparsers(dest='replay_command', required=True)
    for name in ('validate', 'run', 'cleanup'):
        command = replay_commands.add_parser(name)
        command.add_argument('--state', required=True)
        command.add_argument('--expected-revision', required=True, type=int)
        command.add_argument('--manifest' if name == 'validate' else '--binding-id', required=True)
    return parser


def _default_state(repo, issue):
    return Path(repo).expanduser().resolve() / ".ai" / "issue" / issue / "flow-state.json"


def _validate_command_admission(state_path):
    state = read_consistent_state(state_path)
    validate_admission(state)
    return state


def _parse_authorization_decision(raw, kind):
    try:
        decision = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FlowctlError("INVALID_AUTHORIZATION_JSON") from exc
    if not isinstance(decision, dict):
        raise FlowctlError("AUTHORIZATION_DECISION_SCHEMA_INVALID")
    expected = (
        {"decision", "allowed_stages"}
        if kind == "external_review"
        else {"decision"}
    )
    if set(decision) != expected:
        raise FlowctlError("AUTHORIZATION_DECISION_SCHEMA_INVALID")
    value = decision["decision"]
    allowed = (
        {"GRANTED", "DENIED"}
        if kind == "external_review"
        else {"SANITIZED_LOCAL_REPLAY", "SKIP_PRODUCTION_REPLAY"}
    )
    if type(value) is not str or value not in allowed:
        raise FlowctlError("AUTHORIZATION_DECISION_SCHEMA_INVALID")
    if kind == "external_review":
        stages = decision["allowed_stages"]
        if (not isinstance(stages, list) or not stages
                or any(type(stage) is not str or stage not in EXTERNAL_REVIEW_STAGES
                       for stage in stages)
                or len(stages) != len(set(stages))):
            raise FlowctlError("AUTHORIZATION_DECISION_SCHEMA_INVALID")
    return decision


def _authorization_result(state, kind):
    authorization = state["authorizations"][kind]
    return {
        "ok": True,
        "authorization_id": authorization["authorization_id"],
        "authorization_revision": authorization["revision"],
        "authorization": authorization,
        "state": state,
    }


def dispatch(args):
    if args.command == "init":
        state_path = Path(args.state) if args.state else _default_state(args.repo, args.issue)
        state = initialize_state(state_path, args.issue, args.repo, args.branch, args.run_id)
        validate_admission(state)
        return {"ok": True, "state_path": str(state_path.resolve()), "state": state}
    if args.command == "status":
        state = read_consistent_state(args.state)
        admission = validate_admission(state)
        audit = audit_state(state)
        return {"ok": True, "state": state, "admission": admission, "audit": audit}
    if args.command == "artifact" and args.artifact_command == "verify":
        value = verify_artifact(args.path, args.type, args.issue, args.milestone)
        return {"ok": True, "artifact": value}
    if args.command == "artifact" and args.artifact_command == "register":
        _validate_command_admission(args.state)
        value = register_artifact(args.state, args.path, args.type, args.milestone, args.expected_revision)
        return {"ok": True, "state": value}
    if args.command == "resume":
        admitted = _validate_command_admission(args.state)
        if Path(args.repo).expanduser().resolve() != Path(admitted["worktree_path"]):
            raise FlowctlError("WORKTREE_MISMATCH")
        result = resume_flow(args.issue, args.repo, args.inputs)
        result["discovered_next_stage"] = result["next_stage"]
        result["state"] = reconcile_resume(args.state, result, args.expected_revision)
        result["next_stage"] = None if result["state"]["current_stage"] == "complete" else result["state"]["current_stage"]
        result["pending_action"] = result["state"]["pending_action"]
        return result
    if args.command == "review" and args.review_command == "begin":
        _validate_command_admission(args.state)
        value = begin_review(args.state, args.backend, args.stage, args.artifact_key, args.model, args.effort, args.expected_revision)
        return {"ok": True, "review": value}
    if args.command == "review" and args.review_command == "submit":
        _validate_command_admission(args.state)
        value = submit_review(args.state, args.attempt, args.report, args.expected_revision)
        return {"ok": True, "review": value}
    if args.command == "review" and args.review_command == "cursor":
        _validate_command_admission(args.state)
        value = run_cursor_review(
            args.state, args.artifact_key, args.prompt, args.runner,
            args.model, args.effort, args.timeout_seconds, args.expected_revision,
            args.binding_id, args.manifest,
        )
        return {"ok": True, "review": value}
    if args.command == "review" and args.review_command == "ibrain":
        _validate_command_admission(args.state)
        value = run_ibrain_review(
            args.state, args.artifact_key, args.prompt, args.runner,
            args.timeout_seconds, args.expected_revision,
            args.binding_id, args.manifest,
        )
        return {"ok": True, "review": value}
    if args.command == "review" and args.review_command == "repair-classification":
        _validate_command_admission(args.state)
        value = repair_review_attempt(
            args.state, args.attempt, args.kind, args.expected_revision,
        )
        return {"ok": True, "review": value}
    if args.command == "handoff" and args.handoff_command == "accept":
        _validate_command_admission(args.state)
        return accept_handoff(args.state, args.handoff, args.expected_revision)
    if args.command == "coder" and args.coder_command == "update":
        _validate_command_admission(args.state)
        return {"ok": True, "state": update_coder_state(args.state, args.payload, args.expected_revision)}
    if args.command == "snapshot" and args.snapshot_command == "capture":
        _validate_command_admission(args.state)
        return {"ok": True, **record_snapshot(args.state, args.artifact_key, args.expected_revision)}
    if args.command == "signal" and args.signal_command == "record":
        _validate_command_admission(args.state)
        return {"ok": True, **record_signal(args.state, args.payload, args.expected_revision)}
    if args.command == 'replay':
        from .replay import validate_replay_manifest, run_replay, recover_replay_cleanup
        _validate_command_admission(args.state)
        if args.replay_command == 'validate':
            return {'ok': True, **validate_replay_manifest(args.state, args.manifest, args.expected_revision)}
        if args.replay_command == 'cleanup':
            result = recover_replay_cleanup(args.state, args.binding_id, args.expected_revision)
            return {'ok': result['status'] == 'PASSED', **result}
        result = run_replay(args.state, args.binding_id, args.expected_revision)
        return {'ok': result['status'] == 'PASSED', **result}
    if args.command == "authorization":
        if (isinstance(args.expected_revision, bool)
                or not isinstance(args.expected_revision, int)
                or args.expected_revision < 0):
            raise FlowctlError("INVALID_EXPECTED_REVISION")
        _validate_command_admission(args.state)
        if args.authorization_command == 'validate':
            if args.kind == 'production_replay':
                from .replay import validate_replay_manifest
                return {'ok': True, **validate_replay_manifest(args.state, args.manifest, args.expected_revision)}
            from .review_package import validate_review_manifest
            return {'ok': True, **validate_review_manifest(args.state, args.manifest, args.expected_revision)}
        decision = _parse_authorization_decision(args.decision, args.kind)
        if args.authorization_command == "decide":
            state = decide_authorization(
                args.state, args.kind, decision, args.expected_revision,
            )
        elif args.authorization_command == "amend":
            state = begin_authorization_amendment(
                args.state, args.kind, decision, args.expected_revision,
            )
        else:
            raise FlowctlError("UNSUPPORTED_COMMAND")
        return _authorization_result(state, args.kind)
    raise FlowctlError("UNSUPPORTED_COMMAND")


def main(argv=None):
    try:
        result = dispatch(_parser().parse_args(argv))
    except FlowctlError as exc:
        print(json.dumps({"ok": False, "error": exc.as_dict()}, ensure_ascii=False, sort_keys=True))
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "FLOWCTL_RUNTIME_ERROR", "message": str(exc)}}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ok', True) else 2
