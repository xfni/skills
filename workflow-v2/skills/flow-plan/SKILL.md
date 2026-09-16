---
name: flow-plan
description: Use when the user explicitly requests an executable implementation plan from an approved specification.
---

# Flow Plan

In orchestrated mode return the handoff payload unaccepted; the root alone calls `handoff accept` once. Stage-owned acceptance below applies only to Direct progression. Use the available human task boundary; missing historical Requirement metadata, exact duplicate tuples and auxiliary fields never require human unlock. Report available inputs and controller receipts, not invented historical approval.

For each scenario that will replay production-derived data, include `replay_manifest_digest` in its required `production_dependency`. It is SHA-256 of canonical manifest JSON excluding `milestone_id`, `scenario_id`, `plan_revision`, and `plan_digest`; after Plan approval, fill those four manifest fields from the active milestone, TESTCASE ID, and approved Plan. Integration validation and execution recheck that exact pin. A new Plan's `integration_scenarios` contract always requires complete downstream `integration_results`; omission is permitted only for an explicitly recognized legacy Plan checkpoint.

Consume each controller-validated whole-view review binding using flowctl review cursor --binding-id or mechanically eligible flowctl review ibrain --binding-id. Legacy paths are hints only. Execution rechecks the complete filtered frozen worktree and current Git HEAD/index/source binding, never a root-selected file set.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register`. Execute the GPT Lane through `flowctl review begin` and `flowctl review submit`, the Cursor Lane through `flowctl review cursor` (with controller-authorized iBrain fallback), and final consistency review through flowctl; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

Turn one approved spec.md into ordered, executable tasks. Plan how to implement and verify the approved behavior without changing product intent or specification rules.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` only as Cursor's runtime backup.

## Admission

Register the review candidate as `DRAFT` before dispatching reviews. Follow the reviewed-stage lifecycle in `../../flowctl-contract.md`: complete the selected lanes, then update only the APPROVAL envelope on `approve:plan`, register again, and hand off. Registration alone never means approval.

Use the selected milestone, current Spec or explicitly supplied Plan/task boundary, and available context. Do not require all earlier documents or model-authored exact revision/digest tuples. Preserve inherited gaps without pausing. Required reviews are backed by actual controller receipts; missing history is disclosed, not fabricated.

### Direct invocation review scope

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned. If production-dependent scenarios need a replay decision, obtain only the minimal production_replay decision before planning them.

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

Bind every scenario to the active production replay decision through the controller's `production_replay authorization ID and revision`. A scenario that will acquire sanitized production-derived data also defines the exact controller-validated replay operation manifest that Integration must validate; Plan does not execute it. Under `SKIP_PRODUCTION_REPLAY`, keep every unaffected scenario executable. Mark a scenario production-dependent only with a Plan trace that proves its acceptance claim necessarily requires production-derived data and explains why synthetic or isolated test-environment data cannot establish that claim. Record the missing assurance, reason, owner, and remediation needed for a future `PRODUCTION_REPLAY_GAP`; absence of this trace means the scenario must execute and cannot be authorized for skipping.

Prefer `integration_scenarios: {"schema_version":1,"scenarios":[...]}` metadata for the expected scenario IDs and production-dependency flag. Use unique `TESTCASE-*` IDs and retain useful reason, missing assurance, owner and remediation in the readable test outline. Extra descriptive fields and missing optional explanatory metadata are not controller gates; reviewers assess whether the outline is sufficient. Actual production acquisition still requires its authorized, Plan-pinned replay manifest before execution.

A verified legacy Plan without `integration_scenarios` remains usable as a clean historical checkpoint. It cannot authorize `SKIPPED_AUTHORIZED_REPLAY` or a new Integration results contract; revise and re-review that Plan before either behavior is needed.

Supporting databases, Redis, Elasticsearch, queues, and external APIs should use authorized isolated test-environment dependencies when available, with explicit endpoints, non-production verification, namespace/index/database/tenant isolation, collision avoidance, and cleanup. They must not require local containers by default. Plan a local dependency process or container only when no safe authorized test dependency exists or the scenario tests local dependency behavior. A remote test deployment is an explicit exception for the application under test and must state the deployment-specific behavior that requires it, plus its authorization and local fallback analysis.

