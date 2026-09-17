# Flow Run Orchestration Contract

## Unified stage summary

Every Flow stage, including Direct invocation and brainstorming, uses the same outward summary: `status`, `result`, and `explanation`. Display these as 状态、结果、说明. Use JSON `null`, not a new enum or the string "空", when no value exists.

| Field | Values and meaning |
| --- | --- |
| `status` | `null`: not yet started; `等待中`: awaiting human input, choice, confirmation or authorization only; `进行中`: executing, including subagent/service waits, automatic retries and repairs; `阻塞中`: an evidenced obstacle prevents safe continuation; `已完成`: stage handoff conditions have been satisfied. |
| `result` | `null`: no substantive conclusion; `通过`: conditions satisfied without open gaps; `有条件通过`: conditions satisfied with explicitly permitted open gaps; `拒绝`: substantive evidence shows conditions unsatisfied and requires repair or route-back. |
| `explanation` | Current action, required human decision/options, rejection evidence, blocker and recovery action, or conditional-pass gaps/owner/remediation. Explain unusual cases without inventing new enums. |

Normal human confirmation is `等待中`, usually with a null result. Human intervention to resolve an existing safety or execution obstacle remains `阻塞中`. Waiting for a running coder/reviewer and automatic retry remain `进行中`. Never label unstarted stages `等待中`. A rejected conclusion undergoing repair is `进行中` plus `拒绝`; an unavailable reviewer has no substantive conclusion and must not become `拒绝`. A previously evidenced result may remain while waiting, but explanation must state that confirmation is pending and progression is not authorized by that result alone.

Report stage and active milestone separately so results cannot leak between milestones. Do not infer completion from a draft's `APPROVED`/`PASSED` label. After a controller-accepted handoff, report `已完成` with `通过` or `有条件通过`, then automatically enter the next stage. Conditional pass is not permission to defer a blocker; carry every open gap and its follow-up. After target changes or a new evaluation begins, clear stale results and describe the current attempt; retain historical conclusions only as evidence.

These fields are observation, not new handoff/schema/approval gates and not Agent-writable controller state. Existing artifact approval words, reviewer classifications and testcase results remain internal evidence; do not mechanically rename their schemas. `flowctl status.stage_summary` describes the current controller stage; `flowctl handoff accept.stage_summary` describes the stage just completed. Neither is a complete historical stage ledger. Unvisited or skipped stages have null status/result; explain whether not started or intentionally skipped rather than fabricating completion. Admission failures that occur before a usable controller exists must use the same outward wording with their actual cause.

## Human-readable interruption

Every skill reads and applies this section in both Direct and Orchestrated mode, including brainstorming and admission before a controller exists. It changes communication, not gates, enums, schemas or authority. The remaining orchestration protocol requires FLOW_RUN_CONTEXT.

A human interruption is an actionable explanation for someone who has never read Flow documentation. Use the conversation language (Chinese by default). Name stages as 需求讨论、意图确认、开发路线、行为规格、执行计划、编码与单测、集成测试; internal IDs belong in optional diagnostics. Machine null remains null, but omit an unset result in human text instead of printing “结果：null”. Render controller summaries; do not copy an opaque error/explanation as the entire user message.

The message contains, in this order, compactly combined where useful:

1. Current activity and plain-language status: what is paused, not a claim that every independent action is blocked.
2. Concrete problem, impact and known limits: distinguish a product decision, permission/environment obstacle, implementation failure and workflow-tool fault. Unknown is unknown; do not translate a protocol error into a code defect or invent a cause.
3. Verified progress and checks already made; state relevant operations not yet performed. Report only actual checks, no simulated attempts.
4. The smallest human input/action needed. Ask one decision at a time, provide two or three genuine options with a recommendation and consequences when alternatives exist, and accept free-form correction. Do not manufacture an alternative that waives a required review, fixes a counter, grants host authority or counts an unexecuted test as passed.
5. What happens after the reply, from which activity it continues, and what previous work is preserved. Do not promise universal historical recovery or no re-review when changed implementation actually needs it.

Questions request business outcomes or usable source information, not workflow paperwork. A Requirement/Direct approval shows the scope, exclusions, expected outcome and material risks before “确认”; controller-owned digest/revision binding remains recorded, not something the human must calculate, copy or interpret. Stable issue/test-point IDs remain visible when the human needs to identify them. Provide a complete copyable command only when the human must actually run it (for example a verified Codex worktree resume).

