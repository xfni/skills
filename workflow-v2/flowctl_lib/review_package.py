"""Single-use bindings for autonomous exploration of a frozen worktree."""
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

CAPABILITIES = {'workspace_exploration': True, 'write_tools': False}
MAX_BYTES = 4 * 1024 * 1024


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def validate_capabilities(value):
    if (not isinstance(value, dict) or value != CAPABILITIES
            or any(type(value.get(key)) is not bool for key in CAPABILITIES)):
        raise FlowctlError('BACKEND_UNAVAILABLE')


def active_authorization(state, backend, stage):
    # Historical external-review decisions are not human gates.
    if backend not in {'cursor', 'ibrain'} or stage not in {'flow-spec', 'flow-plan', 'flow-code'}:
        raise FlowctlError('AUTHORIZATION_SCOPE_MISMATCH')
    if stage != state['current_stage']:
        raise FlowctlError('STAGE_MISMATCH')
    return state['authorizations']['external_review']


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
    # Paths in a brief are navigation text; read tools enforce the actual scope.
    return value


class ReviewPackage:
    def __init__(self, root, manifest, request_bytes, source_snapshot, controller_path):
        self.root = root
        self.manifest = manifest
        self.request_path = root / 'request.json'
        self.workspace_path = root / 'workspace'
        self.digest = digest(request_bytes)
        self.outbound_prompt = json.loads(request_bytes)['prompt']
        self.source_snapshot = source_snapshot
        self.controller_path = controller_path
        from .review_workspace import capture_review_snapshot
        self.view_snapshot = capture_review_snapshot(self.workspace_path, git_facts=False)

    def verify(self):
        from .review_workspace import verify_review_snapshot
        if set(self.root.iterdir()) != {self.request_path, self.workspace_path}:
            raise FlowctlError('REVIEW_PACKAGE_DRIFT')
        if digest(read_regular(self.root, Path('request.json'))) != self.digest:
            raise FlowctlError('REVIEW_PACKAGE_DRIFT')
        verify_review_snapshot(self.workspace_path, None, self.view_snapshot, git_facts=False)

    def verify_source(self, worktree):
        from .review_workspace import verify_review_snapshot
        return verify_review_snapshot(worktree, self.controller_path, self.source_snapshot)

    def cleanup(self):
        try:
            if self.root.exists():
                for parent, dirs, _ in os.walk(self.root, followlinks=False):
                    Path(parent).chmod(0o700)
                shutil.rmtree(self.root)
        except OSError:
            raise FlowctlError('REVIEW_PACKAGE_CLEANUP_FAILED') from None


