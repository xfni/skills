# Flow v2 Run Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated phrase-based review permission with one controller-bound Flow authorization, enforce minimal external-review egress, and govern sanitized production-data replay and its integration-test gaps.

**Architecture:** `flowctl` becomes the authority for authorization state, transitions, validation bindings, review request construction, and integration outcome aggregation. Review runners accept only a fully materialized prompt with tools/workspace access disabled; Flow skills consume controller IDs instead of interpreting consent text. Schema-v1 controllers migrate deterministically to schema v2 under the existing state lock.

**Tech Stack:** Python 3 standard library, unittest, JSON controller/event records, Cursor SDK, OpenAI-compatible Responses API, Markdown skill contracts.

**Spec:** `docs/superpowers/specs/2026-09-16-flow-authorization-design.md`

## Global Constraints

- Work only in `/Users/nixiaofeng/工作/code/feature-ISSUE-2-flow-authorization` on branch `feature-ISSUE-2-flow-authorization`.
- Never treat natural-language assent, a prompt, or a working directory as authorization.
- Hard exclusions are credentials, secrets, raw production data, unrelated content, production mutation, and remote deployment.
- External review must fail before egress unless the adapter proves local tools and implicit workspace indexing are disabled.
- Raw production records may exist only in a bounded process pipe; no raw disk, log, evidence, prompt, or external-model transmission is allowed.
- `SKIP_PRODUCTION_REPLAY` skips only scenarios proven to require production-derived data and produces `PRODUCTION_REPLAY_GAP` plus `COMPLETE_WITH_DEFECT`.
- Follow RED-GREEN-REFACTOR; do not weaken existing review ordering, fallback, retry, digest, or admission checks.

---

### Task 1: Schema-v2 migration and authorization state machine

**Files:**
- Create: `workflow-v2/flowctl_lib/authorizations.py`
- Modify: `workflow-v2/flowctl_lib/state.py`
- Modify: `workflow-v2/flowctl_lib/errors.py`
- Test: `workflow-v2/tests/test_flowctl.py`

**Interfaces:**
- Produces: `default_authorizations() -> dict`, `migrate_state(state: dict) -> tuple[dict, bool]`, `decide_authorization(state_path, kind, decision, expected_revision) -> dict`, and `begin_authorization_amendment(...) -> dict`.
- Produces: statuses `PENDING`, `GRANTED`, `DENIED`, `AMENDMENT_PENDING`, `INVALIDATED`; modes `SANITIZED_LOCAL_REPLAY`, `SKIP_PRODUCTION_REPLAY`.
- Consumes: `locked_state`, `commit_state`, controller issue/run/worktree identity.

- [ ] **Step 1: Write failing migration and transition tests**

Add tests that create a schema-v1 state, preserve artifacts/reviews/pause/revision, load it through `status` and mutating paths, and assert schema 2 plus pending authorizations. Add table-driven tests for first decision, identical idempotence, denial, legal amendment, new authorization ID/revision, stale-binding invalidation, identity drift, and hard-exclusion rejection.

```python
def test_authorization_amendment_invalidates_old_binding(self):
    granted = decide_authorization(path, "production_replay", "SANITIZED_LOCAL_REPLAY", revision)
    old_id = granted["authorizations"]["production_replay"]["authorization_id"]
    pending = begin_authorization_amendment(path, "production_replay", "SKIP_PRODUCTION_REPLAY", granted["state_revision"])
    self.assertEqual(pending["authorizations"]["production_replay"]["status"], "AMENDMENT_PENDING")
    amended = decide_authorization(path, "production_replay", "SKIP_PRODUCTION_REPLAY", pending["state_revision"])
    self.assertNotEqual(amended["authorizations"]["production_replay"]["authorization_id"], old_id)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest workflow-v2.tests.test_flowctl -k authorization -v`

Expected: import/command failures because authorization APIs and schema-v2 migration do not exist.

- [ ] **Step 3: Implement migration and transitions**

Make `load_state` parse both schema versions internally, but expose only migrated schema-v2 state through locked public entry points. Persist migration atomically with one `STATE_SCHEMA_MIGRATED` event without losing the existing hash chain. Use UUID authorization IDs, revisioned immutable history, and explicit transition validation. Identical decisions return without state revision growth.

