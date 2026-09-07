import argparse
import time
from pathlib import Path

from cursor_sdk import AgentOptions, Client, LocalAgentOptions, ModelParameterValue, ModelSelection, SendOptions


TERMINAL_FAILURES = {"failed", "error", "cancelled", "canceled", "stopped", "expired"}
READ_ONLY_TOOLS = ["read", "grep", "glob", "ls"]


def parse_args():
    parser = argparse.ArgumentParser(description="Run one bounded, read-only Cursor review.")
    parser.add_argument("repo", help="Target repository or worktree")
    parser.add_argument("prompt_file", help="UTF-8 review brief")
    parser.add_argument("agent_id", nargs="?", help="Finished agent to resume in the same workspace")
    parser.add_argument("--api-key-file", required=True, help="Path to an API key file; its value is never printed")
    parser.add_argument("--model", required=True, help="Cursor model ID configured by the caller")
    parser.add_argument("--effort", default="high", help="Model effort parameter")
    parser.add_argument("--timeout-seconds", type=int, default=960, help="Bounded wait time; default: 960")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Run polling interval; default: 10")
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("timeout and poll intervals must be positive")
    return args


def main():
    args = parse_args()
    repo = str(Path(args.repo).resolve(strict=True))
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    api_key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    if not api_key:
        raise RuntimeError("API key file is empty")

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
