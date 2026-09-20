# Dev QC Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a run-scoped `dev_qc` coordinator that delegates clean-room independent reviews while preserving the existing two-lane review receipts, Root ownership, and controller boundaries.

**Architecture:** A concise `dev-qc` skill and `dev_qc` Luna/high Agent implement coordination only. Existing `independent-review` workers and Cursor/iBrain runners remain the evidence producers; Root remains the only repair dispatcher, snapshot owner, and handoff actor. A reconstructible ledger lives under the already excluded controller `reviews/` subtree and never becomes controller state.

**Tech Stack:** Markdown Agent/Skill contracts, TOML custom Agent configuration, YAML Codex skill metadata, Python `unittest`, existing `workflow-v2.flowctl_lib.review_workspace` snapshot functions.

**Spec:** `docs/superpowers/specs/2026-09-20-issues-6-dev-qc-agent-spec.md`

## Global Constraints

- QC coordination never counts as an independent GPT or external receipt.
- Specialist reviewers use `fork_turns="none"` or an equivalent clean-room mechanism, are read-only, and may not delegate.
- Sol/Astra are one GPT lane; Cursor/iBrain are one external lane.
- Root alone dispatches repairs, freezes artifacts/snapshots, writes the QC ledger, and accepts handoffs.
- The ledger path is `<controller-dir>/reviews/qc-ledger.yaml`; it is reconstructible and not controller state.
- No Requirement/Intent/Roadmap/Integration review gate is added in this delivery.
- No controller review state machine, runner, review-package, or production-data policy change is allowed.
- Repository commit is deferred until the human explicitly requests the final commit under the repository commit convention.

## Review Focus

- A coordinator report is accidentally counted as GPT assurance: tests must require real lane language and explicitly reject Luna self-review as a receipt.
- A Specialist inherits the long-lived QC conversation: tests must require `fork_turns="none"`/clean-room wording in both Agent and skill contracts.
- Ledger maintenance invalidates frozen reviews: snapshot tests must cover create/update/delete under `reviews/` and a normal source mutation control.
- QC loss resets receipts or findings: contracts must preserve controller facts and make QC recovery non-blocking.
- A new risk expands the coder task into speculative configuration/platform work: contracts must require current AC/safety evidence or classify it as non-blocking/Scope Delta.

---

### Task 1: Add failing QC contract tests

**Files:**
- Modify: `workflow-v2/tests/test_workflow.py`
- Modify: `workflow-v2/tests/test_worktree_review.py`

**Interfaces:**
- Consumes: existing skill loader in `WorkflowV2Tests`; `capture_review_snapshot()` and `verify_review_snapshot()` from `flowctl_lib.review_workspace`.
- Produces: failing expectations for `dev-qc`, `dev_qc`, Code/Run coordination, packaging, and ledger snapshot behavior.

- [x] **Step 1: Extend the workflow skill inventory test**

Add `dev-qc` to the public skill list and assert that its `SKILL.md` and `agents/openai.yaml` exist with explicit-only invocation. Assert `.codex-plugin/plugin.json` exposes `$dev-qc`.

- [x] **Step 2: Add the QC role contract test**

Assert the future files contain these observable invariants:

```python
qc = self.skill("dev-qc")
agent = (ROOT / "skills/dev-qc/agents/dev-qc.toml").read_text()
self.assertIn('model = "gpt-5.6-luna"', agent)
self.assertIn('model_reasoning_effort = "high"', agent)
self.assertIn('fork_turns="none"', qc)
self.assertIn("coordination is not independent assurance", qc)
self.assertIn("one GPT lane", qc)
self.assertIn("one external lane", qc)
```

Also assert the Agent forbids worktree/controller edits, handoff acceptance, recursive delegation, and Luna self-review receipts.

- [x] **Step 3: Add Code/Run ownership expectations**

Assert `dev-code`, `dev-run`, and `orchestration-contract.md` say that QC is lazy/run-scoped, Root owns repairs/snapshot/handoff, QC returns a checkpoint, clean-room Specialist reports provide receipts, and QC failure falls back to Root coordination without fabricating assurance.

- [x] **Step 4: Add ledger snapshot behavior test**

In `test_worktree_review.py`, create a temporary repository/controller, capture a snapshot, then create/update/delete `<controller-dir>/reviews/qc-ledger.yaml`; each verification must preserve the digest. Mutate a normal source file and assert `FlowctlError.code == "REVIEW_WORKTREE_MUTATED"`.

- [x] **Step 5: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  workflow-v2.tests.test_workflow.WorkflowV2Tests.test_dev_qc_contract \
  workflow-v2.tests.test_worktree_review.WorktreeReviewTests.test_qc_ledger_is_bookkeeping_but_source_mutation_is_detected -v
```

Expected: FAIL because `dev-qc` files and orchestration wording do not exist; the snapshot behavior test may already pass because it verifies an existing mechanical invariant, which must be recorded as a characterization test rather than misreported as RED.

### Task 2: Add the minimal dev-qc Skill and Agent

**Files:**
- Create: `workflow-v2/skills/dev-qc/SKILL.md`
- Create: `workflow-v2/skills/dev-qc/agents/openai.yaml`
- Create: `workflow-v2/skills/dev-qc/agents/dev-qc.toml`
- Create: `workflow-v2/qc-contract.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `workflow-v2/tests/test_workflow.py` only if a test assertion needs a naming correction, never to weaken an invariant.

**Interfaces:**
- Consumes: `review-contract.md`, `orchestration-contract.md`, `independent-review`, current flowctl review commands.
- Produces: `QCRequest`, `QCCheckpoint`, ledger-delta, and Specialist delegation rules for Task 3.

- [x] **Step 1: Write the shared QC contract**

