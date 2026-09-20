---
name: dev-code
description: Use when the user explicitly requests implementation and unit testing of an approved plan.
---

# Dev Code

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Apply the standard dual / minimum single-chain policy in `../../review-contract.md`. Record real independent receipts through flowctl; no mandatory third Astra consistency review. A missing route may degrade with a factual reason, never a fabricated PASS; unresolved blockers survive route changes and artifact revisions.

In orchestrated mode return the handoff payload unaccepted; the root alone calls `handoff accept` once. Stage-owned acceptance below applies only to Direct progression. Missing historical tuples or auxiliary report fields return to the owning Agent if needed, never a human unlock gate.

Pass the controller-validated whole-view review binding to flowctl review cursor --binding-id or human-selected/fallback flowctl review ibrain --binding-id. Legacy paths are hints only. Validation and execution require the recorded Code snapshot plus the complete filtered frozen worktree/source digests; drift or target-only substitution blocks egress.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Register the DRAFT candidate, record the actual independent GPT and selected external review chains, or their permitted degradation. Update approval only after minimum effective assurance and blocker resolution, then hand off through flowctl. Never edit state or self-approve; root owns acceptance in orchestrated mode.

Implement one approved plan.md with TDD and produce reviewable code plus unit-test evidence. This stage proves local behavior; it must not claim integration coverage.

