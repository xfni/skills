---
name: flow-roadmap
description: Use when the user explicitly requests delivery milestones from a confirmed intent and its requirement evidence.
---

# Flow Roadmap

Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.

Turn confirmed product intent into ordered delivery milestones. Read both `requirement.md` and `intent.md`: the requirement supplies evidence, alternatives, and risk history; the intent is authoritative for product scope and success.

## Admission and authority

Require matching issue IDs and paths plus approved revisions and SHA-256 digests for `requirement.md` and `intent.md`, both with `status: CONFIRMED`. Recompute both canonical digests and reject mismatch, drift, or missing confirmation. When the documents conflict, preserve the evidence conflict but follow intent; if the conflict would change Scope, Non-goals, Invariants, or Success Signals, stop and return to `$flow-intent` for a new revision.

Investigate relevant repository architecture, callers, tests, dependencies, and operational constraints. Investigation may change feasibility, sequencing, and estimates, never the confirmed product intent.

## Build milestones

Create the smallest coherent milestones that cumulatively realize the whole intent. Each milestone contains:

```text
MILESTONE-* and name
user or system capability delivered
linked intent outcomes, requirement evidence, and Success Signals
in-scope boundary and explicit exclusions
dependencies and ordering rationale
high-level technical surfaces, migrations, and rollout concerns
acceptance direction for normal, failure, boundary, and compatibility behavior
risks; exit criteria; priority
```

Milestones describe outcomes and dependency order. The roadmap must not include file-level tasks, function edits, test commands, or step-by-step implementation; those belong to Plan. Avoid phases that only create infrastructure without delivering or enabling a named capability.

## Write and confirm roadmap.md

Resolve the output path through the artifact contract with flow_step `roadmap`. Include source paths and revisions, verified repository facts, assumptions, deferred work, milestone dependency graph, acceptance direction, and traceability from every intent outcome to at least one milestone.

Write `status: DRAFT`, compute a canonical SHA-256 body digest, show milestone boundaries and ordering to the human, and require explicit approval of the complete current content revision and digest. Requested content changes increment revision, recompute the digest, and require a new preview. On approval, set `status: CONFIRMED` in a separate envelope and record confirmer, time, `approved_revision`, and `approved_digest`; do not alter the approved body.

Do not create specifications or plans automatically. Ask the human to select exactly one milestone for the next stage. Record or report a handoff tuple containing requirement, intent, and roadmap paths with approved revisions and digests plus the selected `MILESTONE-*`; never infer the selection or reuse it after the roadmap changes. Then stop and provide the fully bound explicit `$flow-spec` invocation.