If read-only discovery can resolve a path, endpoint, environment variable or repository fact, the Agent does that first. For a remaining middleware unknown, report known non-secret facts and ask for the approved test resource or its runbook/configuration location; do not ask the human to repeat discoverable addresses or paste credentials. Credentials are configured through an approved local/host mechanism; never request secret values in chat.

A controller/reviewer tool fault normally returns to the Agent for safe diagnosis/repair, not an approval prompt. When no safe in-scope continuation remains, explain “这是工作流工具问题，不是已发现的需求或代码失败”, identify the required maintainer action and provide a short forwardable diagnostic note. Describe the effect as “审查报告格式异常，暂时无法确认审查结果”; frame/parser/runner internals belong in that diagnostic note, not the required user action. Ordinary users need not understand the internal fix. A “确认继续” reply cannot resolve a tool fault, waive a blocker or override a host refusal. Exhaust safe allowed work before requiring human intervention.

Keep paths, revisions, digests, signal names, attempt counts and raw error codes in a short optional “维护者诊断” after the actionable message; keep the actual structured signal and bindings in controller evidence. Do not dump data values, credentials or private reasoning. Distinct safety/host restrictions stay binding and named clearly. Routine successful handoffs, automatic repairs, reviewer/coder waits and allowed fallback are commentary updates, never extra human confirmation gates. When unchanged human input is still outstanding, reuse that question rather than asking it again.

Example after actual middleware discovery leaves isolation unknown:

> 集成测试暂时不能启动：我已找到测试数据库地址，但还无法确认本次可以使用哪个测试库，以及如何避免影响已有数据。已检查项目配置和启动脚本；尚未连接数据库或发送请求。
>
> 请提供允许使用的测试库/隔离范围，或告诉我对应测试配置、说明文档的位置。无需重新提供已找到的地址，也不要发送密码。确认范围后，我会核验配置、按宿主要求申请启动权限，再继续当前测试；不会重新做需求和编码。

## Internal orchestration protocol

The handoff JSON schema validates context-independent structure and globally known stage names. `flowctl handoff accept` separately validates the context-dependent transition against controller state, milestone readiness, and the fixed transition graph. Passing schema validation never promises that a requested transition is currently legal; callers may use `next_stage: auto` to leave that decision entirely to the controller.

Apply the minimum progression boundary in `flowctl-contract.md`. Auxiliary handoff fields and model-generated bookkeeping do not block. Controller/bridge errors return to the owning Agent for repair; only real product, external-authority or execution-safety obstacles justify `FLOW_RUN_BLOCKED`. Missing historical documents do not force arbitrary-node invocation back to Requirement. Required reviews need actual terminal receipts; an Agent's PASS label alone is not approval.

Read and enforce `flow-contract.md` first. Admission is a Flow-owned prerequisite, not an assumed `AGENTS.md` behavior.

Read `flowctl-contract.md` first. This protocol applies only when a stage receives a controller-verified `FLOW_RUN_CONTEXT` containing:

```text
caller: flow-run
run_id; issue_id; controller_path
stage; input paths/revisions/digests or snapshot binding
optional coder_agent: coder_thread_id; coder_model; coder_effort; active_task; completed_tasks; last_checkpoint; replacement_generation; replacement_reason; prior_coder_thread_id
optional authorization_bindings: production_replay authorization_id/revision; external review package binding
```

Without that envelope, use **Direct invocation** behavior and keep the stage's normal stop-and-suggest-next response. With it, use **Orchestrated invocation** behavior: preserve every stage rule and gate, but return exactly one signal to `$flow-run` instead of ending with a manual next-skill instruction.

```json
{
  "schema_version": 1,
  "signal": "FLOW_RUN_HANDOFF",
  "issue_id": "BCS-710",
  "run_id": "run-bcs-710",
  "from_stage": "flow-spec",
  "next_stage": "flow-plan",
  "artifact_key": "spec:MILESTONE-1"
}
```

The child stage returns this payload without accepting it. The root `$flow-run` writes the temporary JSON and calls `flowctl handoff accept` exactly once, then continues from its returned state. Paths, revisions, digests, review counts and open gaps come from controller state; do not duplicate them as mandatory caller declarations. In Direct mode the stage owns its single acceptance when explicitly progressing; there is no second root acceptance.

Other semantic signals remain:

