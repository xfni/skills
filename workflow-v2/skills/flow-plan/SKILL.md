---
name: flow-plan
description: Use when the user explicitly requests an executable implementation plan from an approved specification.
---

# Flow Plan

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register`. Execute the GPT Lane through `flowctl review begin` and `flowctl review submit`, the Cursor Lane through `flowctl review cursor` (with controller-authorized iBrain fallback), and final consistency review through flowctl; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

Turn one approved spec.md into ordered, executable tasks. Plan how to implement and verify the approved behavior without changing product intent or specification rules.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` only as Cursor's runtime backup.

## Admission

Require the `$flow-spec` handoff tuple: requirement, intent, roadmap, and spec paths with approved revisions and SHA-256 digests plus the milestone ID. Accept `APPROVED` or `APPROVED_WITH_DEFECT`; for the latter require and propagate its open `EXTERNAL_REVIEW_GAP` without pausing orchestration. Recompute and verify every canonical digest; reject drift, missing approval, or multiple milestones.

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

Run independent lanes against the exact Plan revision/digest. In the GPT Lane, the root agent chooses and records one difficulty-based pair: `gpt-5.6-sol` with `high` effort for bounded plans, or `gpt-6-astra` with `medium` effort for complex dependencies, migrations, concurrency, security, compatibility, cross-system work, or substantial ambiguity. The selected GPT owns and rechecks its findings until pass or the controller limit.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker route to its owning stage or `BLOCKED_REVIEW` rather than continuing the reviewer loop.

After GPT passes, the Cursor Lane reviews the same Plan and necessary in-scope repository context. Invoking `$flow-plan` automatically authorizes sending the in-scope code and documents to Cursor and, only as runtime backup, iBrain. Bind `FLOW_CURSOR_AUTHORIZATION` and `FLOW_IBRAIN_AUTHORIZATION`; omit secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content. Cursor owns and rechecks Cursor findings, so a Cursor-driven revision does not rerun GPT. Denied transmission, drift, or unresolved blockers ends `BLOCKED_REVIEW`.

Treat only controller timeout or an allow-listed structured runner error as Cursor `RUN_ERROR`; retry exactly once with the same binding. `UNCLASSIFIED` is not degradable. After two Cursor runtime failures, invoke `$ibrain-review` with `glm-5.3`; iBrain owns and rechecks its findings, and its runtime failure is retried exactly once. A substantive finding from either reviewer never triggers fallback.

After Cursor or iBrain passes, run a fresh `gpt-6-astra`/`medium` final consistency review with no inherited reviewer thread. It checks the final digest, evidence and cross-lane resolution. A failed consistency review routes fixes to the owning stage and reopens necessary lanes; cap it at three cycles, with repeated no-delta blockers ending `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust their runtime retries, consistency still must pass, then create `EXTERNAL_REVIEW_GAP` with the full `review_binding` and binding ID. If any inherited or new gap remains open, the Plan may continue only as `APPROVED_WITH_DEFECT`; include it in every handoff and final completion report.

Require each report to return a `review_binding` with stage `flow-plan`, Plan revision/digest, upstream tuple, backend, exact model/effort, and terminal status. Recompute the Plan and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or any intervening drift invalidates the report and ends `BLOCKED_REVIEW`; never use a stale or unbound report.

Keep the plan body under `content_revision` with a canonical SHA-256 `content_digest` and approval metadata in a separate envelope. After review passes or the two-attempt degradation is recorded, verify the Plan remains inside the Requirement authorization. Under `FLOW_RUN_CONTEXT`, sign it as `ORCHESTRATED` without human approval; use `APPROVED` only when no gap is open and otherwise `APPROVED_WITH_DEFECT`, recording `approved_revision` and `approved_digest`. Under direct invocation, show the body, binding, and gaps and request explicit approval. Content changes invalidate both reviews.

Report a handoff tuple containing requirement, intent, roadmap, spec, and plan paths with all approved revisions and digests, milestone ID, the `TESTCASE-*` set, and all open `EXTERNAL_REVIEW_GAP` records. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-code`; otherwise stop and suggest explicit `$flow-code`. Do not implement code or run plan tasks inside this stage.
