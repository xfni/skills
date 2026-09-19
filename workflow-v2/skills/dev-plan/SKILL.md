---
name: dev-plan
description: Use when the user explicitly requests an executable implementation plan from an approved specification.
---

# Dev Plan

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Apply the standard dual / minimum single-chain policy in `../../review-contract.md`. Record real independent receipts through flowctl; no mandatory third Astra consistency review. A missing route may degrade with a factual reason, never a fabricated PASS; unresolved blockers survive route changes and artifact revisions.

In orchestrated mode return the handoff payload unaccepted; the root alone calls `handoff accept` once. Stage-owned acceptance below applies only to Direct progression. Use the available human task boundary; missing historical Requirement metadata, exact duplicate tuples and auxiliary fields never require human unlock. Report available inputs and controller receipts, not invented historical approval.

Plan describes production-data test sources and runner methods without a replay manifest or adapter registry. Historical `replay_manifest_digest` metadata is advisory. Scenario metadata guides coverage; actual terminal Integration evidence remains necessary for completion, not for recording an obstacle.

Consume each controller-validated whole-view review binding using flowctl review cursor --binding-id or human-selected/fallback flowctl review ibrain --binding-id. Legacy paths are hints only. Execution rechecks the complete filtered frozen worktree and current Git HEAD/index/source binding, never a root-selected file set.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Register the DRAFT candidate, record the actual independent GPT and selected external review chains, or their permitted degradation. Update approval only after minimum effective assurance and blocker resolution, then hand off through flowctl. Never edit state or self-approve; root owns acceptance in orchestrated mode.

