---
name: roadmap-to-spec-plan
description: Use when the user explicitly invokes $roadmap-to-spec-plan to create a specification and executable plan from a confirmed roadmap. Do not invoke for ordinary planning or review requests.
---

# Roadmap to Spec and Plan

Use this explicit-only workflow after a roadmap has a confirmed scope. Deliver a Decision Package, Spec, Plan, acceptance matrix, review ledger, and Deferred items; stop before implementation.

## Preserve the approved scope

Read the roadmap, issue, existing implementation, callers, interfaces, tests, and project instructions. Treat confirmed requirements and decisions as the baseline. A new capability, public or cross-repository impact, changed data policy, or changed compatibility behavior is a Scope Delta, not an implementation detail. Obtain human approval before adding it; otherwise put it in Deferred.

Create a Decision Package before writing the Spec. It must contain verified facts and evidence, in-scope and non-goals, allowed modules/interfaces/data, stable `DEC-*` decisions with their source and status, `AC-*` scenarios, open decisions, and Deferred work. Keep a business decision visible instead of burying it in a long specification.

## Write, review, and revise

Write a Spec covering behavior, interfaces/data constraints, errors and rollback, compatibility, invariants, risks, and acceptance. Connect its assertions to the Decision Package.

Use two distinct review roles:

- Cursor checks repository facts, call paths, technical feasibility, compatibility, and testability.
- An independent reviewer checks roadmap → decisions → Spec/Plan consistency, hidden business decisions, scope expansion, and acceptance completeness.

Give each review finding an ID, category, evidence, affected requirement/file, impact, recommendation, owner action, and verification result. Categorize findings as Blocker, Ambiguity, Scope Delta, Deferred, or Note. A reviewer label is evidence to assess, not approval to broaden the work. End review when Blockers are resolved or disproved, relevant Ambiguities are decided, Scope Deltas are approved or deferred, and acceptance remains verifiable. Do not use “no issues found” as the exit condition.

Write the Plan only after the Spec passes this gate. Each task needs an ID, dependencies, linked decision/acceptance IDs, exact change boundary, minimal implementation steps, explicit forbidden changes, and evidence-producing validation. Select validation by change type: behavior/API/state changes need an executable failing-test path; configuration, generated artifacts, and deployment descriptions need relevant parsing, schema, dry-run, startup, or integration evidence. Record prerequisites, commands verified against the repository, expected observable result, failure diagnosis, and rollback where relevant.

## Cursor read-only review

When the user has authorized external review and a Cursor Local SDK environment is configured, use [scripts/cursor_review.py](scripts/cursor_review.py). It never grants shell or editing tools.

The default model is `grok-4.6` with `high` effort. The default key file is `~/.cursor-review/API_KEY`. Before the first review, check whether that file exists and is non-empty. If it is missing, show this reminder and wait for confirmation before retrying:

> Cursor API key is not configured at `~/.cursor-review/API_KEY`. Generate an API key in Cursor, save only the key to that file, then tell me when it is ready.

Do not print the key, put it in a prompt, commit it, or rewrite this open-source skill with a machine-specific path. The documented fixed location is the durable configuration; `--api-key-file`, `--model`, and `--effort` remain explicit per-call overrides.

```bash
python /path/to/roadmap-to-spec-plan/scripts/cursor_review.py \
  /absolute/path/to/repository /absolute/path/to/review-brief.md
```

Build the brief from the approved scope, baseline version, relevant paths, decisions, acceptance IDs, and required finding schema. The script's exit code only proves whether a non-empty terminal report was received; assess findings separately. Record agent/run IDs, covered version, report, and disposition in the review ledger. If external review is unavailable, report that gap rather than claiming equivalent coverage.
