#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


REPORT_BEGIN = "FLOW_REVIEW_REPORT_BEGIN"
REPORT_END = "FLOW_REVIEW_REPORT_END"
ERROR_BEGIN = "FLOW_REVIEW_ERROR_BEGIN"
ERROR_END = "FLOW_REVIEW_ERROR_END"

DEFAULT_API_KEY_FILE = Path.home() / ".ibrain-review" / "API_KEY"
DEFAULT_MODEL = "glm-5.3"
MODELS_URL = "http://ibrain.qiyi.domain/v1/models"
RESPONSES_BASE_URL = "http://ibrain.qiyi.domain/v1"
RESPONSES_URL = f"{RESPONSES_BASE_URL}/responses"
PROVIDER_ID = "ibrain_review"


def emit_error(code, message):
    print(message, file=sys.stderr, flush=True)
    print(ERROR_BEGIN, file=sys.stderr, flush=True)
    print(json.dumps({"schema_version": 1, "code": code}), file=sys.stderr, flush=True)
    print(ERROR_END, file=sys.stderr, flush=True)


def emit_report(report):
    print(REPORT_BEGIN, flush=True)
    print(report, flush=True)
    print(REPORT_END, flush=True)


def read_api_key(path):
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        value = ""
    if value:
        return value
    detail = "is empty" if path.exists() else "does not exist"
    emit_error(
        "CREDENTIAL_UNAVAILABLE",
        f"INCOMPLETE: iBrain API key is not configured: {path} {detail}. "
        f"Save only the key to {path}.",
    )
    return None


def request_json(url, api_key, *, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-job-id": "codex-ibrain-review-check",
        },
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_models(api_key, timeout):
    payload = request_json(MODELS_URL, api_key, timeout=timeout)
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("missing data array")
    ids = [item.get("id") for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]
    if not ids:
        raise ValueError("model list is empty")
    return ids


def parse_args():
    parser = argparse.ArgumentParser(description="Check iBrain or run one bounded read-only review.")
    parser.add_argument("repo", nargs="?", help="Target repository or worktree")
    parser.add_argument("prompt_file", nargs="?", help="UTF-8 review brief")
    parser.add_argument("--check", action="store_true", help="Check key, model discovery, and Responses API")
    parser.add_argument("--list-models", action="store_true", help="Print current model IDs, one per line")
    parser.add_argument("--api-key-file", default=DEFAULT_API_KEY_FILE, help="API key file; default: %(default)s")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="iBrain model ID; default: %(default)s")
    parser.add_argument("--timeout-seconds", type=int, default=960, help="Review timeout; default: 960")
    parser.add_argument("--network-timeout-seconds", type=int, default=30, help="API probe timeout; default: 30")
    parser.add_argument("--codex-bin", default="codex", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.network_timeout_seconds <= 0:
        parser.error("timeouts must be positive")
    if not (args.check or args.list_models) and (not args.repo or not args.prompt_file):
        parser.error("repo and prompt_file are required unless --check or --list-models is used")
    return args


def check_backend(api_key, model, timeout):
    models = discover_models(api_key, timeout)
    if model not in models:
        emit_error("MODEL_UNAVAILABLE", f"INCOMPLETE: iBrain model {model!r} is not available.")
        return 2
    response = request_json(
        RESPONSES_URL,
        api_key,
        payload={"model": model, "input": "Reply exactly OK", "stream": False, "max_output_tokens": 256},
        timeout=timeout,
    )
    if response.get("error") or response.get("status") != "completed":
        emit_error("RESPONSES_UNAVAILABLE", "INCOMPLETE: iBrain Responses API did not complete the probe.")
        return 2
    print(f"READY: iBrain Responses API and model {model} are available.")
    return 0


def review_command(args, repo, output_file):
    return [
        str(args.codex_bin), "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
        "-C", repo, "-s", "read-only", "-c", 'approval_policy="never"',
        "-c", f'model_provider="{PROVIDER_ID}"',
        "-c", f'model_providers.{PROVIDER_ID}.name="iBrain Review"',
        "-c", f'model_providers.{PROVIDER_ID}.base_url="{RESPONSES_BASE_URL}"',
        "-c", f'model_providers.{PROVIDER_ID}.wire_api="responses"',
        "-c", f'model_providers.{PROVIDER_ID}.env_key="IQIYI_IBRAIN_API_KEY"',
        "-m", args.model, "-o", str(output_file),
    ]


def run_review(args, api_key):
    try:
        repo = str(Path(args.repo).resolve(strict=True))
        if not Path(repo).is_dir():
            raise OSError("repository is not a directory")
        brief = Path(args.prompt_file).read_text(encoding="utf-8").strip()
        if not brief:
            raise ValueError("review brief is empty")
    except (OSError, UnicodeError, ValueError):
        emit_error("INVALID_LOCAL_INPUT", "INCOMPLETE: iBrain review input is unavailable or empty.")
        return 2

    prompt = (
        "Perform a bounded, read-only repository review. Use only the supplied scope and the target "
        "worktree. Do not edit files. Lead with concrete findings and cite file paths and lines. "
        "Follow the finding schema in the brief exactly; if there are no findings, say so explicitly.\n\n"
        "REVIEW BRIEF\n" + brief
    )
    env = dict(os.environ, IQIYI_IBRAIN_API_KEY=api_key)
    try:
        with tempfile.TemporaryDirectory(prefix="ibrain-review-") as temp_dir:
            output_file = Path(temp_dir) / "last-message.txt"
            process = subprocess.Popen(
                review_command(args, repo, output_file),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=True,
            )
            try:
                process.communicate(input=prompt, timeout=args.timeout_seconds)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                emit_error("PROCESS_TIMEOUT", f"INCOMPLETE: iBrain review timed out after {args.timeout_seconds}s.")
                return 2
            report = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
    except (OSError, UnicodeError):
        emit_error("PROCESS_UNAVAILABLE", "INCOMPLETE: Codex review process could not be started or read.")
        return 2

    if process.returncode != 0:
        emit_error("BACKEND_PROCESS_FAILURE", f"INCOMPLETE: iBrain review process exited {process.returncode}.")
        return 2
    if not report:
        emit_error("MISSING_TERMINAL_REPORT", "INCOMPLETE: iBrain review finished without a terminal report.")
        return 2
    emit_report(report)
    return 0


def main():
    args = parse_args()
    api_key = read_api_key(Path(args.api_key_file).expanduser())
    if api_key is None:
        return 2
    try:
        if args.list_models:
            for model in discover_models(api_key, args.network_timeout_seconds):
                print(model)
            return 0
        if args.check:
            return check_backend(api_key, args.model, args.network_timeout_seconds)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
        emit_error("BACKEND_UNAVAILABLE", "INCOMPLETE: iBrain API discovery or probe failed.")
        return 2
    return run_review(args, api_key)


if __name__ == "__main__":
    raise SystemExit(main())
