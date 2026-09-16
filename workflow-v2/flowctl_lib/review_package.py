"""Materialized, single-use review input. No repository is a model workspace."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from uuid import uuid4

from .errors import FlowctlError

CAPABILITIES = {'local_tools': False, 'implicit_indexing': False}
MAX_BYTES = 4 * 1024 * 1024


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def validate_capabilities(value):
    if (not isinstance(value, dict) or set(value) != set(CAPABILITIES)
            or any(value[key] is not False for key in CAPABILITIES)):
        raise FlowctlError('BACKEND_UNAVAILABLE')


def active_authorization(state, backend, stage):
    auth = state['authorizations']['external_review']
    if auth['status'] != 'GRANTED':
        raise FlowctlError('EXTERNAL_REVIEW_AUTHORIZATION_REQUIRED')
    if any(auth.get(key) != state.get(key) for key in ('issue_id', 'run_id', 'worktree_path')):
        raise FlowctlError('AUTHORIZATION_IDENTITY_DRIFT')
    if backend not in auth['allowed_backends'] or stage not in auth['allowed_stages']:
        raise FlowctlError('AUTHORIZATION_SCOPE_MISMATCH')
    if stage != state['current_stage']:
        raise FlowctlError('STAGE_MISMATCH')
    return auth


def relative_path(root, path):
    path = Path(path)
    if '..' in path.parts:
        raise FlowctlError('REVIEW_PATH_ESCAPE')
    if path.is_absolute():
        # Resolve only the admitted root alias (e.g. macOS /var -> /private/var).
        try:
            path = path.relative_to(root)
        except ValueError:
            for parent in path.parents:
                if parent.resolve() == root.resolve():
                    path = path.relative_to(parent)
                    break
            else:
                raise FlowctlError('REVIEW_PATH_ESCAPE') from None
    if not path.parts or any(part == '.git' or part.startswith('.env') for part in path.parts):
        raise FlowctlError('REVIEW_EXCLUDED_PATH')
    return path


def read_regular(root, relative):
    """Walk directory descriptors without following symlinks, including race replacements."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        file_fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise FlowctlError('REVIEW_NON_REGULAR_FILE')
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise FlowctlError('REVIEW_PACKAGE_TOO_LARGE')
        return raw
    except OSError:
        raise FlowctlError('REVIEW_INPUT_UNAVAILABLE') from None
    finally:
        os.close(fd)


def check_content(raw, *, prompt=False):
    try:
        value = raw.decode('utf-8')
    except UnicodeError:
        raise FlowctlError('REVIEW_INVALID_UTF8') from None
    if re.search(r'''(?ix)(?<![\w-])["']?(?:api[_-]?key|password|passwd|token|authorization|secret|access[_-]?token|client[_-]?secret)["']?\s*[:=]\s*\S+|Bearer\s+\S+|-----BEGIN\ .*PRIVATE\ KEY|raw[_\ -]production[_\ -]data''', value):
        raise FlowctlError('REVIEW_SENSITIVE_CONTENT')
    if prompt and re.search(r'(?:^|\s)/(?:[^\s]+)|\.\./', value):
        raise FlowctlError('REVIEW_PROMPT_PATH_ESCAPE')
    return value


class ReviewPackage:
    def __init__(self, root, manifest, request_bytes):
        self.root = root
        self.manifest = manifest
        self.request_path = root / 'request.json'
        self.digest = digest(request_bytes)
        self.outbound_prompt = json.loads(request_bytes)['prompt']

    def verify(self):
        if set(self.root.iterdir()) != {self.request_path}:
            raise FlowctlError('REVIEW_PACKAGE_DRIFT')
        raw = read_regular(self.root, Path('request.json'))
        if digest(raw) != self.digest:
            raise FlowctlError('REVIEW_PACKAGE_DRIFT')

    def cleanup(self):
        try:
            if self.root.exists():
                self.root.chmod(0o700)
                shutil.rmtree(self.root)
        except OSError:
            raise FlowctlError('REVIEW_PACKAGE_CLEANUP_FAILED') from None