- [ ] **Step 4: Run focused and state regression tests**

Run: `python -m unittest workflow-v2.tests.test_flowctl -k authorization -v`

Run: `python -m unittest workflow-v2.tests.test_flowctl -k state -v`

Expected: PASS; existing event recovery and admission tests remain green.

### Task 2: Structured authorization CLI and single Flow gate

**Files:**
- Modify: `workflow-v2/flowctl_lib/cli.py`
- Create: `workflow-v2/schemas/authorization-decision.schema.json`
- Modify: `workflow-v2/skills/flow-run/SKILL.md`
- Modify: `workflow-v2/flow-contract.md`
- Modify: `workflow-v2/orchestration-contract.md`
- Test: `workflow-v2/tests/test_flowctl_cli.py`
- Test: `workflow-v2/tests/test_workflow.py`

**Interfaces:**
- Produces CLI: `flowctl authorization decide --state PATH --kind KIND --decision JSON --expected-revision N`.
- Produces CLI: `flowctl authorization amend --state PATH --kind KIND --decision JSON --expected-revision N`.
- Consumes Task 1 transition functions.

- [ ] **Step 1: Add failing CLI and contract tests**

Test malformed/non-object JSON, unknown fields, replay choice enums, idempotent decisions, amendment flow, and output containing `authorization_id`. Contract tests require one initial Chinese gate with `允许脱敏后回放生产数据（推荐）` and `不进行依赖生产数据的集成测试`, and prohibit stage-local magic phrases.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m unittest workflow-v2.tests.test_flowctl_cli workflow-v2.tests.test_workflow -k authorization -v`

Expected: FAIL because the subcommands/schema/single-gate wording are absent.

- [ ] **Step 3: Implement CLI dispatch and Flow gate contract**

Parse only JSON objects, reject booleans as integers, validate exact keys/enums, and return structured controller state. Update `$flow-run` so pending decisions produce one consolidated human gate, existing IDs are reused, denial pauses once, and changes route through `authorization amend`. Remove `FLOW_CURSOR_AUTHORIZATION`/`FLOW_IBRAIN_AUTHORIZATION` as free-form tokens in favor of controller IDs and manifests.

- [ ] **Step 4: Run CLI and workflow tests**

Run: `python -m unittest workflow-v2.tests.test_flowctl_cli workflow-v2.tests.test_workflow -v`

Expected: PASS.

### Task 3: Bound review package and zero-tool runner protocol

**Files:**
- Create: `workflow-v2/flowctl_lib/review_package.py`
- Modify: `workflow-v2/flowctl_lib/reviews.py`
- Modify: `workflow-v2/flowctl_lib/cli.py`
- Modify: `skills/cursor-review/scripts/cursor_review.py`
- Modify: `skills/ibrain-review/scripts/ibrain_review.py`
- Modify: `skills/cursor-review/SKILL.md`
- Modify: `skills/ibrain-review/SKILL.md`
- Test: `workflow-v2/tests/test_flowctl.py`
- Create: `workflow-v2/tests/test_review_runners.py`

**Interfaces:**
- Produces: `create_review_package(state, backend, stage, artifact_key, prompt_path, paths) -> ReviewPackage` with root, manifest, digest, outbound prompt, and cleanup.
- Produces runner protocol: `runner REVIEW_REQUEST_FILE --no-tools`; request contains exact UTF-8 prompt and file bytes encoded as bounded JSON content, never a repository/workspace path.
- Consumes active external-review authorization and creates a single-use binding tied to authorization revision and package digest.

- [ ] **Step 1: Add failing package-boundary tests**

Use lure files outside the package and assert exact outbound request equality. Cover undeclared file, escaping symlink, `..`, absolute lure path, sensitive prompt patterns, source drift, package mutation, reused binding, and an adapter capability response that reports tools or implicit indexing enabled.

```python
def test_runner_request_contains_only_bound_bytes(self):
    package = create_review_package(state, "cursor", "flow-spec", "spec:M1", prompt, [spec])
    request = json.loads(package.request_path.read_text())
    self.assertNotIn(lure.read_text(), json.dumps(request))
    self.assertNotIn(str(worktree), json.dumps(request))
    self.assertEqual(request["capabilities"], {"local_tools": False, "implicit_indexing": False})
