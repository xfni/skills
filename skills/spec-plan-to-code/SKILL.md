---
name: spec-plan-to-code
description: Use when the user explicitly invokes $spec-plan-to-code to implement an approved specification and plan with evidence-based validation. Do not invoke for ordinary coding, debugging, or code review.
---

# Spec and Plan to Code

Use this explicit-only workflow to implement an approved Decision Package, Spec, and Plan. The primary agent owns all edits, debugging, tests, probes, service runs, and fixes. Reviewers are read-only and do not make product decisions.

**REQUIRED SUB-SKILL:** Use `coding-guidelines` before writing implementation code and when reviewing any change. Its evidence-driven abstraction rule governs whether a direct local orchestration or a new layer is appropriate; no reviewer may turn speculative platformization into a requirement.

**REQUIRED SUB-SKILL:** Every independent review in this workflow must use `independent-review` with the `implementation` profile, or the `concurrency` profile when the changed boundary has shared state, locks, async/cross-thread execution, cancellation, or lifecycle risk. This workflow—not `independent-review`—selects `subagent` versus `cursor`, model, and effort.

## Hold the baseline and record progress

Confirm the worktree, approved artifact versions, selected Phase ID, task and acceptance IDs, existing user changes, authorization, and test environment before editing. Preserve the approved scope. Record any new public interface, compatibility, data-policy, or capability request as a Scope Delta; seek approval or defer it. Do not treat reviewer agreement as human approval.

Update progress with each task's pending, in-progress, under-review, done, or blocked state. Move a Task to under-review only after implementation and primary validation. Move it to done only after the independent review and any required re-review complete. For each completed task, record the actual command, result, evidence location, remaining risk, and scope variance, plus reviewer, review model, and disposition. Never report an expected result as executed evidence.

## Choose validation by change type

For business behavior, defect fixes, APIs, state, and compatibility changes, use TDD: write the smallest acceptance-derived test, run it and confirm it fails for the missing behavior, implement the minimum change, rerun it, then refactor only while green. A syntax or dependency error is not a valid RED result. Tests must assert observable behavior, not implementation branches or mock choreography.

For pure configuration, generated files, deployment descriptions, and documents, use a proportionate equivalent: parser or schema validation, dry run, startup check, or integration check. Explain why a failing unit test does not apply. Existing behavior characterization tests may pass initially, but must not be presented as TDD RED evidence.

## Independent Task and milestone review

The primary agent's self-check does not count as independent review. After completing implementation and primary validation, review each independent Task and each completed milestone with an independent read-only reviewer. A Task or milestone cannot be marked done until its findings are resolved or evidenced as invalid, affected validation is rerun, and the changed boundary is independently re-reviewed.

Route Task and milestone reviewers through `independent-review` with `backend: subagent` by the highest applicable complexity:

- Ordinary work with explicit behavior, local impact, and focused verification: use `gpt-5.5-sol` with `high`.
- Difficult work involving non-local control or data flow, multiple modules, compatibility, state, cache, retry behavior, or multi-step verification: use `gpt-5.5-sol` with `xhigh`.
- Very difficult work involving authentication, authorization, secrets, security controls, irreversible data operations, distributed state, concurrency, transactions, public compatibility, production-critical availability, or repeated unsuccessful repairs: use `gpt-6-astra` with `medium`.

When the primary agent encounters difficult analysis, cannot decide within frozen decisions, or repeatedly fails to correct behavior, it may request a `gpt-6-astra` with `medium` read-only consultation agent. The consultation agent returns facts, analysis, options, risks, and recommendations only; it does not edit files, run external write operations, delegate, replace human decisions, or replace independent review.

Provide the frozen Spec and Plan, Task or milestone boundary, changed version, linked `REQ-*`, `DEC-*`, and `AC-*` IDs, necessary call paths, and actual validation evidence. Limit reviewers to consistency with the approved baseline, regressions, verification gaps, and unapproved scope; do not reopen unrelated product or architecture design. Verify every finding before fixing it; defer scope expansion unless approved. A code or behavior change returns the affected Task or milestone to under-review and requires independent re-review.

## Final review and runtime evidence

After all Task and milestone reviews complete, use this fixed final-review order through `independent-review` with the `implementation` profile: first `backend: subagent`, `gpt-6-astra`, `medium`; only after its findings are resolved or dispositioned, `backend: cursor`, `grok-4.6`, `high` as the last external review. Astra checks decision → Spec → Plan → code → evidence consistency; Cursor checks correctness, non-local flows, compatibility, errors, tests, and regressions. Final review complements rather than replaces the required Task and milestone reviews. Re-run affected validation after every accepted fix and independently re-review the changed boundary. Do not reverse the order or treat Cursor feedback as permission to expand the approved scope.

If Cursor findings cause a code or behavior revision, rerun affected validation, independently re-review the changed boundary, then return to the Astra → Cursor final-review sequence. Cursor is final only when its last review causes no further revision.

Write or reuse probes for critical success, failure, and fallback paths. When authorized, start the local service and send a real request through the intended dependency chain. Keep credentials out of artifacts and prompts; isolate test data by task-specific namespace or identifiers, and clean up only exact objects created by the task.

## Cursor read-only review

Use [scripts/cursor_review.py](scripts/cursor_review.py) only after external review is authorized and configured. The default model is `grok-4.6` with `high` effort, and the default key file is `~/.cursor-review/API_KEY`. Before the first review, check that file. If it is missing or empty, show this reminder and wait for confirmation before retrying:

> Cursor API key is not configured at `~/.cursor-review/API_KEY`. Generate an API key in Cursor, save only the key to that file, then tell me when it is ready.

Never print, commit, or add the key to a prompt. Use `--api-key-file`, `--model`, or `--effort` only when a task explicitly needs an override. The script is read-only (`read`, `grep`, `glob`, `ls`) and returns a terminal report or an incomplete status. Keep its agent/run IDs, coverage version, findings, and dispositions in the final evidence.

```bash
python /path/to/spec-plan-to-code/scripts/cursor_review.py \
  /absolute/path/to/repository /absolute/path/to/review-brief.md
```

## Report and stop

Deliver a test report mapping `REQ-*` → `AC-*` → evidence, with tests, probes, or real requests and `passed`, `failed`, `not-run`, or `blocked` status. Include actual commands, review dispositions, Deferred items, limits, rollback notes, and test-data cleanup. Claim completion only when all required work and validation actually meet the approved acceptance criteria.
