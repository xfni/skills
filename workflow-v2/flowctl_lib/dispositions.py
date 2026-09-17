"""Caller applicability judgments; never rewrite original review receipts."""
import hashlib
import json
from pathlib import Path

from .errors import FlowctlError


def unresolved_review(state, key, digest, backend=None):
    """Only the latest live attempt per role determines unresolved facts."""
    latest = {}
    for item in state.get('reviews', {}).get('attempts', {}).values():
        if (item.get('artifact_key') != key or item.get('artifact_digest') != digest
                or item.get('revoked') or (backend and item.get('backend') != backend)):
            continue
        role = item.get('backend')
        rank = item.get('completed_state_revision', item.get('started_state_revision', 0))
        if role not in latest or rank >= latest[role][0]:
            latest[role] = (rank, item)
    return any(item.get('status') in {'FAILED', 'STARTED', 'INCOMPLETE'}
               or any(f.get('blocking_status') == 'BLOCKING' for f in item.get('findings', []))
               for _, item in latest.values())


def receipt_readable(attempt):
    withdrawal = attempt.get('invalidated_by')
    if (attempt.get('revoked') or withdrawal not in {None, 'resume', attempt.get('artifact_key')}
            or attempt.get('status') != 'PASSED' or attempt.get('classification') != 'REVIEW_RESULT'):
        return False
    if attempt.get('backend') in {'cursor', 'ibrain'} and attempt.get('execution_assurance') != 'CONTROLLER_EXECUTED':
        return False
    try:
        raw = Path(attempt['report_path']).read_bytes()
    except (OSError, KeyError):
        return False
    return 'sha256:' + hashlib.sha256(raw).hexdigest() == attempt.get('report_digest')


def apply_disposition(state, key, path):
    if path is None:
        return
    from .state import reject_if_paused
    reject_if_paused(state)
    try:
        path = Path(path).resolve(strict=True)
        raw = path.read_bytes()
        material = json.loads(raw)
        if (not isinstance(material, dict) or not isinstance(material.get('reason'), str)
                or not material['reason'].strip() or not isinstance(material.get('evidence'), list)
                or not material['evidence']):
            raise ValueError('reason and evidence required')
        evidence = {}
        for reference in material['evidence']:
            file = Path(reference).resolve(strict=True)
            evidence[str(file)] = 'sha256:' + hashlib.sha256(file.read_bytes()).hexdigest()
    except (OSError, ValueError, TypeError) as exc:
        raise FlowctlError('DISPOSITION_EVIDENCE_REQUIRED', action='repair', artifact_key=key) from exc
    artifact = state['artifacts'].get(key)
    if not artifact:
        raise FlowctlError('ARTIFACT_NOT_REGISTERED', artifact_key=key)
    route_event = material.get('route_event')
    if route_event is not None:
        context = state.get('route_back_context')
        if (not context or context.get('owner_stage') != 'flow-' + artifact['type']
                or not artifact['approval']['valid']):
            raise FlowctlError('DISPOSITION_ROUTE_BINDING_REQUIRED')
        events_path = Path(state['controller_path']).with_name('flow-events.jsonl')
        try:
            matches = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()
                       if line.strip()]
            matches = [event for event in matches if event.get('event') == 'FLOW_SIGNAL_RECORDED'
                       and event.get('signal') == 'FLOW_RUN_ROUTE_BACK'
                       and event.get('cause') == context.get('cause')]
        except (OSError, ValueError) as exc:
            raise FlowctlError('DISPOSITION_ROUTE_BINDING_REQUIRED') from exc
        if not matches or matches[-1]['seq'] != route_event:
            raise FlowctlError('DISPOSITION_ROUTE_BINDING_REQUIRED')
    sources = material.get('source_attempts', [])
    if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
        raise FlowctlError('DISPOSITION_SOURCE_INVALID')
    attempts = state.get('reviews', {}).get('attempts', {})
    originals = {}
    for source in sources:
        attempt = attempts.get(source, {})
        if (attempt.get('artifact_key') != key or not receipt_readable(attempt)
                or unresolved_review(state, key, attempt.get('artifact_digest'), attempt.get('backend'))):
            raise FlowctlError('DISPOSITION_RECEIPT_REQUIRED', attempt_id=source)
        originals[source] = {'digest': attempt['artifact_digest'], 'snapshot_digest': attempt.get('snapshot_digest')}
    if unresolved_review(state, key, artifact['digest']):
        raise FlowctlError('DISPOSITION_UNRESOLVED_REVIEW')
    snapshot = None
    if artifact['type'] == 'code':
        from .snapshot import capture_snapshot
        snapshot = capture_snapshot(state['worktree_path'], artifact['path'])['snapshot_digest']
    record = {'path': str(path), 'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(),
              'reason': material['reason'], 'evidence': evidence, 'source_attempts': originals,
              'artifact_digest': artifact['digest'], 'snapshot_digest': snapshot,
              'execution_assurance': 'CALLER_ATTESTED'}
    if route_event is not None:
        record['route_event'] = route_event
        state['route_back_context'] = None
        if state.get('pending_signal', {}).get('signal') == 'FLOW_RUN_ROUTE_BACK':
            state.pop('pending_signal')
    previous = state.setdefault('dispositions', {}).get(key)
    if previous and previous != record:
        state.setdefault('disposition_history', []).append({'artifact_key': key, 'disposition': previous})
    state['dispositions'][key] = record


def applicable(state, key, attempt_id, digest):
    record = state.get('dispositions', {}).get(key, {})
    if record.get('artifact_digest') != digest or attempt_id not in record.get('source_attempts', {}):
        return False
    attempt = state['reviews']['attempts'].get(attempt_id, {})
    if (not receipt_readable(attempt)
            or unresolved_review(state, key, attempt.get('artifact_digest'), attempt.get('backend'))):
        return False
    original = record['source_attempts'][attempt_id]
    if original != {'digest': attempt.get('artifact_digest'), 'snapshot_digest': attempt.get('snapshot_digest')}:
        return False
    try:
        if 'sha256:' + hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['digest']:
            return False
        for path, expected in record['evidence'].items():
            if 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                return False
        if record.get('snapshot_digest'):
            from .snapshot import capture_snapshot
            if capture_snapshot(state['worktree_path'], state['artifacts'][key]['path'])['snapshot_digest'] != record['snapshot_digest']:
                return False
    except (OSError, KeyError, FlowctlError):
        return False
    return not unresolved_review(state, key, digest, attempt.get('backend'))
