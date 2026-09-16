---
name: flow-run
description: Use when the user explicitly requests continuous orchestration of the AI-native Flow v2 workflow from available inputs or artifacts.
---

# Flow Run

Production data handling follows project policy, not a Flow sanitization protocol. Legacy adapter cleanup annotations alone are not progression gates; preserve their history and inspect actual temporary-service or test-side-effect risks. Never interpret missing Integration results as legacy compatibility when the approved Plan contains `integration_scenarios`.

Orchestrate Flow v2 from the deepest valid checkpoint to integration evidence. Read and enforce `../../flow-contract.md`; this skill owns Flow admission and does not rely on `AGENTS.md` for issue or worktree correctness. Preserve every stage's artifact contract, ownership, reviews, and necessary human gates. Read and enforce `../../orchestration-contract.md` for every child-stage transition.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at every entry and `flowctl resume` before selecting a checkpoint. The root must not edit the controller or event log; only controller JSON may authorize a stage transition. After an accepted handoff, automatically invoke the next stage.

Read and follow `../../artifact-contract.md`. Require an issue ID before feature work. Explicit `$flow-run` invocation requests a durable runtime Goal for this Flow's human-stated scope; no separate `/goal` request is needed. Apply the runtime recipe below after issue admission, before dispatching a child stage. Goal persistence never authorizes a Flow transition.

## Runtime Goal

1. Inspect the actual runtime with `get_goal`. Build a concise objective from the human-supplied issue and task: complete the stated Flow scope through required integration evidence, resolving requirement choices with the human where necessary. Do not invent product requirements or scope; before Requirement is settled the objective describes completing the workflow, not a chosen implementation. Omit `token_budget` unless the human explicitly requested one.
2. If there is no Goal, or the previous Goal is genuinely `complete`, call `create_goal` with that objective. If there is an unfinished Goal, reuse it only when the actual objective covers this issue and the same human task, using conversation and any recorded reference as context. A matching broader human Goal can be reused; do not require literal objective equality. An unrelated/ambiguous unfinished Goal requires human direction, never replacement or false completion. A stale controller reference alone does not create a new human gate: after a verified same-task session change, record the new reference and preserve its history. Reuse a matching active Goal without creating another.
3. Verify creation/reuse through `get_goal`, then record the observed `{ "goal": { "threadId": ..., "createdAt": ..., "objective": ..., "status": ... } }` using `flowctl goal record --state <controller> --payload <snapshot.json> --expected-revision <current>`. Obtain all fields from the real tool response; the reference is `(threadId, createdAt)`, not an invented Goal ID. The root may write this input snapshot using normal file-edit tools, but only flowctl writes controller/event state. Refresh after session recovery or Goal status changes, not after every tool call. Recording context does not clear a human/safety pause or provide evidence of host activation.
4. Keep the Goal active across ordinary stage/milestone handoffs. Accept the child handoff and execute the next controller action in the same turn; an intermediate status update is commentary, never a successful-stage final response. On automatic Goal continuation, run `flowctl status`/`resume` and continue the current pending action, without restarting completed stages or creating a replacement coder.
5. A necessary human gate or an explicit human pause ends the turn for that decision, with no repeated automatic work while the gate is outstanding. Keep the Goal active unless the host or human changes it; repeated waiting for the same human decision is not grounds to mark it blocked. If the host reports a paused, blocked or budget-limited matching Goal, respect that state and explain how the human can resume it; `update_goal` cannot activate or extend it. A stage failure alone is not a blocked Goal: follow the host's repeated-blocker threshold and exhaust safe in-scope progress. Never create replacement Goals to evade a pause, limit, or blocker.
6. Only after Flow completion, required cleanup, and the actual Goal's entire objective are fulfilled with no remaining commitments, call `update_goal(status="complete")` for that still-matching Goal and refresh its reference. If Flow is only a sub-scope of a reused broader human Goal, keep it active and continue the remaining authorized work, or obtain a necessary human decision; Flow completion alone never completes the broader Goal. Include the host's final token-usage report if budgeted. If Goal tools are absent or unavailable, report that durable automatic continuation was not activated and continue the normal same-turn controller loop when safe; do not claim Goal creation or add a controller blocker solely for this missing optional runtime capability. Never simulate activation with shell `/goal`, a new `codex` subprocess, or controller JSON. Recheck the actual Goal before any lifecycle-changing call.

After admission, inspect only the controller's production_replay decision for the initial Chinese human gate. External review requires no separate authorization; apply the frozen-worktree review policy below.

```text
生产数据回放授权
范围：仅限当前议题、运行和工作树的生产数据获取及本地测试。
Flow 不负责脱敏或证明脱敏；数据处理遵循项目规定。不向模型外发测试数据，不纳入 Git。
不回放时仍执行所有测试环境或合成数据集成场景。
1. 允许使用生产数据进行本地测试（推荐）
2. 不进行依赖生产数据的集成测试
```

