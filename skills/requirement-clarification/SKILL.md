---
name: requirement-clarification
description: Use when the user explicitly requests human alignment on an existing feature requirement before intent or roadmap creation.
---

# Requirement Clarification

Challenge an existing `requirement.md` with the human, record authoritative decisions, and leave a confirmed or blocked requirement. This stage aligns details; it must not run Requirement Council, generate `intent.md`, or begin roadmap, specification, planning, or implementation.

## Admission

Require an existing `requirement.md` supplied by the caller or found at the repository's established location. It must identify the issue, immutable `issue_context` snapshot when available, sources, current status, candidates or selected direction, scope, non-goals, constraints, success direction, unknowns, and revision. Consume the snapshot without re-fetching PMS. If the artifact is absent, return the missing input instead of reconstructing it independently.

Treat `DRAFT` and `READY_FOR_CLARIFICATION` as valid inputs. A `CONFIRMED` requirement may be reopened only when the human explicitly requests revision; record that event before questioning. Never silently overwrite human-confirmed decisions.

## Use grilling or the built-in fallback

If the `grilling` skill is installed, invoke it with the complete requirement artifact, relevant conversation history, evidence references, candidate choices, objections, and unknowns. Tell it to focus on requirement-critical choices and return decisions to this workflow; it does not own the artifact.

If `grilling` is unavailable, use this built-in fallback:

1. Test whether the problem, affected user, scenario, and desired outcome are real and aligned.
2. Challenge candidate selection, delivery boundary, non-goals, invariants, accepted risks, and success signals.
3. Ask one high-leverage question at a time. Do not ask for facts available from authorized repositories or prior conversation.
4. Present two or three options with a recommendation when a genuine choice remains.
5. Stop when remaining unknowns no longer change intent, or when a named missing fact or authority blocks confirmation.

Grilling intensity changes how aggressively assumptions are tested, not who makes the decision. Agent proposals remain `INFERENCE`; only explicit human answers become `HUMAN` decisions.

## Update the requirement

Update the same logical `requirement.md`, increment `revision`, and preserve prior candidates, objections, and rejected alternatives. Add a `Clarification Decisions` section with stable `DEC-*` IDs, the human answer, rationale when given, source, and affected fields.

The updated artifact contains:

```text
status: CONFIRMED | BLOCKED
issue; sources; revision; selected option
problem; target user and scenario; desired outcome
scope; non-goals; invariants; success signals
accepted risks; Rejected alternatives; remaining unknowns
Clarification Decisions; confirmed_by; confirmed_at
```

Before requesting confirmation, show the complete normalized requirement that will feed intent. Use `CONFIRMED` only after explicit human confirmation of that displayed revision's selected direction and all intent-changing fields. Record the confirmation against the revision so `requirement-to-intent` can reuse it without asking twice while the artifact remains unchanged. Use `BLOCKED` when a missing fact, preference, or authority answer can still change the requirement. Report the path, revision, status, decisions, and blocker if any. Do not create `intent.md`; hand the confirmed artifact back to `requirement-to-intent`.