```

- [ ] **Step 2: Run package/runner tests and verify RED**

Run: `python -m unittest workflow-v2.tests.test_flowctl workflow-v2.tests.test_review_runners -k package -v`

Expected: FAIL because reviews still pass the entire worktree to runners.

- [ ] **Step 3: Implement package creation and authorization binding**

Canonicalize beneath the admitted worktree, reject all symlinks and non-regular files, read/hash once into a private temporary directory, include exact prompt bytes, mark files read-only, rehash immediately before launch, and clean up in `finally`. Record only digests and redacted operational data. Consume the binding once even when the runner fails.

- [ ] **Step 4: Convert Cursor and iBrain runners to zero-tool requests**

Cursor must create an agent without `READ_ONLY_TOOLS`, `LocalAgentOptions`, or `workspace=repo`; it sends the materialized request text only if an SDK capability check proves no tools/indexing. iBrain calls its Responses endpoint directly with the materialized input and no `tools`, replacing `codex exec -C repo`. Both implement `--check-capabilities` and fail with `BACKEND_UNAVAILABLE` before review when guarantees are unavailable.

- [ ] **Step 5: Run runner and review regressions**

Run: `python -m unittest workflow-v2.tests.test_review_runners workflow-v2.tests.test_flowctl -k review -v`

Expected: PASS, including GPT→Cursor/iBrain→consistency ordering and retry limits.

### Task 4: Production replay preflight and execution contract

**Files:**
- Create: `workflow-v2/flowctl_lib/replay.py`
- Create: `workflow-v2/schemas/replay-manifest.schema.json`
- Modify: `workflow-v2/flowctl_lib/cli.py`
- Test: `workflow-v2/tests/test_replay.py`

**Interfaces:**
- Produces CLI: `flowctl replay validate --state PATH --manifest FILE --expected-revision N`.
- Produces CLI: `flowctl replay run --state PATH --binding-id ID --expected-revision N`.
- Produces: `validate_replay_manifest(...) -> ReplayBinding`, `run_replay(...) -> ReplayEvidence`.
- Consumes active `SANITIZED_LOCAL_REPLAY` authorization; rejects execution under `SKIP_PRODUCTION_REPLAY`.

- [ ] **Step 1: Write failing preflight and failure-path tests**

Create fixture adapter/sanitizer executables that communicate over pipes. Test unsupported arbitrary commands, caches/logging enabled, non-ignored destination, source error with raw lure value, mid-transform failure, output validation failure, publish failure, cleanup failure, and successful sanitized replay. Assert lure bytes never appear in files, controller events, evidence, stdout, or stderr.

- [ ] **Step 2: Run replay tests and verify RED**

Run: `python -m unittest workflow-v2.tests.test_replay -v`

Expected: FAIL because replay commands and policy enforcement do not exist.

- [ ] **Step 3: Implement supported adapter profiles and fail-closed preflight**

Require an exact executable plus arguments array, pinned executable digest, explicit `streaming`, `cache_disabled`, `body_logging_disabled`, and `redacted_errors` capabilities. Validate real paths, ignored private destination, limits, sanitizer digest/version, and cleanup command before starting either process. Do not accept shell strings.

- [ ] **Step 4: Implement bounded pipe execution and cleanup**

Launch acquisition stdout directly into sanitizer stdin without parent buffering or raw capture; route adapter stderr to a discard/redacted channel specified by its supported profile. Validate sanitized staging output before atomic publish. On every failure terminate the process group, remove staging/final files, run cleanup, and return only redacted codes/counters. A cleanup failure returns `BLOCKED_CLEANUP`.

- [ ] **Step 5: Run replay tests**

Run: `python -m unittest workflow-v2.tests.test_replay -v`

Expected: PASS with no raw lure value in the test directory or captured output.

### Task 5: Integration authorized-skip aggregation

**Files:**
- Modify: `workflow-v2/flowctl_lib/artifacts.py`
- Modify: `workflow-v2/flowctl_lib/handoff.py`
- Modify: `workflow-v2/flowctl_lib/resume.py`
- Create: `workflow-v2/flowctl_lib/integration_results.py`
- Modify: `workflow-v2/schemas/handoff.schema.json`
- Modify: `workflow-v2/skills/flow-plan/SKILL.md`
- Modify: `workflow-v2/skills/flow-integration/SKILL.md`
- Test: `workflow-v2/tests/test_flowctl.py`
- Test: `workflow-v2/tests/test_workflow.py`

**Interfaces:**
- Produces: `aggregate_integration_results(scenarios: list[dict]) -> dict`.
- Produces statuses `PASSED`, `FAILED`, `BLOCKED`, `SKIPPED_AUTHORIZED_REPLAY`, aggregate `COMPLETE_WITH_DEFECT`, and gap kind `PRODUCTION_REPLAY_GAP`.
- Consumes active replay decision and Plan trace proving production-data necessity.

- [ ] **Step 1: Add failing aggregation and handoff tests**

Cover all-pass, pass+authorized skip, skip-only warning, gap+ordinary failure, gap+blocker, unauthorized skip, missing Plan trace, and preservation through resume/final handoff.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m unittest workflow-v2.tests.test_flowctl workflow-v2.tests.test_workflow -k production_replay -v`

