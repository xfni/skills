---
name: flow-run
description: Use when the user explicitly requests continuous orchestration of the AI-native Flow v2 workflow from available inputs or artifacts.
---

# Flow Run

Orchestrate Flow v2 from the deepest valid checkpoint to integration evidence. Preserve every stage's artifact contract, ownership, reviews, and human gates; orchestration is permission to continue between satisfied gates, not permission to bypass them.

Read and follow `../../artifact-contract.md`. Require an issue ID before feature work. If the user explicitly supplied a goal, create or continue that active goal using the runtime goal mechanism; otherwise do not invent one. Before continuing, compare the runtime goal ID, issue and objective with the controller record. Continue only a matching goal; on a mismatch, pause for the human and must not replace, complete, or attach work to the other unfinished goal. Keep an active goal active across ordinary human gates.

## Resolve the starting stage

Resolve admission in this order:

1. Obtain a human-provided issue ID from the current conversation or from a goal/controller whose issue was originally supplied by the human. The agent must not infer it from a branch name, directory, repository, document contents, or similar clues. If none exists, ask the human for the issue ID and stop before searching or starting a stage.
2. Determine the resolved standard issue location through the artifact contract. Apply the location rules for each artifact type and the controller, because `AGENTS.md` may name different directories or full paths, then scan the union of those resolved locations. Where no artifact-specific rule exists, search the default `.ai/issue/<issue_id>/`.
3. If one or more candidate documents exist, validate them and continue stage resolution. Do not ask for paths merely because some later-stage documents are absent.
4. If no candidate document exists, show one interaction with exactly these choices:

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

Invoke the selected stage with the exact verified handoff. When it returns a successful handoff, recompute its binding and automatically invoke the next stage; the child stage's instruction to stop prevents that child from crossing its boundary, not this orchestrator from regaining control. Never merge stage bodies or write an artifact owned by another stage except the explicit raw requirement bootstrap.

At each owning human gate, display exactly what that stage requires and pause at the owning human gate. Persist a `flow_step: run` controller record through the artifact-contract path rules with issue, active goal reference when any, `target_milestones`, milestone states (`pending`, `completed`, or `deferred`), completed handoffs, pending stage, pending gate, exact revision/digest or snapshot binding, resume condition, open gaps, loop history, and next action. On reply, accept only explicit approval of the displayed binding, reload the record, revalidate artifact digests and worktree state, and resume from the same checkpoint. Discussion, silence, or approval of an older revision is not consent.

Human gates remain owned by their stages, including requirement brainstorming when needed, intent confirmation, roadmap approval and milestone selection, Spec approval, Plan approval, and Direct integration test-point confirmation. Governed integration uses its already approved `TESTCASE-*` authorization without asking again.

## Backward routing and completion

Honor every stage's failure owner and route backward to it. After any upstream body change, invalidate dependent downstream approvals, clear affected completed handoffs from the controller, then re-run reviews and stages in order. Do not automatically retry an external dependency, permission, environment, credential, destructive-action, or review blocker; record the exact resume condition. Prevent loops by recording cause and artifact binding, and stop when the same cause recurs without new evidence.

Propagate `COMPLETE_WITH_DEFECT` and every open `CURSOR_REVIEW_GAP`; never hide them or reinterpret them as a passed review. Automate transitions, but do not bypass any required review, approval, worktree boundary, sandbox permission, or remote-Git boundary.

When the roadmap is confirmed, freeze `target_milestones`: by default it contains every non-deferred milestone required to satisfy the active goal and complete Intent; the human may explicitly narrow the goal or defer named milestones before the set is frozen. Repeat Spec → Plan → Code → Integration one target milestone at a time and require the roadmap-owned human selection before each new milestone. Only mark the goal complete after every `target_milestones` entry is `completed` with fresh `PASSED` integration evidence, all required cleanup succeeds, and no required work remains; unresolved `pending` milestones prevent completion and `deferred` milestones must be reported as outside the goal. A failed scenario routes backward; a human gate merely pauses; blocked goal status follows the runtime goal policy rather than a single stage failure. Report final artifact paths, bindings, test results, open defects, and anything intentionally left outside the goal.
