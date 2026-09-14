---
name: flow-plan
description: Use when the user explicitly requests an executable implementation plan from an approved specification.
---

# Flow Plan

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Turn one approved spec.md into ordered, executable tasks. Plan how to implement and verify the approved behavior without changing product intent or specification rules.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

## Admission

Require the `$flow-spec` handoff tuple: requirement, intent, roadmap, and spec paths with approved revisions and SHA-256 digests plus the milestone ID. Accept `APPROVED` or `APPROVED_WITH_DEFECT`; for the latter require and propagate its open `CURSOR_REVIEW_GAP` without pausing orchestration. Recompute and verify every canonical digest; reject drift, missing approval, or multiple milestones.

Inspect the relevant repository implementation, tests, build commands, dependencies, and conventions. Resolve code facts before planning. If a task requires changing observable behavior, return to `$flow-spec`; if it changes milestone or intent boundaries, return to the owning earlier stage.

## Write executable tasks

Create stable `TASK-*` entries in dependency order. Every task contains:

```text
purpose and linked RULE-*/AC-*/MILESTONE-*
exact files and modules to add or change
preconditions and dependencies
test-first step and expected pre-change failure evidence
minimal implementation step
refactor boundary
verification commands and expected evidence
error, compatibility, migration, and rollback handling when applicable
completion criteria and handoff
```

Tasks must be small enough to implement and review independently. Every behavior-code task starts with a failing unit test. A migration, configuration, build, fixture, or other non-code task starts with the smallest failing automated check or probe that demonstrates the unmet contract; when automation is impossible, require a justified reproducible inspection and expected before/after evidence rather than inventing a unit test. Include unit-test work in the owning task.

Add a separate Integration Verification section with stable `TESTCASE-*` scenarios linked to Spec acceptance criteria and Intent Success Signals. Each scenario distinguishes the system under test from supporting dependencies and names required fixtures/seams, participating components, environment, setup, action, expected cross-boundary result, failure evidence, and safe cleanup. Plan the application under test as a temporary local service launched from the current worktree and frozen snapshot, including build/start, isolated or ephemeral port, readiness, real request, observation, stop, and cleanup commands.

Supporting databases, Redis, Elasticsearch, queues, and external APIs should use authorized isolated test-environment dependencies when available, with explicit endpoints, non-production verification, namespace/index/database/tenant isolation, collision avoidance, and cleanup. They must not require local containers by default. Plan a local dependency process or container only when no safe authorized test dependency exists or the scenario tests local dependency behavior. A remote test deployment is an explicit exception for the application under test and must state the deployment-specific behavior that requires it, plus its authorization and local fallback analysis.

Approve integration-test and fixture paths plus exactly one canonical absolute output directory for the future flow_step `integration`; glob/regex patterns are not allowed, and do not prematurely resolve its final filename. `$flow-integration` resolves that path from its current-stage instructions. If the winning human or AGENTS rule selects another directory, that rule still wins path resolution but requires a Plan revision and approval before writing. `$flow-code` may create planned seams and fixtures but must not claim or execute integration coverage.

## Traceability and approval

Resolve the output path through the artifact contract with flow_step `plan`. Include source snapshot tuples, a dependency graph, allowed change surface, validation matrix, rollback strategy, deferred work, and traceability from every Spec rule and acceptance criterion to at least one task and verification command.

After the complete Plan body and digest are ready, run the fixed GPT → Cursor review gate against that exact revision and digest. The root agent chooses and records one difficulty-based pair: `gpt-5.6-sol` with `high` effort for bounded plans with known paths and commands, or `gpt-6-astra` with `medium` effort for complex dependencies, migrations, concurrency, security, compatibility, cross-system work, or substantial ambiguity. No other GPT pair is allowed. Use the `design` profile, resolve or evidence-disprove blocking findings, and rerun the GPT review after every Plan change until it passes.

Then invoke `$cursor-review` as the mandatory final review of the same Plan revision/digest, approved Spec sources, and necessary in-scope repository context. Invoking `$flow-plan` automatically authorizes sending the in-scope code and documents needed for this review to Cursor, excluding secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content. Record transmitted paths/revisions/digests. Any Cursor-driven change invalidates both reviews and must rerun the GPT review before Cursor runs again. Denied transmission, drift, or unresolved blocker/high findings ends `BLOCKED_REVIEW`; only a classified `RUN_ERROR` follows the retry policy below. Cursor is final only when its last report causes no revision and has no unresolved blocker/high finding.

Treat SDK/credential availability, connection, bridge, timeout, or malformed/missing terminal report as Cursor `RUN_ERROR`; retry exactly once with the same frozen binding and transmission manifest, recording both attempt IDs, timestamps, and sanitized errors. A normal report containing findings is not a review finding failure eligible for degradation and must be resolved. Denied transmission, drift, or invalid local input remains `BLOCKED_REVIEW`.

After a second `RUN_ERROR`, create a durable open `CURSOR_REVIEW_GAP` with the full `review_binding` and binding ID, both attempts referencing that ID, bound revision/digest and upstream tuple, backend/model/effort, missing assurance, owner, and remediation. Combine it with inherited gaps. If any inherited or new `CURSOR_REVIEW_GAP` remains `OPEN`, the Plan may continue only as `APPROVED_WITH_DEFECT`, even when its own Cursor review succeeds; include all gaps in the next handoff and final completion report until a successful bound Cursor review closes each affected artifact. Never call the Plan fully reviewed or pause solely to announce the gap.

Require each report to return a `review_binding` with stage `flow-plan`, Plan revision/digest, upstream tuple, backend, exact model/effort, and terminal status. Recompute the Plan and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or any intervening drift invalidates the report and ends `BLOCKED_REVIEW`; never use a stale or unbound report.

Keep the plan body under `content_revision` with a canonical SHA-256 `content_digest` and approval metadata in a separate envelope. After review passes or the two-attempt degradation is recorded, verify the Plan remains inside the Requirement authorization. Under `FLOW_RUN_CONTEXT`, sign it as `ORCHESTRATED` without human approval; use `APPROVED` only when no gap is open and otherwise `APPROVED_WITH_DEFECT`, recording `approved_revision` and `approved_digest`. Under direct invocation, show the body, binding, and gaps and request explicit approval. Content changes invalidate both reviews.

Report a handoff tuple containing requirement, intent, roadmap, spec, and plan paths with all approved revisions and digests, milestone ID, the `TESTCASE-*` set, and all open `CURSOR_REVIEW_GAP` records. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-code`; otherwise stop and suggest explicit `$flow-code`. Do not implement code or run plan tasks inside this stage.
