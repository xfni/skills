---
name: flow-spec
description: Use when the user explicitly requests a behavioral specification for one confirmed roadmap milestone.
---

# Flow Spec

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

After the GPT Lane passes, enter the Cursor Lane against the same Spec revision/digest and necessary in-scope repository context. Invoking `$flow-spec` automatically authorizes sending the in-scope code and documents needed for this review to Cursor and, solely as runtime backup, iBrain. Materialize or inherit `FLOW_CURSOR_AUTHORIZATION` and `FLOW_IBRAIN_AUTHORIZATION`; do not ask for duplicate confirmation while each manifest remains bound. Both authorizations exclude secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content. Cursor owns its substantive findings: a Cursor-driven revision returns to Cursor, not GPT, because the controller preserves the passed GPT Lane. A denied transmission, drift, or unresolved blocking finding ends `BLOCKED_REVIEW`; only classified `RUN_ERROR` can select the backup.

Classify only a controller timeout or allow-listed structured runner error as Cursor `RUN_ERROR`; never infer it from log keywords. A malformed, missing, unbound, inconsistent, or empty `INCOMPLETE` report is `UNCLASSIFIED` and is not degradable. For `RUN_ERROR`, retry exactly once. After the second Cursor `RUN_ERROR`, run `$ibrain-review` with fixed model `glm-5.3` against the same binding. iBrain owns and rechecks its own substantive findings. Its own `RUN_ERROR` is also retried exactly once. Findings from either backend are not runtime failure and never trigger fallback.

When Cursor or iBrain passes, run a fresh `gpt-6-astra` with `medium` effort and no inherited reviewer thread as the final consistency review. It checks the final digest, cross-lane finding resolution, evidence, scope, and contradictions. If it fails, revise at the owning stage, reopen the required lanes, and rerun consistency; at most three consistency cycles are allowed. Repeated blocker without material delta or exhausted cycles ends `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust two `RUN_ERROR` attempts, consistency still runs; only after it passes may the artifact become `APPROVED_WITH_DEFECT`, with a durable `EXTERNAL_REVIEW_GAP`, full `review_binding` and binding ID, every failed attempt, remediation, and `OPEN` state. Carry it through every handoff and final completion report.

Require each report to return a `review_binding` with stage `flow-spec`, Spec revision/digest, upstream tuple, backend, exact model/effort, and terminal status. Recompute the Spec and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or any intervening drift makes the report invalid and ends `BLOCKED_REVIEW`; never attach a stale or unbound report to the gate.

After the lanes and final consistency review pass, verify the Spec remains inside the Requirement authorization. Under `FLOW_RUN_CONTEXT`, sign the reviewed binding as `ORCHESTRATED`, using `APPROVED` or `APPROVED_WITH_DEFECT`, and record `approved_revision` and `approved_digest`; continue without human approval and propagate every open review gap. Under direct invocation, show the binding and request explicit approval.

Report a handoff tuple with requirement, intent, roadmap, and spec paths plus all approved revisions and digests, milestone ID, and any open `EXTERNAL_REVIEW_GAP`. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-plan`; otherwise stop and suggest explicit `$flow-plan`. Do not create a plan or implementation inside this stage.
