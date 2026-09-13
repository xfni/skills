---
name: flow-run
description: Use when the user explicitly requests continuous orchestration of the AI-native Flow v2 workflow from available inputs or artifacts.
---

# Flow Run

Orchestrate Flow v2 from the deepest valid checkpoint to integration evidence. Read and enforce `../../flow-contract.md`; this skill owns Flow admission and does not rely on `AGENTS.md` for issue or worktree correctness. Preserve every stage's artifact contract, ownership, reviews, and necessary human gates. Read and enforce `../../orchestration-contract.md` for every child-stage transition.

Read and follow `../../artifact-contract.md`. Require an issue ID before feature work. If the user explicitly supplied a goal, create or continue that active goal using the runtime goal mechanism; otherwise do not invent one. Before continuing, compare the runtime goal ID, issue and objective with the controller record. Continue only a matching goal; on a mismatch, pause for the human and must not replace, complete, or attach work to the other unfinished goal. Keep an active goal active across ordinary human gates.

## Resolve the starting stage

Resolve admission in this order:

1. Obtain a human-provided issue ID from the current conversation or from a goal/controller whose issue was originally supplied by the human. The agent must not infer it from a branch name, directory, repository, document contents, or similar clues. If none exists, request it exactly once and stop before searching or starting a stage.
2. Initialize the controller, then create or reuse the matching worktree as required by the Flow admission contract before artifact discovery. On a valid inherited controller, stages must not ask for the issue ID again and must not recreate the worktree.
3. Determine the resolved standard issue location through the artifact contract. Apply the location rules for each artifact type and the controller, because `AGENTS.md` may name different directories or full paths, then scan the union of those resolved locations. Where no artifact-specific rule exists, search the default `.ai/issue/<issue_id>/`.
4. If one or more candidate documents exist, validate them and continue stage resolution. Do not ask for paths merely because some later-stage documents are absent.
5. If no candidate document exists, show one interaction with exactly these choices:

```text
Provide existing document paths
Use the current requirement without requirement discussion
Pause Flow
```

For the first choice, accept either a single document path or an artifact path map keyed by `requirement`, `intent`, `roadmap`, `spec`, `plan`, `code`, `integration`, and `run`. Resolve relative paths against the project root, validate every supplied path, record the accepted absolute paths in the controller, then locate the deepest valid checkpoint. The second choice is explicit bootstrap authorization to skip brainstorming and the requirement agent swarm; use raw bootstrap only when its other admission conditions hold, otherwise explain why and invoke `$flow-requirement`. For the third choice, record the pause without completing or blocking the goal.

Honor an explicit start override after resolving inputs, but validate its prerequisites. Validate every candidate artifact by issue, status, content revision, canonical SHA-256 digest, approval binding, upstream tuple, selected milestone, review gaps, and worktree/code snapshot where applicable. Never choose by filename, modification time, or apparent prose quality. Ambiguous candidates require the human to identify one.

Select the next stage after the deepest valid checkpoint in this chain:

```text
idea or unresolved requirement -> $flow-requirement (which uses $flow-brainstorm)
READY_FOR_INTENT requirement.md -> $flow-intent
confirmed intent.md -> start at `$flow-roadmap`
confirmed roadmap.md plus one selected MILESTONE-* -> $flow-spec
approved spec.md -> start at `$flow-plan`
approved plan.md -> $flow-code
complete code handoff -> $flow-integration
PASSED integration for the selected milestone -> next roadmap milestone or finish
```

An explicit start override never waives prerequisites. For example, an approved spec.md starts at `$flow-plan` only when its requirement, intent, roadmap, milestone, revision, digest, approval, and review-gap chain verifies. A standalone Spec is non-authoritative source evidence, not an approved Flow artifact: must not call `$flow-plan` or `$flow-spec` from it. Ask the human to identify or confirm its requirement source, then use raw bootstrap only if the human requirement independently satisfies bootstrap admission; otherwise start `$flow-requirement`. Preserve the standalone Spec as cited evidence for later stages, but never grant it approval, invent `HUMAN_BOOTSTRAP`, or fabricate its upstream chain.

## Raw requirement bootstrap

When the user supplies a sufficiently explicit requirement and explicitly wants to skip discussion, perform a raw requirement bootstrap instead of `$flow-brainstorm` or the requirement agent swarm. Faithfully normalize the user's complete statement into a canonical `requirement.md` accepted by `$flow-intent`: issue, immutable human source snapshot, one stated candidate direction, user-provided evidence, known objections, unknowns, coverage limits, content revision/digest, and `status: READY_FOR_INTENT`. Mark provenance `HUMAN_BOOTSTRAP` and the skipped substages. Show the captured requirement to permit correction, but must not invent product decisions, evidence, consensus, PMS facts, or agent conclusions. Any unresolved product choice or unclear success boundary disqualifies bootstrap and routes to `$flow-requirement`.

