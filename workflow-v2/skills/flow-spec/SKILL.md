---
name: flow-spec
description: Use when the user explicitly requests a behavioral specification for one confirmed roadmap milestone.
---

# Flow Spec

Pass the validated review binding to `flowctl review cursor --binding-id` (or its authorized iBrain fallback). The manifest explicitly lists the artifact plus necessary source/test/evidence context; execution consumes that same set once and binds original source digests and current Git HEAD/status facts. It must not regenerate a target-only request.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register`. Execute the GPT Lane through `flowctl review begin` and `flowctl review submit`, the Cursor Lane through `flowctl review cursor` (or `flowctl review ibrain` only after controller-declared Cursor runtime exhaustion), and the final consistency review through controller review commands; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

Write the behavioral contract for one selected milestone. Define what the system must do and how it is accepted; must not include implementation tasks or silently make product decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` only as the controller-authorized Cursor runtime backup.

## Admission

Require the exact handoff tuple from `$flow-roadmap`: requirement, intent, and confirmed roadmap paths with approved revisions and SHA-256 digests plus one selected milestone ID. Recompute and verify every canonical digest. Reject ambiguous, multiple, missing, superseded, unconfirmed, or drifted input rather than substituting current files.

### Direct invocation authorization

Without `FLOW_RUN_CONTEXT`, reuse a matching active `external_review` decision only when its persisted stage scope contains `flow-spec`. Otherwise, immediately before the first required external operation, present one minimal stage-bound authorization gate for only `external_review` at `flow-spec`; map grant or denial to the structured decision with `"allowed_stages":["flow-spec"]`, record it through `flowctl authorization decide`, and use the controller-generated authorization ID and revision plus an operation manifest. It must not imply authority for another stage. A later decision or scope change uses `flowctl authorization amend`; prose cannot grant or expand authority.

Intent remains authoritative for Scope, Non-goals, Invariants, and Success Signals. Roadmap defines this milestone's delivery boundary. Repository investigation establishes existing behavior and interfaces. If specification requires changing product intent, return to `$flow-intent`; if it requires changing milestone boundaries or order, return to `$flow-roadmap`.

## Specify behavior

Write observable rules with stable IDs. Cover:

```text
RULE-* behavior and rationale
actors, triggers, preconditions
inputs and outputs
state transitions and lifecycle
normal, empty, boundary, errors, and failure behavior
permissions, privacy, and data ownership
compatibility, migration, and rollback behavior
external and internal interface contracts
observability and operational constraints
AC-* acceptance criteria linked to RULE-* and intent Success Signals
```

Each rule must be testable without prescribing a class, function, framework, or file layout. Separate verified repository facts, approved product decisions, design decisions, assumptions, and unresolved technical questions. A business-level unknown blocks approval; a bounded implementation choice may remain for Plan.

## Review and approve spec.md

Resolve the output path through the artifact contract with flow_step `spec`. Record requirement, intent, and roadmap paths/revisions plus the selected milestone ID. Verify every milestone outcome and acceptance direction maps to at least one rule and acceptance criterion, and every rule traces back to approved scope.

After the complete Spec body and digest are ready, run two independently owned lanes and then a fresh final consistency review. In the GPT Lane, the root agent chooses one GPT reviewer according to requirement difficulty and records the rationale: `gpt-5.6-sol` with `high` effort for bounded, well-understood behavior; `gpt-6-astra` with `medium` effort for complex, cross-boundary, security, compatibility, data, or ambiguous behavior. That same reviewer owns its findings: resolve or evidence-disprove each blocker, revise the artifact, and return it to that reviewer until it passes or reaches the controller limit.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker route to its owning stage or `BLOCKED_REVIEW` rather than continuing the reviewer loop.

After the GPT Lane passes, enter the Cursor Lane against the same Spec revision/digest and necessary in-scope repository context. The stage does not create review authority. Under `FLOW_RUN_CONTEXT`, consume the same active `external_review` authorization ID and revision used by the run; direct invocation uses its stage-bound equivalent. For every attempt obtain a fresh controller-validated operation manifest that is single-use and bound to `flow-spec`, the selected backend, exact prompt, and transmitted paths. The operation manifest must remain inside the authorization's issue, run, worktree, stages, backends, and exclusions; the stage must not re-prompt while that scope remains valid. The exclusions include secrets, credentials, unnecessary personal data, secret-bearing generated files, raw production data, and unrelated content. Cursor owns its substantive findings: a Cursor-driven revision returns to Cursor, not GPT, because the controller preserves the passed GPT Lane. A pending, denied, invalidated, drifted, expanded, or unresolved blocking authorization/manifest ends `BLOCKED_REVIEW`; changed scope uses `flowctl authorization amend`, and only controller-classified retryable process failures can select the iBrain runtime backup.

Use controller-observed process facts; never infer quota, capacity, connection, or timeout from vendor prose. Timeout, structured runner errors, and opaque nonzero exits without a valid report are `RUN_ERROR`; a normal exit without a valid report is `PROTOCOL_ERROR`. Retry either class exactly once without re-prompting, then run `$ibrain-review` with fixed model `glm-5.3`. Conflicting reports, conflicting report/error signals, binding mismatch, inconsistent findings, and drift remain `UNCLASSIFIED` or hard validation failures and are not degradable. For an iBrain fallback, reuse the same active `authorization_id` and revision and the same artifact snapshot, but create a `backend=ibrain` new controller-validated, single-use operation manifest/binding; it must not reuse the Cursor binding and must not re-prompt. iBrain owns and rechecks its own substantive findings and receives the same bounded retry behavior. Findings from either backend never trigger fallback. Reopen a controller-executed legacy bridge failure only with audited `flowctl review repair-classification`; it never creates PASS.

When Cursor or iBrain passes, run a fresh `gpt-6-astra` with `medium` effort and no inherited reviewer thread as the final consistency review. It checks the final digest, cross-lane finding resolution, evidence, scope, and contradictions. If it fails, revise at the owning stage, reopen the required lanes, and rerun consistency; at most three consistency cycles are allowed. Repeated blocker without material delta or exhausted cycles ends `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust two retryable process failures, consistency still runs; only after it passes may the artifact become `APPROVED_WITH_DEFECT`, with a durable `EXTERNAL_REVIEW_GAP`, full `review_binding` and binding ID, every failed attempt, remediation, and `OPEN` state. Carry it through every handoff and final completion report.

Require each report to return a `review_binding` with stage `flow-spec`, Spec revision/digest, upstream tuple, backend, exact model/effort, and terminal status. Recompute the Spec and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or any intervening drift makes the report invalid and ends `BLOCKED_REVIEW`; never attach a stale or unbound report to the gate.

After the lanes and final consistency review pass, verify the Spec remains inside the Requirement authorization. Under `FLOW_RUN_CONTEXT`, sign the reviewed binding as `ORCHESTRATED`, using `APPROVED` or `APPROVED_WITH_DEFECT`, and record `approved_revision` and `approved_digest`; continue without human approval and propagate every open review gap. Under direct invocation, show the binding and request explicit approval.

Report a handoff tuple with requirement, intent, roadmap, and spec paths plus all approved revisions and digests, milestone ID, and any open `EXTERNAL_REVIEW_GAP`. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-plan`; otherwise stop and suggest explicit `$flow-plan`. Do not create a plan or implementation inside this stage.
