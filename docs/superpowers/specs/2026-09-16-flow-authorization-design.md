# Flow v2 Run Authorization Design

## Goal

Make authorization a durable, controller-verified part of one Flow run. A human answers one consolidated gate near `$flow-run` initialization; later stages reuse that decision while their manifests remain inside its boundary. Natural-language assent and prompt text are never authorization.

This change covers two capabilities:

- sending a minimal, explicitly packaged set of in-scope artifacts and source context to Cursor, with iBrain/GLM-5.3 available only under the existing runtime-fallback rule;
- replaying sanitized production-derived data in a local integration-test environment.

It does not authorize production mutation, raw production data persistence, remote deployment, unrelated repository transmission, or expansion beyond the recorded run boundary.

## Initial authorization gate

After issue, run, repository, worktree, and branch admission are known, but before requirement work begins, `$flow-run` presents one Chinese authorization summary. External review and production replay are separate decisions in the same gate.

External review states that the minimum necessary Requirement, Intent, Roadmap, Spec, Plan, Code, tests, and evidence may be sent to Cursor or the iBrain fallback. The scope is limited to the current issue/run/worktree and excludes credentials, secrets, unrelated content, raw production data, and unnecessary personal data.

Production replay offers exactly two choices:

1. `允许脱敏后回放生产数据（推荐）`
2. `不进行依赖生产数据的集成测试`

The first choice authorizes a policy boundary, not unrestricted data access. The second choice does not skip Integration: all scenarios that can use test-environment or synthetic data still run. Only scenarios whose approved acceptance objective necessarily requires production-derived data are skipped.

If external review is denied, Flow records that stable decision and pauses before the first mandatory external review. It does not repeatedly ask at each stage. The human may later amend the decision through the controller.

## Controller state

`flow-state.json` schema version 2 gains an `authorizations` object owned exclusively by flowctl. Each authorization contains a controller-generated `authorization_id`, its own revision, status, immutable scope, decision, and audit timestamps. Example:

```json
{
  "authorizations": {
    "external_review": {
      "authorization_id": "authz-external-0001",
      "revision": 1,
      "status": "GRANTED",
      "issue_id": "ISSUE-2",
      "run_id": "run-issue-2",
      "worktree_path": "/absolute/worktree",
      "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
      "allowed_backends": ["cursor", "ibrain"],
      "exclusions": ["secrets", "credentials", "raw_production_data", "unrelated_content"],
      "granted_by": "HUMAN"
    },
    "production_replay": {
      "authorization_id": "authz-replay-0001",
      "revision": 1,
      "status": "GRANTED",
      "mode": "SANITIZED_LOCAL_REPLAY",
      "raw_persistence": "DENIED",
      "external_model_transmission": "DENIED",
      "git_tracking": "DENIED",
      "cleanup_required": true,
      "granted_by": "HUMAN"
    }
  }
}
```

Secrets, credentials, raw production data, unrelated content, production mutation, and remote deployment are hard exclusions. They cannot be relaxed by an amendment in this feature.

## Authorization state machine

The valid states are `PENDING`, `GRANTED`, `DENIED`, `AMENDMENT_PENDING`, and `INVALIDATED`.

| Current state | Human/controller action | Result |
|---|---|---|
| absent/legacy | migrate | Create `PENDING`; preserve every artifact, review, revision, pause, and event |
| `PENDING` | grant or deny | Create revision 1 and a new authorization ID; record `GRANTED` or `DENIED` |
| `GRANTED`/`DENIED` | submit identical decision | Idempotent success; no revision, binding, or event duplication |
| `GRANTED`/`DENIED` | request a legal changed decision | Set `AMENDMENT_PENDING`; keep prior record for audit but make it unusable for new operations |
| `AMENDMENT_PENDING` | human confirms | Create the next revision with a new authorization ID; invalidate every binding to the prior revision |
| any | issue/run/worktree identity drifts | Set `INVALIDATED`; require a fresh human decision for the corrected identity |
| any | request relaxes a hard exclusion | Reject; state and active authorization remain unchanged |

An amendment may narrow or legally change a decision, including switching from sanitized replay to no replay or changing external review from denied to granted. It never mutates the prior authorization in place. A denial is recoverable only through this amendment transition; stage prompts cannot reinterpret vague text as consent.

## Controller commands and migration

Add deterministic command families:

