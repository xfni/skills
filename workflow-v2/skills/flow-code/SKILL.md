---
name: flow-code
description: Use when the user explicitly requests implementation and unit testing of an approved plan.
---

# Flow Code

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status`, then `flowctl artifact register` for Code evidence and `flowctl snapshot capture` for the frozen implementation. Execute the GPT gate through `flowctl review begin` and `flowctl review submit`, then the mandatory final review through `flowctl review cursor`; finally use `flowctl handoff accept`. The skill must not edit the controller, self-count retries, or self-approve.

Implement one approved plan.md with TDD and produce reviewable code plus unit-test evidence. This stage proves local behavior; it must not claim integration coverage.

**REQUIRED BACKGROUND:** Use `test-driven-development` for RED-GREEN-REFACTOR and `coding-guidelines` for scope and reliability decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `implementation` profile, or `concurrency` when that risk applies, for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

**REQUIRED SUBAGENT:** Use the bundled `agents/flow-coder.toml` identity `flow_coder` (`gpt-5.6-luna`, reasoning effort `max`) as the sole implementation writer. It must not delegate.

## Admission

Require the complete `$flow-plan` handoff tuple: requirement, intent, roadmap, spec, and approved plan paths with approved revisions and SHA-256 digests, milestone ID, reserved `TESTCASE-*`, and any open review gaps. Accept Plan `APPROVED` or `APPROVED_WITH_DEFECT`; propagate inherited `CURSOR_REVIEW_GAP` records without pausing orchestration. Recompute every canonical digest and verify the exact snapshots, repository worktree, allowed change surface, commands, and prerequisites. Stop on drift or missing approval. If `test-driven-development` or `coding-guidelines` is unavailable, end `BLOCKED_DEPENDENCY`; do not improvise their required discipline.

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

After each independently reviewable task, perform a self-check against its rules and acceptance criteria. At milestone completion, run the full planned unit/regression suite, freeze the code snapshot, then run the fixed GPT → Cursor review gate. The root agent chooses and records one requirement-difficulty pair: `gpt-5.6-sol` with `high` effort for bounded, localized changes with direct verification, or `gpt-6-astra` with `medium` effort for complex/non-local flows, security, authorization, data loss, migrations, concurrency, distributed state, public compatibility, or ambiguous evidence. No other GPT pair is allowed. Use the applicable independent-review profile and rerun affected validation plus GPT review after an accepted fix only within the convergence rule below.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker return to the owning stage or end `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Then invoke `$cursor-review` as the mandatory final review of that same snapshot and its approved artifact chain. Invoking `$flow-code` automatically authorizes sending the in-scope code and documents needed for this review to Cursor. Materialize or inherit the corresponding `FLOW_CURSOR_AUTHORIZATION` and pass it with the transmission manifest; neither this stage nor `$cursor-review` may ask for duplicate confirmation while the manifest remains bound. Exclude secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content. Record transmitted paths and content digests. Any Cursor-driven code, test, evidence, or document revision invalidates both reviews: rerun affected validation, freeze a new snapshot, rerun the GPT review, pass it, and then rerun Cursor. Denied transmission, drift, or unresolved correctness/security/data-loss/compatibility/scope blocker ends `BLOCKED_REVIEW`; only a classified `RUN_ERROR` follows the retry policy below. Cursor is the mandatory final review only when its last report causes no revision and has no unresolved blocker/high finding.

Treat only a controller timeout or an allow-listed structured runner error as Cursor `RUN_ERROR`; never infer it from log keywords; retry exactly once against the same frozen snapshot, binding, and transmission manifest. A malformed, missing, unbound, inconsistent, or empty `INCOMPLETE` terminal report is `UNCLASSIFIED` and is not degradable. `UNCLASSIFIED` has its own two-attempt budget for the same digest; exhaustion ends `BLOCKED_REVIEW`, never defect completion. Record attempt IDs, timestamps, and sanitized errors. A report containing findings, including an `INCOMPLETE` report, is substantive; resolve it and rerun the gate. Denied transmission, drift, invalid local input, or failed validation remains blocking.

If the second attempt is also `RUN_ERROR`, add a durable open `CURSOR_REVIEW_GAP` with the full `review_binding` and binding ID, both attempts referencing that ID, snapshot/digests and upstream tuple, backend/model/effort, missing assurance, owner, and remediation. Combine inherited gaps. If any gap remains `OPEN`, permit only `COMPLETE_WITH_DEFECT`, even when this stage's own Cursor review succeeds; include every open gap in the next handoff and final completion report until a successful bound Cursor review closes it. Never claim fully reviewed completion or pause solely to announce the gap.

Require each report to return a `review_binding` with stage `flow-code`, code_snapshot ID and content digests, approved upstream tuple, backend, exact model/effort, and terminal status. Recompute the snapshot and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or intervening drift invalidates the report and ends `BLOCKED_REVIEW`; never use a stale or unbound report.

Resolve the output path through the artifact contract with flow_step `code`, then write or update that document with task status, RED/GREEN evidence, unit-test evidence, changed files, commands and exit results, review findings/dispositions, deviations, and traceability to `TASK-*`, `RULE-*`, and `AC-*`.

End `COMPLETE` only when every plan task is complete, all required unit/regression commands pass freshly, no blocking finding remains, the diff stays within scope, Cursor completed, and no inherited or current gap is open. Use `COMPLETE_WITH_DEFECT` when all non-Cursor conditions are satisfied but any inherited or current `CURSOR_REVIEW_GAP` remains open. Otherwise end `INCOMPLETE` with exact blockers. Do not equate mocks, local probes, or unit suites with cross-component validation.

Report a handoff tuple containing milestone ID; requirement, intent, roadmap, spec, and plan paths with their approved revisions and digests; code-evidence path; reserved `TESTCASE-*`; all open `CURSOR_REVIEW_GAP` records; and a `code_snapshot` of HEAD commit OID, `git status --short`, tracked diff, and content digests for every untracked non-ignored file. Record Plan-declared ignored/generated inputs separately; they cannot contain production code or required fixtures. Integration must compare the same snapshot before testing. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: flow-integration`; otherwise stop without pushing or deploying, then suggest explicit `$flow-integration`.
