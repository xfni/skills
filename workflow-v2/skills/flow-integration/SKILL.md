---
name: flow-integration
description: Use when the user explicitly requests real-service cross-boundary validation, with or without prior Flow artifacts.
---

# Flow Integration

Read and enforce `../../flow-contract.md`; silently verify its issue, controller, and worktree bindings at stage entry. Governed mode also verifies the Requirement authorization; Direct mode obtains its own explicit test authorization.
Read and follow `../../artifact-contract.md` when verifying artifact revisions, digests, and approvals.
When `FLOW_RUN_CONTEXT` is present, also read and follow `../../orchestration-contract.md`; return its signal instead of a manual next-skill instruction.

Read and enforce `../../flowctl-contract.md`. Run `flowctl status` at entry, `flowctl artifact register` for Integration evidence, and `flowctl handoff accept` for terminal completion. The skill must not edit the controller or declare completion before controller acceptance.

Execute a confirmed integration contract against a frozen code snapshot and produce integration evidence. The default execution target is a temporary local service built or launched from the current worktree and frozen snapshot. Validate it by sending real requests across real boundaries; do not repair production code inside this stage.

## Admission modes

Choose exactly one mode and record it.

### Governed mode

Require the `$flow-code` handoff tuple: milestone ID; exact requirement.md, intent.md, roadmap.md, spec.md, and plan.md paths with approved revisions and SHA-256 digests; code-evidence path; reserved `TESTCASE-*`; code_snapshot; and open review gaps. Accept code evidence `COMPLETE` only when no gap is open; accept `COMPLETE_WITH_DEFECT` only with at least one open `EXTERNAL_REVIEW_GAP`. For any open gap regardless of the claimed Code status, propagate it without pausing, preserve remediation, include it in the final report, and reject the inconsistent tuple `COMPLETE` plus an open gap. Recompute every canonical artifact digest, verify every approval and trace, and compare HEAD, status, tracked diff, and untracked content digests to the handed-off snapshot. Drift requires a new `$flow-code` handoff.

Use the Plan-approved `TESTCASE-*` contract and its allowed test-code, fixture, environment, and output boundaries. The approved `TESTCASE-*` integration outline is the prior human authorization for those exact scenarios. Briefly display the test-point IDs being started. Do not ask for another confirmation before execution. This exemption applies only when the complete governed handoff verifies that each scenario already names its objective, participating services, environment, setup, real action/request, expected cross-boundary result, evidence, and safe cleanup. A roadmap alone, a generic test summary, missing detail, drift, or any newly added or expanded scenario does not qualify; use Direct mode and confirmation for the unapproved scope.

### Direct mode

Use Direct mode only when the human explicitly invokes `$flow-integration` without a complete governed handoff. Do not fabricate requirement, intent, roadmap, Spec, Plan, acceptance IDs, approvals, or equivalent coverage.

Read applicable `AGENTS.md`, repository runbooks, service configuration, existing integration tests, code boundaries, and current user changes. Require an issue ID for the persisted evidence, identify the project root, and freeze a `direct_code_snapshot` containing HEAD, status, tracked diff, and digests of untracked non-ignored files.

Draft a `direct_test_charter` with stable `TESTCASE-*` scenarios and record `provenance: DIRECT` separately:

```text
provenance: DIRECT; issue; objective; explicit coverage limits
named non-production environment and authorized dependencies
real participating services and boundaries
system under test versus supporting dependencies
service start, bounded readiness, and stop commands
real protocol requests, identity/permissions, inputs, and expected outputs
fixtures/test data, isolation, idempotence, and safe cleanup
observation oracles: response, probe, logs, audit, state, returned/persisted data
timeouts and bounded polling conditions
allowed test-only code, fixture, and evidence paths
commands, side effects, secrets exclusions, risks, and blockers
```

Before asking for approval, show the complete charter plus a concise list of human-readable test points. Each visible test point must include its `TESTCASE-*` ID, purpose, real services/boundary, setup or test data, real request/action, expected result, observation evidence, side effects, and cleanup. Do not hide the executable scope behind an artifact path or ask the human to confirm before showing it.

Require explicit human confirmation of the displayed Direct test points before starting services, sending requests, creating test data, or writing test code. A correction creates a new charter revision and requires the revised points to be shown again. Direct confirmation authorizes only the named non-production actions and paths; request any additional permission at the point of use. If the objective cannot be tested without changing production implementation or business semantics, end `BLOCKED` and explain the required upstream work.

Require a safe named test environment and authorized dependencies. Unless an approved exception below applies, the system under test is the temporary local application service. Supporting dependencies do not have to run locally: prefer already authorized isolated non-production test dependencies when they preserve the real integration boundary, such as a test database, Redis namespace, Elasticsearch index prefix, test queue/vhost, or sandbox API tenant. Verify endpoint ownership, non-production identity, namespace/data isolation, collision avoidance, permissions, and safe cleanup before use.

