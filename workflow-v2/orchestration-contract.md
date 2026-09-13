# Flow Run Orchestration Contract

Read and enforce `flow-contract.md` first. Admission is a Flow-owned prerequisite, not an assumed `AGENTS.md` behavior.

This protocol applies only when a stage receives a verified `FLOW_RUN_CONTEXT` containing:

```text
caller: flow-run
run_id; issue_id; controller_path
stage; input paths/revisions/digests or snapshot binding
```

Without that envelope, use **Direct invocation** behavior and keep the stage's normal stop-and-suggest-next response. With it, use **Orchestrated invocation** behavior: preserve every stage rule and gate, but return exactly one signal to `$flow-run` instead of ending with a manual next-skill instruction.

```text
FLOW_RUN_HANDOFF
stage; status; output paths; revisions; digests; snapshot; next_stage; open_gaps

FLOW_RUN_HUMAN_GATE
stage; gate; displayed_binding; controller_path; resume_condition

FLOW_RUN_BLOCKED
stage; status; cause; evidence; owner; controller_path; resume_condition

FLOW_RUN_ROUTE_BACK
stage; status: FAILED; cause; evidence; owner_stage; next_stage; invalidated_bindings

FLOW_ADMISSION_GATE
stage; missing_human_input; controller_path; resume_condition

FLOW_ADMISSION_BLOCKED
stage; cause; evidence; controller_path; resume_condition
```

- `FLOW_RUN_HANDOFF` is non-terminal. `$flow-run` validates it and continues to `next_stage` in the same active turn. The stage must not suggest or ask the human to invoke that next skill.
- `FLOW_RUN_HUMAN_GATE` is the only normal pause for human input. Persist the exact binding before asking. After the human responds, `$flow-run` resumes the owning stage under the same context; a successful confirmation returns `FLOW_RUN_HANDOFF`.
- `FLOW_RUN_BLOCKED` pauses only for a real blocked condition and preserves the owning-stage routing.
- `FLOW_RUN_ROUTE_BACK` is non-terminal. It carries an evidenced `FAILED` result to its owning stage; `$flow-run` invalidates affected downstream bindings and continues at `next_stage` in the same active turn.
- Only `$flow-run` may emit `FLOW_RUN_COMPLETE`, after its full completion contract is satisfied.
- `FLOW_ADMISSION_GATE` requests only missing issue identity or a required Codex worktree resume. `FLOW_ADMISSION_BLOCKED` reports an unsafe or inconsistent admission state. `$flow-run` persists either signal and resumes admission before any stage work.

Stage-local wording such as "stop" means return control to the orchestrator when `FLOW_RUN_CONTEXT` is present. It never means present a successful child handoff as the final user response. Direct invocation semantics remain unchanged.
