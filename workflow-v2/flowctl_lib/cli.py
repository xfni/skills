import argparse
import json
from pathlib import Path
import sys

from .artifacts import verify_artifact
from .errors import FlowctlError
from .handoff import accept_handoff
from .resume import reconcile_resume, resume_flow
from .reviews import begin_review, run_cursor_review, run_ibrain_review, submit_review
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
    ibrain = review_commands.add_parser("ibrain")
    ibrain.add_argument("--state", required=True)
    ibrain.add_argument("--artifact-key", required=True)
    ibrain.add_argument("--prompt", required=True)
    ibrain.add_argument("--runner", required=True)
    ibrain.add_argument("--timeout-seconds", type=int, default=960)
    ibrain.add_argument("--expected-revision", required=True, type=int)

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
    return parser


def _default_state(repo, issue):
    return Path(repo).expanduser().resolve() / ".ai" / "issue" / issue / "flow-state.json"


def _validate_command_admission(state_path):
    state = read_consistent_state(state_path)
    validate_admission(state)
    return state


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
        )
        return {"ok": True, "review": value}
    if args.command == "review" and args.review_command == "ibrain":
        _validate_command_admission(args.state)
        value = run_ibrain_review(
            args.state, args.artifact_key, args.prompt, args.runner,
            args.timeout_seconds, args.expected_revision,
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
    return 0