**REQUIRED BACKGROUND:** Use `test-driven-development` for RED-GREEN-REFACTOR and `coding-guidelines` for scope and reliability decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `implementation` profile, or `concurrency` when that risk applies, for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the default external review route.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` as Cursor's backup or the explicitly human-selected external lane.

**REQUIRED SUBAGENT:** Use the bundled `agents/dev-coder.toml` identity `dev_coder` (`gpt-5.6-luna`, reasoning effort `max`) as the sole implementation writer. It must not delegate.

### QC coordination boundary

Read and enforce `../../qc-contract.md`. When dispatching the coordinator,
explicitly invoke `$dev-qc` with the current `QCRequest`; the explicit-only
Skill is the coordinator's complete operating contract, not optional context.

After Root validates the milestone and freezes the current object, submit a
fresh `QCRequest` to the run-scoped `dev_qc`. QC coordinates the clean-room GPT
Specialist and the existing external runner and returns a `QCCheckpoint`; its
Luna summary is not a receipt. Root owns repair dispatch, snapshot, and handoff.
Root validates each repair proposal and sends accepted Code corrections to the
same coder, then freezes the new object for original-reviewer or explicit
takeover review. QC never edits or commands the coder and never accepts the
handoff.

Create QC lazily at the first real quality checkpoint and reuse it for this
run/worktree. Silence or a wait timeout is not replacement evidence. Confirmed
QC loss permits reconstruction from controller receipts, unresolved findings,
and the Ledger. If QC cannot be used, fallback to Root coordination under the
same contract and must not fabricate assurance. These runtime rules do not add
a controller gate or change the existing review commands and lane policy.

For a previously bound live coder thread, a historical `flow_coder` role label alone is not an identity/model mismatch and does not justify replacement. Verify its existing issue/worktree/Plan binding and Luna/max configuration, then reuse the thread under the normal lifecycle rules. Only new threads use `dev_coder`; do not rewrite historical thread IDs or events.

## Admission

Record an explicit human iBrain choice through `flowctl review select-external`. If the human restricts a lane (for example GPT-only), use `flowctl review degrade --lane external --basis human --reason <instruction>` with state/revision. Preserve valid receipts and all known findings; no prohibited reviewer call or failure quota is required.

Before external review, apply declared file/directory data exclusions through the manifest recipe in `../../review-contract.md`. Exclude embedded-sample files without deleting data, disclose missing coverage, repeat exclusions on retries/fallback, and continue; prohibited test-data transfer alone is not a human gate.

Register Code evidence as `DRAFT`, then capture its production snapshot before review. Follow the reviewed-stage lifecycle in `../../flowctl-contract.md`: complete the selected lanes, then update only the APPROVAL envelope on `approve:code`, register again, and hand off. Registration alone never means approval.

Use the current Plan, milestone, worktree, allowed change surface and test commands. Required Plan review receipts must exist; all historical documents and model-declared exact tuples need not. Propagate inherited gaps without pausing and disclose missing history. Preserve protected files, permissions and the frozen code snapshot boundary.

### Direct invocation review scope

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

## Coder lifecycle

Provide a concise observable status before dispatching a coder task, before waiting for the coder, and after receiving its checkpoint. Also report before GPT review, before Cursor review, and when sending review findings back to the same coder. Each update states the task/review identifier, verified outcome so far, next action, Agent being waited on, and whether any gap blocks progress. These are progress notices, never new human gates.

Create the coder lazily, only after the Plan handoff passes admission; must not spawn it at session start. Maintain one coder thread for this Session and this Flow run. Persist `coder_thread_id`, configured model/effort, `active_task`, `completed_tasks`, `last_checkpoint`, `replacement_generation`, `replacement_reason`, and `prior_coder_thread_id` only through the flowctl coder-state command when orchestrated; never edit controller JSON. For direct invocation, retain the same state in the current conversation.

If the recorded thread is live and still bound to this issue, worktree, Plan revision/digest, and code snapshot lineage, reuse that same thread. Otherwise create one `dev_coder`, record why a replacement was necessary, and provide the full verified binding plus current diff/test state. An unavailable custom Agent, or a reported identity/model/effort mismatch, ends `BLOCKED_DEPENDENCY`; do not silently implement with the root or another model.

If the configured coder truly cannot be used after verification, explain “配置的编码 Agent 当前不可用，尚不能按本计划执行”, what work/checkpoints are preserved, and the specific configuration/maintainer action needed. Do not ask the human to identify an Agent thread or approve a model substitution forbidden by the workflow. Long coder/reviewer waits need progress notices, not a user decision.

Dispatch one dependency-ready `TASK-*` at a time. Each task packet must include its exact Plan text, linked `RULE-*`/`AC-*`, owned files and allowed scope, prerequisites, focused checks, current snapshot, and notice that the coder is not alone in the codebase and must not revert unrelated edits. The coder must not delegate. Set `active_task` before dispatch; accept completion only after validating the returned checkpoint and actual worktree state, then append the task to `completed_tasks`, clear `active_task`, update `last_checkpoint`, and send the next task to that same thread.

Apply Necessary configuration and optional behavior in `../../flow-contract.md`. Explicitly include the decided configuration/defaults and optional-behavior boundary in each affected task packet; when none is needed, say no new switch/mode. Derive this from the available authorized task context, not a mandatory historical receipt. The coder must report newly necessary variability to the root; bounded technical decisions and affected Spec/Plan updates are root-owned, not automatic human gates. Reviewers check that new branches are necessary and deliver the approved behavior with proportionate validation, not speculative default-off delivery or redundant compatibility modes.

The root agent owns orchestration, artifact and scope validation, milestone verification, and review. It must not implement the same task in parallel with the coder. Wait for the coder in windows of up to 300 seconds; completion or a message wakes the root immediately. A waiting timeout is not task failure and the root must never interrupt or replace the coder solely because a wait timed out. After each timeout, inspect the agent state and in-scope worktree and wait again. After two consecutive wait windows without an event, send one non-interrupting progress inquiry to the same thread, reset that window counter, and continue waiting. Do not send redundant inquiries while progress messages are arriving. No output, elapsed time, or absence of filesystem changes is sufficient replacement evidence, alone or in combination; long-running reasoning and commands may legitimately be silent.

Interrupt the coder only to stop an observed scope/safety violation or after the runtime confirms the existing thread cannot continue. Replacement is allowed only when the prior coder is confirmed unavailable: the runtime reports a terminal failure or missing thread, a follow-up to that exact thread fails because it no longer exists, or an interrupted scope/safety violator cannot safely resume. Idle or completed agents remain reusable through follow-up and must not be replaced merely for being idle. Before replacement, persist the latest observable state and a `CODER_THREAD_REPLACED` event with `prior_coder_thread_id`, incremented `replacement_generation`, concrete `replacement_reason`, evidence, active task, diff/test state, and recovery packet. Bind the replacement to that packet and the same Plan; never allow both generations to write concurrently. A task/sequence contradiction must return to `$dev-plan`; a behavior contradiction returns to `$dev-spec`.

Keep the coder thread available while GPT and Cursor review findings are resolved. Send each accepted, task-bound correction back to the same thread, then revalidate and rerun the required review gate. Only close the coder thread after the final code handoff is accepted, Flow is genuinely blocked/abandoned, or its binding has been invalidated.

## Execute each task

Follow dependency order and keep changes inside the task boundary:

1. Reconfirm linked `RULE-*`, `AC-*`, files, and completion criteria.
2. RED: add the planned failing unit test for behavior code, or the approved failing check/probe for a non-code task. Run it and capture the expected pre-change failure. When the approved Plan says automation is impossible, perform its justified reproducible inspection and capture the specified before evidence instead. A test that passes immediately or fails for the wrong reason is not RED.
3. GREEN: make the minimal implementation needed for that contract. Run the focused test/check, or repeat the approved inspection, and capture success or after evidence.
4. REFACTOR: when structure can improve without adding behavior, refactor it and rerun applicable checks. Otherwise record a justified no-op; never create unrelated cleanup to satisfy this step.
5. Compare the diff to the task scope and record changed files, commands, results, deviations, and unresolved risk.

Do not weaken tests, change Spec to match code, add speculative infrastructure, or execute reserved `TESTCASE-*` scenarios. Every task must return a checkpoint before the next dispatch. A discovered behavior conflict returns to `$dev-spec`; a task/sequence defect returns to `$dev-plan`.

## Review and verify

Apply Minimum independent guarantee and degradation in `../../review-contract.md`. Prefer GPT + external independent chains; actual unavailability or an explicit human constraint permits one effective chain with a recorded gap. Sol/high and Astra/medium may substitute on unavailability. The original reviewer normally rechecks its findings; an available independent takeover reviewer must receive and explicitly resolve them. No mandatory third consistency review.

After milestone validation, freeze the snapshot and run independent lanes. In the GPT Lane, the root agent chooses by requirement difficulty: `gpt-5.6-sol`/`high` for bounded work or `gpt-6-astra`/`medium` for complex or high-risk work. The selected GPT owns and rechecks its findings; accepted fixes return to the same coder and then the same GPT reviewer.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker return to the owning stage or end `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Cursor owns and rechecks its substantive findings. Material scope/implementation fixes need affected guarantees renewed. Clarification-only fixes may retain the original GPT guarantee through an evidenced applicability disposition; never implicitly carry or rebind its PASS. Budget exhaustion alone returns a local repair recommendation; known unresolved substantive blockers still prevent handoff.

