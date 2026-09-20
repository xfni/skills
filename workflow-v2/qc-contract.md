# QC coordination contract

This contract defines coordination semantics for a run-scoped `dev_qc`. It is
not Flow progression state and never replaces controller facts, review reports,
receipts, approvals, or stage handoffs.

## Hard boundaries

1. QC coordination is not independent assurance. A summary, merged finding,
   recommendation, or `handoff_candidate` produced by QC is not a receipt.
2. Every Specialist Reviewer independently inspects the current frozen object
   and raw evidence entry points in a clean room. It does not inherit QC history.
3. The QC Ledger is a reconstructible index, not a second controller.

Sol and Astra form one GPT lane. Cursor and iBrain form one external lane.
Backends in the same lane are alternatives, never additional votes. Existing
`review-contract.md` minimum-assurance, takeover, retry, and degradation rules
remain authoritative.

## Ownership

| Actor | Owns | Must not do |
|---|---|---|
| Root | freeze/bind the object, authorize scope, dispatch repairs, write Ledger deltas, approve and hand off | count its own or QC opinion as assurance |
| QC | coordinate reviewers, preserve finding provenance, propose repairs/routes, return a checkpoint | edit artifacts/controller, command the coder, approve or hand off |
| Specialist | independently inspect frozen evidence and return a read-only report | inherit QC conclusions, delegate, edit the worktree |
| External runner | execute a controller-bound Cursor/iBrain review | bypass binding or create a second lane vote |

## QCRequest

Root supplies a current request without duplicating every controller tuple:

```yaml
schema_version: 1
request_id: QC-<stable-id>
run_ref: <controller/run reference>
stage: <current Flow stage>
current_object_ref: <current frozen artifact/snapshot/binding>
authorized_boundary_ref: <approved Requirement/Intent/Spec/Plan boundary>
quality_contract_refs: [<applicable contracts>]
changed_boundary: <reviewed scope>
evidence_refs: [<raw evidence entry points>]
carryover_refs: [<unresolved source refs>]
route_constraints: [<actual host/model/backend constraints>]
```

The current object and raw evidence must be readable. A Root summary is
navigation, not sole evidence. An initial independent packet excludes other
reviewers' conclusions. A repair/takeover packet includes original findings,
the repair delta, verification evidence, and the unresolved set. Unknown or
stale references stay unknown; QC must not infer PASS.

## QCCheckpoint

QC returns facts and proposals, never approval:

```yaml
schema_version: 1
request_ref: QC-<stable-id>
checked_object_ref: <same current object or explicit newer binding>
receipt_or_evidence_refs: []
open_question_refs: []
repair_proposals:
  - owner_stage: flow-code
    affected_scope: []
    required_verification: []
route_back_proposals: []
missing_assurance: []
ledger_delta: []
suggested_next_action: repair | rereview | route_back | handoff_candidate
reason: <short explanation>
```

Every receipt and finding keeps its original ID, attempt/receipt reference,
evidence reference, and recurrence key. Display grouping cannot change status.
`handoff_candidate` only asks Root to reread controller facts and evidence.
Object drift invalidates rebinding of an old report. If raw evidence conflicts
with a QC suggestion, expose the conflict and prefer the raw fact.

Repair proposals name the owner stage, affected scope, and required checks.
Root validates scope and sends accepted Code repairs to the same coder. The
original reviewer rechecks its findings; if unavailable, a takeover reviewer
must explicitly dispose every unresolved finding. Generic PASS cannot close a
prior finding.

## Clean-room review and lanes

QC may coordinate at most one Specialist Reviewer at a time. Create it with
`fork_turns="none"` or a host-equivalent no-history mechanism and apply the
`independent-review` skill to that Specialist, not to QC. The Specialist cannot
delegate. If clean-room delegation is unavailable, Root sends the same bounded
packet to a real independent reviewer; QC self-review still does not count.

Select Sol/high or Astra/medium for one GPT lane. Select Cursor or iBrain for
one external lane using existing bound `flowctl review` operations. Do not
manufacture backend failures, maintain parallel retry counters, or invoke a
standalone adapter to bypass controller evidence.

## Ledger and recovery

The Ledger path is `<controller-dir>/reviews/qc-ledger.yaml`. Only Root writes
QC's `ledger_delta`; QC never overwrites, renames, or deletes raw reports.

```yaml
schema_version: 1
run_ref: <run>
items:
  - id: QC-<id>
    source_ref: <original finding/decision/evidence>
    last_checked_object_ref: <binding>
    carry_to: [flow-code]
    question: <bounded question>
    resolution_ref: null
```

Items without a source are invalid. `carry_to` is a suggestion, not pending
controller work. `resolution_ref` points to existing evidence and does not copy
PASS/FAILED. The Ledger stores no raw reports, production data, credentials,
conversation history, review budget, approval, or scheduler state.

Ledger loss or QC loss does not invalidate receipts or create business
BLOCKED. Reconstruct from controller facts, reports, unresolved findings, and
source references. Timeout or silence alone is not evidence that QC died. If QC
is unavailable, fallback to Root coordination under the same contract and must
not fabricate assurance.

## Scope and evidence

A new risk enters the current repair only when evidence connects it to an
approved acceptance criterion, safety boundary, feasibility failure, or an
inevitable regression/loss/security/compatibility effect of the chosen design.
Otherwise retain it as non-blocking advice or a **Scope Delta**. Future
flexibility, symmetry, and hypothetical consumers do not justify configuration
or platform work.

Close a concern with evidence at the concern's level. A branch-level unit test
does not close an end-to-end risk, and reviewer PASS does not replace real
integration evidence.

## Offline contract scenarios

These scenarios guide packet/checkpoint behavior; they are not real-model
compliance evidence:

| Scenario | Expected coordination action |
|---|---|
| normal dual lane | preserve one GPT and one external receipt, then propose handoff |
| GPT finding | propose bounded repair and re-review by the same reviewer |
| reviewer takeover | carry every unresolved original finding explicitly |
| explicit iBrain route | use iBrain directly without manufactured Cursor failures |
| permitted single lane | retain one real PASS and record the durable lane gap |
| zero assurance | do not propose handoff |
| snapshot drift | require a fresh binding; do not rebind the old report |
| QC recovery | rebuild coordination from receipts/findings without rerunning valid reviews |
| Ledger loss | reconstruct the index; do not block the business flow |
| unsupported platformization | record non-blocking advice or Scope Delta |
