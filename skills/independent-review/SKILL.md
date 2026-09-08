---
name: independent-review
description: Use when a workflow has selected an independent review of a design, plan, implementation, or concurrency/lifecycle risk and supplies the review profile and reviewer configuration.
---

# Independent Review

This skill defines the review standard. It does not decide whether a review is required and does not select the reviewer backend, model, or effort. The calling workflow owns those decisions and passes them as part of the review request.

## Required review request

Every request must name:

```text
profile: `design`, `implementation`, or `concurrency`
backend: `subagent` or `cursor`
model and effort: selected by the calling workflow
boundary: artifact/version, allowed scope, linked REQ/DEC/AC IDs
evidence: relevant code paths, tests, commands, and observed results
```

The reviewer is independent and read-only. It may not edit artifacts, make product decisions, delegate, or turn a local concern into a platform, framework, extension point, or unrelated refactor. Scope expansion is a `Scope Delta` for human approval, never an implicit review fix.

## Shared standard

Review the approved baseline, changed boundary, stated non-goals, and evidence—not an imagined future system. Every finding must include an ID, category, concrete evidence, affected artifact or requirement, impact, recommendation, and verification/disposition result.

Categories are `Blocker`, `Ambiguity`, `Scope Delta`, `Deferred`, and `Note`. A severity label or a clean report is evidence to assess, not approval. The primary agent verifies findings before changing anything. Re-review only the changed boundary, unresolved findings, and affected artifacts; do not use “no issues found” as an exit condition.

## Profiles

### `design`

Check requirement → decision → acceptance traceability; scope and non-goals; repository facts and call paths; interfaces, data, compatibility, errors, rollback, feasibility, and executable validation.

### `implementation`

Check approved Spec/Plan compliance, regressions, non-local control or data flow, error behavior, compatibility, tests, probes, runtime evidence, and unapproved scope. Compare implementation evidence with the approved acceptance criteria.

### `concurrency`

Check the actual code path before reasoning about behavior. Cover shared-state ownership, TOCTOU windows, lock ordering and release paths, blocking calls in async contexts, cancellation, lifecycle cleanup, fairness/starvation, timeout fallback, and boundary races. Enumerate at least normal, failure, idle, sustained-load, and edge-timing scenarios when applicable.

## Backend boundary

When the caller selects `subagent`, it supplies the model, effort, read-only constraint, and profile-specific brief. When it selects `cursor`, it uses the calling workflow's bounded read-only Cursor runner and supplies the same profile and boundary. This skill never substitutes one backend for another, retries an incomplete external review automatically, or changes a caller-selected model.

## Handoff

Report the selected profile, backend, model/effort, reviewed version and boundary, findings with evidence, local disposition, required follow-up, and exact re-review scope. A review that times out, lacks a terminal report, or lacks material evidence is incomplete, not passed.
