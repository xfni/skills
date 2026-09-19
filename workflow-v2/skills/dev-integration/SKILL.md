---
name: dev-integration
description: Use when the user explicitly requests real-service cross-boundary validation, with or without prior Flow artifacts.
---

# Dev Integration

For every human question, confirmation or blocked/recovery message, read and apply Human-readable interruption in `../../orchestration-contract.md`, also in Direct mode. Explain the actual problem, prior checks, smallest requested action and next step; internal errors/bindings are optional diagnostics, not the user's task. This changes wording, not gates or authority.

Agent leads action selection and semantic judgment; controller records current-action facts. Apply the cooperation and optional disposition rules in `../../flowctl-contract.md`: registration/resume do not replan or automatically withdraw guarantees, and pending_action is advisory. Missing historical metadata or tool uncertainty goes to safe diagnosis, not a new human/business gate. Never fabricate receipts, revive explicit revocations or bypass actual pauses/host permissions.

Carry every `EXTERNAL_REVIEW_GAP` into the final report. In orchestrated mode return the handoff unaccepted; the root alone accepts it once. Missing historical tuples or auxiliary metadata are not human unlock gates. A failed/unknown real test is not PASS, and production replay safety plus the minimal cleanup boundary remain required.

Before production acquisition/local tests, use the active production-data decision and approved Plan scenario (or the confirmed Direct charter). Use project runners and project data policy; no Flow sanitizer, trusted profile or replay manifest is required. Record source, actual input snapshot digest, execution command, local real requests and results without copying data values into evidence. Prefer production-derived datasets outside the original worktree. For existing in-tree or embedded samples, use the explicit file/directory transport exclusions in `../../review-contract.md` and keep datasets out of Git; Git ignore and a private-looking filename are not review exclusions. Exclusion alone does not pause review. Use project-approved local paths and keep data values out of model-visible output. Do not infer execution from a file's presence or a model claim.

Use a **minimal cleanup boundary** after every pass, failure, or blocked attempt: stop processes or containers started by this run, release ports and locks, and remove only runner-owned transient files that are not evidence or reusable fixtures. Persistent business writes produced by real requests in the named test environment must remain after the run. Do not delete, roll back, truncate, expire, or restore MongoDB, SQL databases, Elasticsearch/OpenSearch, Redis, queues, object storage, or similar business state created or changed by the test. Natural application behavior, such as consuming a queue message or applying its own TTL, is part of the observed execution and must not be counteracted.

This retention rule models real execution and applies to successful, failed, and blocked scenarios. Use collision-resistant issue/run/scenario identifiers when supported, and record their test-environment namespace and identifiers so humans can inspect the result or apply a separately governed retention policy. Clean persistent test data only when the human or an applicable project rule explicitly requires that exact cleanup; record that source and scope. Never clean production, unknown, pre-existing, shared, or another run's data. An unresolved process, port, lock, or unsafe transient artifact owned by this run remains a safety obstacle; retained test-environment business data does not.

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, and worktree bindings at stage entry. Governed mode also verifies the Requirement authorization; Direct mode obtains its own explicit test authorization.
Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at entry, `flowctl artifact register` for Integration evidence, and `flowctl handoff accept` for terminal completion. The skill must not edit the controller or declare completion before controller acceptance.

Execute a confirmed integration contract against a frozen code snapshot and produce integration evidence. The default execution target is a temporary local service built or launched from the current worktree and frozen snapshot. Validate it by sending real requests across real boundaries; do not repair production code inside this stage.

## Admission modes

Choose exactly one mode and record it.

### Governed mode

Use the current milestone, actual code handoff/snapshot when present, available Plan test outline and open gaps. Do not require every earlier artifact or its model-authored digest/approval tuple. Propagate gaps and derive defect completion rather than rejecting a duplicate quality declaration. A governed code snapshot must still match the tested code; actual source drift requires a new Code handoff. Arbitrary standalone entry uses Direct mode and its displayed test-point confirmation.

