#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
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
def capabilities():
    return {"workspace_exploration": True, "write_tools": False}


def emit_error(code, message):
    print(message, file=sys.stderr, flush=True)
    print(ERROR_BEGIN, file=sys.stderr, flush=True)
    print(json.dumps({"schema_version": 1, "code": code}), file=sys.stderr, flush=True)
    print(ERROR_END, file=sys.stderr, flush=True)


def emit_report(report):
    """Emit one transport-owned frame, collapsing identical model-owned frames."""
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    stripped = report.strip()
    begin_count = stripped.count(REPORT_BEGIN)
    end_count = stripped.count(REPORT_END)
    if begin_count or end_count:
        if begin_count != end_count or begin_count == 0:
            emit_error("PROTOCOL_ERROR", "INCOMPLETE: malformed terminal review framing.")
            return False
        values = []
        offset = 0
        for _ in range(begin_count):
            marker = stripped.find(REPORT_BEGIN, offset)
            if marker < 0 or stripped[offset:marker].strip():
                emit_error("PROTOCOL_ERROR", "INCOMPLETE: unexpected terminal review output.")
                return False
            start = marker + len(REPORT_BEGIN)
            end = stripped.find(REPORT_END, start)
            if end < start:
                emit_error("PROTOCOL_ERROR", "INCOMPLETE: malformed terminal review framing.")
                return False
            candidate = stripped[start:end].strip()
            try:
                values.append(json.loads(candidate, object_pairs_hook=unique_object))
            except (json.JSONDecodeError, ValueError):
                emit_error("PROTOCOL_ERROR", "INCOMPLETE: malformed terminal review report.")
                return False
            offset = end + len(REPORT_END)
        if stripped[offset:].strip() or any(value != values[0] for value in values[1:]):
            emit_error("CONFLICTING_TERMINAL_REPORT", "INCOMPLETE: conflicting terminal review reports.")
            return False
        report = json.dumps(values[0], ensure_ascii=False, separators=(",", ":"))
    print(REPORT_BEGIN, flush=True)
    print(report, flush=True)
    print(REPORT_END, flush=True)
    return True


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
    parser.add_argument("request_file", nargs="?", help="Materialized JSON request")
    parser.add_argument("--workspace", help="Controller-frozen read-only review view")
    parser.add_argument("--expected-request-digest")
    parser.add_argument("--check-capabilities", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check key, model discovery, and Responses API")
    parser.add_argument("--list-models", action="store_true", help="Print current model IDs, one per line")
    parser.add_argument("--api-key-file", default=DEFAULT_API_KEY_FILE, help="API key file; default: %(default)s")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="iBrain model ID; default: %(default)s")
    parser.add_argument("--timeout-seconds", type=int, default=960, help="Review timeout; default: 960")
    parser.add_argument("--network-timeout-seconds", type=int, default=30, help="API probe timeout; default: 30")
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.network_timeout_seconds <= 0:
        parser.error("timeouts must be positive")
    if not (args.check or args.list_models or args.check_capabilities) and (not args.request_file or not args.workspace or not args.expected_request_digest):
        parser.error("request_file, --workspace and --expected-request-digest are required")
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


