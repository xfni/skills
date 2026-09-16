import hashlib
import json
from pathlib import Path
import subprocess

from .errors import FlowctlError
from .state import commit_state, locked_state, reject_if_paused


def _git(root, *args, check=True):
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if check and result.returncode:
        raise FlowctlError("SNAPSHOT_GIT_ERROR", command=list(args), stderr=result.stderr.strip())
    return result.stdout


def capture_snapshot(root, evidence_path=None):
    root = Path(root).resolve()
    evidence_rel = None
    if evidence_path:
        try:
            evidence_rel = str(Path(evidence_path).resolve().relative_to(root))
        except ValueError:
            pass
    def excluded(rel):
        return rel == evidence_rel or rel == '.ai' or rel.startswith('.ai/')
    head = _git(root, "rev-parse", "HEAD").strip()
    raw_status = _git(root, "status", "--short", "--untracked-files=all")
    status = "\n".join(
        line for line in raw_status.splitlines()
        if not excluded(line[3:])
    )
    if status:
        status += "\n"
    paths = ['.', ':(exclude).ai/**']
    if evidence_rel:
        paths.append(':(exclude,literal)' + evidence_rel)
    diff = _git(root, 'diff', '--binary', 'HEAD', '--', *paths)
    untracked = {}
    for rel in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        if excluded(rel):
            continue
        path = root / rel
        if path.is_file():
            untracked[rel] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "head": head,
        "status_digest": "sha256:" + hashlib.sha256(status.encode()).hexdigest(),
        "tracked_diff_digest": "sha256:" + hashlib.sha256(diff.encode()).hexdigest(),
        "untracked": untracked,
    }
    if evidence_rel and not evidence_rel.startswith('.ai/'):
        payload['evidence_exclusion'] = evidence_rel
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["snapshot_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return payload


def record_snapshot(state_path, artifact_key, expected_state_revision):
    with locked_state(state_path, expected_state_revision) as state:
        reject_if_paused(state)
        if artifact_key not in state["artifacts"]:
            raise FlowctlError("ARTIFACT_NOT_REGISTERED", artifact_key=artifact_key)
        artifact = state['artifacts'][artifact_key]
        snapshot = capture_snapshot(state['worktree_path'], artifact['path'] if artifact['type'] == 'code' else None)
        existing = state.setdefault("snapshots", {}).get(artifact_key)
        if existing and existing["snapshot_digest"] == snapshot["snapshot_digest"]:
            return {"snapshot": existing, "state_revision": state["state_revision"]}
        bound_reviews = [
            attempt for attempt in state["reviews"]["attempts"].values()
            if attempt.get("artifact_key") == artifact_key and attempt.get("eligible", True)
        ]
        if existing and bound_reviews:
            raise FlowctlError(
                "SNAPSHOT_REVIEW_BINDING_EXISTS",
                attempt_ids=[item["attempt_id"] for item in bound_reviews],
            )
        state.setdefault("snapshots", {})[artifact_key] = snapshot
        if state['artifacts'][artifact_key]['type'] == 'code':
            from .reviews import next_review_action
            state['pending_action'] = next_review_action(state, artifact_key)
        state = commit_state(state_path, state, "CODE_SNAPSHOT_RECORDED", {
            "artifact_key": artifact_key, "snapshot_digest": snapshot["snapshot_digest"],
        })
        return {"snapshot": snapshot, "state_revision": state["state_revision"]}


def verify_recorded_snapshot(state, artifact_key):
    expected = state.get("snapshots", {}).get(artifact_key)
    if not expected:
        raise FlowctlError("CODE_SNAPSHOT_REQUIRED", artifact_key=artifact_key)
    actual = capture_snapshot(state['worktree_path'], state['artifacts'][artifact_key]['path']
                              if expected.get('evidence_exclusion') else None)
    if actual["snapshot_digest"] != expected["snapshot_digest"]:
        raise FlowctlError(
            "CODE_SNAPSHOT_DRIFT", expected=expected["snapshot_digest"],
            actual=actual["snapshot_digest"],
        )
    return actual