Use observable runtime/protocol failures for bounded retry or allowed fallback. Retry at most once where useful; no required failure quota. Prefer iBrain when Cursor is genuinely unavailable, with fresh bindings and data exclusions. UNCLASSIFIED or conflicting reports remain invalid evidence, not a substantive approval; preserve known findings and let an allowed independent reviewer verify them. Never disguise substantive FAILED or bypass host refusal. Audited repair-classification preserves history and never creates PASS.

Finish review when current affected assurance is valid and all known blockers are independently resolved. Dual assurance is 通过; permitted single-chain assurance is 有条件通过 / COMPLETE_WITH_DEFECT with a durable gap. Missing or conflicting reports are not PASS. Resolve drift with a fresh snapshot/binding and retain findings; actual host restrictions remain authoritative. Do not force an additional Astra consistency round or exhaust unavailable channels.

The controller binds the actual code snapshot and reviewer attempt and saves the terminal receipt. Reports need an explicit conclusion and problem summaries when failed; auxiliary fields and historical tuples are not gates. Snapshot/source mutation invalidates review. Repair format or bookkeeping issues through the owning Agent, not a human BLOCKED gate.

Before a necessary interruption, distinguish “实现仍有未修复问题”, “审查工具无法取得可用报告” and “宿主拒绝了该操作”. State actual completed tests without summing overlapping suites, what remains unverified, prior repair attempts and the smallest required action. A maintainer can receive optional report/error paths; ordinary users are not asked to reset review cycles, edit state, reauthorize trusted iBrain, or accept unknown review as passed. Known safe data exclusions and fallback continue automatically under existing policy.

Resolve the output path through the artifact contract with flow_step `code`, then write or update that document with task status, RED/GREEN evidence, unit-test evidence, changed files, commands and exit results, review findings/dispositions, deviations, and traceability to `TASK-*`, `RULE-*`, and `AC-*`.

End COMPLETE only when tasks and validation pass, no known blocker remains, scope is authorized, and standard GPT + external assurance applies. Permitted single-chain assurance or inherited open gaps yields COMPLETE_WITH_DEFECT. No required external failure quota or third consistency round; author self-review or tests alone cannot supply independent assurance.

Record the full artifact tuple, code evidence, `TESTCASE-*`, all open `EXTERNAL_REVIEW_GAP` records, and frozen `code_snapshot` in handoff/evidence. The human report summarizes completed work, actual tests and unverified gaps with document links; raw tuples remain optional diagnostics. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-integration`; otherwise stop without pushing or deploying and suggest explicit `$dev-integration`.
