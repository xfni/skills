# Flowctl Deterministic Control Contract

`flowctl` is the sole writer of `flow-state.json` and `flow-events.jsonl`, and the sole authority for mechanical Flow progression. Agents and skills must not edit the controller or event log, calculate or trust their own digest as workflow fact, count their own review attempts, classify process failures, choose a resume checkpoint, or declare a handoff accepted.

Resolve the executable in this order: an explicitly supplied `FLOWCTL` path, this package's `flowctl.py`, then `~/.codex/flow-v2/flowctl.py`. Failure to locate or execute it is `FLOW_CONTROLLER_UNAVAILABLE`; do not fall back to prompt-owned state.

Every command emits one structured JSON object. Read its returned `state_revision` before mutation and pass it back as `--expected-revision`; `STATE_CONFLICT` requires reloading with `flowctl status`, never overwriting state. Mutations are serialized by a file lock, journaled for crash recovery, atomically replace controller JSON, and append a SHA-256-linked event; status audits the state revision against that event chain. The controller does not trust caller-supplied digests, approvals, retry counts, failure classes, checkpoint depth, or successful-transition claims.

## Required command boundary

- At entry, run `flowctl status --state <controller>`. This revalidates issue, repository worktree, and branch.
- At initial or interrupted orchestration, run `flowctl resume --issue <issue> --repo <worktree> --state <controller> --expected-revision <n>`; provide `--inputs <json>` for explicit arbitrary-node documents. Use only its verified checkpoint and `pending_action`.
- After writing an artifact, run `flowctl artifact register --state <controller> --path <path> --type <kind> [--milestone <id>] --expected-revision <n>`. The controller recomputes canonical bytes, approval, upstream binding, revision monotonicity, and invalidation.
- For GPT review, run `flowctl review begin ... --backend gpt`, dispatch the bound review, then `flowctl review submit`. GPT judgment is caller-attested, but binding, schema, evidence fields, cycle count, and artifact freshness are controller-checked.
- For Cursor, create a review prompt that explicitly contains the controller-returned artifact path and digest, then run `flowctl review cursor`; the controller validates that prompt binding, creates the attempt, and executes the configured runner. The runner encloses its terminal JSON between `FLOW_REVIEW_REPORT_BEGIN` and `FLOW_REVIEW_REPORT_END`; progress may appear outside the frame, and `reviewed_digest` must echo the binding. Process failures use a separate JSON envelope between `FLOW_REVIEW_ERROR_BEGIN` and `FLOW_REVIEW_ERROR_END`. Do not invoke Cursor separately and later claim it as a controlled review.
- Submit only the handoff JSON defined by `schemas/handoff.schema.json` to `flowctl handoff accept`. The schema validates context-independent shape and globally known values; the controller validates the context-dependent transition from current state. Only acceptance changes stages. A rejected handoff returns to the owning stage without advancing.
- `flow-code` records its one session-scoped coder through `flowctl coder update`; this is the only supported writer for coder lifecycle and replacement generation.
- Before Code review and handoff, run `flowctl snapshot capture`; Code-to-Integration handoff is rejected if the current worktree no longer matches that controller-recorded snapshot.
- Record `FLOW_RUN_HUMAN_GATE`, `FLOW_RUN_BLOCKED`, and `FLOW_RUN_ROUTE_BACK` through `flowctl signal record` using `schemas/signal.schema.json`. Route-back invalidation and pause state are controller mutations, never prose-only Agent claims.
- `FLOW_RUN_HUMAN_GATE` and `FLOW_RUN_BLOCKED` pause all progression mechanically. After the named condition is actually satisfied, record `FLOW_RUN_RESUMED` with the same issue, run, and stage binding, then call `flowctl resume`; never clear a pause by editing state or merely asserting that it is resolved.

Spec, Plan, and Code require a passed GPT review followed by a passed controller-executed Cursor review. Only a controller timeout or a framed, allow-listed runner error is `RUN_ERROR`; unframed text never establishes a degradable infrastructure failure. A Cursor runtime error permits one controller-counted retry. Two runtime errors may produce a durable `CURSOR_REVIEW_GAP` and defect completion. Malformed, missing, unbound, inconsistent, or empty-incomplete reports are `UNCLASSIFIED`; two `UNCLASSIFIED` attempts for the same backend and artifact digest exhaust a separate protocol-failure budget and end `BLOCKED_REVIEW`. This state is not degradable. Review findings are not runtime errors and cannot be degraded. Review cycles are capped by controller state, not model memory.

Human product judgment and reviewer content judgment remain semantic inputs. `flowctl` controls whether those inputs are fresh, correctly shaped, correctly bound, ordered, and sufficient to advance; it does not pretend to replace them.

## Host enforcement boundary

This repository cannot force the host Agent to invoke flowctl. If the host omits a required command, the controller cannot advance and later `status` or `resume` exposes detectable non-progression; no prompt or repository script can make tool invocation mandatory inside the host runtime. Flow therefore converts many silent false-progression claims into auditable state mismatches, but host-level mandatory tool routing requires support from the Codex runtime itself.
