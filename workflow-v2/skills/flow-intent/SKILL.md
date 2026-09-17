---
name: flow-intent
description: Use when the user explicitly requests authoritative intent from an authorized prepared requirement.
---

# Flow Intent

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and Requirement authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at entry, `flowctl artifact register` after writing Intent, and `flowctl handoff accept` with schema-valid JSON. The skill must not edit the controller or advance on an unaccepted handoff.

Read the human-authorized `requirement.md` and write the authoritative `intent.md`. This stage normalizes an existing commitment; it must not create roadmap content or reopen settled choices.

## Admission

Read the current issue-bound Requirement and its available sources, candidate directions, evidence, objections and unknowns. It must be ready for intent discussion; DRAFT or a real unresolved blocker returns to Requirement. Let the controller compute content identity; absent/stale declared digest or optional metadata is not a gate. Preserve available issue/conversation snapshots without inventing missing history; never re-fetch PMS or rerun the swarm merely to repair metadata.

## Residual ambiguity

Do not routinely grill or reconfirm the human. First resolve technical and evidence questions from the requirement and authorized repository. If an intent-changing product choice was incorrectly left unresolved, return `FLOW_RUN_ROUTE_BACK` to `flow-requirement`; that stage owns the necessary human question. Under direct invocation, the same condition is a human gate and may use `grilling` or the built-in Decision Card format below.

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

Render Decision Cards as a plain product question, verified context and two or three options with consequences and recommendation; DEC-* is a reference, not something the human must interpret. State which outcome/scope changes and that the affected decision will be updated before continuation; do not ask about a missing optional metadata field.

4. Let the human choose, modify, reject all, or propose another direction. Record the answer as `HUMAN` under `requirement.md`'s `Intent Decisions`, update affected fields, preserve rejected alternatives, and increment the requirement revision.
5. Reverse-question the provisional choice with a realistic failure, boundary, permission, compatibility, or adoption counterexample. Reopen it only when the answer changes intent; only a changed decision or requirement field increments revision.

Each `Intent Decisions` record contains stable `DEC-*`, question, options or free-form answer, selected answer, rationale when supplied, evidence, affected fields, source, and revision. This section in `requirement.md` is the authoritative decision ledger; `intent.md` references rather than duplicates it.

The installed grilling path must produce equivalent records and must not turn model pressure into a decision. Do not repeat a question with no new evidence. Implementation-only uncertainty belongs in `Remaining Unknowns`. If an intent-changing fact or authority choice cannot be resolved, update `requirement.md` to `status: BLOCKED`, increment revision, record the named blocker and required owner/evidence, do not write `intent.md`, and stop with the appropriate resume condition; return to `$flow-requirement` only when new requirement exploration is actually needed.

## Authorization binding

When no intent-changing node remains, derive one normalized representation containing problem, target user and scenario, desired outcome, value, selected direction and rationale, Scope, Non-goals, Invariants, Success Signals, accepted product risks, Rejected Alternatives, and Remaining Unknowns. Do not surface it as an approval prompt under `FLOW_RUN_CONTEXT`.

Require the Flow-level human product decision before autonomous downstream work; record it against controller-owned current content identity, not duplicate model-authored approval tuples. Verify the admitted worktree and issue silently. Never create or migrate a worktree in this stage.

## Write intent.md

Resolve the output path through the artifact contract with flow_step `intent`, then write:

```text
status: CONFIRMED
content_revision in the body; content_digest in the integrity region; approved_revision and approved_digest in approval metadata
issue; requirement path, approved revision, and approved digest; confirmed_by; confirmed_at
Problem; Target User and Scenario; Desired Outcome; Value
Selected Direction and rationale
Scope; Non-goals; Invariants; Success Signals
Accepted Product Risks; Rejected Alternatives
Remaining Unknowns that cannot change intent
```

Render the complete intent body and compute its canonical SHA-256 digest. Under `FLOW_RUN_CONTEXT`, sign it as `ORCHESTRATED` against the Requirement authorization without another human confirmation, report both paths/revisions/digests, and return `FLOW_RUN_HANDOFF` with `next_stage: flow-roadmap`. Under direct invocation, show the human-readable commitments and document link, require explicit confirmation of that recorded binding before signing, then suggest `$flow-roadmap`. Do not include phases, architecture, or tasks; must not create roadmap itself.

For the Direct confirmation, show the intended outcome, selected direction, scope/non-goals, success criteria and material risks, link the full document, then request confirmation or correction of those commitments. Keep the recorded binding in diagnostics, not as the question. Explain that confirmation finishes intent confirmation; Direct mode does not automatically run the whole Flow.
