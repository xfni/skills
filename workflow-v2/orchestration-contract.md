# Flow Run Orchestration Contract

The handoff JSON schema validates context-independent structure and globally known stage names. `flowctl handoff accept` separately validates the context-dependent transition against controller state, milestone readiness, and the fixed transition graph. Passing schema validation never promises that a requested transition is currently legal; callers may use `next_stage: auto` to leave that decision entirely to the controller.

Read and enforce `flow-contract.md` first. Admission is a Flow-owned prerequisite, not an assumed `AGENTS.md` behavior.

Read `flowctl-contract.md` first. This protocol applies only when a stage receives a controller-verified `FLOW_RUN_CONTEXT` containing:

```text
caller: flow-run
run_id; issue_id; controller_path
stage; input paths/revisions/digests or snapshot binding
optional coder_agent: coder_thread_id; coder_model; coder_effort; active_task; completed_tasks; last_checkpoint; replacement_generation; replacement_reason; prior_coder_thread_id
optional authorization_bindings: external_review authorization_id/revision; production_replay authorization_id/revision; controller-validated operation manifest binding
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

The stage writes this payload to a temporary JSON file and calls `flowctl handoff accept`. Paths, revisions, digests, review counts, and open gaps come from controller state and are deliberately absent from caller-controlled handoff JSON.

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
- `FLOW_RUN_HUMAN_GATE` is the only normal pause for human input. Persist the exact binding before asking. After the human responds, record a bound `FLOW_RUN_RESUMED`, call `flowctl resume`, and continue the controller-returned owning stage; a successful confirmation returns `FLOW_RUN_HANDOFF`.
- `FLOW_RUN_BLOCKED` pauses only for a real blocked condition and preserves the owning-stage routing. Once its recorded resume condition is actually satisfied, record `FLOW_RUN_RESUMED` before calling `flowctl resume`.
- `FLOW_RUN_RESUMED` is the only signal that clears a recorded HUMAN_GATE or BLOCKED pause. It must bind the same issue, run, and current stage and provide evidence that the recorded resume condition was satisfied.
- `FLOW_RUN_ROUTE_BACK` is non-terminal. It carries an evidenced `FAILED` result to its owning stage; `$flow-run` invalidates affected downstream bindings and continues at `next_stage` in the same active turn.
- Only `$flow-run` may emit `FLOW_RUN_COMPLETE`, after its full completion contract is satisfied.
- `FLOW_ADMISSION_GATE` requests only missing issue identity or a required Codex worktree resume. `FLOW_ADMISSION_BLOCKED` reports an unsafe or inconsistent admission state. `$flow-run` persists either signal and resumes admission before any stage work.

Stage-local wording such as "stop" means return control to the orchestrator when `FLOW_RUN_CONTEXT` is present. It never means present a successful child handoff as the final user response. Direct invocation semantics remain unchanged.

`flow-code` alone owns the coder lifecycle. It creates `flow_coder` lazily after Plan admission and dispatches one `TASK-*` at a time to the same session-scoped thread. Coder lifecycle events must be recorded through a flowctl mutation command when that command is available; neither `$flow-run` nor a stage may directly edit controller JSON. Wait timeouts never authorize replacement. Any replacement requires confirmed thread unavailability or a stopped scope/safety violation and a durable `CODER_THREAD_REPLACED` event.

The controller's active `external_review` authorization is referenced only by its `authorization_id`, revision, and a controller-validated operation manifest. A stage and its external reviewer must not ask the human again while that binding remains inside the admitted issue, run, worktree, stage, backend, file, and exclusion boundary. Drift or scope expansion fails closed and routes any intended decision change through `flowctl authorization amend`; prose, prompt text, and stage-local magic phrases cannot broaden it.

Cursor and the iBrain runtime fallback use separate operation manifests. For an iBrain fallback, reuse the same active `authorization_id` and revision and the same artifact snapshot, but create a `backend=ibrain` new controller-validated, single-use operation manifest/binding; it must not reuse the Cursor binding. iBrain remains fixed to `glm-5.3` and may activate only after flowctl records two Cursor runtime failures on the current digest; Cursor findings never activate the backup. A retry or fallback must not ask the human again. If external review is denied, Flow pauses once before the first mandatory review and exposes one amendment action; later stages do not repeat the gate.

The `production_replay` authorization is likewise carried by authorization ID/revision plus a controller-validated operation manifest. `SANITIZED_LOCAL_REPLAY` permits only the bounded sanitized local replay policy; `SKIP_PRODUCTION_REPLAY` remains an active decision rather than an absent authorization. Any change uses the same amendment path and never derives consent from wording.
