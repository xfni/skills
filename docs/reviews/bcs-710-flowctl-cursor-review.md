# BCS-710 Flowctl final review brief

## Review intent

Flow v2 originally depended on the root Agent remembering a large prompt contract. This change moves deterministic workflow mechanics into an executable `flowctl` controller so an Agent cannot merely claim that artifacts, handoffs, review cycles, or approvals are valid.

The controller must still support starting or resuming from any valid workflow node. It mechanizes:

- SHA-256 artifact digest calculation and verification;
- BODY / INTEGRITY / APPROVAL structure and approval validity;
- deepest-valid-checkpoint discovery and deterministic resume;
- JSON handoff and route-back schema validation;
- transactional controller state, event journal recovery, and CAS revisions;
- process-fact-based review failure classification;
- GPT-before-Cursor review ordering, evidence binding, retry limits, and durable defect completion;
- Code review binding to the exact Git/worktree snapshot reviewed.

The intended trust boundary is: models create and assess content; `flowctl` alone validates mechanical progression. A substantive review failure must never be converted into a degradable runtime failure.

## Scope to inspect

Inspect the complete uncommitted diff and all new files, with particular attention to:

- `workflow-v2/flowctl.py`
- `workflow-v2/flowctl_lib/`
- `workflow-v2/schemas/`
- `workflow-v2/flowctl-contract.md`
- `workflow-v2/artifact-contract.md`
- `workflow-v2/orchestration-contract.md`
- `workflow-v2/skills/flow-*/SKILL.md`
- `workflow-v2/tests/test_flowctl.py`
- `workflow-v2/tests/test_flowctl_cli.py`
- `workflow-v2/tests/test_workflow.py`

## GPT-6 Astra review history

The GPT reviewer found six initial blocking issues: nested Cursor report misclassification, replaceable Code snapshots, older Cursor PASS overriding later FAILED, torn event append recovery, review-cycle reset across revisions, and terminal attempt resubmission. Those were fixed.

Cycle 2 retained two blockers:

1. route-back/resume could reactivate old Code reviews after code changed;
2. overlapping pre-started Cursor attempts could allow a FAILED result followed by two RUN_ERROR results to degrade completion.

Cycle 3 returned PASSED after independent reproduction confirmed both paths fail closed. It noted one non-blocking stale `pending_action`; that was subsequently fixed by requiring `eligible` reviews when deriving the resume action.

## Cursor round-1 findings and disposition

Cursor round 1 returned FAILED because route-back-invalidated artifact files could be rediscovered by mandatory entry `resume`. It also noted missing lifecycle regressions and incomplete CLI admission coverage.

The remediation adds persistent `invalidated_checkpoints` plus per-artifact `artifact_high_water` history. Resume rejects revisions below the highest accepted revision and same-revision/different-digest history conflicts, filters route-back tombstones, rebuilds the dependency chain, and preserves the route-back owning stage. Replacement registration cannot erase the historical floor. Every state-mutating CLI entry now performs worktree/branch admission first.

Tests now exercise the real route-back -> rediscover files -> resume path, then register intent r2 -> explicitly resume old r1 path. GPT-6 Astra/medium independently reproduced both the original and omitted-node variants and returned PASSED.

Cursor round 2 found that terminal reports could still manufacture degradable `RUN_ERROR` classifications: `INCOMPLETE` with findings, rejected reports containing words such as `connection`, wrong review digests, and empty `INCOMPLETE` reports without process-failure evidence. These paths are now separated from process classification. Any parsed or rejected terminal report without controller-observed runtime failure is `REVIEW_RESULT` or `UNCLASSIFIED`; only actual subprocess, timeout, SDK, credential, or connection facts can become degradable `RUN_ERROR`.

A newly authorized three-round GPT-6 Astra/medium review independently exercised wrong digest, malformed or trailing terminal output, inconsistent statuses, `INCOMPLETE + BLOCKING`, and two `INCOMPLETE + TRANSMISSION_DENIED` attempts followed by handoff. Its round 3 result is PASSED with no unresolved blockers.