def read_bound_request(path, expected_digest):
    """Read once through no-follow descriptors; transmit these exact verified bytes."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('invalid request path')
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        data_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(data_fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('non-regular request')
            raw = stream.read(4 * 1024 * 1024 + 1)
    finally:
        os.close(fd)
    if len(raw) > 4 * 1024 * 1024 or 'sha256:' + hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError('request digest mismatch')
    return raw


REVIEW_TOOLS = [
    {"type":"function", "name":"list_files", "description":"List frozen project files, with pagination.",
     "parameters":{"type":"object","properties":{"offset":{"type":"integer"}},"additionalProperties":False}},
    {"type":"function", "name":"read_file", "description":"Read a frozen project file with line numbers.",
     "parameters":{"type":"object","properties":{"path":{"type":"string"},"start_line":{"type":"integer"},
                    "max_lines":{"type":"integer"}},"required":["path"],"additionalProperties":False}},
    {"type":"function", "name":"search", "description":"Literal text search over frozen project files.",
     "parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"],
                   "additionalProperties":False}},
]


def read_frozen_file(workspace, files, path):
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('outside frozen workspace')
    entry = next((item for item in files if item['path'] == str(relative)), None)
    if entry is None:
        raise ValueError('undeclared frozen file')
    return read_bound_request(Path(workspace) / relative, entry['digest']).decode('utf-8')


def explore_workspace(workspace, files, operation, arguments):
    if operation == 'list_files':
        offset = arguments.get('offset', 0)
        if type(offset) is not int or offset < 0:
            raise ValueError('invalid offset')
        return {'files':[item['path'] for item in files[offset:offset + 500]],
                'next_offset': offset + 500 if offset + 500 < len(files) else None}
    if operation == 'read_file':
        start, count = arguments.get('start_line', 1), arguments.get('max_lines', 200)
        if type(start) is not int or type(count) is not int or start < 1 or not 1 <= count <= 500:
            raise ValueError('invalid line range')
        lines = read_frozen_file(workspace, files, arguments['path']).splitlines()
        return {'path':arguments['path'], 'total_lines':len(lines),
                'content':'\n'.join(f'{i + 1}: {lines[i]}' for i in range(start - 1, min(len(lines), start - 1 + count)))}
    if operation == 'search':
        query = arguments['query']
        if not isinstance(query, str) or not query or len(query) > 500:
            raise ValueError('invalid search')
        matches = []
        for item in files:
            for number, line in enumerate(read_frozen_file(workspace, files, item['path']).splitlines(), 1):
                if query in line:
                    matches.append({'path':item['path'], 'line':number, 'text':line[:1000]})
                    if len(matches) == 100:
                        return {'matches':matches, 'truncated':True}
        return {'matches':matches, 'truncated':False}
    raise ValueError('unsupported operation')


def run_review(args, api_key):
    exploration = []
    deadline = time.monotonic() + args.timeout_seconds
    try:
        raw = read_bound_request(args.request_file, args.expected_request_digest)
        request = json.loads(raw.decode('utf-8'))
        if (set(request) != {"schema_version", "manifest", "prompt", "files", "capabilities"}
                or request["schema_version"] != 2 or request["capabilities"] != capabilities()):
            raise ValueError("invalid request")
        workspace = Path(args.workspace).resolve(strict=True)
        for item in request['files']:
            read_frozen_file(workspace, request['files'], item['path'])
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError):
        emit_error('INVALID_LOCAL_INPUT', 'INCOMPLETE: invalid frozen review input.')
        return 2
    try:
        instructions = (
            "Perform an independent read-only review. Explore the frozen workspace with list_files, "
            "read_file and search rather than trusting the root's summary. No writes, shell or external "
            "reads are available. Inspect target, upstream artifacts, callers and tests as needed. "
            "Disclose declared data exclusions as coverage limits; exclusion alone is non-blocking. "
            "Only demonstrably missing approval-critical evidence warrants a BLOCKING finding; never guess evidence or request excluded data. "
            "Return exactly one JSON object with status PASSED/FAILED/INCOMPLETE, reviewed_digest, "
            "and findings. Each finding has exactly id,severity,summary,blocking_status,recurrence_key,evidence. "
            "PASSED cannot have blocking findings; FAILED requires blocking findings. "
            "Do not emit report boundary markers. Reviewed digest: " + request['manifest']['artifact_digest'])
        transcript = [{"role":"user","content":request['prompt'] + "\nREVIEW MANIFEST\n" +
                       json.dumps(request['manifest'], ensure_ascii=False)}]
        calls = 0
        for _ in range(64):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            response = request_json(RESPONSES_URL, api_key,
                payload={"model":args.model, "input":transcript, "instructions":instructions,
                         "tools":REVIEW_TOOLS, "stream":False}, timeout=remaining)
            if response.get("error") or response.get("status") != "completed":
                emit_error("UNKNOWN_BACKEND_FAILURE", "INCOMPLETE: iBrain backend did not complete.")
                return 2
            output = response.get('output', [])
            functions = [item for item in output if item.get('type') == 'function_call']
            if functions:
                transcript.extend(output)
                for call in functions:
                    calls += 1
                    if calls > 256:
                        emit_error("PROTOCOL_ERROR", "INCOMPLETE: exploration call limit exhausted.")
                        return 2
                    try:
                        arguments = json.loads(call['arguments'])
                        value = explore_workspace(workspace, request['files'], call['name'], arguments)
                        result = json.dumps(value, ensure_ascii=False)
                    except (ValueError, KeyError, TypeError):
                        result = json.dumps({'error':'READ_ONLY_SCOPE_REJECTED'})
                    metadata = {'tool':call.get('name'), 'call_id':call.get('call_id'),
                        'result_digest':'sha256:' + hashlib.sha256(result.encode()).hexdigest()}
                    if call.get('name') == 'read_file' and 'error' not in json.loads(result):
                        entry = next(item for item in request['files'] if item['path'] == str(Path(arguments['path'])))
                        metadata.update(path=entry['path'], source_digest=entry['digest'])
                    exploration.append(metadata)
                    transcript.append({'type':'function_call_output', 'call_id':call['call_id'], 'output':result})
                continue
            report = response.get("output_text") or "".join(
                part.get("text", "") for item in output if item.get("type") == "message"
                for part in item.get("content", []) if part.get("type") == "output_text")
            if not isinstance(report, str) or not report.strip():
                emit_error("PROTOCOL_ERROR", "INCOMPLETE: iBrain returned no terminal report.")
                return 2
            return 0 if emit_report(report) else 2
        emit_error("PROTOCOL_ERROR", "INCOMPLETE: exploration round limit exhausted.")
        return 2
    except TimeoutError:
        emit_error('PROCESS_TIMEOUT', 'INCOMPLETE: iBrain Responses request timed out.')
        return 2
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        emit_error("UNKNOWN_BACKEND_FAILURE", "INCOMPLETE: iBrain review could not complete.")
        return 2
    finally:
        print('FLOW_REVIEW_EXPLORATION_BEGIN', file=sys.stderr)
        print(json.dumps({'schema_version':1,'assurance':'LOCAL_READ_TOOLS',
                          'calls':exploration}), file=sys.stderr)
        print('FLOW_REVIEW_EXPLORATION_END', file=sys.stderr)


def main():
    args = parse_args()
    if args.check_capabilities:
        print(json.dumps(capabilities()))
        return 0
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
