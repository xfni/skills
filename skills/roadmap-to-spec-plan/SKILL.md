---
name: roadmap-to-spec-plan
description: Use when the user explicitly invokes $roadmap-to-spec-plan to create a specification and executable plan from a confirmed roadmap. Do not invoke for ordinary planning or review requests.
---

# Roadmap to Spec and Plan

Use this explicit-only workflow after a roadmap has a confirmed scope. Deliver a Decision Package, Spec, Plan, acceptance matrix, Integration Test Design, review ledger, and Deferred items; stop before implementation. The primary agent researches, writes, and revises. Reviewers are read-only, do not make product decisions, and do not delegate.

**REQUIRED SUB-SKILL:** Every independent review in this workflow must use `independent-review` with the `design` profile. This workflow selects the backend, model, and effort: Astra reviews use `backend: subagent`, `model: gpt-6-astra`, and `effort: medium`; final external reviews use `backend: cursor`, `model: grok-4.6`, and `effort: high`. When the selected phase involves concurrency, locks, shared mutable state, async boundaries, or lifecycle, add a pre-Plan `concurrency`-profile review with `backend: subagent`, `model: gpt-6-astra`, and `effort: medium`.

## Establish the baseline

Read the issue, roadmap, current implementation, callers, interfaces, tests, project instructions, and existing user changes. Select the confirmed target or selected Phase ID; never default to designing the entire roadmap. Treat confirmed requirements and human decisions as the baseline. A new capability, public or cross-repository impact, changed data policy, or changed compatibility behavior is a Scope Delta, not an implementation detail. Obtain human approval before adding it; otherwise put it in Deferred. Reviewer agreement is never human approval.

Create a Decision Package before writing the Spec. It must contain verified facts and evidence; in-scope and non-goals; the selected Phase ID and linked `REQ-*` entries; allowed modules, interfaces, and data; stable `DEC-*` decisions with source and status; `AC-*` scenarios; open decisions; and Deferred work. Preserve the trace `REQ-*` → `DEC-*` → `AC-*`; keep business decisions visible instead of burying them in a long Spec.

## Review governance

Give every finding an ID, category, evidence, affected requirement or file, impact, recommendation, owner action, and verification result. Categorize it as Blocker, Ambiguity, Scope Delta, Deferred, or Note. A reviewer label is evidence to assess, not approval to broaden the work. Resolve or disprove Blockers; decide relevant Ambiguities; approve or defer Scope Deltas; and keep acceptance verifiable. Do not use “no issues found” as the exit condition.

After a revision, review only the changed boundary, unresolved findings, and affected artifacts. If the same dispute remains unresolved for two review rounds without new evidence, record the disagreement and its impact, defer the dependent part for a human decision, and continue independent work. Do not endlessly reopen a settled concern or lower acceptance to close a finding.

## Spec, Integration Test Design, then Plan

Write a Spec that covers behavior, interfaces and data constraints, errors and rollback, compatibility, invariants, risks, and acceptance. Link each assertion to the Decision Package.

Write an **Integration Test Design** after the Spec and before the Plan. It defines the approved test semantics, rather than a complete executable case list: map `REQ-*` and `AC-*` to prioritized test points; identify mandatory real-environment validation; cover critical success, failure, and fallback paths; record environment, data, permissions, observability, safety, cleanup, rollback, and measurable thresholds. State which checks are probes and which need a real request through the intended dependency chain. Keep it sufficiently concrete to expose an untestable acceptance criterion, but defer endpoint-level commands, exact fixtures, and case steps until the implemented version exists.

Treat a change to an approved test point, observable acceptance result, real-environment scope, or threshold as a Scope Delta. Refining one test point into more cases or adding implementation-detail evidence without changing acceptance semantics is permitted and must retain its `REQ-*`/`AC-*` trace.

For each Spec review iteration, use two distinct `independent-review` `design`-profile stages in this fixed order. First use `backend: subagent`, `gpt-6-astra` with `medium` effort. Only after its findings are resolved or dispositioned, use `backend: cursor` with `grok-4.6` and `high` effort as the last external review. Astra checks roadmap → decisions → Spec consistency, hidden business decisions, scope expansion, and acceptance completeness. Cursor checks repository facts, call paths, technical feasibility, compatibility, and testability. Do not reverse the order or treat Cursor feedback as permission to expand the approved scope. A Cursor-driven revision returns to the Astra → Cursor sequence.

Write the Plan only after the Spec and Integration Test Design pass this gate. For every task include an ID, dependencies, linked requirement, decision, and acceptance IDs, exact change boundary, minimal implementation steps, explicit forbidden changes, and evidence-producing validation. Select validation by change type: behavior, API, state, and compatibility changes need an executable failing-test path; configuration, generated artifacts, and deployment descriptions need parsing, schema, dry-run, startup, or integration evidence. Record prerequisites, repository-verified commands, expected observable results, failure diagnosis, and rollback where relevant. Add the explicit post-implementation handoff to `$code-to-integration-testing`; it must name the approved Integration Test Design and the tests or probes each task leaves for that workflow.

Review every Plan iteration through `independent-review` with the `design` profile in the same Astra → Cursor order and backend/model settings. Astra checks Spec → Plan → acceptance coverage, scope consistency, and execution ambiguity. Cursor checks task executability, dependency order, actual paths and commands, tests, and compatibility gaps. Do not start implementation in this skill.

## Cursor read-only review

Use [scripts/cursor_review.py](scripts/cursor_review.py) only after external review is authorized and configured. It never grants shell or editing tools. The default model is `grok-4.6` with `high` effort, and the default key file is `~/.cursor-review/API_KEY`. Before the first review, check that file. If it is missing or empty, show this reminder and wait for confirmation before retrying:

> Cursor API key is not configured at `~/.cursor-review/API_KEY`. Generate an API key in Cursor, save only the key to that file, then tell me when it is ready.

Never print, commit, or include the key in a prompt. Use `--api-key-file`, `--model`, or `--effort` only when a task explicitly needs an override.

```bash
python /path/to/roadmap-to-spec-plan/scripts/cursor_review.py \
  /absolute/path/to/repository /absolute/path/to/review-brief.md
```

Build the brief from approved scope, baseline version, relevant paths, decisions, acceptance IDs, and the required finding schema. The script exit code proves only whether it received a non-empty terminal report; it does not prove approval. Record agent/run IDs, covered version, report, findings, and dispositions in the review ledger. If external review is unavailable, report that gap rather than claiming equivalent coverage.

## Deliver and stop

Deliver the Decision Package, Spec, Plan, acceptance matrix, Integration Test Design, review ledger, and Deferred items. Record reviewed versions, dispositions, remaining limits, and the explicit next invocation. Mark artifacts executable only when the required reviews actually completed; otherwise name the precise gap. Do not automatically start coding or invoke another explicit-only workflow.
