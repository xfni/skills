---
name: flow-code
description: Use when the user explicitly requests implementation and unit testing of an approved plan.
---

# Flow Code

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Register final Astra review with `flowctl review begin --backend consistency --model gpt-6-astra --effort medium`, then submit to that returned attempt. The GPT primary lane uses `--backend gpt`; sharing a model does not merge roles or cycle counts. Use the Review lanes and evidence section of `../../flowctl-contract.md`; pending_action remains advisory.

In orchestrated mode return the handoff payload unaccepted; the root alone calls `handoff accept` once. Stage-owned acceptance below applies only to Direct progression. Missing historical tuples or auxiliary report fields return to the owning Agent if needed, never a human unlock gate.

Pass the controller-validated whole-view review binding to flowctl review cursor --binding-id or human-selected/fallback flowctl review ibrain --binding-id. Legacy paths are hints only. Validation and execution require the recorded Code snapshot plus the complete filtered frozen worktree/source digests; drift or target-only substitution blocks egress.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register` for Code evidence and `flowctl snapshot capture` for the frozen implementation. Execute the GPT Lane through `flowctl review begin` and `flowctl review submit`, the Cursor Lane through `flowctl review cursor` (with controller-authorized iBrain fallback), and final consistency review through flowctl; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

Implement one approved plan.md with TDD and produce reviewable code plus unit-test evidence. This stage proves local behavior; it must not claim integration coverage.

**REQUIRED BACKGROUND:** Use `test-driven-development` for RED-GREEN-REFACTOR and `coding-guidelines` for scope and reliability decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `implementation` profile, or `concurrency` when that risk applies, for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the default external review route.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` as Cursor's backup or the explicitly human-selected external lane.

**REQUIRED SUBAGENT:** Use the bundled `agents/flow-coder.toml` identity `flow_coder` (`gpt-5.6-luna`, reasoning effort `max`) as the sole implementation writer. It must not delegate.

## Admission

An explicit human iBrain choice overrides the default Cursor route described below: record it through `flowctl review select-external` per `../../review-contract.md`, then run GPT -> iBrain -> fresh Astra consistency. Do not require Cursor calls/failures, re-ask external authorization, or clear valid GPT/test evidence. Resume follows the recorded selection; substantive findings and true host restrictions remain in force.

Before external review, apply declared file/directory data exclusions through the manifest recipe in `../../review-contract.md`. Exclude embedded-sample files without deleting data, disclose missing coverage, repeat exclusions on retries/fallback, and continue; prohibited test-data transfer alone is not a human gate.

Register Code evidence as `DRAFT`, then capture its production snapshot before review. Follow the reviewed-stage lifecycle in `../../flowctl-contract.md`: complete the selected lanes, then update only the APPROVAL envelope on `approve:code`, register again, and hand off. Registration alone never means approval.

Use the current Plan, milestone, worktree, allowed change surface and test commands. Required Plan review receipts must exist; all historical documents and model-declared exact tuples need not. Propagate inherited gaps without pausing and disclose missing history. Preserve protected files, permissions and the frozen code snapshot boundary.

### Direct invocation review scope

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

## Coder lifecycle

Provide a concise observable status before dispatching a coder task, before waiting for the coder, and after receiving its checkpoint. Also report before GPT review, before Cursor review, and when sending review findings back to the same coder. Each update states the task/review identifier, verified outcome so far, next action, Agent being waited on, and whether any gap blocks progress. These are progress notices, never new human gates.

Create the coder lazily, only after the Plan handoff passes admission; must not spawn it at session start. Maintain one coder thread for this Session and this Flow run. Persist `coder_thread_id`, configured model/effort, `active_task`, `completed_tasks`, `last_checkpoint`, `replacement_generation`, `replacement_reason`, and `prior_coder_thread_id` only through the flowctl coder-state command when orchestrated; never edit controller JSON. For direct invocation, retain the same state in the current conversation.

