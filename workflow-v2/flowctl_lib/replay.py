"""Narrow, pinned Python adapter contract for sanitized local JSONL replay.

Project profiles require code review here; manifest declarations never establish
trust. No production adapter is bundled. Profiles must attest read-only source
access, no caches/logs/dumps, identifier removal, and self-contained Python code
using only the standard library. Arbitrary shell/native clients are unsupported.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time
from uuid import uuid4

from .errors import FlowctlError
from .review_package import canonical, digest, read_regular, relative_path

TRUSTED_PROFILES = {}
PROFILE_KEYS = {'commands', 'sanitizer_version', 'streaming', 'cache_disabled',
                'body_logging_disabled', 'redacted_errors', 'stderr', 'fields',
                'removed_fields', 'transformations', 'field_categories', 'source_id', 'time_window'}
MANIFEST_KEYS = PROFILE_KEYS | {'profile', 'destination', 'max_records', 'expected_records',
                                'max_bytes', 'timeout_seconds', 'retention_deadline',
                                'milestone_id', 'scenario_id', 'plan_revision', 'plan_digest'}
PLAN_BINDING_KEYS = {'milestone_id', 'scenario_id', 'plan_revision', 'plan_digest'}


def reject_unresolved_cleanup(state):
    for binding in state.get('authorizations', {}).get('production_replay', {}).get('bindings', []):
        if (binding.get('evidence', {}).get('status') in {'BLOCKED_CLEANUP', 'INTERRUPTED'}
                and binding.get('cleanup_recovery', {}).get('status') != 'PASSED'):
            raise FlowctlError('REPLAY_CLEANUP_REQUIRED', binding_id=binding['binding_id'])


def _plan_binding(state, manifest):
    from .artifacts import read_artifact as verify_artifact
    from .integration_results import validate_plan_integration_scenarios
    milestone = state.get('active_milestone')
    plan = state.get('artifacts', {}).get(f'plan:{milestone}')
    requirement = state.get('artifacts', {}).get('requirement')
    if state.get('current_stage') != 'flow-integration' or not plan or not requirement:
        raise FlowctlError('REPLAY_PLAN_BINDING_REQUIRED')
    for recorded in (requirement, plan):
        current = verify_artifact(recorded['path'], expected_type=recorded['type'],
                                  expected_issue=state['issue_id'], expected_milestone=recorded.get('milestone_id'))
        if not current['approval']['valid'] or current['digest'] != recorded['digest']:
            raise FlowctlError('REPLAY_PLAN_BINDING_MISMATCH')
    if (manifest.get('milestone_id') != milestone or manifest.get('plan_revision') != plan['revision']
            or manifest.get('plan_digest') != plan['digest']):
        raise FlowctlError('REPLAY_PLAN_BINDING_MISMATCH')
    contract = validate_plan_integration_scenarios(plan.get('integration_scenarios'))
    scenario = next((s for s in contract['scenarios'] if s['scenario_id'] == manifest.get('scenario_id')), None)
    constraints_digest = digest(canonical({k:v for k,v in manifest.items() if k not in PLAN_BINDING_KEYS}))
    if (not scenario or not scenario['production_dependency']['required']
            or scenario['production_dependency'].get('replay_manifest_digest') != constraints_digest):
        raise FlowctlError('REPLAY_PLAN_BINDING_MISMATCH')


def _active(state):
    auth = state['authorizations']['production_replay']
    if (auth.get('status') != 'GRANTED' or auth.get('mode') != 'SANITIZED_LOCAL_REPLAY'
            or auth.get('decision') != 'SANITIZED_LOCAL_REPLAY' or auth.get('granted_by') != 'HUMAN'):
        raise FlowctlError('PRODUCTION_REPLAY_AUTHORIZATION_REQUIRED')
    if (any(auth.get(field) != 'DENIED' for field in
            ('raw_persistence', 'external_model_transmission', 'git_tracking'))
            or auth.get('cleanup_required') is not True):
        raise FlowctlError('PRODUCTION_REPLAY_SAFETY_POLICY_REQUIRED')
    if any(auth.get(k) != state.get(k) for k in ('issue_id', 'run_id', 'worktree_path')):
        raise FlowctlError('AUTHORIZATION_IDENTITY_DRIFT')
    return auth


def _private_directory(root, relative):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise FlowctlError('REPLAY_DESTINATION_NOT_PRIVATE')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _ignored(root, relative):
    result = subprocess.run(['git', '-C', str(root), 'check-ignore', '--quiet', '--', str(relative)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        raise FlowctlError('REPLAY_DESTINATION_NOT_IGNORED')


def _publish_boundary(root, destination, staging, fd):
    """Recheck policy and prove the admitted pathname still names our open directory."""
    _ignored(root, destination)
    _ignored(root, destination.parent / staging)
    current = _private_directory(root, destination.parent)
    try:
        held = os.fstat(fd)
        resolved = os.fstat(current)
        pathname = root / destination.parent
        named = pathname.lstat()
        if (not stat.S_ISDIR(named.st_mode)
                or pathname.resolve(strict=True) != pathname
                or (held.st_dev, held.st_ino) != (resolved.st_dev, resolved.st_ino)
                or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino)
                or held.st_uid != os.getuid()
                or stat.S_IMODE(held.st_mode) != 0o700):
            raise FlowctlError('REPLAY_DESTINATION_DRIFT')
    finally:
        os.close(current)


def _preflight(state, manifest):
    if not isinstance(manifest, dict):
        raise FlowctlError('INVALID_REPLAY_MANIFEST')
    _active(state)
    _plan_binding(state, manifest)
    try:
        if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
            raise ValueError()
        profile = TRUSTED_PROFILES.get(manifest['profile'])
        if profile is None or any(manifest[k] != profile[k] for k in PROFILE_KEYS):
            raise ValueError()
        if any(profile[k] is not True for k in ('streaming','cache_disabled','body_logging_disabled','redacted_errors')):
            raise ValueError()
        if profile['stderr'] != 'discard' or not profile['fields'] or not profile['removed_fields']:
            raise ValueError()
        if set(profile['fields']) & set(profile['removed_fields']):
            raise ValueError()
        for key, upper in (('max_records',100000), ('expected_records',100000),
                           ('max_bytes',16 * 1024 * 1024), ('timeout_seconds',300)):
            if type(manifest[key]) is not int or not 1 <= manifest[key] <= upper:
                raise ValueError()
        if manifest['expected_records'] > manifest['max_records']:
            raise ValueError()
        deadline = datetime.fromisoformat(manifest['retention_deadline'].replace('Z', '+00:00'))
        if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
            raise ValueError()
        root = Path(state['worktree_path']).resolve()
        commands = {}
        if set(manifest['commands']) != {'acquisition','sanitizer','cleanup'}:
            raise ValueError()
        for role, command in manifest['commands'].items():
            if set(command) != {'argv','digest'} or not isinstance(command['argv'], list) or not command['argv']:
                raise ValueError()
            if any(not isinstance(arg, str) or '\0' in arg for arg in command['argv']):
                raise ValueError()
            path = Path(command['argv'][0])
            if not path.is_absolute() or path.suffix != '.py':
                raise ValueError()
            source = read_regular(root, relative_path(root, path))
            if digest(source) != command['digest']:
                raise FlowctlError('REPLAY_EXECUTABLE_DRIFT')
            # Execute captured reviewed bytes, never reopen a mutable script at launch.
            commands[role] = [sys.executable, '-I', '-B', '-c', source.decode('utf-8'), *command['argv'][1:]]
        destination = relative_path(root, manifest['destination'])
        if len(destination.parts) < 2:
            raise ValueError()
        fd = _private_directory(root, destination.parent)
        try:
            try:
                os.stat(destination.name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FlowctlError('REPLAY_DESTINATION_EXISTS')
        finally:
            os.close(fd)
        _ignored(root, destination)
        _ignored(root, destination.parent / '.flow-replay-staging')
        return root, destination, commands
    except FlowctlError:
        raise
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise FlowctlError('INVALID_REPLAY_MANIFEST') from None


def validate_replay_manifest(state_path, manifest_path, expected_revision):
    from .state import locked_state, commit_state, reject_if_paused
    try:
        raw = Path(manifest_path).read_bytes()
        if len(raw) > 65536:
            raise ValueError()
        manifest = json.loads(raw)
    except (OSError, ValueError):
        raise FlowctlError('INVALID_REPLAY_MANIFEST') from None
    with locked_state(state_path, expected_revision) as state:
        reject_if_paused(state)
        _preflight(state, manifest)
        auth = _active(state)
        binding = dict(binding_id=str(uuid4()), status='BOUND', authorization_id=auth['authorization_id'],
                       authorization_revision=auth['revision'], manifest_digest=digest(canonical(manifest)),
                       manifest=deepcopy(manifest), **{k:manifest[k] for k in PLAN_BINDING_KEYS})
        auth['bindings'].append(binding)
        public = {k:v for k,v in binding.items() if k != 'manifest'}
        state = commit_state(state_path, state, 'REPLAY_MANIFEST_VALIDATED', public)
        return {**public, 'state_revision':state['state_revision']}


def _record(line, manifest):
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError()
                result[key] = value
            return result
        record = json.loads(line, object_pairs_hook=unique)
        if not isinstance(record, dict) or set(record) != set(manifest['fields']):
            raise ValueError()
        for key, rule in manifest['fields'].items():
            value = record[key]
            if 'enum' in rule:
                if type(value) is not str or value not in rule['enum']:
                    raise ValueError()
            elif rule.get('type') == 'integer':
                if type(value) is not int or not rule['minimum'] <= value <= rule['maximum']:
                    raise ValueError()
            elif rule.get('type') == 'boolean':
                if type(value) is not bool:
                    raise ValueError()
            else:
                raise ValueError()
        return canonical(record) + b'\n'
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise FlowctlError('REPLAY_OUTPUT_INVALID') from None


def _terminate(process):
    if process is None:
        return
    # Reap an exited leader before signalling its group (Darwin may report
    # EPERM for a group containing only an unreaped zombie).
    process.poll()
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _execute(root, destination, commands, manifest, staging, record_ownership):
    source = sanitizer = cleanup = None
    fd = _private_directory(root, destination.parent)
    published = False
    records = 0
    byte_count = 0
    output_digest = hashlib.sha256()
    result = dict(status='BLOCKED', code='REPLAY_EXECUTION_FAILED', records=0, cleanup='PENDING')
    try:
        _ignored(root, destination.parent / staging)
        with os.fdopen(os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd), 'wb') as output:
            info = os.fstat(output.fileno())
            identity = {'device':info.st_dev, 'inode':info.st_ino,
                        'digest':'sha256:' + output_digest.hexdigest()}
            record_ownership(staging=identity, acquisition_started=True)
            # Captured stdlib adapters have no workspace-relative dependencies.
            # Never resolve an attacker-replaceable data directory for child cwd.
            settings = dict(cwd=Path('/'), stderr=subprocess.DEVNULL, env={}, start_new_session=True)
            source = subprocess.Popen(commands['acquisition'], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, **settings)
            try:
                sanitizer = subprocess.Popen(commands['sanitizer'], stdin=source.stdout, stdout=subprocess.PIPE, **settings)
            finally:
                source.stdout.close()
            end = time.monotonic() + manifest['timeout_seconds']
            pending = b''
            with selectors.DefaultSelector() as selector:
                selector.register(sanitizer.stdout, selectors.EVENT_READ)
                while True:
                    if time.monotonic() >= end:
                        raise FlowctlError('REPLAY_TIMEOUT')
                    if source.poll() not in (None, 0) or sanitizer.poll() not in (None, 0):
                        raise FlowctlError('REPLAY_PROCESS_FAILED')
                    if not selector.select(min(0.05, max(0, end - time.monotonic()))):
                        continue
                    chunk = os.read(sanitizer.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    byte_count += len(chunk)
                    if byte_count > manifest['max_bytes']:
                        raise FlowctlError('REPLAY_OUTPUT_LIMIT')
                    pending += chunk
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        safe = _record(line, manifest)
                        records += 1
                        if records > manifest['max_records']:
                            raise FlowctlError('REPLAY_OUTPUT_LIMIT')
                        output.write(safe)
                        output_digest.update(safe)
                if pending:
                    raise FlowctlError('REPLAY_OUTPUT_INVALID')
            for process in (source, sanitizer):
                if process.wait(timeout=max(0.001, end - time.monotonic())) != 0:
                    raise FlowctlError('REPLAY_PROCESS_FAILED')
            if records != manifest['expected_records']:
                raise FlowctlError('REPLAY_RECORD_COUNT_MISMATCH')
            output.flush()
            os.fsync(output.fileno())
            identity['digest'] = 'sha256:' + output_digest.hexdigest()
            # Record the controller-created inode before publication. The final
            # name is ours only when it still identifies these exact bytes.
            record_ownership(staging=identity, destination=identity)
        _publish_boundary(root, destination, staging, fd)
        # linkat publishes complete bytes atomically and fails with EEXIST;
        # unlike stat+replace it cannot overwrite a concurrent creator.
        os.link(staging, destination.name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        published = True
        _publish_boundary(root, destination, staging, fd)
        os.unlink(staging, dir_fd=fd)
        os.fsync(fd)
        result.update(status='PASSED', code='REPLAY_SANITIZED', records=records,
                      destination_digest='sha256:' + output_digest.hexdigest(), ignore_proof=True)
    except FlowctlError as exc:
        result['code'] = exc.code
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    finally:
        cleanup_ok = True
        for process in (source, sanitizer):
            try:
                _terminate(process)
                if process is sanitizer and process.stdout:
                    process.stdout.close()
            except OSError:
                cleanup_ok = False
        try:
            cleanup = subprocess.Popen(commands['cleanup'], cwd=Path('/'), env={},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            cleanup_ok = cleanup.wait(timeout=manifest['timeout_seconds']) == 0 and cleanup_ok
        except (OSError, subprocess.SubprocessError):
            cleanup_ok = False
        finally:
            try:
                _terminate(cleanup)
            except OSError:
                cleanup_ok = False
        for name in ([staging, destination.name] if published and (result['status'] != 'PASSED' or not cleanup_ok) else [staging]):
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                pass
            except OSError:
                cleanup_ok = False
        os.close(fd)
        result['cleanup'] = 'PASSED' if cleanup_ok else 'FAILED'
        if not cleanup_ok:
            result.update(status='BLOCKED_CLEANUP', code='REPLAY_CLEANUP_FAILED')
    return result


def run_replay(state_path, binding_id, expected_revision):
    from .state import locked_state, commit_state, reject_if_paused, utc_now
    with locked_state(state_path, expected_revision) as state:
        reject_if_paused(state)
        auth = _active(state)
        reject_unresolved_cleanup(state)
        binding = next((b for b in auth['bindings'] if b['binding_id'] == binding_id), None)
        if (not binding or binding['status'] != 'BOUND'
                or binding['authorization_id'] != auth['authorization_id']
                or binding['authorization_revision'] != auth['revision']
                or digest(canonical(binding['manifest'])) != binding['manifest_digest']):
            raise FlowctlError('AUTHORIZATION_BINDING_STALE')
        manifest = binding['manifest']
        root, destination, commands = _preflight(state, manifest)
        binding['status'] = 'CONSUMED'
        staging = '.flow-replay-' + uuid4().hex
        info = (root / destination.parent).stat()
        binding['cleanup_targets'] = [staging, destination.name]
        binding['cleanup_directory'] = {'device': info.st_dev, 'inode': info.st_ino}
        binding['cleanup_ownership'] = {'staging':None, 'destination':None, 'acquisition_started':False}
        # Durable crash marker: interrupted execution cannot silently authorize
        # another acquisition without evidence that cleanup completed.
        binding['evidence'] = {'status':'BLOCKED_CLEANUP', 'code':'REPLAY_EXECUTION_INTERRUPTED'}
        commit_state(state_path, state, 'REPLAY_STARTED', {'binding_id':binding_id})
        started = utc_now()
        def record_ownership(**updates):
            binding['cleanup_ownership'].update(deepcopy(updates))
            commit_state(state_path, state, 'REPLAY_OUTPUT_OWNERSHIP', {'binding_id':binding_id,
                'cleanup_ownership':deepcopy(binding['cleanup_ownership'])})
        evidence = _execute(root, destination, commands, manifest, staging, record_ownership)
        evidence.update(binding_id=binding_id, manifest_digest=binding['manifest_digest'],
                        **{k:manifest[k] for k in PLAN_BINDING_KEYS},
                        command_digests={role:command['digest'] for role,command in manifest['commands'].items()},
                        sanitizer_version=manifest['sanitizer_version'], started_at=started, finished_at=utc_now())
        binding['evidence'] = evidence
        state = commit_state(state_path, state, 'REPLAY_FINISHED', evidence)
        return {**evidence, 'state_revision':state['state_revision']}


def recover_replay_cleanup(state_path, binding_id, expected_revision):
    """Prove outputs absent without delegating pathname deletion to an adapter.

    This recovery is independent of current authorization/stage: narrowing an
    authorization must neither erase a safety obligation nor prevent cleanup.
    """
    from .state import locked_state, commit_state, utc_now
    with locked_state(state_path, expected_revision) as state:
        binding = next((b for b in state['authorizations']['production_replay']['bindings']
                        if b['binding_id'] == binding_id), None)
        if binding and binding.get('cleanup_recovery', {}).get('status') == 'PASSED':
            return {**binding['cleanup_recovery'], 'state_revision':state['state_revision']}
        if (not binding or binding.get('evidence', {}).get('status') not in {'BLOCKED_CLEANUP', 'INTERRUPTED'}
                or digest(canonical(binding['manifest'])) != binding['manifest_digest']):
            raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
        manifest = binding['manifest']
        profile = TRUSTED_PROFILES.get(manifest['profile'])
        if profile is None or any(manifest[k] != profile[k] for k in PROFILE_KEYS):
            raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
        root = Path(state['worktree_path']).resolve()
        destination = relative_path(root, manifest['destination'])
        command = manifest['commands']['cleanup']
        source = read_regular(root, relative_path(root, command['argv'][0]))
        if digest(source) != command['digest']:
            raise FlowctlError('REPLAY_EXECUTABLE_DRIFT')
        fd = _private_directory(root, destination.parent)
        proof = {'status':'FAILED', 'binding_id':binding_id, 'manifest_digest':binding['manifest_digest'],
                 'cleanup_command_digest':command['digest'], 'verified_at':utc_now()}
        try:
            info = os.fstat(fd)
            if binding.get('cleanup_directory') != {'device':info.st_dev, 'inode':info.st_ino}:
                raise FlowctlError('REPLAY_DESTINATION_DRIFT')
            targets = binding.get('cleanup_targets', [])
            if (len(targets) != 2 or not targets[0].startswith('.flow-replay-')
                    or Path(targets[0]).name != targets[0] or targets[1] != destination.name):
                raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
            _publish_boundary(root, destination, targets[0], fd)
            ownership = binding.get('cleanup_ownership')
            if not isinstance(ownership, dict) or type(ownership.get('acquisition_started')) is not bool:
                raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
            present = {}
            for role, target in zip(('staging', 'destination'), targets):
                try:
                    target_fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                except FileNotFoundError:
                    present[role] = False
                    continue
                with os.fdopen(target_fd, 'rb') as output:
                    info = os.fstat(output.fileno())
                    expected = ownership.get(role)
                    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                            or not isinstance(expected, dict)
                            or expected.get('device') != info.st_dev or expected.get('inode') != info.st_ino
                            or info.st_size > manifest['max_bytes']
                            or expected.get('digest') != digest(output.read(manifest['max_bytes'] + 1))):
                        raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
                present[role] = True
            # Even a matching final identity cannot make a later adapter unlink
            # atomic with this check. Recovery never launches that adapter and
            # never deletes the public final name; it remains blocking.
            if present['destination'] or binding['evidence'].get('cleanup') == 'FAILED':
                raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
            # Do not unlink a name that was absent at the ownership check.
            for target in targets[:1] if present['staging'] else []:
                try:
                    info = os.stat(target, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                expected = ownership['staging']
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or (info.st_dev, info.st_ino) != (expected['device'], expected['inode'])):
                    raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
                os.unlink(target, dir_fd=fd)
            os.fsync(fd)
            _publish_boundary(root, destination, targets[0], fd)
            for target in targets:
                try:
                    os.stat(target, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise FlowctlError('REPLAY_CLEANUP_PROOF_REQUIRED')
            proof['status'] = 'PASSED'
        except (FlowctlError, OSError):
            pass
        finally:
            os.close(fd)
        binding['cleanup_recovery'] = proof
        state = commit_state(state_path, state, 'REPLAY_CLEANUP_RECOVERY', proof)
        return {**proof, 'state_revision':state['state_revision']}
