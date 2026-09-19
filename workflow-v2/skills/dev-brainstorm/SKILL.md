---
name: dev-brainstorm
description: Use when a requirement workflow needs human exploration before autonomous agent analysis.
---

# Dev Brainstorm

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Read and enforce `../../flow-contract.md`. Verify the inherited issue and worktree binding silently before discussion; use its admission gate when directly invoked without a valid controller.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at entry. The skill must not edit the controller or event log; it returns semantic brainstorming input to its owner and cannot advance Flow itself.

Explore a feature idea with the human and return a bounded input for `$dev-requirement`. This adapts the questioning and option-comparison techniques of Superpowers Brainstorming; the Flow stage boundary is authoritative.

## Explore

Use the supplied issue and conversation context. Inspect authorized repository facts before asking the human to recall them. Establish the affected user and scenario, problem, desired outcome, constraints, success criteria, and meaningful uncertainty.

Inherit the supplied discussion baseline from earlier human/Agent conversation. Distinguish explicit human commitments and rejected directions from provisional options and Agent suggestions; retain source references, applicable conditions and superseded statements. Do not re-ask settled questions without new evidence. If an available human-confirmed record still covers the current baseline, return it without another interview or confirmation. If no such confirmation is available, show a concise baseline for correction and ask only about material gaps, then confirm the record. Missing optional confirmer/time metadata alone does not require repeating a supported confirmation; do not invent it. A casual acknowledgment does not authorize scope, and a confirmed brainstorming record is not final development authorization.

Ask one question at a time. Prefer a concise choice when genuine alternatives exist, while allowing the human to modify or reject every option. For a decision, present two or three viable directions with value, cost, risk, scope effect, and an agent recommendation with rationale. Separate human facts and choices from agent inference. Do not pressure the human into premature commitment: confirmation here approves the brainstorming summary as an accurate discussion record, not final product intent.

When a direction introduces a generic platform, framework, registry, plugin system, shared abstraction, broad configurability, or extension mechanism, ask which current demand point requires it and what concrete present benefit it produces; future extensibility alone, architectural symmetry, or a hypothetical second consumer is not a reason to enlarge the requirement. Preserve such ideas as optional future considerations unless the human identifies a current need and benefit; always keep a smallest direct alternative visible.

Scale the number of questions to uncertainty. Stop when the problem and candidate directions are coherent enough for independent challenge; unresolved choices are valid output.

## Return contract

Return to the owning Agent a normalized `brainstorm_result` containing:

```text
status: DRAFT | CONFIRMED
confirmed_by; confirmed_at
issue_context_ref; conversation_context_ref; repository_scope_ref
problem; affected users and scenarios; desired outcomes
human facts and preferences; verified repository facts
constraints; success criteria; assumptions
two or three candidate directions when evidence supports alternatives
recommendation and rationale; rejected ideas
uncertainties; questions for autonomous analysis
```

Keep `status: DRAFT` while correcting the summary. Require human confirmation that it is accurate, or reuse the available explicit confirmation of the unchanged record, then set `status: CONFIRMED`, record available confirmation source/metadata, and return control to `$dev-requirement` with the confirmed result and its exact source references. Human changes are recorded as amendments, with the superseded source preserved.

Present that confirmation as “这是讨论记录，请确认是否准确，或直接修改；确认后由两个 Agent 分析候选方案，这还不是最终开发授权。” Show the short problem/outcome/constraint summary and open choices, not the internal brainstorm_result fields. Do not combine it with final product authorization.

This is a substage, not a delivery workflow: it must not write requirement.md, must not create a Spec or Plan, must not invoke `writing-plans`, and must not implement, commit, push, or dispatch the autonomous requirement-analysis roles. Those actions belong to their owning Flow stages.

Adapted from Superpowers `brainstorming` under the MIT License; maintained independently for the Flow workflow.
