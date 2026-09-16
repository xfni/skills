# Worktree Review Implementation Plan

> **For agentic workers:** Execute inline with TDD, one task at a time. No automatic commits or external writes.

**Goal:** Replace selected-byte-only external review with autonomous read-only worktree exploration and deterministic post-review verification.

**Architecture:** `review_workspace.py` owns file inventory, filtered frozen view and mutation checking. `review_package.py` binds that view to each attempt. Cursor SDK and iBrain Responses runners explore the view; `reviews.py` accepts output only after guards pass.

**Tech Stack:** Python standard library, Cursor SDK, iBrain Responses function tools.

**Spec:** `docs/superpowers/specs/2026-09-16-worktree-review-design.md`

## Global Constraints

- Entire eligible worktree is available; the root's file selection cannot silently limit evidence.
- Reviewers write nothing; controller saves only stdout/API output after verification.
- No extra iBrain or Cursor human authorization gate; production replay remains governed.
- Credential/raw-data/external-path exclusions and host permissions remain enforced.
- Preserve original evidence, bounded retries, and required independent/final consistency lanes.

## Task 1: Frozen review workspace and controller gate

Files: create `workflow-v2/flowctl_lib/review_workspace.py`, `workflow-v2/tests/test_worktree_review.py`; modify `review_package.py`, `reviews.py`.

- [x] Add real Git fixture tests: unselected caller source is included; target/upstream artifacts included; credentials excluded; tracked/untracked/artifact/mode/index/HEAD changes detected; exact controller outputs ignored.
- [x] Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest workflow-v2.tests.test_worktree_review`; observe expected missing behavior failures.
- [x] Implement `capture_review_snapshot(root, controller_path)`, `create_review_view(root, destination, controller_path)`, and `verify_review_snapshot(...)`.
- [x] Bind original and view snapshots in package/attempt; verify before report persistence; mutation records INCOMPLETE/UNCLASSIFIED without rollback.
- [x] Rerun new and existing controller tests; update superseded selected-evidence assertions, preserving escape, drift and credential tests.

## Task 2: Autonomous runner adapters and historical repair

Files: modify `skills/cursor-review/scripts/cursor_review.py`, `skills/ibrain-review/scripts/ibrain_review.py`, `tests/test_ibrain_review.py`, `workflow-v2/tests/test_review_runners.py`, `reviews.py`.

- [x] Add failing Responses multi-turn test using list/read/search calls and an external-path rejection, and Cursor mocked SDK test with readonly tool set/view cwd.
- [x] Implement bounded iBrain function-tool loop, allowlisted manifest paths, no writes/shell, overall deadline and exploration evidence.
- [x] Restore Cursor SDK bridge against the frozen view with read-only tools, bounded timeout and structured failures.
- [x] Add failing historical test: timeout + two old malformed attempts, repair both, then allow a fresh iBrain retry; preserve event/evidence identities.
- [x] Implement eligibility invalidation for legacy-frame repair and update pinned adapter digests.

## Task 3: Skill contracts and behavioral validation

Files: modify Flow shared contracts, flow-run/spec/plan/code skills, cursor-review/ibrain-review skills, README and relevant contract tests.

- [x] Record baseline behavior against existing skills before edits.
- [x] Replace selected-byte/extra-authorization guidance with frozen-view exploration, stdout-only output and post-guard acceptance. Initial human gate covers production replay only.
- [x] Run changed skill frontmatter validation and an independent scenario using updated skills.
- [x] Run all workflow/root tests, compile checks and `git diff --check`; report live-backend checks separately from local/mock verification.

## Verification record

- RED observed: missing frozen-view module/runner behavior; late report-parsing source mutation accepted; conventional credential literal copied; worktree .git pointer copied. Focused regression failures were reproduced before their fixes.
- GREEN: Flow suite 207 tests, no failures, 1 default-runtime SDK skip; root suite 42 tests, no failures, 12 pre-existing absent-legacy-skill skips. Dedicated Cursor SDK runtime executes all 4 runner tests successfully without network.
- Six changed skills pass quick_validate; git diff --check passes.
- Independent implementation/concurrency audit reproduced snapshot TOCTOU and literal-credential leakage, found code-drift recording and SDK tool-wire issues; all five blockers fixed and focused final re-review passed.
- Skill baseline/updated scenario tests verify independent exploration, no external-review gate, stdout-only reports, mechanically eligible iBrain fallback and separate replay authority. Conflicting legacy clauses were removed from shared/current documentation.
- No live Cursor/iBrain review API was called. Local/mock tests and SDK serialization are not real-service evidence. Credential filtering remains conservative, not universal sensitive-data detection.
- Original worktree is not rolled back on detected mutation. Long controller lock and SDK-owned cancellation/cleanup remain existing lifecycle limitations; this batch adds no orphan-process reaper.
- Changes remain only in this feature worktree; no automatic commit, push or global Codex deployment.
