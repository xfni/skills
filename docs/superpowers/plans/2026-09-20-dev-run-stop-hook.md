# dev-run Bounded Stop Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-open, bounded Codex Stop Hook that resumes an admitted `$dev-run` turn only while the controller exposes a known actionable state.

**Architecture:** A new pure observation module reads controller bytes without recovery or locks and returns a stable continuation decision/fingerprint. A user-level helper owns turn markers and per-session/per-controller runtime sidecars under the installed Codex home; an installer merges two command handlers into `hooks.json`. `dev-run` remains the conductor and explicitly activates/deactivates the helper.

**Tech Stack:** Python 3 standard library, existing `flowctl` argparse CLI, `unittest`, Codex `hooks.json` command hooks.

**Spec:** `docs/superpowers/specs/2026-09-19-issues-5-dev-run-stop-hook-spec.md`

## Global Constraints

- Observation and Hook paths are read-only with respect to Flow controller, project and business state.
- Unknown, malformed, timed-out, conflicted or exhausted states always allow Stop.
- Lock order is one session-owner lock followed by one controller lock; never hold two locks of either kind.
- One generation nudges a fingerprint at most once and defaults to four total nudges.
- Runtime files contain no prompt, transcript, assistant message, production data or credentials.
- Runtime Goal remains a long-term result and is not a stage transition mechanism.

## Review Focus

- JSON `null`, invalid action types and route-back signals must not accidentally become actionable.
- Concurrent Stop/activate/deactivate/takeover must not duplicate a nudge or revive an old generation.
- Same-session A→B→A controller changes must close or harmlessly supersede stale sidecars.
- Custom Codex home paths containing spaces must install exact absolute commands without losing existing hooks.
- Read-only inspection must not create locks, recover transactions, touch mtimes or follow the controller final symlink.

---

### Task 1: Pure continuation observation

**Files:**
- Create: `workflow-v2/flowctl_lib/continuation.py`
- Modify: `workflow-v2/flowctl_lib/cli.py`
- Create: `workflow-v2/tests/test_continuation.py`

**Interfaces:**
- Produces: `inspect_continuation(state_path: str | Path) -> dict` and CLI `flowctl continuation inspect --state PATH`.
- Consumes: controller JSON bytes only; no existing mutating state helpers.

- [x] Write tests for every reason code, actual controller actions including `snapshot:capture`, route-back with unknown action, null action, relevant/unrelated fingerprint changes, malformed/symlink/oversize input and byte/mtime/directory stability.
- [x] Run the focused continuation suite and confirm failures are missing module/command behavior.
- [x] Implement strict direct file reading, minimal schema/action classification and canonical projection SHA-256.
- [x] Re-run the focused suite and existing CLI tests until green.

### Task 2: Runtime helper and bounded lifecycle

**Files:**
- Create: `workflow-v2/continuation_hook.py`
- Create: `workflow-v2/tests/test_continuation_hook.py`

**Interfaces:**
- Consumes: `flowctl.py continuation inspect` JSON and hook stdin events.
- Produces: `activate`, `deactivate`, and `hook` subcommands; runtime markers, owner pointers and sidecars under the helper-adjacent `runtime/` directory.

- [x] Write failing lifecycle tests using a temporary installed package: marker content, activate identity, duplicate activate, turn mismatch, fingerprint/budget bounds and all fail-open paths.
- [x] Write barrier-controlled failing tests for duplicate Stops, same-session A/B activation, A→B→A, old-delete/new-publish and inspect/deactivate/takeover races.
- [x] Run the focused suite and confirm expected missing-helper failures.
- [x] Implement atomic 0600 JSON writes, 0700 directories, advisory file locks, fixed lock order, generation checks, lazy stale-owner cleanup and bounded Stop output.
- [x] Re-run the focused suite until green; verify no runtime test writes the real Codex home or worktree.

### Task 3: Idempotent Codex Hook installer

**Files:**
- Create: `workflow-v2/scripts/install_codex_hooks.py`
- Create: `workflow-v2/tests/test_hook_installer.py`

**Interfaces:**
- Consumes: an already deployed `<codex-home>/flow-v2` package and optional explicit Codex home.
- Produces: merged `UserPromptSubmit` and `Stop` command handlers in `<codex-home>/hooks.json`, a reported backup and trust instructions.

- [x] Write failing tests for missing package, empty/existing/invalid hooks, exact-handler idempotency, custom home with spaces, atomic failure and inline-hook warning.
- [x] Run the focused suite and confirm failures are missing installer behavior.
- [x] Implement exact owned-handler merge with resolved interpreter/helper paths, backup and atomic replace; preserve all non-owned JSON.
- [x] Re-run the focused suite until green.

### Task 4: dev-run contract and package documentation

**Files:**
- Modify: `workflow-v2/skills/dev-run/SKILL.md`
- Modify: `workflow-v2/README.md`
- Modify: `workflow-v2/flowctl-contract.md`
- Modify: `workflow-v2/tests/test_workflow.py`

**Interfaces:**
- Consumes: helper activation/deactivation commands and `continuation inspect` observation.
- Produces: explicit conductor-first activation, degradation, owner-conflict and terminal cleanup instructions.

- [x] Add failing contract tests for same-turn handoff priority, helper-adjacent package resolution, Goal separation, activation timing, owner replacement, failure degradation and terminal deactivation.
- [x] Run the focused workflow tests and confirm missing contract text failures.
- [x] Update the three documents without adding controller fields, approvals or `exp-run` behavior.
- [x] Re-run focused tests until green.

### Task 5: Full verification and independent implementation review

**Files:**
- Modify only files required by findings from verification/review.

**Interfaces:**
- Consumes: all earlier tasks.
- Produces: verified implementation and Astra review evidence.

- [x] Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v` and record exact totals: 337 passed, one environment-only Cursor SDK wire test skipped.
- [x] Run `git diff --check`, inspect changed scope and verify every changed file traces to the approved Spec.
- [x] Verify the isolated Codex 0.155.0 probe evidence under `/private/tmp/flow-hook-spike.xhGEXp` without credentials or business data.
- [x] Submit design, Spec, Plan, implementation diff and verification evidence to Astra/medium with concurrency/lifecycle focus for three bounded cycles.
- [x] Resolve every blocking finding using a new red-green cycle and repeat full verification and Astra review until PASS. Astra/medium exceptional cycle 4 closed the final schema-validation finding with no new blocker.