Turn one approved spec.md into ordered, executable tasks. Plan how to implement and verify the approved behavior without changing product intent or specification rules.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the default external review route.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` as Cursor's backup or the explicitly human-selected external lane.

## Admission

Record an explicit human iBrain choice through `flowctl review select-external`. If the human restricts a lane (for example GPT-only), use `flowctl review degrade --lane external --basis human --reason <instruction>` with state/revision. Preserve valid receipts and all known findings; no prohibited reviewer call or failure quota is required.

Before external review, apply declared file/directory data exclusions through the manifest recipe in `../../review-contract.md`. Exclude embedded-sample files without deleting data, disclose missing coverage, repeat exclusions on retries/fallback, and continue; prohibited test-data transfer alone is not a human gate.

Register the review candidate as `DRAFT` before dispatching reviews. Follow the reviewed-stage lifecycle in `../../flowctl-contract.md`: complete the selected lanes, then update only the APPROVAL envelope on `approve:plan`, register again, and hand off. Registration alone never means approval.

Use the selected milestone, current Spec or explicitly supplied Plan/task boundary, and available context. Do not require all earlier documents or model-authored exact revision/digest tuples. Preserve inherited gaps without pausing. Required reviews are backed by actual controller receipts; missing history is disclosed, not fabricated.

### Direct invocation review scope

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned. If production-dependent scenarios need a replay decision, obtain only the minimal production_replay decision before planning them.

Inspect the relevant repository implementation, tests, build commands, dependencies, and conventions. Resolve code facts before planning. If a task requires changing observable behavior, return to `$dev-spec`; if it changes milestone or intent boundaries, return to the owning earlier stage.

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

Apply Necessary configuration and optional behavior in `../../flow-contract.md`. Carry decided configuration boundaries/defaults into the affected TASK, explicitly stating no new behavior switch when that is the decision. Plan only risk-relevant state/invalid-value/switch-timing/interaction checks for the actual mechanism, not exhaustive combinations or assumed hot reload. Include temporary-switch removal trigger, owner and whether removal is in this task or later maintenance. New necessary variability returns to the affected Spec boundary for adjustment when behavior changes; reviewers examine necessity and maintenance cost, not missing historical configuration forms.

Add a separate Integration Verification section with stable `TESTCASE-*` scenarios linked to Spec acceptance criteria and Intent Success Signals. Each scenario distinguishes the system under test from supporting dependencies and names required fixtures/seams, participating components, environment, setup, action, expected cross-boundary result, failure evidence, retained test-data identifiers, and minimal runtime cleanup. Separate the **connectivity harness** from the **evidence oracle** and **Agent decision rule**: the harness only starts/sends/collects and must not encode the business verdict; the evidence oracle names the response, logs, audits, database/search/cache/queue/object observations and bounded waits to collect; the Agent decision rule explains how those observations satisfy or contradict the Spec/charter. Plan the application under test as a temporary local service launched from the current worktree and frozen snapshot, including build/start, isolated or ephemeral port, readiness, real request, observation, stop, and minimal runtime cleanup commands. Explicitly retain real test-environment business writes unless the human or project policy requires their cleanup.

Bind production-dependent scenarios to the active `production_replay` decision ID/revision. Under `LOCAL_PRODUCTION_REPLAY`, describe the existing project acquisition/test runner, source, input snapshot digest, local service requests, expected observations, retained test-environment writes, and minimal runtime cleanup. Plan records the method and does not execute production acquisition. Flow requires no sanitizer, trusted profile, replay manifest or independent adapter scripts. Data governance belongs to project policy; do not send test data to reviewers or add it to Git. Under `SKIP_PRODUCTION_REPLAY`, execute all unaffected scenarios. Only mark a scenario production-dependent when its acceptance claim needs production-derived data and synthetic or isolated test data is insufficient; document the missing assurance, reason, owner and remediation for a future `PRODUCTION_REPLAY_GAP`.

Prefer `integration_scenarios: {"schema_version":1,"scenarios":[...]}` metadata for the expected scenario IDs and production-dependency flag. Use unique `TESTCASE-*` IDs and retain useful reason, missing assurance, owner and remediation in the readable test outline. Extra descriptive fields and missing optional explanatory metadata are not controller gates; reviewers assess whether the outline is sufficient. Actual production acquisition requires its scoped decision and applicable project/host permissions, not a Flow adapter manifest.

A legacy Plan without `integration_scenarios` remains usable. The Integration Agent records actual scope, production-dependency justification and coverage judgment. Do not revise/re-review Plan merely to fill a machine table. Replay skips still require the active scoped decision and open gaps.

Supporting databases, Redis, Elasticsearch, queues, and external APIs should use authorized isolated test-environment dependencies when available, with explicit endpoints, non-production verification, namespace/index/database/tenant isolation, collision avoidance, persistent-write traceability, and minimal runtime cleanup. They must not require local containers by default. Plan a local dependency process or container only when no safe authorized test dependency exists or the scenario tests local dependency behavior. A remote test deployment is an explicit exception for the application under test and must state the deployment-specific behavior that requires it, plus its authorization and local fallback analysis.

Approve integration-test and fixture paths plus exactly one canonical absolute output directory for the future flow_step `integration`; glob/regex patterns are not allowed, and do not prematurely resolve its final filename. `$dev-integration` resolves that path from its current-stage instructions. If the winning human or AGENTS rule selects another directory, that rule still wins path resolution but requires a Plan revision and approval before writing. `$dev-code` may create planned seams and fixtures but must not claim or execute integration coverage.

Apply Test infrastructure permission in `../../flow-contract.md`: identify the existing permission source and effective test launch configuration for required databases/Mongo, Redis, search, queues and object storage. State the scenario-required access, isolation key, retained-data identifiers, and minimal runtime cleanup scope, plus scoped sandbox/network escalation where necessary. Do not require local Docker or another human confirmation within already-approved scope; never leave production/unknown defaults to be discovered by a live startup attempt. This is Agent planning guidance, not new required controller fields.

Apply its discovery-first rule to every middleware: inspect source/config loaders, test profiles and startup scripts for endpoint/resource scope and supported override names before asking the human for them. Record non-secret source references and actual unknowns; never equate a code-found address with authorization or create a new controller prerequisite for this outline.

## Traceability and approval

Apply Minimum independent guarantee and degradation in `../../review-contract.md`. Prefer GPT + external independent chains; actual unavailability or an explicit human constraint permits one effective chain with a recorded gap. Sol/high and Astra/medium may substitute on unavailability. The original reviewer normally rechecks its findings; an available independent takeover reviewer must receive and explicitly resolve them. No mandatory third consistency review.

Resolve the output path through the artifact contract with flow_step `plan`. Include source snapshot tuples, a dependency graph, allowed change surface, validation matrix, rollback strategy, deferred work, and traceability from every Spec rule and acceptance criterion to at least one task and verification command.

Run independent lanes against the exact Plan revision/digest. In the GPT Lane, the root agent chooses and records one difficulty-based pair: `gpt-5.6-sol` with `high` effort for bounded plans, or `gpt-6-astra` with `medium` effort for complex dependencies, migrations, concurrency, security, compatibility, cross-system work, or substantial ambiguity. The selected GPT owns and rechecks its findings until pass or the controller limit.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker route to its owning stage or `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Cursor owns and rechecks its substantive findings. Material scope/implementation fixes need affected guarantees renewed. Clarification-only fixes may retain the original GPT guarantee through an evidenced applicability disposition; never implicitly carry or rebind its PASS. Budget exhaustion alone returns a local repair recommendation; known unresolved substantive blockers still prevent handoff.