If the recorded thread is live and still bound to this issue, worktree, Plan revision/digest, and code snapshot lineage, reuse that same thread. Otherwise create one `flow_coder`, record why a replacement was necessary, and provide the full verified binding plus current diff/test state. An unavailable custom Agent, or a reported identity/model/effort mismatch, ends `BLOCKED_DEPENDENCY`; do not silently implement with the root or another model.

If the configured coder truly cannot be used after verification, explain “配置的编码 Agent 当前不可用，尚不能按本计划执行”, what work/checkpoints are preserved, and the specific configuration/maintainer action needed. Do not ask the human to identify an Agent thread or approve a model substitution forbidden by the workflow. Long coder/reviewer waits need progress notices, not a user decision.

Dispatch one dependency-ready `TASK-*` at a time. Each task packet must include its exact Plan text, linked `RULE-*`/`AC-*`, owned files and allowed scope, prerequisites, focused checks, current snapshot, and notice that the coder is not alone in the codebase and must not revert unrelated edits. The coder must not delegate. Set `active_task` before dispatch; accept completion only after validating the returned checkpoint and actual worktree state, then append the task to `completed_tasks`, clear `active_task`, update `last_checkpoint`, and send the next task to that same thread.

The root agent owns orchestration, artifact and scope validation, milestone verification, and review. It must not implement the same task in parallel with the coder. Wait for the coder in windows of up to 300 seconds; completion or a message wakes the root immediately. A waiting timeout is not task failure and the root must never interrupt or replace the coder solely because a wait timed out. After each timeout, inspect the agent state and in-scope worktree and wait again. After two consecutive wait windows without an event, send one non-interrupting progress inquiry to the same thread, reset that window counter, and continue waiting. Do not send redundant inquiries while progress messages are arriving. No output, elapsed time, or absence of filesystem changes is sufficient replacement evidence, alone or in combination; long-running reasoning and commands may legitimately be silent.

Interrupt the coder only to stop an observed scope/safety violation or after the runtime confirms the existing thread cannot continue. Replacement is allowed only when the prior coder is confirmed unavailable: the runtime reports a terminal failure or missing thread, a follow-up to that exact thread fails because it no longer exists, or an interrupted scope/safety violator cannot safely resume. Idle or completed agents remain reusable through follow-up and must not be replaced merely for being idle. Before replacement, persist the latest observable state and a `CODER_THREAD_REPLACED` event with `prior_coder_thread_id`, incremented `replacement_generation`, concrete `replacement_reason`, evidence, active task, diff/test state, and recovery packet. Bind the replacement to that packet and the same Plan; never allow both generations to write concurrently. A task/sequence contradiction must return to `$flow-plan`; a behavior contradiction returns to `$flow-spec`.

Keep the coder thread available while GPT and Cursor review findings are resolved. Send each accepted, task-bound correction back to the same thread, then revalidate and rerun the required review gate. Only close the coder thread after the final code handoff is accepted, Flow is genuinely blocked/abandoned, or its binding has been invalidated.

## Execute each task

Follow dependency order and keep changes inside the task boundary:

1. Reconfirm linked `RULE-*`, `AC-*`, files, and completion criteria.
2. RED: add the planned failing unit test for behavior code, or the approved failing check/probe for a non-code task. Run it and capture the expected pre-change failure. When the approved Plan says automation is impossible, perform its justified reproducible inspection and capture the specified before evidence instead. A test that passes immediately or fails for the wrong reason is not RED.
3. GREEN: make the minimal implementation needed for that contract. Run the focused test/check, or repeat the approved inspection, and capture success or after evidence.
4. REFACTOR: when structure can improve without adding behavior, refactor it and rerun applicable checks. Otherwise record a justified no-op; never create unrelated cleanup to satisfy this step.
5. Compare the diff to the task scope and record changed files, commands, results, deviations, and unresolved risk.

Do not weaken tests, change Spec to match code, add speculative infrastructure, or execute reserved `TESTCASE-*` scenarios. Every task must return a checkpoint before the next dispatch. A discovered behavior conflict returns to `$flow-spec`; a task/sequence defect returns to `$flow-plan`.