Use the Plan-approved `TESTCASE-*` contract and its allowed test-code, fixture, environment, and output boundaries. The approved `TESTCASE-*` integration outline is the prior human authorization for those exact scenarios. Briefly display the test-point IDs being started. Do not ask for another confirmation before execution. This exemption applies only when the complete governed handoff verifies that each scenario already names its objective, participating services, environment, setup, real action/request, expected cross-boundary result, evidence, persistent test-data identifiers, and minimal runtime cleanup. A roadmap alone, a generic test summary, missing detail, drift, or any newly added or expanded scenario does not qualify; use Direct mode and confirmation for the unapproved scope.

### Direct mode

Use Direct mode only when the human explicitly invokes `$dev-integration` without a complete governed handoff. Do not fabricate requirement, intent, roadmap, Spec, Plan, acceptance IDs, approvals, or equivalent coverage.

### Direct invocation authorization

Direct invocation creates no run-wide permission. If the confirmed charter requires production-derived replay and no matching active decision exists, immediately before replay present one minimal stage-bound authorization gate for only `production_replay` at `flow-integration`; record the structured choice through `flowctl authorization decide` and use the controller-generated authorization ID and revision with the confirmed charter's local-test scope; no adapter manifest is required. It must not imply authority for another stage. A later decision or scope change uses `flowctl authorization amend`. If the charter uses only synthetic or isolated non-production data, do not ask for replay authority at all.

Read applicable `AGENTS.md`, repository runbooks, service configuration, existing integration tests, code boundaries, and current user changes. Require an issue ID for the persisted evidence, identify the project root, and freeze a `direct_code_snapshot` containing HEAD, status, tracked diff, and digests of untracked non-ignored files.

Draft a `direct_test_charter` with stable `TESTCASE-*` scenarios and record `provenance: DIRECT` separately:

```text
provenance: DIRECT; issue; objective; explicit coverage limits
named non-production environment and authorized dependencies
real participating services and boundaries
system under test versus supporting dependencies
service start, bounded readiness, and stop commands
real protocol requests, identity/permissions, inputs, and expected outputs
fixtures/test data, isolation, idempotence, persistent-write identifiers, and minimal runtime cleanup
observation oracles: response, probe, logs, audit, state, returned/persisted data
timeouts and bounded polling conditions
allowed test-only code, fixture, and evidence paths
commands, side effects, secrets exclusions, risks, and blockers
```

Before asking for approval, show the charter's complete executable scope as a concise list of human-readable test points and link the full charter. Each visible test point must include its `TESTCASE-*` ID, purpose, real services/boundary, setup or test data, real request/action, expected result, observation evidence, persistent side effects, retained-data identifiers, and minimal runtime cleanup. Do not hide the executable scope behind an artifact path or ask the human to confirm before showing it.

The Direct question introduces “这是独立集成测试，需要你确认这次会实际执行的操作”, shows the test points in the conversation and links the full charter. Explain the temporary local service, actual read/write scope, retained test-environment business data, minimal runtime cleanup, whether production-derived inputs are involved, and coverage limits. Ask “确认执行以上测试，还是需要修改测试点？” before any side effect. A link, TESTCASE-* list alone or internal charter/snapshot tuple is not a readable confirmation; Governed already-approved tests do not get this extra question.

Require explicit human confirmation of the displayed Direct test points before starting services, sending requests, creating test data, or writing test code. A correction creates a new charter revision and requires the revised points to be shown again. Direct confirmation authorizes only the named non-production actions and paths; request any additional permission at the point of use. If the objective cannot be tested without changing production implementation or business semantics, end `BLOCKED` and explain the required upstream work.

Include the scoped test infrastructure permission from `../../flow-contract.md` in that same Direct confirmation: show actual dependencies, isolated resource scopes, required reads/writes, retained-data policy, and minimal runtime cleanup together with test points. In Governed mode reuse the run's actual confirmation or existing project/Plan permission, without another middleware authorization gate. Reject production or unverified default addresses, not authorized remote test middleware merely because it is remote. Verify effective Mongo/other startup configuration before launching; first sandbox denial follows the shared escalation/retry rule rather than immediate terminal BLOCKED.

