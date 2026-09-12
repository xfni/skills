---
name: intent-to-roadmap
description: Use when the user explicitly invokes $intent-to-roadmap with a confirmed intent to create a bounded delivery roadmap. Do not invoke for requirement discussion or implementation planning.
---

# Intent to Roadmap

Use this explicit-only workflow to turn a confirmed `intent.md` into delivery phases that a later specification can trust. Require `status: CONFIRMED` and a traceable requirement revision. If either is missing, stop and direct the human to `$requirement-to-intent`. Stop after producing the roadmap; never start specification, planning, implementation, or external review automatically.

Treat the intent as the product authority. The roadmap must not reinterpret its `Scope`, `Non-goals`, or `Invariants`. If delivery analysis requires changing one, stop and return to `requirement-to-intent` for a new human-confirmed revision.

## Investigate before deciding

Read the confirmed intent, relevant code, documents, callers, tests, and issue context. Separate verified facts, agent inferences, and unknowns. Do not ask the user for facts that the repository can establish.

Repository investigation may refine delivery feasibility, dependencies, sequencing, and estimates. It may not reopen product choices already frozen by the intent. New facts that contradict intent end the run with a precise conflict and a request for a new intent revision; they are not resolved inside roadmap creation.

## Translate intent into delivery

Map each desired outcome and success signal to requirements and acceptance directions. Create only delivery decisions needed to stage the confirmed scope. Keep technical unknowns visible, move unrelated opportunities to Deferred, and never turn an implementation convenience or platform expansion into a requirement.

## Produce the roadmap

Use the repository's established location; otherwise use `.ai/roadmaps/YYYY-MM-DD-<topic>.md`. Keep stable IDs when revising:

- Context: issue, intent path and requirement revision, status, original problem, verified facts, assumptions, and unknowns.
- Requirements: `REQ-*` entries with a stable Requirement ID, tied to actors and outcomes.
- Decisions: `DEC-*` entries with options, confirmed choice, rationale, source, and status.
- Boundaries: in scope, non-goals, invariants, allowed components, dependencies, and Deferred work.
- Acceptance direction: `AC-*` entries for normal, failure, boundary, and compatibility outcomes.
- Phases: a stable Phase ID, purpose, related requirement, decision, and acceptance IDs, high-level work, dependency, deliverable, completion criterion, and priority.
- Handoff: the selected Phase ID for the next design call, unresolved questions, and decisions that later work must not change.

Before delivery, verify that every requirement has an acceptance direction, every phase supports a requirement, and no unapproved proposal appears in the frozen scope. Report the roadmap path, confirmation state, important decisions, and the explicit next invocation, such as `$roadmap-to-spec-plan`.
