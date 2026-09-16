from copy import deepcopy
from uuid import UUID, uuid4

from .errors import FlowctlError


PENDING = "PENDING"
GRANTED = "GRANTED"
DENIED = "DENIED"
AMENDMENT_PENDING = "AMENDMENT_PENDING"
INVALIDATED = "INVALIDATED"
SANITIZED_LOCAL_REPLAY = "SANITIZED_LOCAL_REPLAY"
LOCAL_PRODUCTION_REPLAY = "LOCAL_PRODUCTION_REPLAY"
SKIP_PRODUCTION_REPLAY = "SKIP_PRODUCTION_REPLAY"

AUTHORIZATION_KINDS = {"external_review", "production_replay"}
AUTHORIZATION_STATUSES = {PENDING, GRANTED, DENIED, AMENDMENT_PENDING, INVALIDATED}
# Historical decisions retain their recorded identity; they prove no sanitization.
PRODUCTION_REPLAY_MODES = {LOCAL_PRODUCTION_REPLAY, SANITIZED_LOCAL_REPLAY, SKIP_PRODUCTION_REPLAY}
EXTERNAL_REVIEW_STAGES = ("flow-spec", "flow-plan", "flow-code")
HARD_EXCLUSIONS = (
    "credentials",
    "secrets",
    "raw_production_data",
    "unrelated_content",
    "production_mutation",
    "remote_deployment",
)
IDENTITY_FIELDS = ("issue_id", "run_id", "worktree_path")
SCOPE_FIELDS = {
    "exclusions", "raw_persistence", "external_model_transmission", "git_tracking",
    "cleanup_required", "allowed_stages", "allowed_backends",
}


def default_authorizations():
    common = {
        "authorization_id": None,
        "revision": 0,
        "status": PENDING,
        "issue_id": None,
        "run_id": None,
        "worktree_path": None,
        "decision": None,
        "granted_by": None,
        "history": [],
        "bindings": [],
    }
    return {
        "external_review": {
            **deepcopy(common),
            "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
            "allowed_backends": ["cursor", "ibrain"],
            "exclusions": list(HARD_EXCLUSIONS),
        },
        "production_replay": {
            **deepcopy(common),
            "mode": None,
            "external_model_transmission": DENIED,
            "git_tracking": DENIED,
            "exclusions": [item for item in HARD_EXCLUSIONS if item != 'raw_production_data'],
        },
    }


def _is_authorization_id(value):
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _has_hard_exclusions(authorization, kind='external_review'):
    exclusions = authorization.get("exclusions")
    return (
        isinstance(exclusions, list)
        and all(isinstance(item, str) for item in exclusions)
        and len(exclusions) == len(set(exclusions))
        and (set(exclusions) == set(HARD_EXCLUSIONS) or
             kind == 'production_replay' and
             set(exclusions) == set(HARD_EXCLUSIONS) - {'raw_production_data'})
    )


def _valid_prior_decision(kind, authorization):
    decision = authorization.get("decision")
    if type(decision) is not str:
        return False
    if kind == "external_review":
        return decision in {GRANTED, DENIED}
    return decision in PRODUCTION_REPLAY_MODES and authorization.get("mode") == decision