- `flowctl authorization decide`: accepts a schema-valid structured human decision, performs the state transition above, and emits the active authorization ID/revision. The interactive skill converts the selected Chinese options to this input; it does not require a magic sentence.
- `flowctl authorization amend`: opens `AMENDMENT_PENDING` and emits one bound human gate with enumerated choices and the proposed difference.
- `flowctl authorization validate`: validates a review-package or replay manifest against the active authorization immediately before the operation. It returns a single-use binding ID and manifest digest; it never expands scope.

Controller initialization records both decisions as pending. `$flow-run` asks once when either is pending. A stage consumes only controller IDs, never free-form consent. A resume gate references the authorization ID and proposed structured decision, so alternate wording cannot cause rejection.

Every locked state entry point performs schema migration before reading or mutating state. Read-only entry points either take the same lock and migrate atomically or fail closed with a migration-required result; they do not operate on partially migrated state. Migration is deterministic, preserves existing artifacts/reviews/revisions/pause state and events, appends one migration event, and creates pending authorization records. Direct `resume`, `status`, `review`, and `handoff` calls therefore cannot bypass migration.

## External-review package and actual egress

The authorization manifest includes backend, stage, artifact bindings, the exact prompt bytes/digest, and every transmitted file path/digest. Validation and transmission use the same immutable review package:

1. Flowctl resolves paths beneath the admitted worktree without following escaping symlinks, checks artifact-chain eligibility and hard exclusions, and reads each file once.
2. Under a controller-owned private temporary directory, it creates a package containing only the manifest, exact prompt, and verified file bytes. Relative paths are preserved only inside a neutral `inputs/` directory. `.git`, sockets, devices, symlinks, environment files, credentials, and undeclared files are absent.
3. Flowctl hashes the completed package, marks it read-only, creates a single-use binding to that package digest, and serializes the exact manifest, prompt, and input bytes into the runner request. The review request exposes no filesystem, shell, search, MCP, URL-fetch, or other local-content tool to the model. The runner receives neither the original worktree path nor a general-purpose workspace.
4. Immediately before invocation, flowctl re-verifies package files and digest. Any drift, missing file, added file, consumed binding, or inability of the backend adapter to prove tool-disabled operation fails closed before egress.
5. The controller captures the process result, then removes the package. Cleanup failure is recorded as a review run error and cannot be presented as a successful review.

Cursor and iBrain runners are changed to use a narrow `review_bytes(request, tools=disabled)` adapter: the host reads the verified package, builds one bounded request, and supplies those bytes as the complete review input. Each backend adapter has an explicit capability check proving that local tools and implicit workspace indexing are disabled. If the SDK cannot provide that guarantee, that backend is unavailable and the controller applies the existing runtime fallback or blocks. The temporary package is controller input, not the model's workspace. An OS-level sandbox may remain defense in depth, but authorization correctness is enforced by the tool-disabled adapter and fail-closed capability check, not by `cwd` or instructions asking the model to ignore files.

Flowctl rejects a different issue/run/worktree/stage, an unapproved backend, a path outside the worktree or approved artifact chain, sensitive/production content, or an expanded/unbound manifest. Review revisions and retries need no new human gate while they create a new package within the same active authorization revision. Cursor findings do not authorize iBrain; existing runtime-fallback rules still select the backend.

Negative verification covers an undeclared worktree file, a symlink escape, sensitive prompt content, source drift between declaration and package creation, package mutation before invocation, and runner attempts to access package-external lure files by known absolute path and `..` traversal. The fake adapters assert that no file/search/shell tool is registered and that neither lure bytes nor paths enter the outbound model request. A backend that reports tools or implicit workspace indexing enabled is rejected before any outbound call.

## Sanitized local replay execution

The initial decision grants a strict policy; it does not itself fetch data. Plan must define a replay manifest containing the source identifier, field categories, time window, maximum records, exact acquisition tool/command, exact sanitizer executable/version, required transformations, test-only destination, retention deadline, cleanup command, and proof method for every safety property.

Before acquisition, `flowctl authorization validate --kind production-replay` performs a fail-closed preflight:

- the acquisition adapter must support streaming records directly to the sanitizer over an in-memory/process pipe and must disable response caches, debug bodies, request/response logging, shell tracing, and raw diagnostic dumps;
- the sanitizer must emit only sanitized records and machine-readable counters on separate channels; stderr and exception rendering must be value-redacted;
- the destination and staging paths must be private, inside the admitted worktree's declared ignored test-data directory, and proven ignored by Git;
- no acquisition starts unless the controller can verify these properties from a supported adapter profile and the Plan-pinned command. An arbitrary shell command or an unverifiable client is rejected.

