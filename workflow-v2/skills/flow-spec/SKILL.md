---
name: flow-spec
description: Use when the user explicitly requests a behavioral specification for one confirmed roadmap milestone.
---

# Flow Spec

Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.

Write the behavioral contract for one selected milestone. Define what the system must do and how it is accepted; must not include implementation tasks or silently make product decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

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

After the complete Spec body and digest are ready, run the fixed GPT → Cursor review gate against that exact revision and digest. The root agent chooses one GPT reviewer according to requirement difficulty and records the rationale: `gpt-5.6-sol` with `high` effort for bounded, well-understood behavior; `gpt-6-astra` with `medium` effort for complex, cross-boundary, security, compatibility, data, or ambiguous behavior. No other GPT model/effort pair is allowed. Resolve or evidence-disprove every blocking finding, update the revision/digest when content changes, and rerun the GPT review until it passes.

Only then invoke `$cursor-review` as the mandatory final review of the same Spec revision/digest and necessary in-scope repository context. Invoking `$flow-spec` automatically authorizes sending the in-scope code and documents needed for this review to Cursor. This authorization excludes secrets, credentials, personal data not required by the approved scope, generated secret-bearing files, and unrelated repository content; redact or omit them. Record the exact transmitted paths/revisions/digests. Cursor receipt is not approval: resolve or disprove its findings. Any Cursor-driven content change invalidates both reviews and must rerun the GPT review, pass it, and then rerun Cursor. Denied transmission, snapshot drift, or an unresolved blocking finding ends `BLOCKED_REVIEW`; only a classified `RUN_ERROR` follows the retry policy below. Cursor is final only when its last report causes no revision and has no unresolved blocker/high finding.

Classify a Cursor `INCOMPLETE` caused by SDK/credential availability, connection, bridge, timeout, or malformed/missing terminal report as `RUN_ERROR`, not a review finding. With the same frozen binding and transmission manifest, retry exactly once and record both attempt IDs, timestamps, and sanitized errors. A returned review with findings is not a review finding failure eligible for retry or degradation: resolve it through the normal gate. Denied transmission, source drift, or an invalid local input is also not degradable and remains `BLOCKED_REVIEW`.

If the second Cursor attempt ends in `RUN_ERROR`, allow human approval but mark the artifact `APPROVED_WITH_DEFECT`, add a durable `CURSOR_REVIEW_GAP` containing a full `review_binding` and binding ID, both attempts referencing that same ID, affected revision/digest and upstream tuple, backend/model/effort, unperformed assurance, owner, remediation, and `OPEN` state, and remind the human before approval. Carry that record in the next handoff and remind the human at every downstream admission until a successful bound Cursor review of that exact binding closes it. Never describe this state as fully reviewed.

Require each report to return a `review_binding` with stage `flow-spec`, Spec revision/digest, upstream tuple, backend, exact model/effort, and terminal status. Recompute the Spec and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or any intervening drift makes the report invalid and ends `BLOCKED_REVIEW`; never attach a stale or unbound report to the gate.

After the review gate passes or the two-attempt degradation record is complete, show the content revision, digest, and any open review gap to the human and request approval. Content changes increment that revision, recompute the digest, invalidate both reviews, and require the full GPT → Cursor gate again before a new preview. Keep status and signatures in a separate approval envelope; confirmation records `status: APPROVED` or `APPROVED_WITH_DEFECT`, confirmer, time, `approved_revision`, and `approved_digest` equal to the reviewed body.

Stop after approval. Report a handoff tuple with requirement, intent, roadmap, and spec paths plus all approved revisions and digests, milestone ID, and any open `CURSOR_REVIEW_GAP`; suggest explicit `$flow-plan`. Do not create a plan or implementation automatically.