def _valid_authorization(kind, authorization):
    if not _has_hard_exclusions(authorization, kind):
        return False
    if any(not isinstance(authorization.get(field), str) or not authorization[field]
           for field in IDENTITY_FIELDS):
        return False
    revision = authorization.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        return False
    status = authorization.get("status")
    if type(status) is not str or status not in AUTHORIZATION_STATUSES:
        return False
    if (not isinstance(authorization.get("history"), list)
            or not isinstance(authorization.get("bindings"), list)):
        return False

    if kind == "external_review":
        if (not _valid_allowed_stages(authorization.get("allowed_stages"))
                or authorization.get("allowed_backends") != ["cursor", "ibrain"]):
            return False
    elif (
        authorization.get("external_model_transmission") != DENIED
        or authorization.get("git_tracking") != DENIED
    ):
        return False

    authorization_id = authorization.get("authorization_id")
    if status == PENDING:
        return (
            revision == 0
            and authorization_id is None
            and authorization.get("decision") is None
            and authorization.get("granted_by") is None
            and not any(field in authorization for field in (
                "decided_at", "proposed_decision", "amendment_requested_at",
                "invalidated_at", "invalidation_reason",
            ))
            and (kind != "production_replay" or authorization.get("mode") is None)
        )

    if status == INVALIDATED:
        if (not isinstance(authorization.get("invalidated_at"), str)
                or not authorization["invalidated_at"]
                or not isinstance(authorization.get("invalidation_reason"), str)
                or not authorization["invalidation_reason"]
                or "proposed_decision" in authorization
                or "amendment_requested_at" in authorization):
            return False
        if revision == 0:
            return (
                authorization_id is None
                and authorization.get("decision") is None
                and authorization.get("granted_by") is None
                and (kind != "production_replay" or authorization.get("mode") is None)
            )

    if (revision < 1 or not _is_authorization_id(authorization_id)
            or authorization.get("granted_by") != "HUMAN"
            or not isinstance(authorization.get("decided_at"), str)
            or not authorization["decided_at"]
            or not _valid_prior_decision(kind, authorization)):
        return False
    if status == INVALIDATED:
        return True
    if "invalidated_at" in authorization or "invalidation_reason" in authorization:
        return False
    if status == AMENDMENT_PENDING:
        proposal = authorization.get("proposed_decision")
        if kind == "external_review":
            valid_proposal = (
                isinstance(proposal, dict)
                and set(proposal) == {"decision", "allowed_stages"}
                and proposal["decision"] in {GRANTED, DENIED}
                and _valid_allowed_stages(proposal["allowed_stages"])
            )
        else:
            valid_proposal = type(proposal) is str and proposal in PRODUCTION_REPLAY_MODES
        return (
            valid_proposal
            and proposal != _active_decision(kind, authorization)
            and isinstance(authorization.get("amendment_requested_at"), str)
            and bool(authorization["amendment_requested_at"])
        )
    if "proposed_decision" in authorization or "amendment_requested_at" in authorization:
        return False
    if kind == "external_review":
        return status in {GRANTED, DENIED} and authorization["decision"] == status
    return status == GRANTED


def validate_authorizations(authorizations):
    return (
        isinstance(authorizations, dict)
        and set(authorizations) == AUTHORIZATION_KINDS
        and all(
            isinstance(authorizations[kind], dict)
            and _valid_authorization(kind, authorizations[kind])
            for kind in AUTHORIZATION_KINDS
        )
    )


def migrate_state(state):
    if not isinstance(state, dict):
        raise FlowctlError("INVALID_CONTROLLER")
    if state.get("schema_version") == 2:
        return state, False
    if state.get("schema_version") != 1:
        raise FlowctlError("INVALID_CONTROLLER")

    migrated = deepcopy(state)
    authorizations = default_authorizations()
    for authorization in authorizations.values():
        for field in IDENTITY_FIELDS:
            authorization[field] = migrated[field]
    migrated["schema_version"] = 2
    migrated["authorizations"] = authorizations
    return migrated, True


def _valid_allowed_stages(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(type(stage) is str and stage in EXTERNAL_REVIEW_STAGES for stage in value)
        and len(value) == len(set(value))
    )


def _normalize_allowed_stages(value):
    if not _valid_allowed_stages(value):
        raise FlowctlError("INVALID_AUTHORIZATION_DECISION", field="allowed_stages")
    selected = set(value)
    return [stage for stage in EXTERNAL_REVIEW_STAGES if stage in selected]


