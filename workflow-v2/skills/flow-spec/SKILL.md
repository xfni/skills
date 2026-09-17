---
name: flow-spec
description: Use when the user explicitly requests a behavioral specification for one confirmed roadmap milestone.
---

# Flow Spec

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Apply the standard dual / minimum single-chain policy in `../../review-contract.md`. Record real independent receipts through flowctl; no mandatory third Astra consistency review. A missing route may degrade with a factual reason, never a fabricated PASS; unresolved blockers survive route changes and artifact revisions.

Pass the controller-validated whole-view review binding to flowctl review cursor --binding-id or human-selected/fallback flowctl review ibrain --binding-id. Legacy paths are hints only; never reconstruct a target-only package.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, worktree, and authorization bindings at stage entry.
Read and follow `../../artifact-contract.md` for every artifact revision, digest, and approval operation.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Register the DRAFT candidate, record the actual independent GPT and selected external review chains, or their permitted degradation. Update approval only after minimum effective assurance and blocker resolution, then hand off through flowctl. Never edit state or self-approve; root owns acceptance in orchestrated mode.

In orchestrated mode, return the handoff payload unaccepted; the root alone calls `handoff accept` once. The command above is stage-owned only in Direct progression. Missing auxiliary metadata or historical documents never triggers human unlock.

Write the behavioral contract for one selected milestone. Define what the system must do and how it is accepted; must not include implementation tasks or silently make product decisions.

**REQUIRED SUB-SKILL:** Use independent-review with the `design` profile for the GPT review.

**REQUIRED SUB-SKILL:** Use cursor-review for the default external review route.

**REQUIRED SUB-SKILL:** Use ibrain-review with `glm-5.3` as the controller-authorized Cursor backup or explicitly human-selected external lane.

## Admission

Record an explicit human iBrain choice through `flowctl review select-external`. If the human restricts a lane (for example GPT-only), use `flowctl review degrade --lane external --basis human --reason <instruction>` with state/revision. Preserve valid receipts and all known findings; no prohibited reviewer call or failure quota is required.

Before external review, apply declared file/directory data exclusions through the manifest recipe in `../../review-contract.md`. Exclude embedded-sample files without deleting data, disclose missing coverage, repeat exclusions on retries/fallback, and continue; prohibited test-data transfer alone is not a human gate.

Register the review candidate as `DRAFT` before dispatching reviews. Follow the reviewed-stage lifecycle in `../../flowctl-contract.md`: complete the selected lanes, then update only the APPROVAL envelope on `approve:spec`, register again, and hand off. Registration alone never means approval.

Use the current issue/worktree, selected milestone and available delivery boundary. In normal orchestration, read Intent and Roadmap; at explicit arbitrary-node entry, use the supplied Spec/task boundary and disclose missing history. Controller-owned input bindings replace model-declared exact tuples. Resolve genuine product ambiguity, not missing historical metadata.

### Direct invocation review scope

Read and enforce [the frozen worktree review contract](../../review-contract.md). Review the complete filtered frozen worktree with independent exploration of source, tests and secrets exclusions; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

Intent remains authoritative for Scope, Non-goals, Invariants, and Success Signals. Roadmap defines this milestone's delivery boundary. Repository investigation establishes existing behavior and interfaces. If specification requires changing product intent, return to `$flow-intent`; if it requires changing milestone boundaries or order, return to `$flow-roadmap`.

## Specify behavior

Write observable rules with stable IDs. Cover:

```text
RULE-* behavior and rationale
actors, triggers, preconditions
inputs and outputs
state transitions and lifecycle
normal, empty, boundary, errors, and failure behavior
permissions, privacy, and data ownership
compatibility, migration, and rollback behavior
external and internal interface contracts
observability and operational constraints
AC-* acceptance criteria linked to RULE-* and intent Success Signals
```

Each rule must be testable without prescribing a class, function, framework, or file layout. Separate verified repository facts, approved product decisions, design decisions, assumptions, and unresolved technical questions. A business-level unknown blocks approval; a bounded implementation choice may remain for Plan.

