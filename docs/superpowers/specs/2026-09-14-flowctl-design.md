# Flowctl Deterministic Orchestration Design

## Goal and boundary

Move Flow v2's mechanical progression rules out of the root Agent prompt and into a local deterministic controller. Agents continue to analyze requirements, write artifacts, implement code, and judge content. They cannot directly assert digests, review counts, failure classes, checkpoint validity, or stage completion.

`flowctl` owns artifact parsing and canonical SHA-256, approval/upstream binding checks, structured controller and append-only events, arbitrary-entry checkpoint discovery, handoff schema and transition validation, review attempt binding, retry counts, and process-fact failure classification. It does not decide whether product intent is correct, whether a review finding is substantively valid, or whether a human understood an approval.

## Commands

- `init`: create a controller bound to an issue, repository, worktree, and branch.
- `status`: return controller state and the deterministic pending action.
- `artifact verify|register`: verify one three-region artifact; registration derives facts and invalidates stale reviews/downstream nodes.
- `resume`: scan standard locations or an explicit input map, validate dependency chains, and return the deepest valid checkpoint plus next stage.
- `review begin|submit|cursor`: bind attempts, validate reports, execute Cursor when requested, and count actual attempts.
- `handoff accept`: validate a JSON handoff and all transition rules before updating state.

`advance` is omitted because it duplicates `handoff accept`.

## Artifacts and state

The parser enforces BODY, INTEGRITY, and APPROVAL marker order; UTF-8 without BOM; LF line endings; exactly one final LF in BODY; one positive `content_revision`; and `content_digest` equality with bytes strictly inside BODY. Approval is valid only when its revision and digest match the current body. Registration compares state and artifact revisions, verifies issue/type/milestone and upstream references, and is idempotent only for the same path/revision/digest. The controller never accepts a caller-supplied digest as fact.

The defaults are `.ai/issue/<issue>/flow-state.json` and `flow-events.jsonl`. Mutations use a controller lock, expected-state-revision compare-and-swap, temporary-file write, fsync, and atomic replace. Each successful mutation increments `state_revision` and appends a structured event.

## Arbitrary entry

`resume` accepts no artifacts, a standard directory, or a JSON map keyed by `requirement`, `intent`, `roadmap`, `spec:<milestone>`, `plan:<milestone>`, `code:<milestone>`, and `integration:<milestone>`. Validation walks Requirement → Intent → Roadmap → Spec → Plan → Code → Integration for each milestone. Equal valid candidates with the same revision and different digests produce `AMBIGUOUS_CHECKPOINT`. An unbound middle artifact remains source evidence and cannot waive missing upstream semantics.

## Reviews and handoffs

`review begin` creates an attempt ID bound to current inputs. `review submit` validates a report and records GPT assurance as `CALLER_ATTESTED`. `review cursor` records `CONTROLLER_EXECUTED`, exit code, timeout, output digests, sanitized evidence, and deterministic classification. Retry counts come from recorded attempts. Recognized process failures include missing SDK/credentials, connection/DNS/TLS, timeout, malformed or empty reports, and explicit process failures; valid findings are `REVIEW_RESULT`; ambiguous output is `UNCLASSIFIED`.

The handoff JSON schema validates shape. Semantic validation confirms current stage, issue/run, transition, current artifact bytes, upstream bindings, approval, GPT-before-Cursor order, review binding, retry/degradation rules, and code snapshot where applicable. Only an accepted handoff changes `current_stage` or `pending_action`.

## Skill integration and verification

Every Flow stage runs `flowctl status` at entry, registers its output, records reviews through the controller, and submits a handoff. `$flow-run` uses `resume` instead of selecting checkpoints itself. Tests cover canonical bytes, tampering, stale approval, revision monotonicity, compare-and-swap, invalidation, arbitrary-node resume, ambiguity, handoff rejection, review binding/order/retries, failure classification, and end-to-end progression.
