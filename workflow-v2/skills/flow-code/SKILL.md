---
name: flow-code
description: Use when the user explicitly requests implementation and unit testing of an approved plan.
---

# Flow Code

Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.

Implement one approved plan.md with TDD and produce reviewable code plus unit-test evidence. This stage proves local behavior; it must not claim integration coverage.

**REQUIRED BACKGROUND:** Use `test-driven-development` for RED-GREEN-REFACTOR and `coding-guidelines` for scope and reliability decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `implementation` profile, or `concurrency` when that risk applies, for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the mandatory Cursor final review.

## Admission

Require the complete `$flow-plan` handoff tuple: requirement, intent, roadmap, spec, and approved plan paths with approved revisions and SHA-256 digests, milestone ID, reserved `TESTCASE-*`, and any open review gaps. Accept Plan `APPROVED` or `APPROVED_WITH_DEFECT`; display inherited `CURSOR_REVIEW_GAP` records, remind the human, and propagate them. Recompute every canonical digest and verify the exact snapshots, repository worktree, allowed change surface, commands, and prerequisites. Stop on drift or missing approval. If `test-driven-development` or `coding-guidelines` is unavailable, end `BLOCKED_DEPENDENCY`; do not improvise their required discipline.

## Execute each task

Follow dependency order and keep changes inside the task boundary:

1. Reconfirm linked `RULE-*`, `AC-*`, files, and completion criteria.
2. RED: add the planned failing unit test for behavior code, or the approved failing check/probe for a non-code task. Run it and capture the expected pre-change failure. When the approved Plan says automation is impossible, perform its justified reproducible inspection and capture the specified before evidence instead. A test that passes immediately or fails for the wrong reason is not RED.
3. GREEN: make the minimal implementation needed for that contract. Run the focused test/check, or repeat the approved inspection, and capture success or after evidence.
4. REFACTOR: when structure can improve without adding behavior, refactor it and rerun applicable checks. Otherwise record a justified no-op; never create unrelated cleanup to satisfy this step.
5. Compare the diff to the task scope and record changed files, commands, results, deviations, and unresolved risk.

Do not weaken tests, change Spec to match code, add speculative infrastructure, or execute reserved `TESTCASE-*` scenarios. A discovered behavior conflict returns to `$flow-spec`; a task/sequence defect returns to `$flow-plan`.

## Review and verify

After each independently reviewable task, perform a self-check against its rules and acceptance criteria. At milestone completion, run the full planned unit/regression suite, freeze the code snapshot, then run the fixed GPT → Cursor review gate. The root agent chooses and records one requirement-difficulty pair: `gpt-5.6-sol` with `high` effort for bounded, localized changes with direct verification, or `gpt-6-astra` with `medium` effort for complex/non-local flows, security, authorization, data loss, migrations, concurrency, distributed state, public compatibility, or ambiguous evidence. No other GPT pair is allowed. Use the applicable independent-review profile and rerun affected validation plus the GPT review after every accepted fix until it passes on the frozen snapshot.

Then invoke `$cursor-review` as the mandatory final review of that same snapshot and its approved artifact chain. Invoking `$flow-code` automatically authorizes sending the in-scope code and documents needed for this review to Cursor, excluding secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content. Record transmitted paths and content digests. Any Cursor-driven code, test, evidence, or document revision invalidates both reviews: rerun affected validation, freeze a new snapshot, rerun the GPT review, pass it, and then rerun Cursor. Denied transmission, drift, or unresolved correctness/security/data-loss/compatibility/scope blocker ends `BLOCKED_REVIEW`; only a classified `RUN_ERROR` follows the retry policy below. Cursor is the mandatory final review only when its last report causes no revision and has no unresolved blocker/high finding.

Treat SDK/credential availability, connection, bridge, timeout, or malformed/missing terminal report as Cursor `RUN_ERROR`; retry exactly once against the same frozen snapshot, binding, and transmission manifest, recording both attempt IDs, timestamps, and sanitized errors. A normal report containing findings is not a review finding failure eligible for degradation; resolve it and rerun the gate. Denied transmission, drift, invalid local input, or failed validation remains blocking.

If the second attempt is also `RUN_ERROR`, add a durable open `CURSOR_REVIEW_GAP` with the full `review_binding` and binding ID, both attempts referencing that ID, snapshot/digests and upstream tuple, backend/model/effort, missing assurance, owner, and remediation. Combine inherited gaps. If any gap remains `OPEN`, permit only `COMPLETE_WITH_DEFECT`, even when this stage's own Cursor review succeeds; remind the human before completion, include every open gap in the next handoff, and remind the human downstream until a successful bound Cursor review of each affected artifact closes it. Never claim fully reviewed completion.

Require each report to return a `review_binding` with stage `flow-code`, code_snapshot ID and content digests, approved upstream tuple, backend, exact model/effort, and terminal status. Recompute the snapshot and upstream digests immediately before dispatch and after receipt. A missing/mismatched binding or intervening drift invalidates the report and ends `BLOCKED_REVIEW`; never use a stale or unbound report.

Resolve the output path through the artifact contract with flow_step `code`, then write or update that document with task status, RED/GREEN evidence, unit-test evidence, changed files, commands and exit results, review findings/dispositions, deviations, and traceability to `TASK-*`, `RULE-*`, and `AC-*`.

End `COMPLETE` only when every plan task is complete, all required unit/regression commands pass freshly, no blocking finding remains, the diff stays within scope, Cursor completed, and no inherited or current gap is open. Use `COMPLETE_WITH_DEFECT` when all non-Cursor conditions are satisfied but any inherited or current `CURSOR_REVIEW_GAP` remains open. Otherwise end `INCOMPLETE` with exact blockers. Do not equate mocks, local probes, or unit suites with cross-component validation.

Report a handoff tuple containing milestone ID; requirement, intent, roadmap, spec, and plan paths with their approved revisions and digests; code-evidence path; reserved `TESTCASE-*`; all open `CURSOR_REVIEW_GAP` records; and a `code_snapshot` of HEAD commit OID, `git status --short`, tracked diff, and content digests for every untracked non-ignored file. Record Plan-declared ignored/generated inputs separately; they cannot contain production code or required fixtures. Integration must compare the same snapshot before testing. Stop without pushing or deploying, then suggest explicit `$flow-integration`.