def _normalize_decision(kind, decision):
    if type(kind) is not str or kind not in AUTHORIZATION_KINDS:
        raise FlowctlError("INVALID_AUTHORIZATION_KIND", kind=kind)
    if isinstance(decision, dict):
        if kind == "production_replay" and "allowed_stages" in decision:
            raise FlowctlError("INVALID_AUTHORIZATION_DECISION", unexpected=["allowed_stages"])
        allowed_scope = {"allowed_stages"} if kind == "external_review" else set()
        attempted_scope = sorted((set(decision) & SCOPE_FIELDS) - allowed_scope)
        if attempted_scope:
            raise FlowctlError("AUTHORIZATION_HARD_EXCLUSION", fields=attempted_scope)
        allowed_key = "status" if kind == "external_review" else "mode"
        allowed = {"decision", allowed_key} | allowed_scope
        unexpected = sorted(set(decision) - allowed)
        if unexpected:
            raise FlowctlError("INVALID_AUTHORIZATION_DECISION", unexpected=unexpected)
        values = [decision[key] for key in ("decision", allowed_key) if key in decision]
        if len(values) != 1:
            raise FlowctlError("INVALID_AUTHORIZATION_DECISION")
        value = values[0]
        if kind == "external_review":
            if "allowed_stages" not in decision:
                raise FlowctlError("INVALID_AUTHORIZATION_DECISION", field="allowed_stages")
            stages = _normalize_allowed_stages(decision["allowed_stages"])
            decision = {"decision": value, "allowed_stages": stages}
        else:
            decision = value
    elif kind == "external_review" and type(decision) is str:
        decision = {
            "decision": decision,
            "allowed_stages": list(EXTERNAL_REVIEW_STAGES),
        }
    if kind == "external_review":
        if not isinstance(decision, dict):
            raise FlowctlError("INVALID_AUTHORIZATION_DECISION")
        value = decision.get("decision")
        if type(value) is not str or value not in {GRANTED, DENIED}:
            raise FlowctlError("INVALID_AUTHORIZATION_DECISION", kind=kind, decision=value)
        return decision
    if type(decision) is not str:
        raise FlowctlError("INVALID_AUTHORIZATION_DECISION")
    if decision not in PRODUCTION_REPLAY_MODES:
        raise FlowctlError("INVALID_AUTHORIZATION_DECISION", kind=kind, decision=decision)
    return decision


def _decision_status(kind, decision):
    return decision["decision"] if kind == "external_review" else GRANTED


def _active_decision(kind, authorization):
    if kind == "external_review":
        return {
            "decision": authorization.get("decision"),
            "allowed_stages": list(authorization.get("allowed_stages", [])),
        }
    return authorization.get("decision")


def _identity_matches(state, authorization):
    return all(authorization.get(field) == state.get(field) for field in IDENTITY_FIELDS)


def _history_snapshot(authorization):
    excluded = {
        "history", "bindings", "proposed_decision", "amendment_requested_at",
        "invalidated_at", "invalidation_reason",
    }
    return deepcopy({key: value for key, value in authorization.items() if key not in excluded})


def _invalidate_bindings(authorization, at):
    for binding in authorization.get("bindings", []):
        if binding.get("status") != INVALIDATED:
            binding["status"] = INVALIDATED
            binding["invalidated_at"] = at


def _invalidate_for_identity_drift(state_path, state, kind, authorization):
    from .state import commit_state, utc_now

    if authorization.get("authorization_id"):
        history = authorization.setdefault("history", [])
        snapshot = _history_snapshot(authorization)
        if not history or history[-1].get("authorization_id") != snapshot.get("authorization_id"):
            history.append(snapshot)
    now = utc_now()
    _invalidate_bindings(authorization, now)
    authorization["status"] = INVALIDATED
    authorization["invalidated_at"] = now
    authorization["invalidation_reason"] = "IDENTITY_DRIFT"
    authorization.pop("proposed_decision", None)
    authorization.pop("amendment_requested_at", None)
    return commit_state(state_path, state, "AUTHORIZATION_INVALIDATED", {
        "kind": kind,
        "authorization_id": authorization.get("authorization_id"),
        "authorization_revision": authorization.get("revision", 0),
        "reason": "IDENTITY_DRIFT",
    })


