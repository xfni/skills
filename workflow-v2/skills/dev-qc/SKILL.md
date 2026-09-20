---
name: dev-qc
description: Use when Root supplies a QCRequest for coordinated independent checks in an admitted Flow run.
---

# Dev QC

Coordinate quality checks; do not perform or impersonate an independent review.
Read `../../qc-contract.md`, `../../review-contract.md`,
`../../orchestration-contract.md`, and `../../flow-contract.md` completely.

Accept work only with a `QCRequest` bound to the current issue, canonical
worktree/run, frozen object, authorized boundary, and raw evidence references.
The three hard boundaries are:

- coordination is not independent assurance;
- every real reviewer independently examines the current frozen evidence;
- the reconstructible QC Ledger never becomes controller state.

Treat Sol/Astra as one GPT lane and Cursor/iBrain as one external lane. Preserve
all original findings, receipts, evidence refs, and recurrence keys. Do not
count the coordinator's Luna opinion, Root self-review, tests, or a summary as a
review receipt.

For the GPT lane, dispatch at most one clean-room Specialist at a time using
`fork_turns="none"` or a host-equivalent no-history mechanism. The Specialist
uses `independent-review`, is read-only, and cannot delegate. For the external
lane, use only existing controller-bound Cursor/iBrain commands. Never run a
standalone adapter to bypass a binding, route constraint, or recorded result.

Return a `QCCheckpoint` containing checked-object and real receipt/evidence
references, open questions, bounded repair or route-back proposals, missing
assurance, a Root-applied ledger delta, and one suggested next action. A
`handoff_candidate` is only advice for Root to reread facts; it is not approval
or handoff.

Do not edit the worktree, artifacts, reports, or controller. Do not command the
coder, accept a handoff, create approval, reset findings, or invent PASS. Root
owns repair dispatch, snapshot, and handoff. If QC is unavailable, fallback to
Root coordination under the same rules and must not fabricate assurance.

New risks need an evidence-backed relationship to the current approved outcome.
Otherwise label them non-blocking or **Scope Delta**; do not introduce optional
configuration, generalized infrastructure, or platform work for hypothetical
future needs.
