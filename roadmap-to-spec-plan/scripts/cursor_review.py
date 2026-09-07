import argparse
import sys
import time
from pathlib import Path

from cursor_sdk import AgentOptions, Client, LocalAgentOptions, ModelParameterValue, ModelSelection, SendOptions


TERMINAL_FAILURES = {"failed", "error", "cancelled", "canceled", "stopped", "expired"}
READ_ONLY_TOOLS = ["read", "grep", "glob", "ls"]
DEFAULT_API_KEY_FILE = Path.home() / ".cursor-review" / "API_KEY"
DEFAULT_MODEL = "grok-4.6"
DEFAULT_EFFORT = "high"


def parse_args():
    parser = argparse.ArgumentParser(description="Run one bounded, read-only Cursor review.")
    parser.add_argument("repo", help="Target repository or worktree")
    parser.add_argument("prompt_file", help="UTF-8 review brief")
    parser.add_argument("agent_id", nargs="?", help="Finished agent to resume in the same workspace")
    parser.add_argument("--api-key-file", default=DEFAULT_API_KEY_FILE, help="API key file; default: %(default)s")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Cursor model ID; default: %(default)s")
    parser.add_argument("--effort", default=DEFAULT_EFFORT, help="Model effort parameter; default: %(default)s")
    parser.add_argument("--timeout-seconds", type=int, default=960, help="Bounded wait time; default: 960")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Run polling interval; default: 10")
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("timeout and poll intervals must be positive")
    return args


def read_api_key(api_key_file):
    try:
        api_key = api_key_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        print(
            f"INCOMPLETE: Cursor API key is not configured at {api_key_file}. Generate an API key in Cursor, "
            f"save only the key to {DEFAULT_API_KEY_FILE}, then rerun this command.",
            file=sys.stderr,
        )
        return None
    if api_key:
        return api_key
    print(
        f"INCOMPLETE: Cursor API key is not configured: {api_key_file} is empty. Generate an API key in Cursor, "
        f"save only the key to {DEFAULT_API_KEY_FILE}, then rerun this command.",
        file=sys.stderr,
    )
    return None


def main():
    args = parse_args()
    repo = str(Path(args.repo).resolve(strict=True))
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    api_key_file = Path(args.api_key_file).expanduser()
    api_key = read_api_key(api_key_file)
    if api_key is None:
        return 2

    model = ModelSelection(
        id=args.model,
        params=[ModelParameterValue(id="effort", value=args.effort)],
    )
    options = AgentOptions(
        api_key=api_key,
        model=model,
        mode="plan",
        tools=["read", "grep", "glob", "ls"],
        local=LocalAgentOptions(cwd=repo),
    )
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
                    print(report, flush=True)
                    return 0
                print("INCOMPLETE: finished without terminal report", flush=True)
                return 2
            if last_status in TERMINAL_FAILURES:
                print(f"INCOMPLETE: status={last_status}", flush=True)
                return 2
            print(f"status={last_status} elapsed={int(time.monotonic() - started)}s", flush=True)
            time.sleep(args.poll_seconds)
        elapsed = int(time.monotonic() - started)
        print(f"INCOMPLETE: timeout agent_id={agent.agent_id} run_id={run.id} status={last_status} elapsed={elapsed}s", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