Use observable runtime/protocol failures for bounded retry or allowed fallback. Retry at most once where useful; no required failure quota. Prefer iBrain when Cursor is genuinely unavailable, with fresh bindings and data exclusions. UNCLASSIFIED or conflicting reports remain invalid evidence, not a substantive approval; preserve known findings and let an allowed independent reviewer verify them. Never disguise substantive FAILED or bypass host refusal. Audited repair-classification preserves history and never creates PASS.

Finish review when current affected assurance is valid and all known blockers are independently resolved. Dual assurance is 通过; permitted single-chain assurance is 有条件通过 / COMPLETE_WITH_DEFECT with a durable gap. Missing or conflicting reports are not PASS. Resolve drift with a fresh snapshot/binding and retain findings; actual host restrictions remain authoritative. Do not force an additional Astra consistency round or exhaust unavailable channels.

The controller binds the actual Plan and reviewer attempt and saves the terminal receipt. Reports need an explicit conclusion and problem summaries when failed; auxiliary fields and duplicate upstream tuples are not gates. Current target/source mutation invalidates review. Return bookkeeping and format issues to the owning Agent, not a human BLOCKED gate.

Keep the plan body under `content_revision` with a canonical SHA-256 `content_digest` and approval metadata in a separate envelope. After review passes or the degradation threshold is met, verify the Plan remains inside the available Requirement authorization or explicit human task boundary; absent historical artifacts alone are not an authorization failure. Under `FLOW_RUN_CONTEXT`, sign it as `ORCHESTRATED` without human approval; use `APPROVED` only when no gap is open and otherwise `APPROVED_WITH_DEFECT`, recording `approved_revision` and `approved_digest`. Under direct invocation, show a readable execution-scope summary and material gaps, link the full body, and request explicit approval of that recorded scope. Byte changes are recorded, not automatic withdrawal. Material changes require necessary fresh reviews; supported clarification may use a bounded disposition, retaining original receipt identities.

Report the current Plan, available inputs, milestone, test outline and controller-recorded receipts/gaps. Under `FLOW_RUN_CONTEXT`, return the unaccepted `FLOW_RUN_HANDOFF` with `next_stage: flow-code`; otherwise stop and suggest `$dev-code`. Do not implement code or run Plan tasks here.

Direct approval shows what will change, the task sequence, validation/test outline, expected side effects/rollback and material gaps, with a link to the full Plan; ask to confirm or correct this execution scope rather than approve YAML/digest metadata. Missing replay authority uses only the existing local-data/skip choice with its missing-coverage consequence; missing middleware facts follow discovery-first and ask only the remaining approved resource or source location. Review/report faults require Agent repair or a readable maintainer request, not fabricated adapter requirements or user consent to waive verification.