Using those supporting dependencies does not require local containers. Do not start a local database, Redis, Elasticsearch, queue, or similar middleware merely to make the topology fully local. Docker or OrbStack being stopped or unavailable must not by itself become `BLOCKED` when an authorized isolated test dependency can provide the real boundary. Start a local dependency process or container only when no safe authorized test dependency exists or the scenario explicitly tests that dependency's local lifecycle, version, configuration, or failure mode. Never default to production, mutate uncontrolled external data, or bypass permission prompts.

## Execute integration scenarios

For every governed `TESTCASE-*`, verify its linked Spec acceptance criteria and Intent Success Signals. For every confirmed direct `TESTCASE-*`, verify only its charter objective and explicitly report that requirement/Spec coverage is unknown. Use the approved fixtures and seams, and capture:

```text
environment and dependency versions
setup and safe cleanup
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

Use the returned response plus appropriate probe, logs, audit records, state inspection, or bounded wait for returned or persisted data to decide the result. Observability is evidence, not a substitute for starting the real service and sending real requests. Record readiness and observation deadlines; an unmet condition ends `FAILED` or `BLOCKED` according to whether behavior or environment caused it. Run normal, error, boundary, permission, compatibility, and recovery cases required by the governed Spec or confirmed direct charter; do not add unrelated exploratory scope. After the run, stop the local service and clean its isolated data, including failed or blocked runs when cleanup remains safe.

The stage may add or update minimal test-only code, integration tests, drivers, observers, fixtures, and evidence only in paths explicitly allowed by the approved Plan or confirmed direct charter. Such test code may drive requests, prepare isolated data, wait, or observe, but must not change business-logic semantics, production source, production defaults, authorization, transactions, or the real boundary under test. Compare its diff to the frozen snapshot before execution. If production implementation must change, stop and route the work outside this stage. Diagnose failures without production edits; after an upstream fix, obtain a new governed handoff or reconfirm a new direct snapshot and rerun affected scenarios.

## Evidence and result

Resolve the output path through the artifact contract with flow_step `integration` using current-stage instructions. In Governed mode, canonicalize its parent directory with realpath semantics and require exact equality with the Plan-approved canonical absolute directory; reject `..` or symlink traversal outside it. When the winning rule selects another directory, return to `$flow-plan` for approval without ignoring that rule or writing early. In Direct mode, require the resolved path to fall inside the charter-approved canonical directory with the same traversal checks.

Write the document with mode/provenance, source tuple or direct snapshot/charter revision, environment, system-under-test and supporting-dependency topology, local-versus-remote decision, dependency authorization, isolation and cleanup evidence, real service lifecycle, start command, process or container identity, port, actual request URL, scenario matrix, observation evidence, results, cleanup status, test-code diff, artifacts, failures, and traceability. Direct evidence must state its coverage limits and must not claim Intent, Spec, milestone, or release acceptance. Keep the tested production snapshot separate from approved test/evidence changes.

End:

- `PASSED` only when every required scenario passes freshly, evidence is available, cleanup succeeds, and the tested production-code snapshot remains unchanged except approved integration tests, fixtures, and evidence artifacts.
- `FAILED` when observed behavior contradicts an approved contract.
- `BLOCKED` when the environment or authority cannot support a required scenario.

Record `PASSED`, `FAILED`, or `BLOCKED` for every governed `TESTCASE-*` and every direct `TESTCASE-*`. Aggregate with strict priority: any failed scenario makes the run `FAILED`, even when others are blocked; otherwise any blocked scenario makes it `BLOCKED`; only all-passed is `PASSED`.

In Governed mode, route every failure to its owning stage: implementation defect → `$flow-code`; missing or incorrect task/seam → `$flow-plan`; behavioral contract gap → `$flow-spec`; milestone boundary/order problem → `$flow-roadmap`; product intent conflict → `$flow-intent`. In Direct mode, report the evidenced failure category and required next action without pretending an absent upstream artifact exists; suggest the appropriate Flow stage only if the human chooses to enter that workflow. Do not claim completion while any required scenario is failed or blocked.

Report the integration evidence path, status, tested code snapshot, coverage gaps, and required next action. Under `FLOW_RUN_CONTEXT`, return `FLOW_RUN_HANDOFF` with `next_stage: auto` only when the aggregate result is `PASSED`; flowctl marks the milestone complete and decides the next dependency-ready milestone or terminal completion. Return `FLOW_RUN_ROUTE_BACK` when the aggregate result is `FAILED` with evidence plus the classified `owner_stage` and `next_stage`, `FLOW_RUN_HUMAN_GATE` for Direct test-point confirmation, or `FLOW_RUN_BLOCKED` for a true blocked result. Do not deploy, push, or mark a release complete automatically.