Create `qc-contract.md` containing the three hard boundaries, role table, exact QCRequest/QCCheckpoint fields, ledger path/schema, finding ownership, two-lane counting, recovery, Scope Delta, and evidence-level rules from Spec §§2–12. Keep it authoritative for coordination semantics but explicitly non-authoritative for Flow progression.

- [x] **Step 2: Write the concise dev-qc skill**

Keep `SKILL.md` focused: trigger only when Root supplies a QCRequest; read `qc-contract.md` and `review-contract.md`; coordinate at most one clean-room Specialist; invoke existing external runners through flowctl; return QCCheckpoint; never edit reviewed artifacts/controller or accept handoff.

- [x] **Step 3: Add explicit-only metadata**

Create `agents/openai.yaml`:

```yaml
interface:
  display_name: "Dev QC"
  short_description: "Coordinate independent checks for one Flow run"
  default_prompt: "Use $dev-qc with this QCRequest to coordinate the required independent checks."
policy:
  allow_implicit_invocation: false
```

- [x] **Step 4: Add the Luna/high coordinator Agent**

Create `dev-qc.toml` with the exact model configuration and instructions from Spec §3. State that the coordinator may spawn one Specialist with no inherited history, while the Specialist itself may not delegate.

- [x] **Step 5: Expose the skill in the plugin manifest**

Add one default prompt for `$dev-qc` without changing existing stage names or controller IDs.

- [x] **Step 6: Run focused GREEN tests**

Run the Task 1 workflow QC contract test and confirm it passes. Run `python <skill-creator>/scripts/quick_validate.py workflow-v2/skills/dev-qc` and fix only reported skill-format issues.

### Task 3: Route Code review coordination through dev_qc

**Files:**
- Modify: `workflow-v2/skills/dev-code/SKILL.md`
- Modify: `workflow-v2/skills/dev-run/SKILL.md`
- Modify: `workflow-v2/orchestration-contract.md`
- Modify: `workflow-v2/review-contract.md`
- Modify: `workflow-v2/tests/test_workflow.py`

**Interfaces:**
- Consumes: Task 2 `QCRequest`/`QCCheckpoint`; existing coder lifecycle and review receipts.
- Produces: a run-scoped lazy QC lifecycle and Code review repair loop without controller schema changes.

- [x] **Step 1: Update orchestration ownership**

Add `dev_qc` lifecycle next to the existing coder lifecycle: lazy creation at the first actual quality checkpoint, binding to run/worktree, reuse across stages, timeout is not replacement evidence, confirmed loss permits reconstruction from receipts and ledger, Flow end closes it. State that these are runtime coordination rules, not progression gates.

- [x] **Step 2: Update dev-run**

Require Root to reuse/create the bound QC before a stage requests coordinated checking, pass a fresh stage QCRequest, process its checkpoint, and keep human-facing progress reporting at Root. Do not create QC when no quality checkpoint occurs.

- [x] **Step 3: Replace dev-code root-owned review prose with QC coordination**

Preserve all existing review guarantees and runner commands. Change only the organizer: Root freezes and submits a QCRequest; QC dispatches GPT Specialist and existing external runner, returns repair proposals; Root validates and sends accepted Code fixes to the same coder; QC arranges original/takeover re-review; Root performs approval and handoff.

- [x] **Step 4: Clarify coordinator versus reviewer in review-contract**

Add a short boundary: coordinator may delegate but produces no independent assurance; `independent-review` applies to the Specialist, which cannot delegate and starts from frozen evidence without inherited coordinator history.

- [x] **Step 5: Run focused orchestration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest workflow-v2.tests.test_workflow -v
```

Expected: all workflow contract tests pass.

### Task 4: Package, document, and verify the complete delivery

**Files:**
- Modify: `workflow-v2/README.md`
- Modify: `.codex-plugin/plugin.json` if not completed in Task 2
- Modify: `workflow-v2/tests/test_workflow.py`
- Modify: `workflow-v2/tests/test_worktree_review.py`
- Verify: all Issue 6 design/spec/plan files.

**Interfaces:**
- Consumes: completed QC Skill/Agent and Code orchestration contract.
- Produces: install instructions and complete regression evidence.

- [x] **Step 1: Update installation documentation**

Change nine installed dev skill directories to ten, list `dev-qc`, and instruct copying `skills/dev-qc/agents/dev-qc.toml` to `~/.codex/agents/dev-qc.toml`. Explain lazy/run-scoped lifecycle and that deployment does not create a QC thread at Codex startup.

- [x] **Step 2: Record offline scenario walkthrough coverage**

In the workflow contract test or a concise test fixture, enumerate and assert the expected next action for: normal dual lane, GPT finding repair, reviewer takeover, explicit iBrain route, permitted single lane, zero assurance, snapshot drift, QC recovery, ledger loss, and unsupported platformization. Label this as contract scenario coverage, not real-model compliance evidence.

- [x] **Step 3: Run skill validation**

Run:

```bash
python /Users/nixiaofeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py workflow-v2/skills/dev-qc
```

Expected: validation succeeds with no unfinished scaffold placeholders.

- [x] **Step 4: Run focused snapshot and workflow suites**

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  workflow-v2.tests.test_worktree_review \
  workflow-v2.tests.test_workflow -v
```

Expected: all tests pass; one or more pre-existing environment-dependent skips remain explicitly reported.

- [x] **Step 5: Run the full suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
```

Expected: all tests pass, with only documented environment-dependent skips.

- [x] **Step 6: Verify scope and documents**

Run `git diff --check`, inspect `git status --short`, and confirm no controller state machine, runner, review package, production-data policy, global Codex config, or unrelated file changed. Do not commit or deploy until the human explicitly requests it.
