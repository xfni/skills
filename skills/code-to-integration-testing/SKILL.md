---
name: code-to-integration-testing
description: Use when an implemented change has an approved Integration Test Design and needs probes, real-environment test execution, regression evidence, or a formal integration test report.
---

# Code to Integration Testing

Use this explicit-only workflow after `$spec-plan-to-code` has completed an implementation. Execute approved integration semantics; do not invent product requirements or silently adjust acceptance.

## Establish the test baseline

Read the approved Decision Package, Spec, Plan, Integration Test Design, implementation version, primary-validation evidence, deployment/configuration prerequisites, repository instructions, and existing user changes. Verify the target environment, authorization, test-data namespace, observability access, and cleanup owner before sending a request or changing external state. Keep credentials, tokens, PII, and production data out of artifacts and prompts.

Expand the approved Integration Test Design into executable **test cases**. For each case, record its ID, linked `REQ-*` and `AC-*`, test point, priority, preconditions, environment, isolated data, exact steps or probe command, expected observable result, required logs/metrics/traces, rollback or cleanup, and status. Before execution, freeze the case set.

Refine a test point into more cases or add implementation-detail evidence only when that does not change acceptance semantics. A changed test point, observable result, threshold, or real-environment scope is a **Scope Delta**: stop the affected work and obtain approval through Spec/Plan. Do not change acceptance semantics to match the implementation.

## Execute probes, then real-environment cases

Run probes first for critical success, failure, and fallback paths. Use them to validate the environment, dependency chain, instrumentation, and safe test data before the full suite. Record actual commands, input, output, evidence locations, and cleanup outcomes.

After probes pass or their findings are dispositioned, execute frozen real-environment test cases one by one. Use a real request through the intended dependency chain where the Integration Test Design requires it. Record every result as `passed`, `failed`, `blocked`, or `not-run`; a HTTP success alone is not success unless it satisfies the approved observable outcome.

## Triage, repair, and regression

Apply the following disposition without changing the test case:

| Finding | Action |
|---|---|
| Blocking prerequisite: environment, data, permission, startup, or base dependency failure | Repair the prerequisite immediately, then re-run affected cases; do not treat later results as valid until it is restored. |
| Isolated business defect | Preserve evidence, continue independent cases, then return the defect to the implementation workflow for repair. |
| Safety, data pollution, security, or result-corrupting failure | Stop affected execution immediately, contain it, repair through the implementation workflow, and re-run affected cases before continuing. |

Do not modify product code in this workflow. Hand defects to `$spec-plan-to-code` with the failing case, environment/version, actual versus expected result, evidence, and regression scope. After a repair, regenerate only implementation-detail case steps when necessary; preserve frozen acceptance semantics, re-run affected cases, then run the required critical-path regression.

## Report and stop

Deliver a formal report mapping `REQ-*` → `AC-*` → test case → evidence. Include environment and version, case results, probe results, commands, real-request evidence, defects and dispositions, blocked/not-run scope, regressions, remaining risks, rollback notes, and test-data cleanup. Claim integration completion only when all mandatory cases meet the approved acceptance criteria; otherwise report the precise failed or blocked condition and the next required action.