```text

FLOW_RUN_HUMAN_GATE
stage; gate; displayed_binding; controller_path; resume_condition

FLOW_RUN_BLOCKED
stage; status; cause; evidence; owner; controller_path; resume_condition

FLOW_RUN_RESUMED
stage; cause; evidence; controller_path; satisfied_resume_condition

FLOW_RUN_ROUTE_BACK
stage; status: FAILED; cause; evidence; owner_stage; next_stage; invalidated_bindings

FLOW_ADMISSION_GATE
stage; missing_human_input; controller_path; resume_condition

FLOW_ADMISSION_BLOCKED
stage; cause; evidence; controller_path; resume_condition
```

Serialize each non-success signal according to `schemas/signal.schema.json` and call `flowctl signal record`. A prose signal is not durable state and must not be used to resume, block, or route the workflow.

- `FLOW_RUN_HANDOFF` is non-terminal. `flowctl handoff accept` validates it and changes controller stage; `$flow-run` then continues to the returned stage in the same active turn. The stage must not suggest or ask the human to invoke that next skill.
- `FLOW_RUN_HUMAN_GATE` is the only normal pause for human input. Persist the exact binding before asking; present the bound scope and decision using Human-readable interruption, not raw bookkeeping. After the human responds, record a bound `FLOW_RUN_RESUMED`, call `flowctl resume`, and continue the controller-returned owning stage; a successful confirmation returns `FLOW_RUN_HANDOFF`.
- `FLOW_RUN_BLOCKED` pauses only for a real blocked condition and preserves the owning-stage routing. Its user message names the actual obstacle, prior checks and actionable recovery in plain language; a controller error alone is not a request for user consent. Once its recorded resume condition is actually satisfied, record `FLOW_RUN_RESUMED` before calling `flowctl resume`.
- `FLOW_RUN_RESUMED` is the only signal that clears a recorded HUMAN_GATE or BLOCKED pause. It must bind the same issue, run, and current stage and provide evidence that the recorded resume condition was satisfied.
- `FLOW_RUN_ROUTE_BACK` is non-terminal. It carries an evidenced Agent-selected repair/scope owner (available FAILED observations when applicable); `$flow-run` invalidates affected downstream bindings and continues at `next_stage` in the same active turn.
- Only `$flow-run` may emit `FLOW_RUN_COMPLETE`, after its full completion contract is satisfied.
- `FLOW_ADMISSION_GATE` requests only missing issue identity or a required Codex worktree resume. `FLOW_ADMISSION_BLOCKED` reports an unsafe or inconsistent admission state. `$flow-run` persists either signal and resumes admission before any stage work.

Stage-local wording such as "stop" means return control to the orchestrator when `FLOW_RUN_CONTEXT` is present. It never means present a successful child handoff as the final user response. Direct invocation semantics remain unchanged.

`flow-code` alone owns the coder lifecycle. It creates `flow_coder` lazily after Plan admission and dispatches one `TASK-*` at a time to the same session-scoped thread. Coder lifecycle events must be recorded through a flowctl mutation command when that command is available; neither `$flow-run` nor a stage may directly edit controller JSON. Wait timeouts never authorize replacement. Any replacement requires confirmed thread unavailability or a stopped scope/safety violation and a durable `CODER_THREAD_REPLACED` event.

Read and enforce [the frozen worktree review contract](review-contract.md). Review the complete filtered frozen worktree with independent exploration; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

Cursor and iBrain use separate single-use package bindings on the same artifact snapshot. iBrain is fixed to glm-5.3. In the default Cursor route, iBrain fallback requires two controller-recorded retryable Cursor process failures; an explicit human-selected iBrain route starts directly without Cursor attempts. Findings never select fallback. Exhaustion means two retryable failures per required backend: Cursor then iBrain in the default route, iBrain alone in the selected-iBrain route. Either exhausted route still requires fresh Astra consistency before defect completion and an EXTERNAL_REVIEW_GAP. Follow `review-contract.md`; no human review authorization is required, and legacy denied/pending Cursor decisions must not resurrect a gate. Production replay remains independently authorized.

The `production_replay` decision is carried by authorization ID/revision. `LOCAL_PRODUCTION_REPLAY` permits scoped production acquisition and local tests under project data policy, without a Flow sanitization/profile/manifest gate; `SKIP_PRODUCTION_REPLAY` is an active skip decision. Historical `SANITIZED_LOCAL_REPLAY` identities may be reused without asserting that data was sanitized or weakening a narrower human instruction. Amend changed authority; never derive consent from wording.