def create_review_package(state, backend, stage, artifact_key, prompt_path, paths):
    auth = active_authorization(state, backend, stage)
    root = Path(state['worktree_path'])
    artifact = state['artifacts'].get(artifact_key)
    if not artifact:
        raise FlowctlError('ARTIFACT_NOT_REGISTERED')
    # Registered artifacts must belong to the upstream chain; other explicit
    # paths are bounded source/test/evidence context, never a workspace grant.
    allowed = {artifact_key}
    pending = [artifact_key]
    while pending:
        current = state['artifacts'][pending.pop()]
        for key, item in state['artifacts'].items():
            ref = current.get('upstream', {}).get(item.get('type'))
            if ref and ref.get('digest') == item['digest'] and key not in allowed:
                allowed.add(key)
                pending.append(key)
    declared = {str(relative_path(root, state['artifacts'][key]['path'])): state['artifacts'][key]
                for key in allowed}
    prompt = check_content(read_regular(root, relative_path(root, prompt_path)), prompt=True)
    files = []
    hashes = []
    seen = set()
    total_bytes = len(prompt.encode('utf-8'))
    if not isinstance(paths, list) or not paths or len(paths) > 100:
        raise FlowctlError('INVALID_REVIEW_MANIFEST')
    from .snapshot import _git, verify_recorded_snapshot
    if stage == 'flow-code':
        source_snapshot = verify_recorded_snapshot(state, artifact_key)
    else:
        source_snapshot = {'head': _git(root, 'rev-parse', 'HEAD').strip(),
                           'status_digest': digest(_git(root, 'status', '--short', '--untracked-files=all').encode())}
    for path in paths:
        rel = relative_path(root, path)
        if str(rel) in seen:
            raise FlowctlError('REVIEW_UNDECLARED_FILE')
        ignored = subprocess.run(['git', '-C', str(root), 'check-ignore', '--quiet', '--', str(rel)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if ignored.returncode != 1:
            raise FlowctlError('REVIEW_EXCLUDED_PATH')
        if any(re.search(r'(?i)(credential|secret|private[_-]?key|id_rsa|\.pem$)', part) for part in rel.parts):
            raise FlowctlError('REVIEW_EXCLUDED_PATH')
        if str(rel) not in declared and any(str(relative_path(root, a['path'])) == str(rel) for a in state['artifacts'].values()):
            raise FlowctlError('REVIEW_UNDECLARED_FILE')
        seen.add(str(rel))
        raw = read_regular(root, rel)
        total_bytes += len(raw)
        if total_bytes > MAX_BYTES:
            raise FlowctlError('REVIEW_PACKAGE_TOO_LARGE')
        content = check_content(raw)
        artifact_hashes = {}
        if str(rel) in declared:
            expected = declared[str(rel)]['digest']
            from .artifacts import _split_regions, INTEGRITY_BEGIN, INTEGRITY_END
            body, integrity, approval = _split_regions(content)
            if digest(body.encode('utf-8')) != expected:
                raise FlowctlError('ARTIFACT_DRIFT')
            artifact_hashes = {'artifact_digest': expected, 'approval_digest': digest(approval.encode())}
            # Location metadata is local bookkeeping outside the approved body.
            neutral = re.sub(r'(?m)^(\s*(?:[-*]\s*)?(?:resolved_path|path_source|path_rule):).*$', r'\1 [local metadata omitted]', integrity)
            if any(Path(value.strip(' `')).is_absolute() for value in re.findall(r'(?m)^\s*(?:resolved_path|path_source|path_rule):\s*(.+)$', integrity)):
                content = content.replace(INTEGRITY_BEGIN + '\n' + integrity + INTEGRITY_END,
                                          INTEGRITY_BEGIN + '\n' + neutral + INTEGRITY_END)
        if str(root) in content or str(root.resolve()) in content:
            raise FlowctlError('REVIEW_WORKSPACE_PATH_FORBIDDEN')
        files.append({'path': str(rel), 'content': content})
        hashes.append({'path': str(rel), 'digest': digest(content.encode('utf-8')),
                       'source_digest': digest(raw), **artifact_hashes})
    if str(relative_path(root, artifact['path'])) not in seen:
        raise FlowctlError('REVIEW_ARTIFACT_MISSING')
    manifest = dict(backend=backend, stage=stage, artifact_key=artifact_key,
                    artifact_digest=artifact['digest'], authorization_id=auth['authorization_id'],
                    authorization_revision=auth['revision'], prompt_digest=digest(prompt.encode('utf-8')),
                    files=hashes, source_snapshot=source_snapshot)
    raw = canonical(dict(schema_version=1, manifest=manifest, prompt=prompt,
                         files=files, capabilities=CAPABILITIES))
    if len(raw) > MAX_BYTES:
        raise FlowctlError('REVIEW_PACKAGE_TOO_LARGE')
    package_root = Path(tempfile.mkdtemp(prefix='flow-review-')).resolve()
    package = ReviewPackage(package_root, manifest, raw)
    try:
        package.request_path.write_bytes(raw)
        package.request_path.chmod(0o400)
        package.root.chmod(0o500)
    except OSError:
        package.cleanup()
        raise FlowctlError('REVIEW_PACKAGE_WRITE_FAILED') from None
    return package


def bind_package(state, package):
    manifest = package.manifest
    auth = active_authorization(state, manifest['backend'], manifest['stage'])
    if (auth['authorization_id'] != manifest['authorization_id']
            or auth['revision'] != manifest['authorization_revision']):
        raise FlowctlError('AUTHORIZATION_BINDING_STALE')
    package.verify()
    binding = dict(binding_id=str(uuid4()), authorization_id=auth['authorization_id'],
                   authorization_revision=auth['revision'], package_digest=package.digest,
                   backend=manifest['backend'], status='BOUND')
    auth['bindings'].append(binding)
    return binding


def consume_binding(state, package, binding_id):
    auth = active_authorization(state, package.manifest['backend'], package.manifest['stage'])
    binding = next((b for b in auth['bindings'] if b['binding_id'] == binding_id), None)
    if (not binding or binding['status'] != 'BOUND' or binding['package_digest'] != package.digest
            or binding['authorization_id'] != auth['authorization_id']
            or binding['authorization_revision'] != auth['revision']):
        raise FlowctlError('AUTHORIZATION_BINDING_STALE')
    package.verify()
    binding['status'] = 'CONSUMED'


def validate_review_manifest(state_path, manifest_path, expected_revision):
    from .state import locked_state, commit_state, reject_if_paused, audit_state
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        if set(manifest) != {'backend', 'stage', 'artifact_key', 'prompt_path', 'paths'}:
            raise ValueError('invalid manifest')
    except (OSError, ValueError, TypeError):
        raise FlowctlError('INVALID_REVIEW_MANIFEST') from None
    with locked_state(state_path, expected_revision) as state:
        reject_if_paused(state)
        audit_state(state)
        package = create_review_package(state, **manifest)
        try:
            binding = bind_package(state, package)
            binding['input_manifest'] = manifest
            # The request is rematerialized and rehashed by review before consumption.
            result = dict(binding)
        finally:
            package.cleanup()
        state = commit_state(state_path, state, 'REVIEW_PACKAGE_VALIDATED', result)
        return {**result, 'state_revision': state['state_revision']}