Map choice 1 to {"decision":"LOCAL_PRODUCTION_REPLAY"}, choice 2 to {"decision":"SKIP_PRODUCTION_REPLAY"}. Record only a pending production_replay decision through flowctl authorization decide, using the current state revision. Reuse an active replay ID/revision on resume; changed replay authority follows flowctl authorization amend and the bound human decision. No Cursor/iBrain gate or repeated reviewer confirmation is permitted.

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

## Resolve the starting stage

Use the controller's current `pending_action`, including iBrain, final consistency, `snapshot:capture`, and `approve:<kind>`; do not reset every reviewed-stage resume to GPT. Approval actions are downstream envelope updates, not new human gates: follow `../../flowctl-contract.md`, register unchanged BODY again, and continue automatically when the handoff action is returned.

Resolve admission in this order:

1. Obtain a human-provided issue ID from the current conversation or from a goal/controller whose issue was originally supplied by the human. The agent must not infer it from a branch name, directory, repository, document contents, or similar clues. If none exists, request it exactly once and stop before searching or starting a stage.
2. Initialize the controller, then create or reuse the matching worktree as required by the Flow admission contract before artifact discovery. On a valid inherited controller, stages must not ask for the issue ID again and must not recreate the worktree.
3. Resolve the Runtime Goal recipe and consolidated run authorization gate above. Reuse active Goal/authorization references on resume and do not enter requirement work while the production_replay decision remains pending.
4. Determine the resolved standard issue location through the artifact contract. Apply the location rules for each artifact type and the controller, because `AGENTS.md` may name different directories or full paths, then scan the union of those resolved locations. Where no artifact-specific rule exists, search the default `.ai/issue/<issue_id>/`.
5. If one or more candidate documents exist, validate them and continue stage resolution. Do not ask for paths merely because some later-stage documents are absent.
6. If no candidate document exists, show one interaction with exactly these choices:

```text
Provide existing document paths
Use the current requirement without requirement discussion
Pause Flow
```

For the first choice, accept either a single document path or an artifact path map keyed by `requirement`, `intent`, `roadmap`, `spec`, `plan`, `code`, `integration`, and `run`. Resolve relative paths against the project root, validate every supplied path, record the accepted absolute paths in the controller, then locate the deepest valid checkpoint. The second choice is explicit bootstrap authorization to skip brainstorming and the requirement agent swarm; use raw bootstrap only when its other admission conditions hold, otherwise explain why and invoke `$flow-requirement`. For the third choice, record the pause without completing or blocking the goal.

Honor an explicit start override after resolving its necessary current inputs. Let `flowctl resume` discover readable issue/stage-bound artifacts without demanding precise document metadata or a complete historical chain. Report missing history and uncertainty to the owning Agent. Never fabricate prior approvals, executed reviews or tests. Current operations need clear worktree/issue identity and actual terminal review receipts, not perfect historical paperwork.

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

An explicit arbitrary-node start does not require reconstructing earlier stages. An existing Spec can enter Spec review and then Plan; an existing Plan can enter Plan review and then Code. Use the supplied document and human task boundary, disclose missing history, and perform any still-required current reviews. Do not send the human back to Requirement merely because old revision/digest tuples are absent. Genuine unresolved product decisions still belong to the human; do not manufacture `HUMAN_BOOTSTRAP`, old consensus or old approvals.

## Raw requirement bootstrap

When the user supplies a sufficiently explicit requirement and explicitly wants to skip discussion, perform a raw requirement bootstrap instead of `$flow-brainstorm` or the requirement agent swarm. Faithfully normalize the user's complete statement into a canonical `requirement.md` accepted by `$flow-intent`: issue, immutable human source snapshot, one stated candidate direction, user-provided evidence, known objections, unknowns, coverage limits, content revision/digest, and `status: READY_FOR_INTENT`. Mark provenance `HUMAN_BOOTSTRAP` and the skipped substages. Show the captured requirement to permit correction, but must not invent product decisions, evidence, consensus, PMS facts, or agent conclusions. Any unresolved product choice or unclear success boundary disqualifies bootstrap and routes to `$flow-requirement`.

## Run and resume

Known test datasets must not cause a data-transfer authorization stop: use the child review manifest's file/directory exclusions under `../../review-contract.md`, then continue automatically and disclose coverage limits. Keep current target evidence required and repeat exclusions for every fresh attempt/backend. Never send excluded data through the root brief instead.

Controller validation errors are not automatically business `BLOCKED`. Missing current input or an unreadable conclusion returns to its owning Agent for repair. Metadata warnings, optional-field differences, historical annotations and redundant counts do not require human unlock. Use `FLOW_RUN_BLOCKED` only for an evidenced substantive or safety obstacle; report a broken controller/runner as a tool error, never as proof that the requirement is blocked. Do not silently turn an unknown review/test result into PASS.