def _record_decision(state_path, state, kind, authorization, decision):
    from .state import commit_state, utc_now

    now = utc_now()
    if authorization["status"] == AMENDMENT_PENDING:
        _invalidate_bindings(authorization, now)
    authorization["authorization_id"] = str(uuid4())
    authorization["revision"] += 1
    authorization["status"] = _decision_status(kind, decision)
    authorization["decision"] = (
        decision["decision"] if kind == "external_review" else decision
    )
    authorization["granted_by"] = "HUMAN"
    authorization["decided_at"] = now
    for field in IDENTITY_FIELDS:
        authorization[field] = state[field]
    if kind == "external_review":
        authorization["allowed_stages"] = list(decision["allowed_stages"])
    else:
        authorization["mode"] = decision
    authorization.pop("proposed_decision", None)
    authorization.pop("amendment_requested_at", None)
    authorization.pop("invalidated_at", None)
    authorization.pop("invalidation_reason", None)
    return commit_state(state_path, state, "AUTHORIZATION_DECIDED", {
        "kind": kind,
        "authorization_id": authorization["authorization_id"],
        "authorization_revision": authorization["revision"],
        "status": authorization["status"],
        "decision": _active_decision(kind, authorization),
    })


def decide_authorization(state_path, kind, decision, expected_revision):
    from .state import locked_state

    decision = _normalize_decision(kind, decision)
    with locked_state(state_path, expected_revision) as state:
        authorization = state["authorizations"][kind]
        if authorization["status"] != INVALIDATED and not _identity_matches(state, authorization):
            return _invalidate_for_identity_drift(state_path, state, kind, authorization)

        status = authorization["status"]
        if status in {GRANTED, DENIED}:
            if _active_decision(kind, authorization) == decision:
                return state
            raise FlowctlError("AUTHORIZATION_AMENDMENT_REQUIRED", kind=kind)
        if status == AMENDMENT_PENDING and authorization.get("proposed_decision") != decision:
            raise FlowctlError("AUTHORIZATION_AMENDMENT_MISMATCH", kind=kind)
        if status not in {PENDING, AMENDMENT_PENDING, INVALIDATED}:
            raise FlowctlError("INVALID_AUTHORIZATION_TRANSITION", kind=kind, status=status)
        return _record_decision(state_path, state, kind, authorization, decision)


def begin_authorization_amendment(state_path, kind, decision, expected_revision):
    from .state import commit_state, locked_state, utc_now

    decision = _normalize_decision(kind, decision)
    with locked_state(state_path, expected_revision) as state:
        authorization = state["authorizations"][kind]
        if authorization["status"] != INVALIDATED and not _identity_matches(state, authorization):
            return _invalidate_for_identity_drift(state_path, state, kind, authorization)

        status = authorization["status"]
        if status in {PENDING, INVALIDATED}:
            raise FlowctlError("INVALID_AUTHORIZATION_TRANSITION", kind=kind, status=status)
        if status == AMENDMENT_PENDING:
            if authorization.get("proposed_decision") == decision:
                return state
            raise FlowctlError("AUTHORIZATION_AMENDMENT_PENDING", kind=kind)
        if status not in {GRANTED, DENIED}:
            raise FlowctlError("INVALID_AUTHORIZATION_TRANSITION", kind=kind, status=status)
        if _active_decision(kind, authorization) == decision:
            return state

        history = authorization.setdefault("history", [])
        history.append(_history_snapshot(authorization))
        now = utc_now()
        _invalidate_bindings(authorization, now)
        authorization["status"] = AMENDMENT_PENDING
        authorization["proposed_decision"] = decision
        authorization["amendment_requested_at"] = now
        return commit_state(state_path, state, "AUTHORIZATION_AMENDMENT_BEGUN", {
            "kind": kind,
            "authorization_id": authorization["authorization_id"],
            "authorization_revision": authorization["revision"],
            "proposed_decision": decision,
        })