Before requesting middleware details or declaring a dependency blocker, follow the shared discovery-first rule for MongoDB, MySQL/PostgreSQL, Redis, ES/OpenSearch, queues and object storage. Search the relevant project sources and effective configuration read-only; recover discoverable endpoints, resource scopes and override names yourself. Carry verified non-secret facts and the existing permission source into the host application. If an unneeded dependency has an existing safe local/disabled mode, verify its effect on the required scenario before using it. Report checked sources and only remaining unknowns when human input is genuinely necessary; do not connect to an unknown target or retry a host refusal blindly.

For an actual dependency/isolation gap, show known non-secret target facts, the checked configuration/runbook sources and the one remaining unknown. Ask for the approved test resource/isolation range or where its configuration/documentation is maintained; do not ask the user to invent environment-variable names or provide passwords. Say whether startup, connections and requests happened. Explain that verifying the supplied scope permits the affected tests to resume, subject to host permission, rather than requiring new requirement approval.

Require a safe named test environment and authorized dependencies. Unless an approved exception below applies, the system under test is the temporary local application service. Supporting dependencies do not have to run locally: prefer already authorized isolated non-production test dependencies when they preserve the real integration boundary, such as a test database, Redis namespace, Elasticsearch index prefix, test queue/vhost, or sandbox API tenant. Verify endpoint ownership, non-production identity, namespace/data isolation, collision avoidance, permissions, persistent-write traceability, and the minimal cleanup boundary before use.

Using those supporting dependencies does not require local containers. Do not start a local database, Redis, Elasticsearch, queue, or similar middleware merely to make the topology fully local. Docker or OrbStack being stopped or unavailable must not by itself become `BLOCKED` when an authorized isolated test dependency can provide the real boundary. Start a local dependency process or container only when no safe authorized test dependency exists or the scenario explicitly tests that dependency's local lifecycle, version, configuration, or failure mode. Never default to production, mutate uncontrolled external data, or bypass permission prompts.

## Execute integration scenarios

On `inspect:integration-snapshot`, inspect changes since the accepted Code handoff before running tests. Approved test-only drivers, fixtures and evidence may be added without redoing Code review, but retain the original reviewed snapshot and disclose the auxiliary diff. If a change affects production source or business semantics, record an explicit route-back; never declare the old receipts current for changed production code. Keep the accepted Integration position while diagnosing environment or auxiliary-file differences.

If local loopback binding or required test-dependency access is sandbox-denied, request the permitted escalation and retry the scoped startup before declaring the environment blocked. A refusal remains binding. Before startup, explicitly configure and verify the selected non-production dependencies; do not let a default Mongo or other remote connection silently choose the environment. Stop safely before requests when identity or isolation is unverified.

Explain a remaining host refusal as “当前运行环境不允许启动本地测试服务/访问已确认的测试资源”, with the specific denied operation and verified permitted recovery action. An already-given business authorization does not release it; request host approval through its actual permission mechanism, not a repeated Flow consent or an invented command. If that mechanism is unavailable, identify the environment/maintainer action needed. For a test behavior failure, report expected versus observed behavior and route automatic fixes internally; ask the human only when a real product or authority decision is missing. Never phrase an unexecuted test as a failed code assertion.

For every governed `TESTCASE-*`, verify its linked Spec acceptance criteria and Intent Success Signals. For every confirmed direct `TESTCASE-*`, verify only its charter objective and explicitly report that requirement/Spec coverage is unknown. Use the approved fixtures and seams, and capture:

```text
environment and dependency versions
setup, retained test-data identifiers, and minimal runtime cleanup
cross-component path and end-to-end action
request/input and observable output
state transitions and persisted data
permissions and identity behavior
compatibility or migration behavior
dependency failure and failure recovery
command, timestamps, exit result, logs, and artifact references
```