Cursor round 3 found global artifact-type depth overriding per-milestone progress, non-zero and timeout process results overriding terminal review JSON, in-place resume eligibility mutation, and direct reopening after `complete`. The implementation now selects the first dependency-ready milestone and its own deepest valid Spec/Plan/Code checkpoint; parses terminal JSON before using process exit classification; decodes `TimeoutExpired` byte output before parsing; deep-copies resume state before change comparison; rejects direct registration after completion; and rejects milestone-local route-back without an active milestone before committing invalidation. GPT-6 Astra/medium independently reproduced the timeout, complete-route, and global-route controls and returned PASSED in round 2.

Cursor round 4 found that HUMAN_GATE/BLOCKED pauses could be discarded and that global route-back retained other-milestone downstream artifacts. Pauses are now enforced by controller mutations: resume preserves them, state-changing review/artifact/snapshot/coder operations and handoff reject them, and only an explicit bound `FLOW_RUN_RESUMED` signal clears them before reconciliation. Global requirement/intent/roadmap route-back now invalidates downstream artifacts across every milestone; milestone-local route-back remains scoped to the active milestone. The signal schema and Flow contract document the resume signal, and Spec/Plan/Code skills now match the controller's non-degradable malformed-terminal behavior.

The caller-supplied Cursor runner trust-root observation remains explicitly open as a non-blocking architecture finding; the current assurance proves execution of the configured runner, not the identity of an independently trusted executable. Do not treat this disclosure as resolved.

Cursor round 5 found pause bypass through a second route-back signal and degradable missing/truncated terminal output. While paused, the controller now accepts only a bound `FLOW_RUN_RESUMED`; every other signal fails with `FLOW_PAUSED`. The resume signal clears the pause without becoming a new pending signal. Missing official-runner terminal output and JSON fragments containing terminal fields are forced to `UNCLASSIFIED`, even when their text contains connection/timeout terms. Regression tests cover paused route-back, explicit resume, `finished without terminal report`, and truncated FAILED JSON.

Cursor round 6 found that pausing after route-back overwrote the only owner-stage record. Route-back ownership is now stored independently in durable `route_back_context`; HUMAN_GATE/BLOCKED and FLOW_RUN_RESUMED do not erase it. Resume continues to return the owning `revise:*` stage, and only successful registration of the matching owner-stage artifact clears the context. A regression covers route-back to Intent, HUMAN_GATE, explicit resume signal, and checkpoint reconciliation.

Cursor round 7 found that missing-terminal evidence on stderr bypassed the stdout-only interception. Terminal evidence detection now examines combined stdout and stderr before process classification. A stderr-only `finished without terminal report` regression failed before the fix and now records `UNCLASSIFIED`. `flow-run` and the orchestration contract now explicitly require recording `FLOW_RUN_RESUMED` before controller resume for both HUMAN_GATE and BLOCKED pauses.

## Current verification evidence

From the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
Ran 64 tests
OK

git diff --check
exit 0
```

## Required review output

Review correctness, security/trust boundaries, lifecycle consistency, arbitrary-node recovery, snapshot/review binding, journal recovery, and whether tests prove the claims. Treat selective or fabricated evidence as a blocking problem.

Return a terminal JSON object as the final output with exactly this shape:

```json
{
  "status": "PASSED or FAILED",
  "reviewed_digest": "sha256 digest supplied by the caller if one is supplied; otherwise WORKTREE",
  "findings": [
    {
      "id": "CURSOR-*",
      "severity": "BLOCKER|HIGH|MEDIUM|LOW|INFO",
      "summary": "concise finding",
      "blocking_status": "BLOCKING|NON_BLOCKING",
      "recurrence_key": "stable-key",
      "evidence": "specific file/line/test evidence"
    }
  ]
}
```

Use `FAILED` if any blocking finding exists; otherwise use `PASSED`.