def create_review_package(state, backend, stage, artifact_key, prompt_path, paths=None, exclusions=None):
    active_authorization(state, backend, stage)
    root = Path(state['worktree_path']).resolve()
    artifact = state['artifacts'].get(artifact_key)
    if not artifact:
        raise FlowctlError('ARTIFACT_NOT_REGISTERED')
    if stage != 'flow-' + artifact['type']:
        raise FlowctlError('REVIEW_ARTIFACT_STAGE_MISMATCH')
    prompt = check_content(read_regular(root, relative_path(root, prompt_path)), prompt=True)
    if paths is not None:
        if not isinstance(paths, list) or not paths:
            raise FlowctlError('INVALID_REVIEW_MANIFEST')
        for path in paths:
            relative_path(root, path)  # Hints never restrict the autonomous evidence scope.
    from .review_workspace import capture_review_snapshot, create_review_view, normalize_review_exclusions
    exclusions = normalize_review_exclusions(exclusions)
    for item in exclusions:
        check_content(item['reason'].encode(), prompt=True)
    from .artifacts import read_artifact as verify_artifact
    from .snapshot import verify_recorded_snapshot
    if stage == 'flow-code':
        verify_recorded_snapshot(state, artifact_key)
    controller_path = state.get('controller_path')
    source_snapshot = capture_review_snapshot(root, controller_path)
    package_root = Path(tempfile.mkdtemp(prefix='flow-review-')).resolve()
    try:
        view = create_review_view(root, package_root / 'workspace', controller_path, exclusions=exclusions)
        available = {item['path'] for item in view['files']}
        # Historical context is available to the reviewer but only its target
        # is mandatory. Missing/excluded history is not a package-wide gate.
        required = {artifact_key}
        for key in required:
            item = state['artifacts'][key]
            rel = str(relative_path(root, item['path']))
            if rel not in available:
                raise FlowctlError('REVIEW_REQUIRED_INPUT_EXCLUDED', path=rel)
            current = verify_artifact(item['path'], expected_type=item['type'], expected_issue=state['issue_id'])
            if current['digest'] != item['digest']:
                raise FlowctlError('ARTIFACT_DRIFT')
        manifest = dict(issue_id=state['issue_id'], run_id=state['run_id'],
            worktree_binding=digest(str(root).encode()), backend=backend, stage=stage, artifact_key=artifact_key,
            artifact_digest=artifact['digest'], authorization_id=None, authorization_revision=0,
            authorization_basis='ORGANIZATION_TRUSTED' if backend == 'ibrain' else 'EXPLICIT_FLOW_INVOCATION',
            prompt_digest=digest(prompt.encode()), files=view['files'], excluded=view['excluded'],
            source_snapshot={key: value for key, value in source_snapshot.items() if key != 'files'})
        if exclusions:
            manifest['exclusions'] = exclusions
        raw = canonical(dict(schema_version=2, manifest=manifest, prompt=prompt,
                             files=view['files'], capabilities=CAPABILITIES))
        (package_root / 'request.json').write_bytes(raw)
        (package_root / 'request.json').chmod(0o400)
        package = ReviewPackage(package_root, manifest, raw, source_snapshot, controller_path)
        package.verify_source(root)
        return package
    except BaseException:
        shutil.rmtree(package_root)
        raise


def bind_package(state, package):
    manifest = package.manifest
    auth = active_authorization(state, manifest['backend'], manifest['stage'])
    package.verify()
    binding = dict(binding_id=str(uuid4()), authorization_id=None,
        authorization_revision=0, authorization_basis=manifest['authorization_basis'],
        package_digest=package.digest, backend=manifest['backend'], status='BOUND')
    auth['bindings'].append(binding)
    return binding


def consume_binding(state, package, binding_id):
    auth = active_authorization(state, package.manifest['backend'], package.manifest['stage'])
    binding = next((b for b in auth['bindings'] if b['binding_id'] == binding_id), None)
    if (not binding or binding['status'] != 'BOUND' or binding['package_digest'] != package.digest
            or binding.get('authorization_basis') != package.manifest['authorization_basis']):
        raise FlowctlError('AUTHORIZATION_BINDING_STALE')
    package.verify()
    binding['status'] = 'CONSUMED'


def validate_review_manifest(state_path, manifest_path, expected_revision):
    from .state import locked_state, commit_state, reject_if_paused
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        required = {'backend', 'stage', 'artifact_key', 'prompt_path'}
        if not isinstance(manifest, dict) or not required.issubset(manifest) or set(manifest) - required - {'paths', 'exclusions'}:
            raise ValueError('invalid manifest')
    except (OSError, ValueError, TypeError):
        raise FlowctlError('INVALID_REVIEW_MANIFEST') from None
    with locked_state(state_path, expected_revision) as state:
        reject_if_paused(state)
        package = create_review_package(state, **manifest)
        try:
            binding = bind_package(state, package)
            binding['input_manifest'] = manifest
            result = dict(binding)
        finally:
            package.cleanup()
        state = commit_state(state_path, state, 'REVIEW_PACKAGE_VALIDATED', result)
        return {**result, 'state_revision': state['state_revision']}