Execution is controller-owned: the acquisition adapter streams raw bytes only through a pipe to the sanitizer. Raw bytes are never written to disk, logs, evidence, prompts, command lines, environment values, or external models. Sanitized records may be written to a private staging file only after each record passes field-level sanitization; the final replay file is atomically published only after whole-output schema, record-count, identifier-removal, and policy validation succeed.

On acquisition, transform, or output-validation failure, flowctl terminates both processes, deletes staging/final outputs, runs the declared cleanup, and emits only redacted operational evidence. A cleanup failure is a blocker; Flow must not claim that raw or sanitized material was removed. If a tool could have emitted raw data in an error channel, that adapter profile is unsupported and acquisition must not begin. Evidence contains command identities/digests, counts, sanitizer version, package/destination digests, ignore proof, timestamps, and cleanup result—never source values.

This feature provides the policy verifier and a narrow adapter contract, not a general production-data collector. A project must supply or select a supported adapter and sanitizer in Plan. If it cannot prove the contract, Flow offers amendment to `SKIP_PRODUCTION_REPLAY` or remains blocked before acquisition.

Negative verification covers failure halfway through transformation, acquisition-tool errors, attempted raw stderr output, final-output validation failure, publish failure, and cleanup failure. Every case asserts that acquisition was prevented when preflight proof was absent and that no raw file or raw evidence was created.

## No-replay behavior and completion mapping

With `SKIP_PRODUCTION_REPLAY`, Integration executes every unaffected `TESTCASE-*`. A production-dependent scenario is skippable only when Plan traces why synthetic or isolated test-environment data cannot establish its acceptance claim. Each such scenario receives status `SKIPPED_AUTHORIZED_REPLAY` and creates one durable `PRODUCTION_REPLAY_GAP` with scenario IDs, missing assurance, reason, owner, remediation, and `OPEN` status.

Integration aggregates deterministically:

| Scenario/result set | Integration outcome |
|---|---|
| any ordinary test failure | `FAILED` |
| unresolved infrastructure/safety/cleanup blocker | `BLOCKED` |
| all scenarios `PASSED` | `PASSED` |
| only `PASSED` plus `SKIPPED_AUTHORIZED_REPLAY` | `COMPLETE_WITH_DEFECT` |
| no executable passing scenario and one or more authorized skips | `COMPLETE_WITH_DEFECT` with explicit zero-executed warning |

An authorized skip never masks an ordinary failure or blocker. `COMPLETE_WITH_DEFECT` is terminal for the milestone but carries open gaps through milestone and final reports and prevents a fully clean completion claim. Handoff schema, resume logic, controller terminal-state validation, and reports all use the same enum and aggregation rule.

## Failure and recovery

- Missing authorization: persist one authorization human gate; do not ask from individual review stages.
- Denied external review: pause at the first mandatory external review with one amendment action; do not repeat a phrase request.
- Manifest outside scope: reject before packaging/transmission/acquisition and identify the exact mismatched field.
- Sanitization or cleanup failure: stop replay, record only redacted operational evidence, and remain blocked until cleanup is proven.
- Controller drift or run/worktree mismatch: invalidate use of the active authorization, not its historical audit record.
- Resume: reload/migrate controller state and continue without prompting when the active authorization and operation binding still match.

## Verification

Controller tests cover schema-v2 migration through every public state entry point; preservation of artifacts, reviews, revisions, pause and events; pending decisions; grant and denial; identical idempotence; legal amendments in both directions; invalidation of old bindings; hard-exclusion rejection; stable recovery from denied external review; and resume reuse without repeated prompts.

External-review tests prove that the exact prompt and declared files are the only outbound request content, the runner receives no worktree or general workspace, all local tools and implicit indexing are disabled, bindings are single-use, review order/fallback rules remain intact, retries/revisions reuse authorization but create fresh packages, and all drift/escape/sensitive-content/capability-check cases fail before egress.

Replay tests cover supported-adapter preflight, raw-persistence rejection, no-log enforcement, mid-stream failure cleanup, redacted tool errors, output-validation failure, cleanup failure, ignored destination proof, and absence of raw bytes from filesystem and evidence. Integration tests cover unaffected execution, authorized skip status, gap creation, all-pass, gap-only, gap-plus-failure, gap-plus-blocker, and final `COMPLETE_WITH_DEFECT` propagation. Workflow contract tests assert the Chinese choices and prohibit stage-local duplicate authorization prompts.
