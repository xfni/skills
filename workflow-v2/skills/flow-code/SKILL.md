---
name: flow-code
description: Use when the user explicitly requests implementation and unit testing of an approved plan.
---

# Flow Code

Pass the validated review binding to `flowctl review cursor --binding-id` (or its authorized iBrain fallback). Explicitly include necessary implementation, tests, and evidence files in the manifest. Validation and execution require the recorded Code snapshot and the identical file set/source digests; drift or target-only substitution blocks egress.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register` for Code evidence and `flowctl snapshot capture` for the frozen implementation. Execute the GPT Lane through `flowctl review begin` and `flowctl review submit`, the Cursor Lane through `flowctl review cursor` (with controller-authorized iBrain fallback), and final consistency review through flowctl; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

Implement one approved plan.md with TDD and produce reviewable code plus unit-test evidence. This stage proves local behavior; it must not claim integration coverage.

**REQUIRED BACKGROUND:** Use `test-driven-development` for RED-GREEN-REFACTOR and `coding-guidelines` for scope and reliability decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `implementation` profile, or `concurrency` when that risk applies, for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` only as Cursor's runtime backup.

**REQUIRED SUBAGENT:** Use the bundled `agents/flow-coder.toml` identity `flow_coder` (`gpt-5.6-luna`, reasoning effort `max`) as the sole implementation writer. It must not delegate.

## Admission

Require the complete `$flow-plan` handoff tuple: requirement, intent, roadmap, spec, and approved plan paths with approved revisions and SHA-256 digests, milestone ID, `TESTCASE-*`, and gaps. Propagate inherited `EXTERNAL_REVIEW_GAP` records without pausing orchestration. Recompute every canonical digest and verify snapshots, worktree, allowed change surface, commands, and prerequisites.

### Direct invocation authorization

Without `FLOW_RUN_CONTEXT`, reuse a matching active `external_review` decision only when its persisted stage scope contains `flow-code`. Otherwise, immediately before the first required external operation, present one minimal stage-bound authorization gate for only `external_review` at `flow-code`; map grant or denial to the structured decision with `"allowed_stages":["flow-code"]`, record it through `flowctl authorization decide`, and use the controller-generated authorization ID and revision plus an operation manifest. It must not imply authority for another stage. A later decision or scope change uses `flowctl authorization amend`; prose cannot grant or expand authority.

## Coder lifecycle

Provide a concise observable status before dispatching a coder task, before waiting for the coder, and after receiving its checkpoint. Also report before GPT review, before Cursor review, and when sending review findings back to the same coder. Each update states the task/review identifier, verified outcome so far, next action, Agent being waited on, and whether any gap blocks progress. These are progress notices, never new human gates.

Create the coder lazily, only after the Plan handoff passes admission; must not spawn it at session start. Maintain one coder thread for this Session and this Flow run. Persist `coder_thread_id`, configured model/effort, `active_task`, `completed_tasks`, `last_checkpoint`, `replacement_generation`, `replacement_reason`, and `prior_coder_thread_id` only through the flowctl coder-state command when orchestrated; never edit controller JSON. For direct invocation, retain the same state in the current conversation.

If the recorded thread is live and still bound to this issue, worktree, Plan revision/digest, and code snapshot lineage, reuse that same thread. Otherwise create one `flow_coder`, record why a replacement was necessary, and provide the full verified binding plus current diff/test state. An unavailable custom Agent, or a reported identity/model/effort mismatch, ends `BLOCKED_DEPENDENCY`; do not silently implement with the root or another model.

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

After GPT passes, the Cursor Lane reviews the same snapshot. The stage does not create review authority. Under `FLOW_RUN_CONTEXT`, consume the same active `external_review` authorization ID and revision used by Spec, Plan, and the run; direct invocation uses its stage-bound equivalent. For every attempt obtain a fresh controller-validated operation manifest that is single-use and bound to `flow-code`, the selected backend, exact prompt, frozen snapshot, and transmitted paths. The operation manifest must remain inside the authorization's issue, run, worktree, stages, backends, and exclusions; the stage must not re-prompt while that scope remains valid. Exclude secrets, credentials, raw production data, unrelated content, and every other recorded exclusion. A pending, denied, invalidated, drifted, or expanded authorization/manifest ends `BLOCKED_REVIEW`; changed scope uses `flowctl authorization amend`. Cursor owns Cursor findings: send accepted fixes to the same coder, rerun affected validation, freeze a new snapshot, and return to Cursor without rerunning GPT.

Use controller-observed process facts rather than vendor error wording. Retry classified `RUN_ERROR` or `PROTOCOL_ERROR` exactly once and do not re-prompt; conflicting review signals remain `UNCLASSIFIED` and are not degradable, while findings are never fallback conditions. After the second retryable Cursor process failure invoke `$ibrain-review` with `glm-5.3`. For an iBrain fallback, reuse the same active `authorization_id` and revision and the same artifact snapshot, but create a `backend=ibrain` new controller-validated, single-use operation manifest/binding; it must not reuse the Cursor binding and must not re-prompt. iBrain owns and rechecks its findings and receives the same bounded retry behavior. Reopen a controller-executed legacy bridge failure only with audited `flowctl review repair-classification`; it never creates PASS. Findings from either backend never select the other backend.

After Cursor or iBrain passes, run a fresh `gpt-6-astra`/`medium` final consistency review with no inherited thread. It validates final digest, evidence, scope, and cross-lane resolution. A failure returns accepted fixes to the same coder, reopens necessary lanes, and reruns consistency, capped at three cycles; repeated no-delta blockers end `BLOCKED_REVIEW`. If both Cursor and iBrain exhaust retryable process failures, consistency must still pass before creating `EXTERNAL_REVIEW_GAP` and allowing `COMPLETE_WITH_DEFECT`. Carry the full `review_binding` and binding ID through every handoff and final completion report.

Require each report to return a `review_binding` with stage `flow-code`, code_snapshot ID and content digests, approved upstream tuple, backend, exact model/effort, and terminal status. Recompute the snapshot and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or intervening drift invalidates the report and ends `BLOCKED_REVIEW`; never use a stale or unbound report.

Resolve the output path through the artifact contract with flow_step `code`, then write or update that document with task status, RED/GREEN evidence, unit-test evidence, changed files, commands and exit results, review findings/dispositions, deviations, and traceability to `TASK-*`, `RULE-*`, and `AC-*`.

End `COMPLETE` only when tasks and validation pass, no blocker remains, the diff is in scope, an external lane and final consistency review passed, and no gap is open. Use `COMPLETE_WITH_DEFECT` only when all other conditions pass but both Cursor and iBrain are unavailable or an inherited `EXTERNAL_REVIEW_GAP` remains open.

Report the full artifact tuple, code evidence, `TESTCASE-*`, all open `EXTERNAL_REVIEW_GAP` records, and frozen `code_snapshot`. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-integration`; otherwise stop without pushing or deploying and suggest explicit `$flow-integration`.