For every scenario, start the real service that is the system under test by building or launching the frozen application code from the current worktree as a temporary local service process or container, bind an isolated or ephemeral port, wait for bounded local readiness, and send real requests to its actual local protocol endpoint. Configure that local application to use the selected supporting dependencies, whether local or in the isolated test environment. Record the application start command, process or container identity, port, dependency endpoints and isolation keys, readiness evidence, actual request URL, and frozen snapshot. A separately running application counts only after proving it executes that exact snapshot.

A remote test deployment is an explicit exception, never the default. Use it only when the authorized Requirement, Intent, or Plan explicitly requires deployment-environment behavior, or when local execution is technically impossible because a required real dependency or infrastructure boundary cannot be reproduced locally. Record the reason and authorization. A remote endpoint returning `404`, lacking the new route, or otherwise showing that the frozen code is not deployed does not prove the frozen code is untestable and must not immediately become `BLOCKED`; attempt the temporary local service first. Only block after local execution is technically impossible and the authorized remote path is also unavailable. Do not deploy code as an implicit integration-test step.

If local build, start, readiness, or request delivery fails, capture evidence and classify the cause: an observed implementation or contract contradiction is `FAILED`; a verified external dependency, credential, permission, or authority preventing all valid execution paths is `BLOCKED`; insufficient evidence to distinguish them is `BLOCKED` with an explicit diagnostic gap. Never replace the action with a mock or static claim. Mocks, unit suites, static inspection, and a single happy-path request do not prove cross-component coverage.

Use the returned response plus appropriate probe, logs, audit records, state inspection, or bounded wait for returned or persisted data to decide the result. Observability is evidence, not a substitute for starting the real service and sending real requests. Record readiness and observation deadlines; an unmet condition ends `FAILED` or `BLOCKED` according to whether behavior or environment caused it. Run normal, error, boundary, permission, compatibility, and recovery cases required by the governed Spec or confirmed direct charter; do not add unrelated exploratory scope. After the run, stop the local service and perform only the minimal runtime cleanup. Retain real test-environment business writes and record where they can be inspected.

The stage may add or update minimal test-only code, integration tests, drivers, observers, fixtures, and evidence only in paths explicitly allowed by the approved Plan or confirmed direct charter. Such test code may drive requests, prepare isolated data, wait, or observe, but must not change business-logic semantics, production source, production defaults, authorization, transactions, or the real boundary under test. Compare its diff to the frozen snapshot before execution. If production implementation must change, stop and route the work outside this stage. Diagnose failures without production edits; after an upstream fix, obtain a new governed handoff or reconfirm a new direct snapshot and rerun affected scenarios.

## Evidence and result

Resolve the output path through the artifact contract with flow_step `integration` using current-stage instructions. In Governed mode, canonicalize its parent directory with realpath semantics and require exact equality with the Plan-approved canonical absolute directory; reject `..` or symlink traversal outside it. When the winning rule selects another directory, return to `$dev-plan` for approval without ignoring that rule or writing early. In Direct mode, require the resolved path to fall inside the charter-approved canonical directory with the same traversal checks.

Write the document with mode/provenance, source tuple or direct snapshot/charter revision, environment, system-under-test and supporting-dependency topology, local-versus-remote decision, dependency authorization, isolation, retained test-data namespaces/identifiers, real service lifecycle, start command, process or container identity, port, actual request URL, scenario matrix, observation evidence, results, minimal runtime cleanup status, test-code diff, artifacts, failures, and traceability. Direct evidence must state its coverage limits and must not claim Intent, Spec, milestone, or release acceptance. Keep the tested production snapshot separate from approved test/evidence changes.

End:

- `PASSED` only when every required scenario passes freshly, evidence is available, the minimal runtime cleanup succeeds, and the tested production-code snapshot remains unchanged except approved integration tests, fixtures, and evidence artifacts. Retained test-environment business writes are expected and do not prevent `PASSED`.
- `FAILED` when observed behavior contradicts an approved contract.
- `BLOCKED` when the environment or authority cannot support a required scenario.

Record `PASSED`, `FAILED`, or `BLOCKED` for every governed `TESTCASE-*` and every direct `TESTCASE-*`. Aggregate with strict priority: any failed scenario makes the run `FAILED`, even when others are blocked; otherwise any blocked scenario makes it `BLOCKED`; only all-passed is `PASSED`.

