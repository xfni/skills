import argparse
import os
import sys
import time
from pathlib import Path


REPORT_BEGIN = "FLOW_REVIEW_REPORT_BEGIN"
REPORT_END = "FLOW_REVIEW_REPORT_END"
ERROR_BEGIN = "FLOW_REVIEW_ERROR_BEGIN"
ERROR_END = "FLOW_REVIEW_ERROR_END"


def emit_error(code, message):
    import json

    print(message, file=sys.stderr, flush=True)
    print(ERROR_BEGIN, file=sys.stderr, flush=True)
    print(json.dumps({"schema_version": 1, "code": code}), file=sys.stderr, flush=True)
    print(ERROR_END, file=sys.stderr, flush=True)


def emit_report(report):
    print(REPORT_BEGIN, flush=True)
    print(report, flush=True)
    print(REPORT_END, flush=True)


DEFAULT_RUNTIME_PYTHON = Path.home() / ".codex" / "runtime" / "cursor-review" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
RUNTIME_PYTHON = Path(os.environ.get("CURSOR_REVIEW_RUNTIME_PYTHON", DEFAULT_RUNTIME_PYTHON)).expanduser()


def enter_dedicated_runtime():
    try:
        current = Path(sys.executable).resolve()
        target = RUNTIME_PYTHON.resolve(strict=True)
    except OSError:
        emit_error(
            "SDK_UNAVAILABLE",
            "INCOMPLETE: Cursor SDK dedicated runtime is unavailable; "
            "run scripts/install_cursor_sdk.py.",
        )
        return False
    if current != target:
        os.execv(str(target), [str(target), str(Path(__file__).resolve()), *sys.argv[1:]])
    return True


if not enter_dedicated_runtime():
    raise SystemExit(2)

try:
    from cursor_sdk import AgentOptions, Client, LocalAgentOptions, ModelParameterValue, ModelSelection, SendOptions
except ImportError as exc:
    SDK_IMPORT_ERROR = exc
else:
    SDK_IMPORT_ERROR = None


TERMINAL_FAILURES = {"failed", "error", "cancelled", "canceled", "stopped", "expired"}
READ_ONLY_TOOLS = ["read", "grep", "glob", "ls"]
DEFAULT_API_KEY_FILE = Path.home() / ".cursor-review" / "API_KEY"
DEFAULT_MODEL = "grok-4.6"
DEFAULT_EFFORT = "high"


def parse_args():
    parser = argparse.ArgumentParser(description="Check Cursor or run one bounded, read-only review.")
    parser.add_argument("repo", nargs="?", help="Target repository or worktree")
    parser.add_argument("prompt_file", nargs="?", help="UTF-8 review brief")
    parser.add_argument("agent_id", nargs="?", help="Finished agent to resume in the same workspace")
    parser.add_argument("--check", action="store_true", help="Check SDK and API key without starting a review")
    parser.add_argument("--api-key-file", default=DEFAULT_API_KEY_FILE, help="API key file; default: %(default)s")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Cursor model ID; default: %(default)s")
    parser.add_argument("--effort", default=DEFAULT_EFFORT, help="Model effort parameter; default: %(default)s")
    parser.add_argument("--timeout-seconds", type=int, default=960, help="Bounded wait time; default: 960")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Run polling interval; default: 10")
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("timeout and poll intervals must be positive")
    if not args.check and (not args.repo or not args.prompt_file):
        parser.error("repo and prompt_file are required unless --check is used")
    return args


def read_api_key(api_key_file):
    try:
        api_key = api_key_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        api_key = ""
    if api_key:
        return api_key
    detail = "is empty" if api_key_file.exists() else "does not exist"
    emit_error(
        "CREDENTIAL_UNAVAILABLE",
        f"INCOMPLETE: Cursor API key is not configured: {api_key_file} {detail}. "
        f"Generate an API key in Cursor and save only the key to {api_key_file}.",
    )
    return None


def main():
    args = parse_args()
    if SDK_IMPORT_ERROR is not None:
        emit_error(
            "SDK_UNAVAILABLE",
            "INCOMPLETE: Cursor SDK is unavailable in the dedicated runtime; "
            "run scripts/install_cursor_sdk.py.",
        )
        return 2

    api_key_file = Path(args.api_key_file).expanduser()
    api_key = read_api_key(api_key_file)
    if api_key is None:
        return 2
    if args.check:
        print(f"READY: Cursor SDK and API key are configured at {api_key_file}.")
        return 0

    try:
        repo = str(Path(args.repo).resolve(strict=True))
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        emit_error(
            "INVALID_LOCAL_INPUT",
            f"INCOMPLETE: Cursor review input is unavailable ({type(exc).__name__}).",
        )
        return 2
    model = ModelSelection(id=args.model, params=[ModelParameterValue(id="effort", value=args.effort)])
    options = AgentOptions(
        api_key=api_key,
        model=model,
        mode="plan",
        tools=READ_ONLY_TOOLS,
        local=LocalAgentOptions(cwd=repo),
    )
    try:
        with Client.launch_bridge(workspace=repo) as client:
            agent = client.agents.resume(args.agent_id, options) if args.agent_id else client.agents.create(options)
            run = agent.send(prompt, SendOptions(model=model))
            started = time.monotonic()
            last_status = "unknown"
            print(f"agent_id={agent.agent_id} run_id={run.id}", flush=True)
            while time.monotonic() - started < args.timeout_seconds:
                snapshot = client.agents.get_run(run.id)
                last_status = snapshot.status
                if last_status == "finished":
                    report = (snapshot.result or "").strip()
                    if report:
                        emit_report(report)
                        return 0
                    emit_error("MISSING_TERMINAL_REPORT", "INCOMPLETE: finished without terminal report")
                    return 2
                if last_status in TERMINAL_FAILURES:
                    emit_error("BACKEND_TERMINAL_FAILURE", f"INCOMPLETE: status={last_status}")
                    return 2
                print(f"status={last_status} elapsed={int(time.monotonic() - started)}s", flush=True)
                time.sleep(args.poll_seconds)
            elapsed = int(time.monotonic() - started)
            emit_error(
                "PROCESS_TIMEOUT",
                f"INCOMPLETE: timeout agent_id={agent.agent_id} run_id={run.id} status={last_status} elapsed={elapsed}s",
            )
            return 2
    except Exception as exc:
        emit_error("BRIDGE_ERROR", f"INCOMPLETE: Cursor bridge failed ({type(exc).__name__}).")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
