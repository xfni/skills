---
name: flow-spec
description: Use when the user explicitly requests a behavioral specification for one confirmed roadmap milestone.
---

# Flow Spec

Pass the controller-validated whole-view review binding to flowctl review cursor --binding-id (or mechanically eligible iBrain fallback). Legacy paths are hints only; never reconstruct a target-only package.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register`. Execute the GPT Lane through `flowctl review begin` and `flowctl review submit`, the Cursor Lane through `flowctl review cursor` (or `flowctl review ibrain` only after controller-declared Cursor runtime exhaustion), and the final consistency review through controller review commands; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

In orchestrated mode, return the handoff payload unaccepted; the root alone calls `handoff accept` once. The command above is stage-owned only in Direct progression. Missing auxiliary metadata or historical documents never triggers human unlock.

Write the behavioral contract for one selected milestone. Define what the system must do and how it is accepted; must not include implementation tasks or silently make product decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` only as the controller-authorized Cursor runtime backup.

## Admission

Register the review candidate as `DRAFT` before dispatching reviews. Follow the reviewed-stage lifecycle in `../../flowctl-contract.md`: complete the selected lanes, then update only the APPROVAL envelope on `approve:spec`, register again, and hand off. Registration alone never means approval.

Use the current issue/worktree, selected milestone and available delivery boundary. In normal orchestration, read Intent and Roadmap; at explicit arbitrary-node entry, use the supplied Spec/task boundary and disclose missing history. Controller-owned input bindings replace model-declared exact tuples. Resolve genuine product ambiguity, not missing historical metadata.

### Direct invocation review scope

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

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

Resolve the output path with flow_step `spec`. Record available input paths and the selected milestone, explicitly noting absent history. Review outcome-to-rule coverage against the available authorized task boundary; do not invent unavailable upstream documents or approvals.

After the complete Spec body and digest are ready, run two independently owned lanes and then a fresh final consistency review. In the GPT Lane, the root agent chooses one GPT reviewer according to requirement difficulty and records the rationale: `gpt-5.6-sol` with `high` effort for bounded, well-understood behavior; `gpt-6-astra` with `medium` effort for complex, cross-boundary, security, compatibility, data, or ambiguous behavior. That same reviewer owns its findings: resolve or evidence-disprove each blocker, revise the artifact, and return it to that reviewer until it passes or reaches the controller limit.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker route to its owning stage or `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Cursor owns and rechecks its substantive findings; accepted fixes return to Cursor (or the same coder then Cursor) without rerunning the passed GPT Lane.

Use controller-observed process facts; never infer quota, capacity, connection, or timeout from vendor prose. Timeout, structured runner errors, and opaque nonzero exits without a valid report are `RUN_ERROR`; a normal exit without a valid report is `PROTOCOL_ERROR`. Retry either class exactly once without re-prompting, then run `$ibrain-review` with fixed model `glm-5.3`. Conflicting reports, conflicting report/error signals, binding mismatch, inconsistent findings, and drift remain `UNCLASSIFIED` or hard validation failures and are not degradable. For iBrain fallback, create a fresh backend=ibrain package binding on the same artifact snapshot; no human authorization is needed. iBrain owns and rechecks its own substantive findings and receives the same bounded retry behavior. Findings from either backend never trigger fallback. Reopen a controller-executed legacy bridge failure only with audited `flowctl review repair-classification`; it never creates PASS.

When Cursor or iBrain passes, run a fresh `gpt-6-astra` with `medium` effort and no inherited reviewer thread as the final consistency review. It checks the final digest, cross-lane finding resolution, evidence, scope, and contradictions. If it fails, revise at the owning stage, reopen the required lanes, and rerun consistency; at most three consistency cycles are allowed. Repeated blocker without material delta or exhausted cycles ends `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust two retryable process failures, consistency still runs; only after it passes may the artifact become `APPROVED_WITH_DEFECT`, with a durable `EXTERNAL_REVIEW_GAP`, full `review_binding` and binding ID, every failed attempt, remediation, and `OPEN` state. Carry it through every handoff and final completion report.

The controller binds the actual Spec and reviewer attempt and saves the terminal receipt. Reports need an explicit conclusion and problem summaries when failed; auxiliary fields and duplicate upstream tuples are not gates. Current target/source mutation invalidates review, but missing historical metadata or format differences return to the owning Agent without a human BLOCKED gate.

After reviews pass, verify the Spec remains inside the available human-authorized task boundary. Under `FLOW_RUN_CONTEXT`, use `ORCHESTRATED` and controller-owned current binding, propagate gaps and continue without human approval. Direct mode retains its explicit approval gate. Absent historical Requirement metadata is not itself a blocker.

Report current Spec, available inputs, milestone and controller-recorded review receipts/gaps. Under `FLOW_RUN_CONTEXT`, return the unaccepted `FLOW_RUN_HANDOFF` with `next_stage: flow-plan`; otherwise stop and suggest `$flow-plan`. Do not create a Plan or implementation here.
