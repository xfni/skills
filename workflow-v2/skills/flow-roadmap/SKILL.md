---
name: flow-roadmap
description: Use when the user explicitly requests delivery milestones from a confirmed intent and its requirement evidence.
---

# Flow Roadmap

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at entry, `flowctl artifact register` after writing Roadmap, and `flowctl handoff accept` with schema-valid JSON. The skill must not edit the controller or select a checkpoint itself.

Turn confirmed product intent into ordered delivery milestones. Read both `requirement.md` and `intent.md`: the requirement supplies evidence, alternatives, and risk history; the intent is authoritative for product scope and success.

## Admission and authority

Use confirmed Intent and available Requirement context in the admitted issue/worktree. Controller-owned bindings replace model-declared exact revision/digest tuples; missing historical context is disclosed rather than fabricated or treated as a format blocker. Product confirmation remains necessary. Follow Intent on a documented conflict; changing Scope, Non-goals, Invariants or Success Signals returns to Intent for a real decision.

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

Resolve the output path through the artifact contract with flow_step `roadmap`. Include source paths and revisions, verified repository facts, assumptions, deferred work, milestone dependency graph, acceptance direction, and traceability from every intent outcome to at least one milestone. Emit the artifact contract's machine-readable `target_milestones` JSON array and `milestone_dependencies` JSON object; prose headings are not a substitute.

Write `status: DRAFT` and compute a canonical SHA-256 body digest. Under `FLOW_RUN_CONTEXT`, verify the roadmap remains inside the Requirement authorization, freeze all non-deferred milestones required by Intent as `target_milestones`, and sign it as `ORCHESTRATED` without another human approval. Its approval envelope records `approved_revision` and `approved_digest`. Under direct invocation, show milestone boundaries and ordering and require explicit approval of the current binding. Content changes increment revision and invalidate its approval.

Do not create specifications or plans inside this stage. Under `FLOW_RUN_CONTEXT`, submit the Roadmap handoff with `next_stage: auto`; flowctl selects and returns the first dependency-ready target milestone. Do not ask the human to select it. Under direct invocation, ask the human to select exactly one milestone and then suggest `$flow-spec`. Record the handoff tuple containing requirement, intent, and roadmap paths with approved revisions/digests plus the controller-selected `MILESTONE-*`.
