"""Cursor SDK read-only exploration of a controller-frozen worktree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time

REPORT_BEGIN = "FLOW_REVIEW_REPORT_BEGIN"
REPORT_END = "FLOW_REVIEW_REPORT_END"
ERROR_BEGIN = "FLOW_REVIEW_ERROR_BEGIN"
ERROR_END = "FLOW_REVIEW_ERROR_END"
DEFAULT_API_KEY_FILE = Path.home() / ".cursor-review" / "API_KEY"


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
    try:
        raw = read_bound_request(args.request_file, args.expected_request_digest)
        request = json.loads(raw)
        if request.get('schema_version') != 2 or request.get('capabilities') != capabilities():
            raise ValueError('invalid request')
        workspace = Path(args.workspace).resolve(strict=True)
        for item in request['files']:
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('outside view')
            read_bound_request(workspace / relative, item['digest'])
    except (OSError, ValueError, KeyError, TypeError):
        emit_error('INVALID_LOCAL_INPUT', 'INCOMPLETE: invalid frozen review view.')
        return 2
    try:
        from cursor_sdk import AgentOptions, Client, CustomTool, LocalAgentOptions, ModelParameterValue, ModelSelection, SendOptions
    except ImportError:
        emit_error('SDK_UNAVAILABLE', 'INCOMPLETE: Cursor SDK is unavailable in the review runtime.')
        return 2
    model = ModelSelection(id=args.model, params=[ModelParameterValue(id='effort', value=args.effort)])
    calls = []
    call_lock = threading.Lock()
    call_count = 0
    def execute_tool(name, arguments, context=None):
        nonlocal call_count
        with call_lock:
            if call_count >= 256:
                raise ValueError('review tool limit exceeded')
            call_count += 1
        try:
            result = explore_workspace(workspace, request['files'], name, arguments)
        except (ValueError, KeyError, TypeError, OSError):
            result = {'error':'READ_ONLY_SCOPE_REJECTED'}
        metadata = {'tool':name, 'result_digest':'sha256:' + hashlib.sha256(
            json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        if name == 'read_file' and 'error' not in result:
            entry = next(item for item in request['files'] if item['path'] == str(Path(arguments['path'])))
            metadata.update(path=entry['path'], source_digest=entry['digest'])
        with call_lock:
            calls.append(metadata)
        return result
    custom = {tool['name']: CustomTool(description=tool['description'], input_schema=tool['parameters'],
        execute=lambda arguments, context=None, name=tool['name']: execute_tool(name, arguments, context))
        for tool in REVIEW_TOOLS}
    options = AgentOptions(api_key=api_key, model=model, mode='plan',
                           tools=[], local=LocalAgentOptions(cwd=str(workspace),
                           setting_sources=['project'], dirs=[], custom_tools=custom))
    prompt = (
        'Independently review this frozen project workspace. Explore callers, tests, configuration and '
        'upstream artifacts; treat the root brief as a lead, not the only evidence. Use only list_files/read_file/search. '
        'Never write, run commands, fetch URLs or access paths outside this workspace. '
        'If excluded/insufficient evidence prevents a decision, return a blocking finding. '
        'Return one JSON object with exactly status,reviewed_digest,findings and no boundary markers. '
        'Each finding has exactly id,severity,summary,blocking_status,recurrence_key,evidence. '
        'PASSED cannot have blocking findings; FAILED requires blocking findings.\n'
        + request['prompt'] + '\nREVIEW MANIFEST\n' + json.dumps(request['manifest'], ensure_ascii=False))
    deadline = time.monotonic() + args.timeout_seconds
    try:
        with Client.launch_bridge(workspace=str(workspace)) as client:
            agent = client.agents.create(options)
            run = agent.send(prompt, SendOptions(model=model))
            while time.monotonic() < deadline:
                snapshot = client.agents.get_run(run.id)
                if snapshot.status == 'finished':
                    report = snapshot.result
                    if not isinstance(report, str) or not report.strip():
                        emit_error('PROTOCOL_ERROR', 'INCOMPLETE: Cursor returned no terminal report.')
                        return 2
                    return 0 if emit_report(report) else 2
                if snapshot.status in {'failed','error','cancelled','canceled','stopped','expired'}:
                    emit_error('UNKNOWN_BACKEND_FAILURE', 'INCOMPLETE: Cursor backend did not complete.')
                    return 2
                time.sleep(min(args.poll_seconds, max(0, deadline - time.monotonic())))
            emit_error('PROCESS_TIMEOUT', 'INCOMPLETE: Cursor review timed out.')
            return 2
    except Exception:
        emit_error('UNKNOWN_BACKEND_FAILURE', 'INCOMPLETE: Cursor bridge did not complete.')
        return 2
    finally:
        print('FLOW_REVIEW_EXPLORATION_BEGIN', file=sys.stderr)
        print(json.dumps({'schema_version':1, 'assurance':'LOCAL_READ_TOOLS', 'calls':calls}), file=sys.stderr)
        print('FLOW_REVIEW_EXPLORATION_END', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='Cursor frozen-worktree review')
    parser.add_argument('request_file', nargs='?')
    parser.add_argument('--workspace')
    parser.add_argument('--expected-request-digest')
    parser.add_argument('--check-capabilities', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--api-key-file', default=DEFAULT_API_KEY_FILE)
    parser.add_argument('--model', default='grok-4.6')
    parser.add_argument('--effort', default='high')
    parser.add_argument('--timeout-seconds', type=int, default=960)
    parser.add_argument('--poll-seconds', type=float, default=10)
    args = parser.parse_args()
    if args.check_capabilities:
        print(json.dumps(capabilities()))
        return 0
    if args.timeout_seconds <= 0 or args.poll_seconds <= 0:
        parser.error('timeouts must be positive')
    try:
        api_key = Path(args.api_key_file).expanduser().read_text().strip()
    except OSError:
        api_key = ''
    if not api_key:
        emit_error('CREDENTIAL_UNAVAILABLE', 'INCOMPLETE: configure ~/.cursor-review/API_KEY.')
        return 2
    if args.check:
        try:
            import cursor_sdk
        except ImportError:
            emit_error('SDK_UNAVAILABLE', 'INCOMPLETE: install cursor-sdk in the Cursor review runtime.')
            return 2
        print('READY: Cursor SDK and credential configured.')
        return 0
    if not args.request_file or not args.workspace or not args.expected_request_digest:
        parser.error('request_file, --workspace and --expected-request-digest are required')
    return run_review(args, api_key)


if __name__ == '__main__':
    raise SystemExit(main())
