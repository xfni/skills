# Flowctl: facts and accounting for Agent-led Flow

## Cooperation boundary

Agent owns starting-stage selection, authorized next actions, semantic impact, evidence sufficiency, coverage and uncertainty diagnosis. Controller owns actual identities/digests, original receipts, finite process budgets and atomic acceptance/accounting. It does not prove business correctness or coordinate every possible exception.

Only flowctl writes flow-state.json and flow-events.jsonl. Never invent a PASS, edit receipt assurance, reset counters or call a standalone external runner to escape accounting. GPT submissions and semantic dispositions are CALLER_ATTESTED; controller-launched external attempts retain CONTROLLER_EXECUTED on their original reviewed object only.

pending_action is a recommendation, not an exhaustive permission list. Choose safe authorized actions from current facts. A controller/bridge error leaves the affected action unresolved, not automatically business BLOCKED, human-gated or back at Requirement. Continue safe read-only diagnosis/preparation; do not repeat an audited external operation when persistence is uncertain. Unknown/FAILED/unexecuted is never PASS. Existing human/host pauses, explicit revocations, production-data permissions and remote-Git boundaries remain binding.

Use four status values and three nullable results from orchestration-contract.md. Tool repair, coder/reviewer waits and bounded retry are 进行中 unless an actual substantive or safety obstacle prevents continuation. No new lifecycle enums.

## Commands and position

Resolve the executable from explicit FLOWCTL, this package's flowctl.py, then ~/.codex/flow-v2/flowctl.py. Commands return JSON. Reload actual state_revision before mutations and pass --expected-revision; on STATE_CONFLICT reload, do not overwrite or blindly repeat execution. Existing file locks, transaction recovery, atomic replacement and linked events remain.

At entry use status. New controllers may use init --stage flow-code --milestone MILESTONE-1 (default flow-requirement). This records an Agent-chosen entry, not fictitious Spec/Plan approval or execution. Existing init is idempotent and cannot relocate or clear a pause. Apply flow-contract.md worktree/issue admission first.

resume restores the recorded execution position and actual accepted handoffs, not the deepest directory candidate. Registered readable paths take precedence over unrelated historical files. First admission, explicit --inputs or missing-path repair may discover documents; Agent selects an initial stage and discloses missing history. Never reconstruct unrelated earlier stages merely to repair metadata.

This change preserves recorded position and receipts; it is not a universal reconstruction of already-corrupted legacy stage fields from event history. If recorded position conflicts with a known accepted handoff, Agent investigates that specific inconsistency instead of claiming recovery or guessing a deeper stage from directory contents.

artifact register records a readable issue/type/milestone-bound object and actual bytes. It preserves current stage, downstream artifacts/snapshots/receipts/gaps/coder state and original upstream tuples. Byte changes are facts, not automatic semantic revocation. Completion stays complete when supplemental material is registered. Material new work/scope/implementation uses explicit FLOW_RUN_ROUTE_BACK to its owner; preserve withdrawn evidence and original receipts.

Spec/Plan/Code register DRAFT before review. DRAFT is not approval. After required guarantees are satisfied, update the APPROVAL envelope and register again; unchanged BODY retains identity. Actual handoff acceptance alone advances stages, irrespective of pending-action wording. Strict artifact verify/audit is optional diagnosis, never a normal prerequisite.

## Original guarantees and optional disposition

For a clarification/auxiliary change, Agent may judge approved scope and reviewed implementation unchanged. Use one optional --disposition <json> on artifact register, resume, snapshot capture or handoff accept. Ordinary unchanged flows need no new paperwork.

Example material:

```json
{
  "reason": "Clarification only; approved scope and reviewed implementation unchanged",
  "evidence": ["/absolute/readable/change-analysis.md"],
  "source_attempts": ["original-real-passed-attempt-id"]
}
```

For stale-route closure also reference route_event (the original route signal revision). Controller derives current target/digest/actual Code snapshot and original guarantee binding; Agent must not calculate tuples. Record material/evidence identities and CALLER_ATTESTED provenance, reuse for the same change across commands. Another change, revocation or unresolved contradictory result ends applicability. Original PASS/source/digest/snapshot never changes.

Historical real PASS plus supported disposition may satisfy its role, including an unchanged original consistency guarantee. It cannot supply a missing receipt, revive an explicitly revoked guarantee, turn FAILED/unknown into PASS, waive a known unresolved blocker, authorize material scope/implementation change or clear human/host pauses. Final report distinguishes original independent guarantee from Agent applicability judgment; it must not claim that the last entire worktree was externally reviewed.