### Observable status

Use the unified `status` / `result` / `explanation` summary in `../../orchestration-contract.md` for every stage update and final report. Four statuses are 等待中 (human only), 进行中, 阻塞中, 已完成; unstarted is null. Results are 通过, 有条件通过, 拒绝 or null. Report stage/milestone, show the action or required decision in explanation, and keep controller errors distinct from substantive rejection. Prefer controller-returned summaries when available; never let these display fields authorize progression.

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

Repair controllers produced by older or interrupted orchestration through `flowctl resume`; never rewrite them directly. This command may migrate the controller from a verified legacy checkpoint. A clean legacy Plan checkpoint without `integration_scenarios` remains resumable when no replay skip or new Integration results contract is used. Before either is needed, require a Plan revision and re-review that adds the machine contract. Resume must revalidate every Integration result against its same-milestone Plan and must reject any replay skip or gap unless the controller still has active `SKIP_PRODUCTION_REPLAY` authorization. A `pending_gate: explicit_stage_invocation`, a resume condition asking the human to copy a next-stage command, or an equivalent manual relay is obsolete orchestration state, never a valid human gate. The root must not ask the human to copy that command. Use only the controller's verified pending action; when roadmap approval is valid and milestone selection is already recorded, immediately continue to `flow-spec` without another selection or explicit invocation.

For a historical pause caused solely by a removed Flow sanitizer/profile/manifest/raw-data-cleanup prerequisite, preserve its history, verify that it names no actual unresolved safety issue, then record a bound FLOW_RUN_RESUMED with the current production-data policy and resume. This is not evidence that data was sanitized or deleted. Project constraints, host refusals, temporary-service/test-side-effect cleanup, review findings and mixed/unverified blockers remain valid gates. For a pause caused solely by the superseded external_review human gate, preserve history and record FLOW_RUN_RESUMED with current review policy and verified binding, then resume with a fresh package; never fabricate an old approval.

At each necessary human gate, display exactly what decision or authority is missing and pause there. Have flowctl persist the structured gate, issue provenance, repository/worktree/branch binding, Requirement authorization, active goal reference, milestones, handoffs, pending action, exact bindings, gaps, and loop history; the Agent must not write these fields. The controller also owns `coder_agent` fields `coder_thread_id`, `coder_model`, `coder_effort`, `active_task`, `completed_tasks`, `last_checkpoint`, `replacement_generation`, `replacement_reason`, and `prior_coder_thread_id`, recording them through controller commands. On reply, run `flowctl status` and revalidate before resuming.

Normal human interaction is limited to missing issue admission, the initial production-replay authorization gate, requirement brainstorming, final Requirement authorization, a required Codex worktree resume, and Direct integration test-point confirmation. After Requirement authorization, Intent, Roadmap, milestone selection, Spec, Plan, Code, and governed Integration continue autonomously. Escalate only the authority-changing or unsafe conditions enumerated by the Flow admission contract. A Cursor runtime degradation is recorded and propagated without prompting unless it makes safe continuation impossible.

## Backward routing and completion

Honor every stage's failure owner and route backward to it. Registering a changed upstream artifact makes flowctl invalidate dependent downstream approvals and reviews and clear affected completed handoffs; the Agent must not clear them itself. Do not automatically retry an external dependency, permission, environment, credential, destructive-action, or review blocker. Use controller-recorded causes, bindings, and retry facts to prevent loops.

Propagate `COMPLETE_WITH_DEFECT` and every open gap, including `EXTERNAL_REVIEW_GAP` and `PRODUCTION_REPLAY_GAP`; never hide them or reinterpret them as clean success. Automate transitions, but do not bypass either independently owned review lane, the fresh GPT-6 Astra final consistency review, approval, worktree boundary, sandbox permission, or remote-Git boundary.

When the roadmap is confirmed, freeze `target_milestones`: by default it contains every non-deferred milestone required to satisfy the active goal and complete Intent. Repeat Spec → Plan → Code → Integration one dependency-ready target milestone at a time, selecting the next milestone deterministically without human relay. A milestone may terminate with fresh `PASSED` evidence or a valid terminal `COMPLETE_WITH_DEFECT` whose skipped scenarios and open gaps are bound to the current approved Plan. Only mark the goal complete after every `target_milestones` entry is `completed`, all required cleanup succeeds, and no required work remains; unresolved `pending` milestones prevent completion and `deferred` milestones must be reported as outside the goal. If any terminal result is `COMPLETE_WITH_DEFECT`, propagate every open gap in the final response and must not claim clean completion. A failed scenario routes backward; a necessary human gate merely pauses; blocked goal status follows the runtime goal policy rather than a single stage failure. Report final artifact paths, bindings, test results, open defects, and anything intentionally left outside the goal.
