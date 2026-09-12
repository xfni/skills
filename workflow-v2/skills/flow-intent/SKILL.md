---
name: flow-intent
description: Use when the user explicitly requests human confirmation of a prepared requirement before roadmap work.
---

# Flow Intent

Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.

Read `requirement.md`, interrogate intent-changing choices with the human, and write the authoritative `intent.md`. This stage converts exploration into commitment; it must not create roadmap content.

## Admission

Require `requirement.md` with an issue, sources, content revision and digest, `status: READY_FOR_INTENT`, candidate directions, evidence, objections, and unknowns. Recompute and verify its canonical digest before use. A `DRAFT` or `BLOCKED` input returns to `$flow-requirement`. Preserve its immutable issue and conversation snapshots; never re-fetch PMS or rerun the agent swarm.

## Grilling

If the `grilling` skill is installed, use it as the questioning engine with the complete requirement and relevant history. Keep this skill's artifact, decision, and confirmation rules authoritative. If grilling is unavailable, use this built-in fallback:

1. Identify intent-changing decision nodes affecting the problem, user, outcome, selected direction, scope, non-goals, invariants, accepted product risk, or success signals.
2. Resolve evidence questions from the requirement and authorized repository before asking the human.
3. Present one `Decision Card` and one high-leverage question at a time:

```text
DEC-* and question
known evidence and conflict
two or three genuine options
each option's value, cost, risk, and scope impact
agent recommendation and rationale
```

4. Let the human choose, modify, reject all, or propose another direction. Record the answer as `HUMAN` under `requirement.md`'s `Intent Decisions`, update affected fields, preserve rejected alternatives, and increment the requirement revision.
5. Reverse-question the provisional choice with a realistic failure, boundary, permission, compatibility, or adoption counterexample. Reopen it only when the answer changes intent; only a changed decision or requirement field increments revision.

Each `Intent Decisions` record contains stable `DEC-*`, question, options or free-form answer, selected answer, rationale when supplied, evidence, affected fields, source, and revision. This section in `requirement.md` is the authoritative decision ledger; `intent.md` references rather than duplicates it.

The installed grilling path must produce equivalent records and must not turn model pressure into a decision. Do not repeat a question with no new evidence. Implementation-only uncertainty belongs in `Remaining Unknowns`. If an intent-changing fact or authority choice cannot be resolved, update `requirement.md` to `status: BLOCKED`, increment revision, record the named blocker and required owner/evidence, do not write `intent.md`, and stop with the appropriate resume condition; return to `$flow-requirement` only when new requirement exploration is actually needed.

## Confirmation gate

When no intent-changing node remains, show one normalized preview containing problem, target user and scenario, desired outcome, value, selected direction and rationale, Scope, Non-goals, Invariants, Success Signals, accepted product risks, Rejected Alternatives, and Remaining Unknowns.

Require explicit human confirmation of that exact current content revision and digest. Agreement with individual answers, participation, an earlier revision, or silence is insufficient. A requested content change increments the requirement revision, recomputes its digest, updates `DEC-*`, and requires a new preview. On confirmation, place `status: CONFIRMED`, `confirmed_by`, `confirmed_at`, `approved_revision`, and `approved_digest` in an approval envelope without changing the approved body revision.

Before writing `intent.md`, satisfy the enclosing repository's feature-worktree gate. When it requires creating a dedicated worktree and resuming the session, stop after reporting the exact resume command. After resume, resolve the requirement destination again through the artifact contract using the new project root and its original flow_step/date/subject, preserve the exact confirmed BODY bytes, digest, and approval binding while regenerating only excluded path metadata, recompute and compare its body digest and revision, record the new absolute path, and use only that copy downstream. A mismatch, missing source, unverified current worktree, or inability to preserve the body ends `BLOCKED`; never write intent in the original checkout after the gate applies.

## Write intent.md

Resolve the output path through the artifact contract with flow_step `intent`, then write:

```text
status: CONFIRMED
content_revision in the body; content_digest in the integrity region; approval metadata outside both
issue; requirement path, approved revision, and approved digest; confirmed_by; confirmed_at
Problem; Target User and Scenario; Desired Outcome; Value
Selected Direction and rationale
Scope; Non-goals; Invariants; Success Signals
Accepted Product Risks; Rejected Alternatives
Remaining Unknowns that cannot change intent
```

Render the complete intent body, compute its canonical SHA-256 digest, and show the exact body, revision, and digest to the human. Require explicit confirmation of this intent artifact itself; confirmation of earlier Decision Cards or the requirement preview is insufficient. Only then sign its approval envelope, binding the intent revision and digest plus the re-homed requirement path, approved revision, and approved digest. Report both paths, approved revisions, and approved digests, then stop. Do not include phases, architecture, or tasks; must not create roadmap or automatically invoke it. Suggest explicit `$flow-roadmap` as the next step.