Apply Necessary configuration and optional behavior in `../../flow-contract.md`. For necessary new variability, state the behavior/defaults and current rationale in the existing rules, including rollout acceptance or safety lifecycle where relevant. Do not add a toggle or legacy mode just for flexibility, or equate an ordinary business input with an operational switch. Reviewers assess current necessity, added cost and consistency with the authorized outcome; no new configuration approval or receipt is required.

## Review and approve spec.md

Apply Minimum independent guarantee and degradation in `../../review-contract.md`. Prefer GPT + external independent chains; actual unavailability or an explicit human constraint permits one effective chain with a recorded gap. Sol/high and Astra/medium may substitute on unavailability. The original reviewer normally rechecks its findings; an available independent takeover reviewer must receive and explicitly resolve them. No mandatory third consistency review.

Resolve the output path with flow_step `spec`. Record available input paths and the selected milestone, explicitly noting absent history. Review outcome-to-rule coverage against the available authorized task boundary; do not invent unavailable upstream documents or approvals.

After the Spec body is ready, prefer independent GPT + external review chains. Select Sol/high for bounded behavior or Astra/medium for complex boundaries, security or ambiguity. A chain includes necessary targeted repair reviews, not just one call; use the same reviewer normally, or an independent takeover carrying original findings if unavailable.

Apply independent-review's evidence audit and finding-weight convergence. A non-blocking finding must not trigger another review cycle; consolidate the same recurrence_key, and after three review cycles with the same unresolved blocker route to its owning stage or `BLOCKED_REVIEW` rather than continuing the reviewer loop.

Cursor owns and rechecks its substantive findings. Material scope/implementation fixes need affected guarantees renewed. Clarification-only fixes may retain the original GPT guarantee through an evidenced applicability disposition; never implicitly carry or rebind its PASS. Budget exhaustion alone returns a local repair recommendation; known unresolved substantive blockers still prevent handoff.

Use observable runtime/protocol failures for bounded retry or allowed fallback. Retry at most once where useful; no required failure quota. Prefer iBrain when Cursor is genuinely unavailable, with fresh bindings and data exclusions. UNCLASSIFIED or conflicting reports remain invalid evidence, not a substantive approval; preserve known findings and let an allowed independent reviewer verify them. Never disguise substantive FAILED or bypass host refusal. Audited repair-classification preserves history and never creates PASS.

Finish review when current affected assurance is valid and all known blockers are independently resolved. Dual assurance is 通过; permitted single-chain assurance is 有条件通过 / COMPLETE_WITH_DEFECT with a durable gap. Missing or conflicting reports are not PASS. Resolve drift with a fresh snapshot/binding and retain findings; actual host restrictions remain authoritative. Do not force an additional Astra consistency round or exhaust unavailable channels.

The controller binds the actual Spec and reviewer attempt and saves the terminal receipt. Reports need an explicit conclusion and problem summaries when failed; auxiliary fields and duplicate upstream tuples are not gates. Current target/source mutation invalidates review, but missing historical metadata or format differences return to the owning Agent without a human BLOCKED gate.

After reviews pass, verify the Spec remains inside the available human-authorized task boundary. Under `FLOW_RUN_CONTEXT`, use `ORCHESTRATED` and controller-owned current binding, propagate gaps and continue without human approval. Direct mode retains its explicit approval gate. Absent historical Requirement metadata is not itself a blocker.

Direct approval summarizes observable behavior, acceptance examples, exclusions and material review gaps, links the complete specification, and asks whether to confirm or correct that behavior. An unresolved business choice describes the conflicting outcomes and their consequences. A review/tool limit returns first to the Agent for diagnosis; if human help is genuinely necessary, explain the unresolved substantive issue or required tool-maintainer repair, not “BLOCKED_REVIEW/请重置次数”. Automatic review repair/fallback is progress commentary, never a new authorization question.

Report current Spec, available inputs, milestone and controller-recorded review receipts/gaps. Under `FLOW_RUN_CONTEXT`, return the unaccepted `FLOW_RUN_HANDOFF` with `next_stage: flow-plan`; otherwise stop and suggest `$flow-plan`. Do not create a Plan or implementation here.
