---
name: flow-brainstorm
description: Use when a requirement workflow needs human exploration before autonomous agent analysis.
---

# Flow Brainstorm

Read and enforce `../../flow-contract.md`. Verify the inherited issue and worktree binding silently before discussion; use its admission gate when directly invoked without a valid controller.

Explore a feature idea with the human and return a bounded input for `$flow-requirement`. This adapts the questioning and option-comparison techniques of Superpowers Brainstorming; the Flow stage boundary is authoritative.

## Explore

Use the supplied issue and conversation context. Inspect authorized repository facts before asking the human to recall them. Establish the affected user and scenario, problem, desired outcome, constraints, success criteria, and meaningful uncertainty.

Ask one question at a time. Prefer a concise choice when genuine alternatives exist, while allowing the human to modify or reject every option. For a decision, present two or three viable directions with value, cost, risk, scope effect, and an agent recommendation with rationale. Separate human facts and choices from agent inference. Do not pressure the human into premature commitment: confirmation here approves the brainstorming summary as an accurate discussion record, not final product intent.

When a direction introduces a generic platform, framework, registry, plugin system, shared abstraction, broad configurability, or extension mechanism, ask which current demand point requires it and what concrete present benefit it produces; future extensibility alone, architectural symmetry, or a hypothetical second consumer is not a reason to enlarge the requirement. Preserve such ideas as optional future considerations unless the human identifies a current need and benefit; always keep a smallest direct alternative visible.

Scale the number of questions to uncertainty. Stop when the problem and candidate directions are coherent enough for independent challenge; unresolved choices are valid output.

## Return contract

Show a normalized `brainstorm_result` containing:

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

Keep `status: DRAFT` while correcting the summary. Require human confirmation that it is accurate, then set `status: CONFIRMED`, record confirmer and time, and return control to `$flow-requirement` with the confirmed result and its exact source references.

This is a substage, not a delivery workflow: it must not write requirement.md, must not create a Spec or Plan, must not invoke `writing-plans`, and must not implement, commit, push, or dispatch the autonomous requirement-analysis roles. Those actions belong to their owning Flow stages.

Adapted from Superpowers `brainstorming` under the MIT License; maintained independently for the Flow workflow.