## Review and verify

After milestone validation, freeze the snapshot and run independent lanes. In the GPT Lane, the root agent chooses by requirement difficulty: `gpt-5.6-sol`/`high` for bounded work or `gpt-6-astra`/`medium` for complex or high-risk work. The selected GPT owns and rechecks its findings; accepted fixes return to the same coder and then the same GPT reviewer.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker return to the owning stage or end `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Cursor owns and rechecks its substantive findings. Material scope/implementation fixes need affected guarantees renewed. Clarification-only fixes may retain the original GPT guarantee through an evidenced applicability disposition; never implicitly carry or rebind its PASS. Budget exhaustion alone returns a local repair recommendation; known unresolved substantive blockers still prevent handoff.

Use controller-observed process facts rather than vendor error wording. Retry classified `RUN_ERROR` or `PROTOCOL_ERROR` exactly once and do not re-prompt; conflicting review signals remain `UNCLASSIFIED` and are not degradable, while findings are never fallback conditions. After the second retryable Cursor process failure invoke `$ibrain-review` with `glm-5.3`. For iBrain fallback, create a fresh backend=ibrain package binding on the same artifact snapshot; no human authorization is needed. iBrain owns and rechecks its findings and receives the same bounded retry behavior. Reopen a controller-executed legacy bridge failure only with audited `flowctl review repair-classification`; it never creates PASS. Findings from either backend never select the other backend.

After Cursor or iBrain passes, run a fresh `gpt-6-astra`/`medium` final consistency review with no inherited thread. It validates final digest, evidence, scope, and cross-lane resolution. A failure returns accepted fixes to the same coder, reopens necessary lanes, and reruns consistency, capped at three cycles; repeated no-delta blockers end `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust retryable process failures, consistency must still pass before creating `EXTERNAL_REVIEW_GAP` and allowing `COMPLETE_WITH_DEFECT`. Carry the full `review_binding` and binding ID through every handoff and final completion report.

The controller binds the actual code snapshot and reviewer attempt and saves the terminal receipt. Reports need an explicit conclusion and problem summaries when failed; auxiliary fields and historical tuples are not gates. Snapshot/source mutation invalidates review. Repair format or bookkeeping issues through the owning Agent, not a human BLOCKED gate.

Before a necessary interruption, distinguish “实现仍有未修复问题”, “审查工具无法取得可用报告” and “宿主拒绝了该操作”. State actual completed tests without summing overlapping suites, what remains unverified, prior repair attempts and the smallest required action. A maintainer can receive optional report/error paths; ordinary users are not asked to reset review cycles, edit state, reauthorize trusted iBrain, or accept unknown review as passed. Known safe data exclusions and fallback continue automatically under existing policy.

Resolve the output path through the artifact contract with flow_step `code`, then write or update that document with task status, RED/GREEN evidence, unit-test evidence, changed files, commands and exit results, review findings/dispositions, deviations, and traceability to `TASK-*`, `RULE-*`, and `AC-*`.

End `COMPLETE` only when tasks and validation pass, no blocker remains, the diff is in scope, an external lane and final consistency review passed, and no gap is open. Use `COMPLETE_WITH_DEFECT` only when all other conditions pass but the current external route has exhausted its controller-recorded retryable failures or an inherited `EXTERNAL_REVIEW_GAP` remains open. Default-route exhaustion requires two failures each from Cursor and iBrain; explicit selected-iBrain exhaustion requires two from iBrain alone, without Cursor attempts. Fresh consistency must pass in either case; findings, ambiguity and host refusal do not qualify as runtime exhaustion.

Record the full artifact tuple, code evidence, `TESTCASE-*`, all open `EXTERNAL_REVIEW_GAP` records, and frozen `code_snapshot` in handoff/evidence. The human report summarizes completed work, actual tests and unverified gaps with document links; raw tuples remain optional diagnostics. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-integration`; otherwise stop without pushing or deploying and suggest explicit `$flow-integration`.
