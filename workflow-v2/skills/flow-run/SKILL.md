---
name: flow-run
description: Use when the user explicitly requests continuous orchestration of the AI-native Flow v2 workflow from available inputs or artifacts.
---

# Flow Run

Orchestrate Flow v2 from the deepest valid checkpoint to integration evidence. Read and enforce `../../flow-contract.md`; this skill owns Flow admission and does not rely on `AGENTS.md` for issue or worktree correctness. Preserve every stage's artifact contract, ownership, reviews, and necessary human gates. Read and enforce `../../orchestration-contract.md` for every child-stage transition.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at every entry and `flowctl resume` before selecting a checkpoint. The root must not edit the controller or event log; only controller JSON may authorize a stage transition. After an accepted handoff, automatically invoke the next stage.

Read and follow `../../artifact-contract.md`. Require an issue ID before feature work. If the user explicitly supplied a goal, create or continue that active goal using the runtime goal mechanism; otherwise do not invent one. Before continuing, compare the runtime goal ID, issue and objective with the controller record. Continue only a matching goal; on a mismatch, pause for the human and must not replace, complete, or attach work to the other unfinished goal. Keep an active goal active across ordinary human gates.

Invoking `$flow-run` explicitly authorizes the mandatory read-only Cursor reviews throughout the entire Flow run and the iBrain runtime backup. Persist both `cursor_transmission_authorization` and backup `ibrain_transmission_authorization`, bound to `issue_id`, `run_id`, worktree, review stages, and an `allowed_scope` containing only the necessary in-scope artifact/source manifest. Pass them as `FLOW_CURSOR_AUTHORIZATION` and `FLOW_IBRAIN_AUTHORIZATION`; while a manifest remains bound, children must not ask the human again. Exclude secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content. iBrain with fixed `glm-5.3` is invoked only after flowctl records two Cursor `RUN_ERROR` attempts, never because of Cursor findings.

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

### Observable status

Keep the human oriented without turning internal handoffs into approval gates: before each material transition, emit one concise status update that names the current stage, what was just completed, the next action, what Agent or external operation the run is waiting for, and whether any reported defect is blocking or non-blocking. Material transitions include entering a stage, dispatching or completing a subagent task, beginning a potentially long wait, receiving review findings, sending fixes back, starting GPT or Cursor review, routing backward, and recording degraded completion.

Use concrete identifiers such as `TASK-*`, milestone, Agent path, review kind, and affected snapshot. Do not expose chain-of-thought, dump the controller, ask for acknowledgement, or repeat unchanged status after every tool call. A wait timeout may produce a short heartbeat only when it changes the wait-window count or triggers the configured progress inquiry. Successful child handoffs remain internal and automatically continue after the status update.

Before executing a selected stage, supply a `FLOW_RUN_CONTEXT` bound to the run, issue, controller, stage, and exact verified handoff. Consume its orchestration signal in a controller loop:

- `FLOW_RUN_HANDOFF` is non-terminal: submit it to `flowctl handoff accept`, reload the returned controller state, and automatically invoke the accepted next stage in the same active turn.
- `FLOW_RUN_HUMAN_GATE`: submit it through `flowctl signal record`, display the recorded binding, and end the turn only to obtain the required human decision. On reply, record a bound `FLOW_RUN_RESUMED`, call `flowctl resume`, and continue only from the controller-returned owning stage.
- `FLOW_RUN_BLOCKED`: submit the cause, owner, evidence, and resume condition through `flowctl signal record`, then stop automatic progress. When that condition is actually satisfied, record `FLOW_RUN_RESUMED` before calling `flowctl resume`.
- `FLOW_RUN_RESUMED` is the only way to clear a recorded HUMAN_GATE or BLOCKED pause; bind it to the same issue, run, and current stage and include evidence that the recorded condition was satisfied.
- `FLOW_RUN_ROUTE_BACK` is non-terminal: submit it through `flowctl signal record`; use the returned invalidation and stage, then invoke that stage in the same active turn.
- Emit `FLOW_RUN_COMPLETE` only after the completion rules below pass.

A child-stage report is internal orchestration output. The root must not surface a successful child handoff or its manual next-skill suggestion as the final response. The child stage's instruction to stop prevents that child from crossing its boundary; it returns control to this loop. Never merge stage bodies or write an artifact owned by another stage except the explicit raw requirement bootstrap.

Repair controllers produced by older or interrupted orchestration through `flowctl resume`; never rewrite them directly. This command may migrate the controller from a verified legacy checkpoint. A `pending_gate: explicit_stage_invocation`, a resume condition asking the human to copy a next-stage command, or an equivalent manual relay is obsolete orchestration state, never a valid human gate. The root must not ask the human to copy that command. Use only the controller's verified pending action; when roadmap approval is valid and milestone selection is already recorded, immediately continue to `flow-spec` without another selection or explicit invocation.

At each necessary human gate, display exactly what decision or authority is missing and pause there. Have flowctl persist the structured gate, issue provenance, repository/worktree/branch binding, Requirement authorization, active goal reference, milestones, handoffs, pending action, exact bindings, gaps, and loop history; the Agent must not write these fields. The controller also owns `coder_agent` fields `coder_thread_id`, `coder_model`, `coder_effort`, `active_task`, `completed_tasks`, `last_checkpoint`, `replacement_generation`, `replacement_reason`, and `prior_coder_thread_id`, recording them through controller commands. On reply, run `flowctl status` and revalidate before resuming.

Normal human interaction is limited to missing issue admission, requirement brainstorming, final Requirement authorization, a required Codex worktree resume, and Direct integration test-point confirmation. After Requirement authorization, Intent, Roadmap, milestone selection, Spec, Plan, Code, and governed Integration continue autonomously. Escalate only the authority-changing or unsafe conditions enumerated by the Flow admission contract. A Cursor runtime degradation is recorded and propagated without prompting unless it makes safe continuation impossible.

## Backward routing and completion

Honor every stage's failure owner and route backward to it. Registering a changed upstream artifact makes flowctl invalidate dependent downstream approvals and reviews and clear affected completed handoffs; the Agent must not clear them itself. Do not automatically retry an external dependency, permission, environment, credential, destructive-action, or review blocker. Use controller-recorded causes, bindings, and retry facts to prevent loops.

Propagate `COMPLETE_WITH_DEFECT` and every open `EXTERNAL_REVIEW_GAP`; never hide them or reinterpret them as a passed review. Automate transitions, but do not bypass either independently owned review lane, the fresh GPT-6 Astra final consistency review, approval, worktree boundary, sandbox permission, or remote-Git boundary.

When the roadmap is confirmed, freeze `target_milestones`: by default it contains every non-deferred milestone required to satisfy the active goal and complete Intent. Repeat Spec → Plan → Code → Integration one dependency-ready target milestone at a time, selecting the next milestone deterministically without human relay. Only mark the goal complete after every `target_milestones` entry is `completed` with fresh `PASSED` integration evidence, all required cleanup succeeds, and no required work remains; unresolved `pending` milestones prevent completion and `deferred` milestones must be reported as outside the goal. A failed scenario routes backward; a necessary human gate merely pauses; blocked goal status follows the runtime goal policy rather than a single stage failure. Report final artifact paths, bindings, test results, open defects, and anything intentionally left outside the goal.
