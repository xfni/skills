---
name: spec-plan-to-code
description: Use when the user explicitly invokes $spec-plan-to-code to implement an approved specification and plan with evidence-based validation. Do not invoke for ordinary coding, debugging, or code review.
---

# Spec and Plan to Code

Use this explicit-only workflow to implement an approved Decision Package, Spec, and Plan. The primary agent owns all edits, debugging, tests, probes, service runs, and fixes. Reviewers are read-only and do not make product decisions.

## Hold the baseline

Confirm the worktree, approved artifact versions, task/acceptance IDs, current user changes, authorization, and test environment before editing. Preserve the approved scope. Record any new public interface, compatibility, data-policy, or capability request as a Scope Delta; seek approval or defer it. Do not treat reviewer agreement as human approval.

Update progress with each task's pending, in-progress, done, or blocked state. For each completed task, record the actual command, result, evidence location, remaining risk, and scope variance. Never report an expected result as executed evidence.

## Choose validation by change type

For business behavior, defect fixes, APIs, state, and compatibility changes, use TDD: write the smallest acceptance-derived test, run it and confirm it fails for the missing behavior, implement the minimum change, rerun it, then refactor only while green. A syntax or dependency error is not a valid RED result. Tests must assert observable behavior, not implementation branches or mock choreography.

For pure configuration, generated files, deployment descriptions, and documents, use a proportionate equivalent: parser/schema validation, dry run, startup check, or integration check. Explain why a failing unit test does not apply. Existing behavior characterization tests may pass initially, but must not be presented as TDD RED evidence.

After each material milestone, perform primary self-review and targeted validation. Use an allowed independent reviewer only for meaningful risk or blast radius; provide the frozen Spec, changed version, affected flow, acceptance IDs, and validation evidence. Verify each finding before fixing it; classify scope expansion as Deferred unless approved.

## Final review and runtime evidence

After implementation and primary validation, have Cursor review correctness, non-local flows, compatibility, errors, tests, and regressions. Then use a distinct final reviewer for decision → Spec → Plan → code → evidence consistency. Re-run affected validation after every accepted fix.

Write or reuse probes for critical success, failure, and fallback paths. When authorized, start the local service and send a real request through the intended dependency chain. Keep credentials out of artifacts and prompts; isolate test data and clean up only exact objects created by the task.

Use [scripts/cursor_review.py](scripts/cursor_review.py) only after external review is authorized and configured. The default model is `grok-4.6` with `high` effort, and the default key file is `~/.cursor-review/API_KEY`. Before the first review, check that file. If it is missing or empty, show this reminder and wait for confirmation before retrying:

> Cursor API key is not configured at `~/.cursor-review/API_KEY`. Generate an API key in Cursor, save only the key to that file, then tell me when it is ready.

Never print, commit, or add the key to a prompt. Do not rewrite this open-source skill with a machine-specific path: the documented fixed location persists across calls. Use `--api-key-file`, `--model`, or `--effort` only when a task explicitly needs an override.

```bash
python /path/to/spec-plan-to-code/scripts/cursor_review.py \
  /absolute/path/to/repository /absolute/path/to/review-brief.md
```

The script is read-only (`read`, `grep`, `glob`, `ls`) and returns a terminal report or an incomplete status. Keep its agent/run IDs, coverage version, findings, and dispositions in the final evidence.

Deliver a test report mapping every `AC-*` to tests/probes/real-request evidence and `passed`, `failed`, `not-run`, or `blocked`. Include actual commands, review dispositions, Deferred items, limits, rollback notes, and test-data cleanup. Claim completion only when all required work and validation actually meet the approved acceptance criteria.