## Run and resume

Before executing a selected stage, supply a `FLOW_RUN_CONTEXT` bound to the run, issue, controller, stage, and exact verified handoff. Consume its orchestration signal in a controller loop:

- `FLOW_RUN_HANDOFF` is non-terminal: recompute its binding, update the controller, and automatically invoke the next stage in the same active turn.
- `FLOW_RUN_HUMAN_GATE`: persist the displayed binding and end the turn only to obtain the required human decision. On reply, resume from the same checkpoint in the owning stage; if it returns a handoff, continue the loop immediately.
- `FLOW_RUN_BLOCKED`: persist the cause, owner, evidence, and resume condition, then stop automatic progress.
- `FLOW_RUN_ROUTE_BACK` is non-terminal: record the failed binding and evidence, invalidate affected downstream state, and invoke its verified `owner_stage`/`next_stage` in the same active turn.
- Emit `FLOW_RUN_COMPLETE` only after the completion rules below pass.

A child-stage report is internal orchestration output. The root must not surface a successful child handoff or its manual next-skill suggestion as the final response. The child stage's instruction to stop prevents that child from crossing its boundary; it returns control to this loop. Never merge stage bodies or write an artifact owned by another stage except the explicit raw requirement bootstrap.

Repair controllers produced by older or interrupted orchestration. A `pending_gate: explicit_stage_invocation`, a resume condition asking the human to copy a next-stage command, or an equivalent manual relay is an obsolete orchestration state, never a valid human gate. The root must not ask the human to copy that command. Revalidate the recorded output tuple; when valid, migrate the controller to `FLOW_RUN_HANDOFF` and immediately continue its next stage. In particular, when roadmap approval and milestone selection is already recorded, continue to `flow-spec` without another selection or explicit invocation. If the tuple is invalid, route to its owning stage instead of preserving the obsolete gate.

At each necessary human gate, display exactly what decision or authority is missing and pause there. Persist a `flow_step: run` controller record through the artifact-contract path rules with issue provenance, repository/worktree/branch binding, Requirement authorization, active goal reference when any, `target_milestones`, milestone states (`pending`, `completed`, or `deferred`), completed handoffs, pending stage, pending gate, exact revision/digest or snapshot binding, resume condition, open gaps, loop history, and next action. On reply, reload and revalidate the exact binding before resuming.

Normal human interaction is limited to missing issue admission, requirement brainstorming, final Requirement authorization, a required Codex worktree resume, and Direct integration test-point confirmation. After Requirement authorization, Intent, Roadmap, milestone selection, Spec, Plan, Code, and governed Integration continue autonomously. Escalate only the authority-changing or unsafe conditions enumerated by the Flow admission contract. A Cursor runtime degradation is recorded and propagated without prompting unless it makes safe continuation impossible.

## Backward routing and completion

Honor every stage's failure owner and route backward to it. After any upstream body change, invalidate dependent downstream approvals, clear affected completed handoffs from the controller, then re-run reviews and stages in order. Do not automatically retry an external dependency, permission, environment, credential, destructive-action, or review blocker; record the exact resume condition. Prevent loops by recording cause and artifact binding, and stop when the same cause recurs without new evidence.

Propagate `COMPLETE_WITH_DEFECT` and every open `CURSOR_REVIEW_GAP`; never hide them or reinterpret them as a passed review. Automate transitions, but do not bypass any required review, approval, worktree boundary, sandbox permission, or remote-Git boundary.

When the roadmap is confirmed, freeze `target_milestones`: by default it contains every non-deferred milestone required to satisfy the active goal and complete Intent. Repeat Spec → Plan → Code → Integration one dependency-ready target milestone at a time, selecting the next milestone deterministically without human relay. Only mark the goal complete after every `target_milestones` entry is `completed` with fresh `PASSED` integration evidence, all required cleanup succeeds, and no required work remains; unresolved `pending` milestones prevent completion and `deferred` milestones must be reported as outside the goal. A failed scenario routes backward; a necessary human gate merely pauses; blocked goal status follows the runtime goal policy rather than a single stage failure. Report final artifact paths, bindings, test results, open defects, and anything intentionally left outside the goal.