Expected: FAIL because Integration accepts only `PASSED` and has no replay-gap type.

- [ ] **Step 3: Implement deterministic aggregation and Flow contract wording**

Give `FAILED` and `BLOCKED` precedence over authorized skips. Permit `COMPLETE_WITH_DEFECT` only when every non-skipped scenario passes and each skip has a Plan trace and open gap. Ensure unaffected scenarios always execute and the final report carries every gap.

- [ ] **Step 4: Run integration/controller regressions**

Run: `python -m unittest workflow-v2.tests.test_flowctl workflow-v2.tests.test_workflow -v`

Expected: PASS.

### Task 6: End-to-end contracts, documentation, and deployment verification

**Files:**
- Modify: `workflow-v2/README.md`
- Modify: `workflow-v2/artifact-contract.md`
- Modify: `workflow-v2/flowctl-contract.md`
- Modify: `workflow-v2/skills/flow-spec/SKILL.md`
- Modify: `workflow-v2/skills/flow-plan/SKILL.md`
- Modify: `workflow-v2/skills/flow-code/SKILL.md`
- Modify: `workflow-v2/skills/flow-integration/SKILL.md`
- Modify: `workflow-v2/tests/test_workflow.py`

**Interfaces:**
- Consumes all prior tasks.
- Produces one documented resume-safe workflow whose stages use controller authorization IDs and never re-prompt within unchanged scope.

- [ ] **Step 1: Add end-to-end contract assertions**

Assert requirement discussion remains the normal human product gate; initial run authorization is consolidated; Spec/Plan/Code use the same external authorization revision; retry and iBrain fallback do not re-prompt; changed scope uses amendment; replay choice reaches Integration; and direct stage invocation creates the minimal stage-bound authorization gate.

- [ ] **Step 2: Run full suite and fix only demonstrated regressions**

Run: `python -m unittest discover -s workflow-v2/tests -v`

Expected: all tests PASS.

- [ ] **Step 3: Run static and repository checks**

Run: `python -m compileall -q workflow-v2/flowctl_lib skills/cursor-review/scripts skills/ibrain-review/scripts`

Run: `git diff --check`

Run: `git status --short`

Expected: compilation and whitespace checks PASS; status contains only ISSUE-2 files.

- [ ] **Step 4: Verify installable copies without mutating global skills**

Compare `workflow-v2/skills/*`, `skills/cursor-review`, and `skills/ibrain-review` against the intended Codex destinations and record the synchronization commands. Do not write `~/.codex/skills` until the user authorizes deployment or the current request explicitly includes it.

- [ ] **Step 5: Review the final diff**

Inspect every changed file and map it back to the approved design sections. Confirm no API key, raw data, temporary review package, generated replay output, or unrelated main-checkout change is tracked.