Approve integration-test and fixture paths plus exactly one canonical absolute output directory for the future flow_step `integration`; glob/regex patterns are not allowed, and do not prematurely resolve its final filename. `$flow-integration` resolves that path from its current-stage instructions. If the winning human or AGENTS rule selects another directory, that rule still wins path resolution but requires a Plan revision and approval before writing. `$flow-code` may create planned seams and fixtures but must not claim or execute integration coverage.

## Traceability and approval

Resolve the output path through the artifact contract with flow_step `plan`. Include source snapshot tuples, a dependency graph, allowed change surface, validation matrix, rollback strategy, deferred work, and traceability from every Spec rule and acceptance criterion to at least one task and verification command.

Run independent lanes against the exact Plan revision/digest. In the GPT Lane, the root agent chooses and records one difficulty-based pair: `gpt-5.6-sol` with `high` effort for bounded plans, or `gpt-6-astra` with `medium` effort for complex dependencies, migrations, concurrency, security, compatibility, cross-system work, or substantial ambiguity. The selected GPT owns and rechecks its findings until pass or the controller limit.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker route to its owning stage or `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Cursor owns and rechecks its substantive findings; accepted fixes return to Cursor (or the same coder then Cursor) without rerunning the passed GPT Lane.

Use controller-observed process facts rather than vendor error wording: timeout, structured runner errors, and opaque nonzero exits without a valid report are `RUN_ERROR`; a normal exit without a valid report is `PROTOCOL_ERROR`. Retry either class exactly once for the same artifact snapshot with a new controller-validated, single-use operation manifest/binding and do not re-prompt. Conflicting review signals remain `UNCLASSIFIED` and are not degradable. After two retryable Cursor process failures, invoke `$ibrain-review` with `glm-5.3`. For iBrain fallback, create a fresh backend=ibrain package binding on the same artifact snapshot; no human authorization is needed. iBrain owns and rechecks its findings and receives the same bounded retry behavior. A substantive finding from either reviewer never triggers fallback. Reopen a controller-executed legacy bridge failure only with audited `flowctl review repair-classification`; it never creates PASS.

After Cursor or iBrain passes, run a fresh `gpt-6-astra`/`medium` final consistency review with no inherited reviewer thread. It checks the final digest, evidence and cross-lane resolution. A failed consistency review routes fixes to the owning stage and reopens necessary lanes; cap it at three cycles, with repeated no-delta blockers ending `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust their retryable process failures, consistency still must pass, then create `EXTERNAL_REVIEW_GAP` with the full `review_binding` and binding ID. If any inherited or new gap remains open, the Plan may continue only as `APPROVED_WITH_DEFECT`; include it in every handoff and final completion report.

The controller binds the actual Plan and reviewer attempt and saves the terminal receipt. Reports need an explicit conclusion and problem summaries when failed; auxiliary fields and duplicate upstream tuples are not gates. Current target/source mutation invalidates review. Return bookkeeping and format issues to the owning Agent, not a human BLOCKED gate.

Keep the plan body under `content_revision` with a canonical SHA-256 `content_digest` and approval metadata in a separate envelope. After review passes or the degradation threshold is met, verify the Plan remains inside the available Requirement authorization or explicit human task boundary; absent historical artifacts alone are not an authorization failure. Under `FLOW_RUN_CONTEXT`, sign it as `ORCHESTRATED` without human approval; use `APPROVED` only when no gap is open and otherwise `APPROVED_WITH_DEFECT`, recording `approved_revision` and `approved_digest`. Under direct invocation, show the body, binding, and gaps and request explicit approval. Content changes invalidate both reviews.

Report the current Plan, available inputs, milestone, test outline and controller-recorded receipts/gaps. Under `FLOW_RUN_CONTEXT`, return the unaccepted `FLOW_RUN_HANDOFF` with `next_stage: flow-code`; otherwise stop and suggest `$flow-code`. Do not implement code or run Plan tasks here.
