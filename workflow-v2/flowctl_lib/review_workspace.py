"""Frozen whole-worktree review views and pre/post mutation detection."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from .errors import FlowctlError

CACHE_DIRS = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
              'node_modules', '.venv', 'venv', 'dist', 'build', '.tox', '.cache'}
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_VIEW_BYTES = 256 * 1024 * 1024


def contains_credentials(content):
    # Literal credentials, not ordinary variable references or environment reads.
    return bool(re.search(r'''(?ix)-----BEGIN\ .*PRIVATE\ KEY|Bearer\ [A-Za-z0-9._~+/=-]{16,}|(?<![\w-])["']?(?:api[_-]?key|password|passwd|access[_-]?token|client[_-]?secret|authorization)["']?\s*[:=]\s*(?:["'][^"'\n]{8,}["']|[A-Za-z0-9._~+/-]{16,}(?:\s|$))''', content))


def _digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _bookkeeping(root, controller_path):
    if controller_path is None:
        return set(), None
    controller = Path(controller_path).resolve()
    try:
        rel = controller.relative_to(root)
    except ValueError:
        return set(), None
    exact = {rel, rel.with_suffix(rel.suffix + '.lock'),
             rel.with_suffix(rel.suffix + '.txn.json'), rel.parent / 'flow-events.jsonl'}
    return exact, rel.parent / 'reviews'


def _inventory(root, controller_path=None):
    root = Path(root).resolve()
    exact, reports = _bookkeeping(root, controller_path)
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory).relative_to(root)
        links = [name for name in dirs if (Path(directory) / name).is_symlink()]
        dirs[:] = sorted(name for name in dirs if name not in CACHE_DIRS
                         and name not in links and (reports is None or parent / name != reports))
        for name in sorted(files + links):
            rel = parent / name
            if rel in exact:
                continue
            path = root / rel
            info = path.lstat()
            item = {'mode': stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):
                item.update(type='symlink', digest=_digest(os.readlink(path).encode()))
            elif stat.S_ISREG(info.st_mode):
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise FlowctlError('REVIEW_NON_REGULAR_FILE')
                    content = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        content.update(chunk)
                item.update(type='file', digest='sha256:' + content.hexdigest(), size=info.st_size)
            else:
                item.update(type='special')
            result[str(rel)] = item
    return result


def capture_review_snapshot(root, controller_path=None, *, git_facts=True):
    root = Path(root).resolve()
    payload = {'files': _inventory(root, controller_path)}
    if git_facts:
        def git(*args):
            value = subprocess.run(['git', '-C', str(root), *args], text=True, capture_output=True)
            if value.returncode:
                raise FlowctlError('SNAPSHOT_GIT_ERROR')
            return value.stdout.strip()
        payload['head'] = git('rev-parse', 'HEAD')
        index = Path(git('rev-parse', '--git-path', 'index'))
        if not index.is_absolute():
            index = root / index
        payload['index_digest'] = _digest(index.read_bytes()) if index.exists() else None
    payload['snapshot_digest'] = _digest(json.dumps(payload, sort_keys=True,
        ensure_ascii=False, separators=(',', ':')).encode())
    return payload


def verify_review_snapshot(root, controller_path, expected, *, git_facts=True):
    actual = capture_review_snapshot(root, controller_path, git_facts=git_facts)
    if actual['snapshot_digest'] != expected['snapshot_digest']:
        changes = sorted(path for path in set(expected['files']) | set(actual['files'])
                         if expected['files'].get(path) != actual['files'].get(path))
        raise FlowctlError('REVIEW_WORKTREE_MUTATED', changed_paths=changes[:100],
                           expected=expected['snapshot_digest'], actual=actual['snapshot_digest'])
    return actual


def normalize_review_exclusions(exclusions):
    if exclusions is None:
        return []
    if not isinstance(exclusions, list):
        raise FlowctlError('INVALID_REVIEW_EXCLUSIONS')
    result = []
    for item in exclusions:
        if (not isinstance(item, dict) or set(item) != {'path', 'kind', 'reason'}
                or not isinstance(item['path'], str) or not item['path'].strip()
                or item['kind'] not in ('file', 'directory')
                or not isinstance(item['reason'], str) or not item['reason'].strip()):
            raise FlowctlError('INVALID_REVIEW_EXCLUSIONS')
        if any(character in item['path'] for character in '*?[]'):
            raise FlowctlError('INVALID_REVIEW_EXCLUSIONS')
        path = Path(item['path'])
        if path.is_absolute() or not path.parts or '..' in path.parts or '\x00' in item['path']:
            raise FlowctlError('REVIEW_PATH_ESCAPE')
        result.append({'path': str(path), 'kind': item['kind'], 'reason': item['reason'].strip()})
    return sorted(result, key=lambda item: (item['path'], item['kind'], item['reason']))


def create_review_view(root, destination, controller_path=None, *, exclusions=None):
    from .review_package import read_regular
    root, destination = Path(root).resolve(), Path(destination)
    exclusions = normalize_review_exclusions(exclusions)
    destination.mkdir(parents=True)
    files, excluded, total = [], [], 0
    for path, identity in _inventory(root, controller_path).items():
        rel = Path(path)
        selected = next((item for item in exclusions if rel == Path(item['path']) or
                         item['kind'] == 'directory' and Path(item['path']) in rel.parents), None)
        if selected:
            excluded.append({'path': path, 'reason': 'DECLARED_EXCLUSION', 'detail': selected['reason']})
            continue
        reason = None
        if '.git' in rel.parts:
            reason = 'VCS_METADATA'
        elif '.cursor' in rel.parts or rel.name == '.mcp.json':
            reason = 'REVIEWER_CONFIGURATION'
        elif any(part.startswith('.env') or re.search(
                r'(?i)(credential|secret|private[_-]?key|id_rsa|api_key|raw[_-]?(production|replay)|\.pem$)', part)
                for part in rel.parts):
            reason = 'SENSITIVE_PATH'
        elif identity['type'] != 'file':
            reason = 'NON_REGULAR'
        elif identity['size'] > MAX_FILE_BYTES:
            reason = 'OVERSIZED'
        if reason is None:
            raw = read_regular(root, rel)
            if _digest(raw) != identity['digest']:
                raise FlowctlError('REVIEW_PACKAGE_DRIFT')
            try:
                content = raw.decode('utf-8')
            except UnicodeError:
                reason = 'BINARY'
            else:
                if '\x00' in content:
                    reason = 'BINARY'
                elif contains_credentials(content):
                    reason = 'SENSITIVE_CONTENT'
        if reason is not None:
            excluded.append({'path': path, 'reason': reason})
            continue
        total += len(raw)
        if total > MAX_VIEW_BYTES:
            raise FlowctlError('REVIEW_VIEW_TOO_LARGE')
        output = destination / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw)
        output.chmod(0o444)
        files.append({'path': path, 'source_digest': identity['digest'], 'digest': _digest(raw)})
    return {'files': files, 'excluded': excluded}
