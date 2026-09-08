---
name: roadmap-to-spec-plan
description: Use when the user explicitly invokes $roadmap-to-spec-plan to create a specification and executable plan from a confirmed roadmap. Do not invoke for ordinary planning or review requests.
---

# Roadmap to Spec and Plan

Use this explicit-only workflow after a roadmap has a confirmed scope. Deliver a Decision Package, Spec, Plan, acceptance matrix, review ledger, and Deferred items; stop before implementation. The primary agent researches, writes, and revises. Reviewers are read-only, do not make product decisions, and do not delegate.

## Establish the baseline

Read the issue, roadmap, current implementation, callers, interfaces, tests, project instructions, and existing user changes. Select the confirmed target or selected Phase ID; never default to designing the entire roadmap. Treat confirmed requirements and human decisions as the baseline. A new capability, public or cross-repository impact, changed data policy, or changed compatibility behavior is a Scope Delta, not an implementation detail. Obtain human approval before adding it; otherwise put it in Deferred. Reviewer agreement is never human approval.

Create a Decision Package before writing the Spec. It must contain verified facts and evidence; in-scope and non-goals; the selected Phase ID and linked `REQ-*` entries; allowed modules, interfaces, and data; stable `DEC-*` decisions with source and status; `AC-*` scenarios; open decisions; and Deferred work. Preserve the trace `REQ-*` → `DEC-*` → `AC-*`; keep business decisions visible instead of burying them in a long Spec.

## Review governance

Give every finding an ID, category, evidence, affected requirement or file, impact, recommendation, owner action, and verification result. Categorize it as Blocker, Ambiguity, Scope Delta, Deferred, or Note. A reviewer label is evidence to assess, not approval to broaden the work. Resolve or disprove Blockers; decide relevant Ambiguities; approve or defer Scope Deltas; and keep acceptance verifiable. Do not use “no issues found” as the exit condition.

After a revision, review only the changed boundary, unresolved findings, and affected artifacts. If the same dispute remains unresolved for two review rounds without new evidence, record the disagreement and its impact, defer the dependent part for a human decision, and continue independent work. Do not endlessly reopen a settled concern or lower acceptance to close a finding.

## Spec, then Plan

Write a Spec that covers behavior, interfaces and data constraints, errors and rollback, compatibility, invariants, risks, and acceptance. Link each assertion to the Decision Package.

For each Spec review iteration, use two distinct final-review stages in this fixed order. First use `gpt-6-astra` with `medium` effort for the independent final review. Only after its findings are resolved or dispositioned, use Cursor as the last external review. Astra checks roadmap → decisions → Spec consistency, hidden business decisions, scope expansion, and acceptance completeness. Cursor checks repository facts, call paths, technical feasibility, compatibility, and testability. Do not reverse the order or treat Cursor feedback as permission to expand the approved scope. A Cursor-driven revision returns to the Astra → Cursor sequence.

Write the Plan only after the Spec passes this gate. For every task include an ID, dependencies, linked requirement, decision, and acceptance IDs, exact change boundary, minimal implementation steps, explicit forbidden changes, and evidence-producing validation. Select validation by change type: behavior, API, state, and compatibility changes need an executable failing-test path; configuration, generated artifacts, and deployment descriptions need parsing, schema, dry-run, startup, or integration evidence. Record prerequisites, repository-verified commands, expected observable results, failure diagnosis, and rollback where relevant.

Review every Plan iteration in the same Astra → Cursor order. Astra checks Spec → Plan → acceptance coverage, scope consistency, and execution ambiguity. Cursor checks task executability, dependency order, actual paths and commands, tests, and compatibility gaps. Do not start implementation in this skill.

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

Deliver the Decision Package, Spec, Plan, acceptance matrix, review ledger, and Deferred items. Record reviewed versions, dispositions, remaining limits, and the explicit next invocation. Mark artifacts executable only when the required reviews actually completed; otherwise name the precise gap. Do not automatically start coding or invoke another explicit-only workflow.