Consume the active decision through its `production_replay authorization ID and revision`. Under `LOCAL_PRODUCTION_REPLAY`, run the Plan-described project tools against the temporary local service and record actual evidence. Flow requires no sanitizer or replay manifest. Under `SKIP_PRODUCTION_REPLAY`, still execute every unaffected `TESTCASE-*`. The stage must not ask for replay authorization again while the identity, decision, and test scope remain valid; a changed choice or expanded test scope uses `flowctl authorization amend`. Only a scenario whose approved Plan trace proves production-derived data is necessary and synthetic or isolated test-environment data is insufficient may become `SKIPPED_AUTHORIZED_REPLAY`. Create one durable open `PRODUCTION_REPLAY_GAP` per skipped scenario with scenario IDs, missing assurance, reason, owner, and remediation. Any `FAILED` result takes precedence, then any `BLOCKED` result; authorized skips never mask either. All `PASSED` remains `PASSED`; only `PASSED` plus authorized skips, or skip-only, becomes `COMPLETE_WITH_DEFECT`. A skip-only outcome must carry an explicit zero-executed warning. Carry every gap through the handoff, resume state, and final report, and never make a clean completion claim while one remains open.

Use the approved Plan/Direct outline to judge coverage, not an exact scenario-ID universe. Record the current test object, readable raw evidence, explicit terminal result and Agent execution/coverage judgment. Missing machine metadata does not require Plan revision/re-review. Known FAILED/BLOCKED/unexecuted cannot become PASS through omission. A new actual result references the same test object and the replaced prior observation (integration_results.replaces = prior registered digest), preserving other unresolved failures. Replay skips still require active authority and justified gaps.

An environment/startup `FLOW_RUN_BLOCKED` may omit `integration_results`: provide the actual cause, evidence and resume condition even when the Plan has no machine scenario contract or no request ran. This records an obstacle, not completion or coverage. If supplied BLOCKED results contain no replay gaps, incomplete Plan coverage is not a signal-registration gate. Replay skips/gaps and successful completion still require their existing Plan/authorization checks.

FLOW_RUN_ROUTE_BACK and FLOW_RUN_BLOCKED record actual available cause/evidence; integration_results is optional when nothing ran. When supplied, terminal status matches the observation. Replay gaps still need actual independently granted skip permission; a caller-only open_gaps claim is not permission. Do not manufacture FAILED or a full scenario table merely to route a contract repair.

In Governed mode, route every failure to its owning stage: implementation defect → `$dev-code`; missing or incorrect task/seam → `$dev-plan`; behavioral contract gap → `$dev-spec`; milestone boundary/order problem → `$dev-roadmap`; product intent conflict → `$dev-intent`. In Direct mode, report the evidenced failure category and required next action without pretending an absent upstream artifact exists; suggest the appropriate Flow stage only if the human chooses to enter that workflow. Do not claim completion while any required scenario is failed or blocked.

Report the integration evidence path, status, tested code snapshot, coverage gaps, and required next action. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: auto` when the aggregate result is `PASSED` or `COMPLETE_WITH_DEFECT`; for the latter include `completion_quality: COMPLETE_WITH_DEFECT` and every open gap. Flowctl marks the milestone complete and decides the next dependency-ready milestone or terminal completion. Return `FLOW_RUN_ROUTE_BACK` when the aggregate result is `FAILED` with evidence plus the classified `owner_stage` and `next_stage`, `FLOW_RUN_HUMAN_GATE` for Direct test-point confirmation, or `FLOW_RUN_BLOCKED` for a true blocked result. Do not deploy, push, or mark a release complete automatically.

Translate an open gap into what was not verified, why, impact, owner and follow-up; keep raw gap names and bindings in evidence. A permitted conditional completion is a notice, not a fresh “是否接受缺陷” gate. A blocked report asks for the precise missing action only when human intervention is necessary and identifies which tests remain unexecuted. Preserve previously collected evidence and rerun affected checks rather than promising all previous conclusions remain valid after a code change.