Code uses existing whole-worktree snapshots. snapshot capture preserves old snapshot evidence when recording a new one. Execution freezes/filtering remain strict under review-contract.md. Integration auxiliary drivers/fixtures preserve the accepted position and original Code handoff; Agent inspects and records applicability, or routes back on material implementation impact.

## Review lanes and evidence

Use review begin --backend gpt, dispatch the selected GPT, then submit its exact returned attempt/report. Backend identifies role, not model. Final review uses review begin --backend consistency --model gpt-6-astra --effort medium, then submit to that fresh attempt; do not relabel primary GPT results.

Default GPT -> Cursor -> Astra consistency; after two or more controller-recorded retryable Cursor failures, iBrain glm-5.3 replaces Cursor, with its own single retry. Explicit human iBrain selection uses review select-external --backend ibrain --reason <instruction>: GPT -> iBrain -> consistency, no Cursor attempts. Each lane rechecks its substantive findings. Material fixes reopen required guarantees; clarification uses disposition rather than automatic PASS carry-over. Findings are not fallback reasons.

Execute external review through review cursor/ibrain --binding-id or --manifest. Fresh single-use packages contain the complete filtered frozen worktree, not just a root summary. Apply declared file/directory data exclusions, retain omitted-coverage limits, return stdout/API only. iBrain is organization-trusted; no separate reviewer authorization gate. Actual stricter host refusal remains binding.

Current artifact/role terminal budgets exclude old objects and explicitly withdrawn guarantees; Code includes frozen snapshot identity. Three current cycles or two conflicting UNCLASSIFIED attempts return repair recommendations, never invented PASS or automatic global business pause. RUN_ERROR/PROTOCOL_ERROR retries remain bounded; source drift/conflicting reports and substantive failures cannot degrade. Observed process facts support fallback, not vendor-wording guesses. The existing audited repair-classification command preserves old evidence and never creates PASS.

Runtime-exhausted external review still needs actual passed final consistency and a durable EXTERNAL_REVIEW_GAP for conditional completion. Carry all gaps; denied transmission and findings cannot use this policy.

## Tests, signals and Goal context

Integration completion needs a clear current tested object, readable raw evidence, explicit terminal result and Agent execution/coverage judgment. Machine Plan scenario-universe matching and explanatory metadata are not routine gates. Known FAILED/BLOCKED/unexecuted observations cannot aggregate PASS or disappear through a partial replacement; a new actual result references the same object and replaced prior observation, preserving other unresolved failures.

For successful Integration handoff, integration_results.test_object identifies the tested service/build (an existing upstream Code digest also supplies identity), and integration_results.evidence lists readable execution evidence paths, absolute or relative to the worktree. Failed/startup signals do not require these success fields. A rerun uses replaces (the prior result artifact digest); if the tested build changed, replaces_test_object explicitly relates the previous object. An aggregate failure without failed scenario IDs also needs an Agent resolution explanation. These fields preserve facts, not machine proof of test coverage or resolution correctness.

Handoff returns original review_facts and current input-binding warnings. Changed upstream input is an Agent impact/authorization assessment, not automatic receipt revocation or a full-history gate; unchanged BODY does not imply unchanged intent. Agent must inspect disclosed differences and record disposition or explicit route-back when warranted.

BLOCKED/FAILED signals may record startup/permission/error/unexecuted evidence without full scenarios or successful requests. Route-back is an Agent action supported by evidence, not restricted to a machine-proven business failure. Actual replay skip retains scoped production_replay permission and PRODUCTION_REPLAY_GAP; missing Plan tables do not require automatic Plan re-review.

Record human/blocked/route/resumed signals with signal record and schemas/signal.schema.json. FLOW_RUN_RESUMED alone clears an actual pause; optional pause_revision binds its original signal, automatically derived when unambiguous for legacy callers. A mismatched/unknown pause stays paused. Controller records Agent-observed release evidence, not proof of natural-language truth or host permission.

goal record persists the real host Goal reference (threadId, createdAt, objective, status), retains replacement history and never advances Flow or clears pauses. A historical blocked Goal reference is not a controller gate; flow-run respects real host state and explicit human continuation. coder update remains the sole writer of the one session-scoped coder lifecycle.

This repository cannot force a host to call flowctl. Mechanical checks prevent accepted false progress, not all Agent semantic errors; mandatory host tool routing is outside this package.
