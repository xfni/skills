---
name: requirements-to-roadmap
description: Use when the user explicitly invokes $requirements-to-roadmap to turn a discussed product request into a confirmed, bounded roadmap. Do not invoke for ordinary requirement discussion or implementation planning.
---

# Requirements to Roadmap

Use this explicit-only workflow to turn an ambiguous request into a decision record that a later specification can trust. Stop after producing the roadmap; never start specification, planning, implementation, or external review automatically.

## Investigate before deciding

Read the relevant code, documents, callers, tests, and issue context. Separate verified facts, agent inferences, and unknowns. Do not ask the user for facts that the repository can establish.

If `brainstorming` and `grilling` skills are installed, use their applicable parts. If either is unavailable, use the equivalent method below and state that it is an in-skill fallback rather than pretending the dependency ran.

## Explore, then stress-test

First, restate the problem in user terms: affected actor, scenario, current outcome, and desired outcome. Ask one high-leverage unanswered question at a time. When there is a real choice, present a small set of options with a recommendation, cost, affected scope, and non-goals. Never turn an implementation convenience or a platform expansion into a requirement without approval.

Then create decision nodes for the remaining material choices. Ask only nodes whose prerequisites are known. Use concrete counterexamples to test happy paths, errors, boundary input, compatibility, permissions, privacy/retention, and defaults. Treat AI recommendations as proposals, never as approved decisions. Move unrelated good ideas to Deferred.

Stop only when the target, terms, scope, non-goals, key decisions, and observable acceptance direction are clear. If a required business choice remains, produce a draft and name the blocker rather than silently filling it in.

## Produce the roadmap

Use the repository's established location; otherwise use `.ai/roadmaps/YYYY-MM-DD-<topic>.md`. Keep stable IDs when revising:

- Context: issue/source, status, original problem, verified facts, assumptions, and unknowns.
- Requirements: `REQ-*` entries with a stable Requirement ID, tied to actors and outcomes.
- Decisions: `DEC-*` entries with options, confirmed choice, rationale, source, and status.
- Boundaries: in scope, non-goals, invariants, allowed components, dependencies, and Deferred work.
- Acceptance direction: `AC-*` entries for normal, failure, boundary, and compatibility outcomes.
- Phases: a stable Phase ID, purpose, related requirement, decision, and acceptance IDs, high-level work, dependency, deliverable, completion criterion, and priority.
- Handoff: the selected Phase ID for the next design call, unresolved questions, and decisions that later work must not change.

Before delivery, verify that every requirement has an acceptance direction, every phase supports a requirement, and no unapproved proposal appears in the frozen scope. Report the roadmap path, confirmation state, important decisions, and the explicit next invocation, such as `$roadmap-to-spec-plan`.
