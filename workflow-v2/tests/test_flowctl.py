import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flowctl_lib.artifacts import verify_artifact
from flowctl_lib.authorizations import (
    begin_authorization_amendment,
    decide_authorization,
)
from flowctl_lib.errors import FlowctlError
from flowctl_lib.handoff import accept_handoff
from flowctl_lib.resume import _review_eligible_after_resume, reconcile_resume, resume_flow
from flowctl_lib.reviews import (
    begin_review, classify_process, record_process_result, repair_review_attempt,
    run_cursor_review, submit_review,
)
from flowctl_lib.snapshot import record_snapshot
from flowctl_lib.signals import record_signal
from flowctl_lib.state import initialize_state, load_state, read_consistent_state, register_artifact


def write_bound_runner(path, source):
    path.write_text(
        'import sys, json\n'
        'if "--check-capabilities" in sys.argv:\n'
        '    print(json.dumps({"local_tools":False,"implicit_indexing":False})); sys.exit(0)\n'
        + source)
    # Explicit test-only adapter registration, restored by each test's cleanup.
    from flowctl_lib.reviews import TRUSTED_ADAPTER_DIGESTS
    patch.dict(TRUSTED_ADAPTER_DIGESTS, {'cursor': TRUSTED_ADAPTER_DIGESTS['cursor'] |
               {hashlib.sha256(path.read_bytes()).hexdigest()}}).start()


def write_artifact(directory, kind, revision=1, issue="BCS-710", milestone=None,
                   upstream=None, approval_status="APPROVED", name=None,
                   target_milestones=None, milestone_dependencies=None,
                   integration_results=None, integration_scenarios=None,
                   legacy_plan=False):
    upstream = upstream or {}
    if kind == "integration" and approval_status == "APPROVED":
        approval_status = "PASSED"
    lines = [
        f"artifact_type: {kind}",
        f"issue_id: {issue}",
        f"content_revision: {revision}",
        f"status: {approval_status}",
    ]
    if milestone:
        lines.append(f"milestone_id: {milestone}")
    if kind == "roadmap":
        target_milestones = target_milestones or ["M1"]
        milestone_dependencies = milestone_dependencies or {target: [] for target in target_milestones}
        lines.append("target_milestones: " + json.dumps(target_milestones, separators=(",", ":")))
        lines.append("milestone_dependencies: " + json.dumps(milestone_dependencies, separators=(",", ":")))
    if kind == "plan" and not legacy_plan:
        integration_scenarios = integration_scenarios or {
            "schema_version": 1,
            "scenarios": [{
                "scenario_id": "TESTCASE-DEFAULT",
                "production_dependency": {"required": False},
            }],
        }
        lines.append("integration_scenarios: " + json.dumps(integration_scenarios, separators=(",", ":")))
    if integration_results is not None:
        lines.append("integration_results: " + json.dumps(integration_results, separators=(",", ":")))
    for upstream_kind, ref in upstream.items():
        lines.append(f"{upstream_kind}_revision: {ref['revision']}")
        lines.append(f"{upstream_kind}_digest: {ref['digest']}")
    body = "\n".join(lines) + "\n"
    digest = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    confirmer = "HUMAN" if kind == "requirement" else "ORCHESTRATED"
    authority = ""
    if kind != "requirement" and "requirement" in upstream:
        authority = (
            "controller_run_id: run-bcs-710\n"
            f"requirement_revision: {upstream['requirement']['revision']}\n"
            f"requirement_digest: {upstream['requirement']['digest']}\n"
            "scope_binding: test-scope\n"
        )
    approval = (
        f"status: {approval_status}\n"
        f"approved_revision: {revision}\n"
        f"approved_digest: {digest}\n"
        f"confirmer: {confirmer}\n" + authority
    )
    text = (
        "--- FLOW BODY BEGIN ---\n" + body +
        "--- FLOW BODY END ---\n"
        "--- FLOW INTEGRITY BEGIN ---\n"
        f"content_digest: {digest}\n"
        "path_rule: default\npath_source: test\nresolved_path: pending\n"
        "--- FLOW INTEGRITY END ---\n"
        "--- FLOW APPROVAL BEGIN ---\n" + approval +
        "--- FLOW APPROVAL END ---\n"
    )
    path = directory / (name or f"{kind}_{revision}.md")
    path.write_text(text)
    return path, {"revision": revision, "digest": digest}


class ArtifactTests(unittest.TestCase):
    def test_verifies_canonical_body_and_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, expected = write_artifact(Path(tmp), "requirement")
            artifact = verify_artifact(path, expected_type="requirement", expected_issue="BCS-710")
            self.assertEqual(expected["digest"], artifact["digest"])
            self.assertEqual(1, artifact["revision"])
            self.assertTrue(artifact["approval"]["valid"])

    def test_rejects_tamper_crlf_duplicate_revision_and_stale_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path, _ = write_artifact(directory, "requirement")
            path.write_text(path.read_text().replace("status: APPROVED\n", "status: CHANGED\n", 1))
            with self.assertRaisesRegex(FlowctlError, "DIGEST_MISMATCH"):
                verify_artifact(path)

            crlf, _ = write_artifact(directory, "intent", name="crlf.md")
            crlf.write_bytes(crlf.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaisesRegex(FlowctlError, "NON_CANONICAL_LINE_ENDINGS"):
                verify_artifact(crlf)

            duplicate, _ = write_artifact(directory, "intent", name="duplicate.md")
            duplicate.write_text(duplicate.read_text().replace("content_revision: 1\n", "content_revision: 1\ncontent_revision: 2\n"))
            with self.assertRaises(FlowctlError):
                verify_artifact(duplicate)

            stale, _ = write_artifact(directory, "roadmap", name="stale.md")
            stale.write_text(stale.read_text().replace("approved_revision: 1", "approved_revision: 0"))
            artifact = verify_artifact(stale)
            self.assertFalse(artifact["approval"]["valid"])

    def test_legacy_plan_without_machine_contract_remains_a_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirement, requirement_ref = write_artifact(root, "requirement")
            intent, intent_ref = write_artifact(
                root, "intent", upstream={"requirement": requirement_ref},
            )
            roadmap, roadmap_ref = write_artifact(
                root, "roadmap", upstream={
                    "requirement": requirement_ref, "intent": intent_ref,
                },
            )
            spec, spec_ref = write_artifact(
                root, "spec", milestone="M1", upstream={
                    "requirement": requirement_ref, "intent": intent_ref,
                    "roadmap": roadmap_ref,
                },
            )
            plan, _ = write_artifact(
                root, "plan", milestone="M1", legacy_plan=True, upstream={
                    "requirement": requirement_ref, "intent": intent_ref,
                    "roadmap": roadmap_ref, "spec": spec_ref,
                },
            )
            verified = verify_artifact(plan, expected_type="plan", expected_milestone="M1")
            self.assertTrue(verified["approval"]["valid"])
            self.assertIsNone(verified["integration_scenarios"])

            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            fixture = load_state(state_path)
            fixture["artifacts"] = {
                "requirement": verify_artifact(requirement),
                "intent": verify_artifact(intent),
                "roadmap": verify_artifact(roadmap),
                "spec:M1": verify_artifact(spec),
            }
            fixture["target_milestones"] = ["M1"]
            fixture["milestones"] = {"M1": {"status": "pending", "dependencies": []}}
            fixture["active_milestone"] = "M1"
            fixture["current_stage"] = "flow-plan"
            state_path.write_text(json.dumps(fixture))
            registered = register_artifact(state_path, plan, "plan", "M1", 0)
            self.assertEqual(verified["digest"], registered["artifacts"]["plan:M1"]["digest"])


class IntegrationResultsTests(unittest.TestCase):
    @staticmethod
    def authorized_production_replay_skip(scenario_id="TESTCASE-REPLAY"):
        return {
            "scenario_id": scenario_id,
            "status": "SKIPPED_AUTHORIZED_REPLAY",
            "replay_mode": "SKIP_PRODUCTION_REPLAY",
            "plan_trace": {"requires_production_data": False, "reason": "caller-forged"},
            "owner": "caller-forged",
        }

    @staticmethod
    def unaffected(scenario_id):
        return {"scenario_id": scenario_id, "production_dependency": {"required": False}}

    @staticmethod
    def production_dependent(scenario_id="TESTCASE-REPLAY"):
        return {
            "scenario_id": scenario_id,
            "production_dependency": {
                "required": True,
                "reason": "Synthetic and isolated test data cannot reproduce the production distribution.",
                "missing_assurance": "Production distribution behavior remains unverified.",
                "owner": "flow-integration",
                "remediation": "Run after SANITIZED_LOCAL_REPLAY is authorized.",
            },
        }

    @staticmethod
    def plan_contract(*scenarios):
        return {"schema_version": 1, "scenarios": list(scenarios)}

    def aggregate(self, scenarios, *plan_scenarios):
        from flowctl_lib.integration_results import aggregate_integration_results
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requirement_ref = write_artifact(root, "requirement")
            plan_path, plan_ref = write_artifact(
                root, "plan", milestone="M1", upstream={"requirement": requirement_ref},
                integration_scenarios=self.plan_contract(*plan_scenarios),
            )
            return aggregate_integration_results(scenarios, plan_path), plan_ref

    def test_production_replay_all_pass_is_passed(self):
        result, _ = self.aggregate([
            {"scenario_id": "TESTCASE-1", "status": "PASSED"},
            {"scenario_id": "TESTCASE-2", "status": "PASSED"},
        ], self.unaffected("TESTCASE-1"), self.unaffected("TESTCASE-2"))
        self.assertEqual("PASSED", result["status"])
        self.assertEqual(2, result["executed_count"])
        self.assertEqual([
            {"scenario_id": "TESTCASE-1", "status": "PASSED"},
            {"scenario_id": "TESTCASE-2", "status": "PASSED"},
        ], result["scenarios"])
        self.assertEqual([], result["gaps"])
        self.assertEqual([], result["warnings"])

    def test_production_replay_pass_plus_authorized_skip_is_defect_with_gap(self):
        result, plan_ref = self.aggregate([
            {"scenario_id": "TESTCASE-1", "status": "PASSED"},
            self.authorized_production_replay_skip(),
        ], self.unaffected("TESTCASE-1"), self.production_dependent())
        self.assertEqual("COMPLETE_WITH_DEFECT", result["status"])
        self.assertEqual(1, result["executed_count"])
        self.assertEqual(1, result["skipped_count"])
        self.assertEqual([{
            "type": "PRODUCTION_REPLAY_GAP",
            "scenario_ids": ["TESTCASE-REPLAY"],
            "missing_assurance": "Production distribution behavior remains unverified.",
            "reason": "Synthetic and isolated test data cannot reproduce the production distribution.",
            "owner": "flow-integration",
            "remediation": "Run after SANITIZED_LOCAL_REPLAY is authorized.",
            "status": "OPEN", "plan_digest": plan_ref["digest"], "plan_revision": 1,
        }], result["gaps"])

    def test_production_replay_skip_only_has_zero_executed_warning(self):
        result, _ = self.aggregate(
            [self.authorized_production_replay_skip()], self.production_dependent(),
        )
        self.assertEqual("COMPLETE_WITH_DEFECT", result["status"])
        self.assertEqual(0, result["executed_count"])
        self.assertEqual(["ZERO_EXECUTED_SCENARIOS"], result["warnings"])

    def test_production_replay_failure_and_blocker_take_precedence_over_gap(self):
        failed, _ = self.aggregate([
            self.authorized_production_replay_skip(),
            {"scenario_id": "TESTCASE-FAILED", "status": "FAILED"},
            {"scenario_id": "TESTCASE-BLOCKED", "status": "BLOCKED"},
        ], self.production_dependent(), self.unaffected("TESTCASE-FAILED"), self.unaffected("TESTCASE-BLOCKED"))
        blocked, _ = self.aggregate([
            self.authorized_production_replay_skip(),
            {"scenario_id": "TESTCASE-BLOCKED", "status": "BLOCKED"},
        ], self.production_dependent(), self.unaffected("TESTCASE-BLOCKED"))
        self.assertEqual("FAILED", failed["status"])
        self.assertEqual("BLOCKED", blocked["status"])
        self.assertEqual("PRODUCTION_REPLAY_GAP", failed["gaps"][0]["type"])
        self.assertEqual("PRODUCTION_REPLAY_GAP", blocked["gaps"][0]["type"])

    def test_production_replay_skip_requires_active_decision_and_approved_plan_trace(self):
        unauthorized = self.authorized_production_replay_skip()
        unauthorized["replay_mode"] = "SANITIZED_LOCAL_REPLAY"
        with self.assertRaisesRegex(FlowctlError, "UNAUTHORIZED_PRODUCTION_REPLAY_SKIP"):
            self.aggregate([unauthorized], self.production_dependent())

        with self.assertRaisesRegex(FlowctlError, "PRODUCTION_REPLAY_SKIP_NOT_IN_PLAN"):
            self.aggregate(
                [self.authorized_production_replay_skip()], self.unaffected("TESTCASE-REPLAY"),
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requirement_ref = write_artifact(root, "requirement")
            legacy_plan, _ = write_artifact(
                root, "plan", milestone="M1", legacy_plan=True,
                upstream={"requirement": requirement_ref},
            )
            from flowctl_lib.integration_results import aggregate_integration_results
            with self.assertRaisesRegex(FlowctlError, "PLAN_INTEGRATION_SCENARIOS_REQUIRED"):
                aggregate_integration_results(
                    [self.authorized_production_replay_skip()], legacy_plan,
                )

    def test_production_replay_results_must_match_complete_plan_scenario_set(self):
        with self.assertRaisesRegex(FlowctlError, "INTEGRATION_SCENARIO_SET_MISMATCH"):
            self.aggregate(
                [{"scenario_id": "TESTCASE-1", "status": "PASSED"}],
                self.unaffected("TESTCASE-1"), self.unaffected("TESTCASE-2"),
            )
        with self.assertRaisesRegex(FlowctlError, "INTEGRATION_SCENARIO_SET_MISMATCH"):
            self.aggregate(
                [
                    {"scenario_id": "TESTCASE-1", "status": "PASSED"},
                    {"scenario_id": "TESTCASE-EXTRA", "status": "PASSED"},
                ],
                self.unaffected("TESTCASE-1"),
            )

    def test_production_replay_gap_metadata_comes_from_approved_plan_not_result(self):
        forged = self.authorized_production_replay_skip()
        forged.update({
            "missing_assurance": "caller-forged", "remediation": "caller-forged",
        })
        result, _ = self.aggregate([forged], self.production_dependent())
        self.assertEqual("flow-integration", result["gaps"][0]["owner"])
        self.assertEqual(
            "Synthetic and isolated test data cannot reproduce the production distribution.",
            result["gaps"][0]["reason"],
        )

    def test_production_replay_summary_invariants_reject_inconsistent_counts_and_warnings(self):
        from flowctl_lib.integration_results import validate_integration_results
        passed, _ = self.aggregate(
            [{"scenario_id": "TESTCASE-1", "status": "PASSED"}],
            self.unaffected("TESTCASE-1"),
        )
        bad_count = {**passed, "executed_count": 0}
        with self.assertRaisesRegex(FlowctlError, "INVALID_INTEGRATION_RESULTS"):
            validate_integration_results(bad_count)
        bad_warning = {**passed, "warnings": ["ZERO_EXECUTED_SCENARIOS"]}
        with self.assertRaisesRegex(FlowctlError, "INVALID_INTEGRATION_RESULTS"):
            validate_integration_results(bad_warning)

        skip_only, _ = self.aggregate(
            [self.authorized_production_replay_skip()], self.production_dependent(),
        )
        with self.assertRaisesRegex(FlowctlError, "INVALID_INTEGRATION_RESULTS"):
            validate_integration_results({**skip_only, "warnings": []})

    def test_production_replay_defect_artifact_is_a_valid_final_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, requirement_ref = write_artifact(root, "requirement")
            plan_path, plan_ref = write_artifact(
                root, "plan", milestone="M1", upstream={"requirement": requirement_ref},
                integration_scenarios=self.plan_contract(self.production_dependent()),
            )
            from flowctl_lib.integration_results import aggregate_integration_results
            aggregate = aggregate_integration_results(
                [self.authorized_production_replay_skip()], plan_path,
            )
            path, _ = write_artifact(
                root, "integration", milestone="M1", upstream={"plan": plan_ref},
                approval_status="COMPLETE_WITH_DEFECT", integration_results=aggregate,
            )
            artifact = verify_artifact(path, expected_type="integration", expected_milestone="M1")
            self.assertTrue(artifact["approval"]["valid"])
            self.assertEqual(aggregate, artifact["integration_results"])

    def test_production_replay_gap_survives_final_handoff_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue_dir = root / ".ai" / "issue" / "BCS-710"
            issue_dir.mkdir(parents=True)
            state_path = issue_dir / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            decided = decide_authorization(
                state_path, "production_replay", "SKIP_PRODUCTION_REPLAY", 0,
            )

            refs = {}
            artifacts = {}
            for kind in ("requirement", "intent", "roadmap", "spec", "plan", "code"):
                upstream_names = {
                    "requirement": (),
                    "intent": ("requirement",),
                    "roadmap": ("requirement", "intent"),
                    "spec": ("requirement", "intent", "roadmap"),
                    "plan": ("requirement", "intent", "roadmap", "spec"),
                    "code": ("requirement", "intent", "roadmap", "spec", "plan"),
                }[kind]
                options = {"milestone": "M1"} if kind in {"spec", "plan", "code"} else {}
                if kind == "plan":
                    options["integration_scenarios"] = self.plan_contract(
                        self.unaffected("TESTCASE-1"), self.production_dependent(),
                    )
                path, refs[kind] = write_artifact(
                    issue_dir, kind,
                    upstream={name: refs[name] for name in upstream_names},
                    name=f"{kind}_fixture.md", **options,
                )
                key = f"{kind}:M1" if kind in {"spec", "plan", "code"} else kind
                artifacts[key] = verify_artifact(path)

            from flowctl_lib.integration_results import aggregate_integration_results
            aggregate = aggregate_integration_results([
                {"scenario_id": "TESTCASE-1", "status": "PASSED"},
                self.authorized_production_replay_skip(),
            ], artifacts["plan:M1"]["path"])
            integration_path, _ = write_artifact(
                issue_dir, "integration", milestone="M1", upstream=refs,
                approval_status="COMPLETE_WITH_DEFECT", name="integration_M1.md",
                integration_results=aggregate,
            )
            artifacts["integration:M1"] = verify_artifact(integration_path)
            valid_integration = artifacts["integration:M1"]
            forged_aggregate = json.loads(json.dumps(aggregate))
            forged_aggregate["gaps"][0]["owner"] = "caller-forged"
            forged_path, _ = write_artifact(
                issue_dir, "integration", milestone="M1", upstream=refs,
                approval_status="COMPLETE_WITH_DEFECT", name="forged-integration-M1.md",
                integration_results=forged_aggregate,
            )
            forged_integration = verify_artifact(forged_path)

            fixture_state = load_state(state_path)
            fixture_state["artifacts"] = artifacts
            fixture_state["artifact_high_water"] = {
                key: {"revision": value["revision"], "digest": value["digest"]}
                for key, value in artifacts.items()
            }
            fixture_state["target_milestones"] = ["M1"]
            fixture_state["milestones"] = {"M1": {"status": "pending", "dependencies": []}}
            fixture_state["active_milestone"] = "M1"
            fixture_state["current_stage"] = "flow-integration"
            fixture_state["pending_action"] = "handoff:integration"
            external_gap = {
                "type": "EXTERNAL_REVIEW_GAP", "artifact_key": "code:M1",
                "attempt_ids": ["cursor-1", "cursor-2", "ibrain-1", "ibrain-2"],
            }
            fixture_state["open_gaps"] = [external_gap]

            durable_gaps = [
                external_gap,
                {**aggregate["gaps"][0], "artifact_key": "integration:M1"},
            ]
            handoff_path = issue_dir / "handoff.json"
            fixture_state["artifacts"]["integration:M1"] = forged_integration
            state_path.write_text(json.dumps(fixture_state))
            forged_gaps = [
                external_gap,
                {**forged_aggregate["gaps"][0], "artifact_key": "integration:M1"},
            ]
            handoff_path.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-integration",
                "next_stage": "complete", "artifact_key": "integration:M1",
                "completion_quality": "COMPLETE_WITH_DEFECT", "open_gaps": forged_gaps,
            }))
            with self.assertRaisesRegex(FlowctlError, "INTEGRATION_PLAN_BINDING_MISMATCH"):
                accept_handoff(state_path, handoff_path, decided["state_revision"])

            fixture_state["artifacts"]["integration:M1"] = valid_integration
            state_path.write_text(json.dumps(fixture_state))
            handoff_path.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-integration",
                "next_stage": "complete", "artifact_key": "integration:M1",
                "completion_quality": "COMPLETE_WITH_DEFECT", "open_gaps": durable_gaps,
            }))
            accepted = accept_handoff(
                state_path, handoff_path, decided["state_revision"],
            )
            self.assertEqual("COMPLETE_WITH_DEFECT", accepted["completion_quality"])
            self.assertEqual(durable_gaps, accepted["open_gaps"])
            self.assertEqual(durable_gaps, load_state(state_path)["open_gaps"])

            discovery = resume_flow("BCS-710", root)
            resumed = reconcile_resume(state_path, discovery, accepted["state_revision"])
            self.assertEqual("complete", resumed["current_stage"])
            self.assertEqual(durable_gaps, resumed["open_gaps"])

    def test_production_replay_gap_survives_route_back_and_blocked_signals(self):
        for signal in ("FLOW_RUN_ROUTE_BACK", "FLOW_RUN_BLOCKED"):
            with self.subTest(signal=signal), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = root / "flow-state.json"
                initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
                decided = decide_authorization(
                    state_path, "production_replay", "SKIP_PRODUCTION_REPLAY", 0,
                )
                requirement_path, requirement_ref = write_artifact(root, "requirement")
                plan_path, _ = write_artifact(
                    root, "plan", milestone="M1", upstream={"requirement": requirement_ref},
                    integration_scenarios=self.plan_contract(
                        self.production_dependent(), self.unaffected("TESTCASE-OUTCOME"),
                    ),
                )
                from flowctl_lib.integration_results import aggregate_integration_results
                outcome = "FAILED" if signal == "FLOW_RUN_ROUTE_BACK" else "BLOCKED"
                aggregate = aggregate_integration_results(
                    [
                        self.authorized_production_replay_skip(),
                        {"scenario_id": "TESTCASE-OUTCOME", "status": outcome},
                    ], plan_path,
                )
                fixture = load_state(state_path)
                fixture["artifacts"] = {
                    "requirement": verify_artifact(requirement_path),
                    "plan:M1": verify_artifact(plan_path),
                }
                fixture["target_milestones"] = ["M1"]
                fixture["milestones"] = {"M1": {"status": "pending", "dependencies": []}}
                fixture["active_milestone"] = "M1"
                fixture["current_stage"] = "flow-integration"
                fixture["pending_action"] = "execute:integration"
                state_path.write_text(json.dumps(fixture))

                payload = {
                    "schema_version": 1, "signal": signal, "issue_id": "BCS-710",
                    "run_id": "run-bcs-710", "stage": "flow-integration",
                    "cause": "integration not successful", "evidence": "integration report digest",
                    "resume_condition": "repair or restore environment",
                    "integration_results": aggregate,
                }
                if signal == "FLOW_RUN_ROUTE_BACK":
                    payload.update({"owner_stage": "flow-code", "next_stage": "flow-code"})

                missing_results = dict(payload)
                missing_results.pop("integration_results")
                missing_path = root / "missing-results-signal.json"
                missing_path.write_text(json.dumps(missing_results))
                with self.assertRaisesRegex(FlowctlError, "SIGNAL_SCHEMA_INVALID"):
                    record_signal(state_path, missing_path, decided["state_revision"])

                self_reported = dict(missing_results, open_gaps=aggregate["gaps"])
                self_reported_path = root / "self-reported-gap-signal.json"
                self_reported_path.write_text(json.dumps(self_reported))
                with self.assertRaisesRegex(FlowctlError, "SIGNAL_SCHEMA_INVALID"):
                    record_signal(state_path, self_reported_path, decided["state_revision"])

                unauthorized = json.loads(json.dumps(fixture))
                replay = unauthorized["authorizations"]["production_replay"]
                replay["decision"] = "SANITIZED_LOCAL_REPLAY"
                replay["mode"] = "SANITIZED_LOCAL_REPLAY"
                state_path.write_text(json.dumps(unauthorized))
                unauthorized_path = root / "unauthorized-signal.json"
                unauthorized_path.write_text(json.dumps(payload))
                with self.assertRaisesRegex(
                    FlowctlError, "UNAUTHORIZED_PRODUCTION_REPLAY_SKIP",
                ):
                    record_signal(
                        state_path, unauthorized_path, decided["state_revision"],
                    )
                state_path.write_text(json.dumps(fixture))

                malformed_results = {}
                forged = json.loads(json.dumps(aggregate))
                forged["gaps"][0]["owner"] = "caller-forged"
                malformed_results["forged"] = forged
                subset = json.loads(json.dumps(aggregate))
                subset["gaps"] = []
                malformed_results["subset"] = subset
                extra = json.loads(json.dumps(aggregate))
                extra["gaps"].append(json.loads(json.dumps(extra["gaps"][0])))
                malformed_results["extra"] = extra
                for name, integration_results in malformed_results.items():
                    invalid = {**payload, "integration_results": integration_results}
                    invalid_path = root / f"{name}-results-signal.json"
                    invalid_path.write_text(json.dumps(invalid))
                    with self.assertRaises(FlowctlError):
                        record_signal(
                            state_path, invalid_path, decided["state_revision"],
                        )

                wrong_status = aggregate_integration_results([
                    self.authorized_production_replay_skip(),
                    {
                        "scenario_id": "TESTCASE-OUTCOME",
                        "status": "BLOCKED" if outcome == "FAILED" else "FAILED",
                    },
                ], plan_path)
                wrong_status_path = root / "wrong-status-signal.json"
                wrong_status_path.write_text(json.dumps({
                    **payload, "integration_results": wrong_status,
                }))
                with self.assertRaisesRegex(
                    FlowctlError, "INTEGRATION_SIGNAL_STATUS_MISMATCH",
                ):
                    record_signal(
                        state_path, wrong_status_path, decided["state_revision"],
                    )
                payload_path = root / "signal.json"
                payload_path.write_text(json.dumps(payload))
                recorded = record_signal(
                    state_path, payload_path, decided["state_revision"],
                )
                state = load_state(state_path)
                self.assertEqual(aggregate["gaps"], state["open_gaps"])
                self.assertEqual(
                    "flow-code" if signal == "FLOW_RUN_ROUTE_BACK" else "flow-integration",
                    recorded["current_stage"],
                )
                discovery = {"issue_id": "BCS-710", "valid_artifacts": {},
                             "deepest_valid_stage": None, "invalid_candidates": []}
                resumed = reconcile_resume(
                    state_path, discovery, recorded["state_revision"],
                )
                self.assertEqual(aggregate["gaps"], resumed["open_gaps"])

    def test_integration_failure_signal_schema_requires_complete_results_not_open_gaps(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT / "schemas" / "signal.schema.json").read_text())
        result, _ = self.aggregate([
            self.authorized_production_replay_skip(),
            {"scenario_id": "TESTCASE-FAILED", "status": "FAILED"},
        ], self.production_dependent(), self.unaffected("TESTCASE-FAILED"))
        signal = {
            "schema_version": 1, "signal": "FLOW_RUN_ROUTE_BACK",
            "issue_id": "BCS-710", "run_id": "run-bcs-710",
            "stage": "flow-integration", "cause": "failed",
            "evidence": "integration report digest", "resume_condition": "repair",
            "owner_stage": "flow-code", "next_stage": "flow-code",
            "integration_results": result,
        }
        validator = Draft202012Validator(schema)
        self.assertTrue(validator.is_valid(signal))
        without_results = dict(signal)
        without_results.pop("integration_results")
        self.assertFalse(validator.is_valid(without_results))
        self_reported = {**without_results, "open_gaps": result["gaps"]}
        self.assertFalse(validator.is_valid(self_reported))
        wrong_status = json.loads(json.dumps(signal))
        wrong_status["integration_results"]["status"] = "BLOCKED"
        self.assertFalse(validator.is_valid(wrong_status))


class StateTests(unittest.TestCase):
    def test_register_is_cas_monotonic_idempotent_and_invalidates_downstream(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            requirement, req = write_artifact(root, "requirement")
            state = register_artifact(state_path, requirement, "requirement", None, 0)
            self.assertEqual(1, state["state_revision"])
            state = register_artifact(state_path, requirement, "requirement", None, 1)
            self.assertEqual(1, state["state_revision"])
            with self.assertRaisesRegex(FlowctlError, "STATE_CONFLICT"):
                register_artifact(state_path, requirement, "requirement", None, 0)

            handoff = root / "state-handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-requirement",
                "next_stage": "flow-intent", "artifact_key": "requirement",
            }))
            accepted = accept_handoff(state_path, handoff, state["state_revision"])
            intent, intent_ref = write_artifact(root, "intent", upstream={"requirement": req})
            state = register_artifact(state_path, intent, "intent", None, accepted["state_revision"])
            self.assertIn("intent", state["artifacts"])
            newer, _ = write_artifact(root, "requirement", revision=2, name="requirement_2.md")
            state = register_artifact(state_path, newer, "requirement", None, state["state_revision"])
            self.assertNotIn("intent", state["artifacts"])
            self.assertTrue(state["invalidations"])

            older, _ = write_artifact(root, "requirement", revision=1, name="old.md")
            with self.assertRaisesRegex(FlowctlError, "REVISION_NOT_MONOTONIC"):
                register_artifact(state_path, older, "requirement", None, state["state_revision"])
            events = [json.loads(line) for line in state_path.with_name("flow-events.jsonl").read_text().splitlines()]
            self.assertEqual([1, 2, 3, 4], [event["seq"] for event in events])

    def test_incomplete_transaction_is_recovered_under_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            requirement, _ = write_artifact(root, "requirement")
            state = register_artifact(state_path, requirement, "requirement", None, 0)
            recovered = json.loads(json.dumps(state))
            recovered["state_revision"] = 2
            recovered["pending_action"] = "recovered"
            event = {
                "seq": 2, "at": "2026-09-14T00:00:00+00:00", "event": "RECOVERY_TEST",
                "previous_event_digest": state["event_head"],
            }
            canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            event["event_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
            recovered["event_head"] = event["event_digest"]
            transaction = state_path.with_suffix(state_path.suffix + ".txn.json")
            events_path = state_path.with_name("flow-events.jsonl")
            offset = events_path.stat().st_size
            transaction.write_text(json.dumps({"state": recovered, "event": event, "event_log_offset": offset}))
            result = read_consistent_state(state_path)
            self.assertEqual(2, result["state_revision"])
            self.assertEqual("recovered", result["pending_action"])
            self.assertFalse(transaction.exists())

    def test_torn_event_tail_is_recovered_from_transaction_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            requirement, _ = write_artifact(root, "requirement")
            state = register_artifact(state_path, requirement, "requirement", None, 0)
            recovered = json.loads(json.dumps(state))
            recovered["state_revision"] = 2
            event = {
                "seq": 2, "at": "2026-09-14T00:00:00+00:00", "event": "TORN_TEST",
                "previous_event_digest": state["event_head"],
            }
            canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            event["event_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
            recovered["event_head"] = event["event_digest"]
            events_path = state_path.with_name("flow-events.jsonl")
            offset = events_path.stat().st_size
            transaction = state_path.with_suffix(state_path.suffix + ".txn.json")
            transaction.write_text(json.dumps({"state": recovered, "event": event, "event_log_offset": offset}))
            with events_path.open("ab") as handle:
                handle.write((json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode()[:30])
            result = read_consistent_state(state_path)
            self.assertEqual(2, result["state_revision"])
            lines = events_path.read_text().splitlines()
            self.assertEqual(2, len(lines))
            self.assertEqual(event["event_digest"], json.loads(lines[-1])["event_digest"])


class AuthorizationTests(unittest.TestCase):
    def _write_schema_v1_state(self, root, *, with_event=False):
        state_path = root / "flow-state.json"
        state = {
            "schema_version": 1,
            "issue_id": "BCS-710",
            "issue_provenance": "HUMAN_PROVIDED",
            "run_id": "run-bcs-710",
            "controller_path": str(state_path),
            "state_revision": 0,
            "repo_root": str(root),
            "worktree_path": str(root),
            "branch": "feature-BCS-710-flowctl",
            "current_stage": "flow-spec",
            "pending_action": "human:existing-pause",
            "pending_signal": {"signal": "FLOW_RUN_HUMAN_GATE", "gate": "existing"},
            "artifacts": {"requirement": {"digest": "sha256:preserved"}},
            "reviews": {"attempts": {"review-1": {"status": "PASSED"}}, "lanes": {}},
            "snapshots": {},
            "coder_agent": {},
            "open_gaps": [],
            "target_milestones": [],
            "milestones": {},
            "active_milestone": None,
            "invalidations": [],
            "invalidated_checkpoints": {},
            "artifact_high_water": {},
            "route_back_context": None,
            "created_at": "2026-09-15T00:00:00+00:00",
            "updated_at": "2026-09-15T00:00:00+00:00",
            "event_head": None,
        }
        if with_event:
            event = {
                "seq": 1,
                "at": "2026-09-15T00:00:00+00:00",
                "event": "EXISTING_EVENT",
                "previous_event_digest": None,
                "preserved": True,
            }
            canonical = json.dumps(
                event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            event["event_digest"] = "sha256:" + hashlib.sha256(canonical).hexdigest()
            state["state_revision"] = 1
            state["event_head"] = event["event_digest"]
            state_path.with_name("flow-events.jsonl").write_text(
                json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
            )
        state_path.write_text(json.dumps(state))
        return state_path, state

    def test_authorization_status_migrates_schema_v1_and_preserves_state_and_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path, legacy = self._write_schema_v1_state(Path(tmp), with_event=True)

            state = read_consistent_state(state_path)

            self.assertEqual(2, state["schema_version"])
            self.assertEqual(2, state["state_revision"])
            for field in ("artifacts", "reviews", "pending_action", "pending_signal"):
                self.assertEqual(legacy[field], state[field])
            self.assertEqual(
                {"external_review", "production_replay"}, set(state["authorizations"])
            )
            self.assertEqual(
                {"PENDING"},
                {authorization["status"] for authorization in state["authorizations"].values()},
            )
            events = [
                json.loads(line)
                for line in state_path.with_name("flow-events.jsonl").read_text().splitlines()
            ]
            self.assertEqual(["EXISTING_EVENT", "STATE_SCHEMA_MIGRATED"], [e["event"] for e in events])
            self.assertEqual(events[0]["event_digest"], events[1]["previous_event_digest"])
            self.assertEqual(events[1]["event_digest"], state["event_head"])

    def test_authorization_mutation_migrates_schema_v1_before_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path, _ = self._write_schema_v1_state(Path(tmp))

            state = decide_authorization(state_path, "external_review", "GRANTED", 0)

            self.assertEqual(2, state["schema_version"])
            self.assertEqual(2, state["state_revision"])
            self.assertEqual("GRANTED", state["authorizations"]["external_review"]["status"])
            events = [
                json.loads(line)["event"]
                for line in state_path.with_name("flow-events.jsonl").read_text().splitlines()
            ]
            self.assertEqual(["STATE_SCHEMA_MIGRATED", "AUTHORIZATION_DECIDED"], events)

    def test_authorization_existing_schema_v1_admission_mismatch_does_not_migrate(self):
        cases = ("issue", "repo", "worktree", "branch")
        for mismatch in cases:
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                state_path, legacy = self._write_schema_v1_state(root, with_event=True)
                expected_root = root
                issue = legacy["issue_id"]
                branch = legacy["branch"]
                if mismatch == "issue":
                    issue = "BCS-711"
                    branch = "feature-BCS-711-flowctl"
                elif mismatch == "repo":
                    legacy["repo_root"] = str(root / "different-repo")
                    state_path.write_text(json.dumps(legacy))
                elif mismatch == "worktree":
                    expected_root = root / "different-worktree"
                else:
                    branch = "feature-BCS-710-other"
                controller_before = state_path.read_bytes()
                events_path = state_path.with_name("flow-events.jsonl")
                events_before = events_path.read_bytes()

                with self.assertRaisesRegex(
                    FlowctlError, "ISSUE_MISMATCH|CONTROLLER_ADMISSION_MISMATCH"
                ):
                    initialize_state(state_path, issue, expected_root, branch)

                self.assertEqual(controller_before, state_path.read_bytes())
                self.assertEqual(events_before, events_path.read_bytes())
                self.assertEqual(1, json.loads(state_path.read_text())["state_revision"])
                self.assertFalse(state_path.with_suffix(state_path.suffix + ".txn.json").exists())

    def test_authorization_first_decisions_and_identical_idempotence(self):
        cases = (
            ("external_review", "GRANTED", "GRANTED"),
            ("external_review", "DENIED", "DENIED"),
            ("production_replay", "SANITIZED_LOCAL_REPLAY", "GRANTED"),
            ("production_replay", "SKIP_PRODUCTION_REPLAY", "GRANTED"),
        )
        for kind, decision, expected_status in cases:
            with self.subTest(kind=kind, decision=decision), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = root / "flow-state.json"
                initial = initialize_state(
                    state_path, "BCS-710", root, "feature-BCS-710-flowctl"
                )

                decided = decide_authorization(
                    state_path, kind, decision, initial["state_revision"]
                )
                authorization = decided["authorizations"][kind]
                UUID(authorization["authorization_id"])
                self.assertEqual(1, authorization["revision"])
                self.assertEqual(expected_status, authorization["status"])
                self.assertEqual(decision, authorization["decision"])
                revision = decided["state_revision"]

                repeated = decide_authorization(state_path, kind, decision, revision)
                self.assertEqual(revision, repeated["state_revision"])
                self.assertEqual(authorization, repeated["authorizations"][kind])

    def test_authorization_changed_decision_requires_amendment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            granted = decide_authorization(state_path, "external_review", "GRANTED", 0)

            with self.assertRaisesRegex(FlowctlError, "AUTHORIZATION_AMENDMENT_REQUIRED"):
                decide_authorization(
                    state_path, "external_review", "DENIED", granted["state_revision"]
                )

    def test_external_review_scope_is_part_of_decision_idempotence_and_amendment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            spec_only = {"decision": "GRANTED", "allowed_stages": ["flow-spec"]}
            granted = decide_authorization(state_path, "external_review", spec_only, 0)
            authorization = granted["authorizations"]["external_review"]
            self.assertEqual(["flow-spec"], authorization["allowed_stages"])
            old_id = authorization["authorization_id"]
            authorization["bindings"].append({
                "binding_id": "binding-direct-spec",
                "authorization_id": old_id,
                "authorization_revision": 1,
                "status": "BOUND",
            })
            state_path.write_text(json.dumps(granted))

            repeated = decide_authorization(
                state_path, "external_review", spec_only, granted["state_revision"]
            )
            self.assertEqual(granted["state_revision"], repeated["state_revision"])

            plan_only = {"decision": "GRANTED", "allowed_stages": ["flow-plan"]}
            with self.assertRaisesRegex(FlowctlError, "AUTHORIZATION_AMENDMENT_REQUIRED"):
                decide_authorization(
                    state_path, "external_review", plan_only, repeated["state_revision"]
                )
            pending = begin_authorization_amendment(
                state_path, "external_review", plan_only, repeated["state_revision"]
            )
            self.assertEqual(plan_only, pending["authorizations"]["external_review"]["proposed_decision"])
            self.assertEqual(
                "INVALIDATED",
                pending["authorizations"]["external_review"]["bindings"][0]["status"],
            )
            amended = decide_authorization(
                state_path, "external_review", plan_only, pending["state_revision"]
            )
            current = amended["authorizations"]["external_review"]
            self.assertEqual(["flow-plan"], current["allowed_stages"])
            self.assertNotEqual(old_id, current["authorization_id"])
            self.assertEqual(2, current["revision"])
            self.assertEqual("INVALIDATED", current["bindings"][0]["status"])
            self.assertEqual(["flow-spec"], current["history"][0]["allowed_stages"])

    def test_external_review_denial_and_invalid_scopes_are_structured(self):
        invalid_scopes = ([], ["flow-spec", "flow-spec"], ["flow-integration"],
                          "flow-spec", [True])
        for index, allowed_stages in enumerate(invalid_scopes):
            with self.subTest(allowed_stages=allowed_stages), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = root / "flow-state.json"
                initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
                with self.assertRaisesRegex(FlowctlError, "INVALID_AUTHORIZATION_DECISION"):
                    decide_authorization(
                        state_path, "external_review",
                        {"decision": "DENIED", "allowed_stages": allowed_stages}, 0,
                    )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            denied = {"decision": "DENIED", "allowed_stages": ["flow-code"]}
            state = decide_authorization(state_path, "external_review", denied, 0)
            self.assertEqual(["flow-code"], state["authorizations"]["external_review"]["allowed_stages"])
            repeated = decide_authorization(
                state_path, "external_review", denied, state["state_revision"]
            )
            self.assertEqual(state["state_revision"], repeated["state_revision"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            with self.assertRaisesRegex(FlowctlError, "INVALID_AUTHORIZATION_DECISION"):
                decide_authorization(
                    state_path, "production_replay",
                    {"decision": "SKIP_PRODUCTION_REPLAY", "allowed_stages": ["flow-spec"]}, 0,
                )

    def test_authorization_amendment_creates_new_revision_and_invalidates_old_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            granted = decide_authorization(
                state_path, "production_replay", "SANITIZED_LOCAL_REPLAY", 0
            )
            old = granted["authorizations"]["production_replay"]
            old_id = old["authorization_id"]
            old.setdefault("bindings", []).append({
                "binding_id": "binding-1",
                "authorization_id": old_id,
                "authorization_revision": 1,
                "status": "ACTIVE",
            })
            state_path.write_text(json.dumps(granted))

            pending = begin_authorization_amendment(
                state_path,
                "production_replay",
                "SKIP_PRODUCTION_REPLAY",
                granted["state_revision"],
            )
            self.assertEqual(
                "AMENDMENT_PENDING",
                pending["authorizations"]["production_replay"]["status"],
            )
            amended = decide_authorization(
                state_path,
                "production_replay",
                "SKIP_PRODUCTION_REPLAY",
                pending["state_revision"],
            )
            authorization = amended["authorizations"]["production_replay"]
            self.assertNotEqual(old_id, authorization["authorization_id"])
            self.assertEqual(2, authorization["revision"])
            self.assertEqual("GRANTED", authorization["status"])
            self.assertEqual("INVALIDATED", authorization["bindings"][0]["status"])
            self.assertEqual(old_id, authorization["history"][0]["authorization_id"])

    def test_authorization_identity_drift_invalidates_before_changed_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            granted = decide_authorization(state_path, "external_review", "GRANTED", 0)
            granted["run_id"] = "run-bcs-710-replacement"
            state_path.write_text(json.dumps(granted))

            invalidated = begin_authorization_amendment(
                state_path, "external_review", "DENIED", granted["state_revision"]
            )

            authorization = invalidated["authorizations"]["external_review"]
            self.assertEqual("INVALIDATED", authorization["status"])
            self.assertEqual("IDENTITY_DRIFT", authorization["invalidation_reason"])
            self.assertNotIn("proposed_decision", authorization)
            self.assertEqual(
                authorization,
                load_state(state_path)["authorizations"]["external_review"],
            )

    def test_authorization_hard_exclusions_cannot_be_relaxed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            granted = decide_authorization(state_path, "external_review", "GRANTED", 0)
            before = json.loads(state_path.read_text())

            with self.assertRaisesRegex(FlowctlError, "AUTHORIZATION_HARD_EXCLUSION"):
                begin_authorization_amendment(
                    state_path,
                    "external_review",
                    {"decision": "GRANTED", "exclusions": []},
                    granted["state_revision"],
                )

            self.assertEqual(before, json.loads(state_path.read_text()))

    def test_authorization_load_rejects_tampered_schema_v2_safety_invariants(self):
        cases = (
            (
                "external hard exclusion removed",
                lambda state: state["authorizations"]["external_review"]["exclusions"].remove(
                    "secrets"
                ),
            ),
            (
                "production hard exclusion removed",
                lambda state: state["authorizations"]["production_replay"]["exclusions"].remove(
                    "raw_production_data"
                ),
            ),
            (
                "non-string hard exclusion",
                lambda state: state["authorizations"]["external_review"]["exclusions"].__setitem__(
                    0, {"name": "credentials"}
                ),
            ),
            (
                "raw persistence allowed",
                lambda state: state["authorizations"]["production_replay"].update(
                    raw_persistence="GRANTED"
                ),
            ),
            (
                "external transmission allowed",
                lambda state: state["authorizations"]["production_replay"].update(
                    external_model_transmission="GRANTED"
                ),
            ),
            (
                "git tracking allowed",
                lambda state: state["authorizations"]["production_replay"].update(
                    git_tracking="GRANTED"
                ),
            ),
            (
                "cleanup disabled",
                lambda state: state["authorizations"]["production_replay"].update(
                    cleanup_required=False
                ),
            ),
            (
                "unknown status",
                lambda state: state["authorizations"]["external_review"].update(
                    status="BYPASSED"
                ),
            ),
            (
                "unknown replay mode",
                lambda state: state["authorizations"]["production_replay"].update(
                    mode="RAW_REPLAY"
                ),
            ),
            (
                "boolean revision",
                lambda state: state["authorizations"]["external_review"].update(revision=True),
            ),
            (
                "pending with an authorization id",
                lambda state: state["authorizations"]["external_review"].update(
                    authorization_id="ba271f25-52bd-4ce0-b7df-72869ae5db6e"
                ),
            ),
            (
                "pending with a decision timestamp",
                lambda state: state["authorizations"]["external_review"].update(
                    decided_at="2026-09-16T00:00:00+00:00"
                ),
            ),
        )
        for name, tamper in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = root / "flow-state.json"
                state = initialize_state(
                    state_path, "BCS-710", root, "feature-BCS-710-flowctl"
                )
                tamper(state)
                state_path.write_text(json.dumps(state))

                with self.assertRaisesRegex(FlowctlError, "INVALID_CONTROLLER"):
                    load_state(state_path)

    def test_authorization_load_rejects_invalid_active_id_and_state_field_combinations(self):
        cases = (
            (
                "invalid active uuid",
                lambda authorization: authorization.update(authorization_id="not-a-uuid"),
            ),
            (
                "active zero revision",
                lambda authorization: authorization.update(revision=0),
            ),
            (
                "granted with denied decision",
                lambda authorization: authorization.update(decision="DENIED"),
            ),
            (
                "amendment without a proposal",
                lambda authorization: (
                    authorization.update(status="AMENDMENT_PENDING"),
                    authorization.pop("proposed_decision", None),
                ),
            ),
            (
                "active decision with invalidation fields",
                lambda authorization: authorization.update(
                    invalidated_at="2026-09-16T00:00:00+00:00",
                    invalidation_reason="IDENTITY_DRIFT",
                ),
            ),
        )
        for name, tamper in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = root / "flow-state.json"
                initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
                state = decide_authorization(state_path, "external_review", "GRANTED", 0)
                tamper(state["authorizations"]["external_review"])
                state_path.write_text(json.dumps(state))

                with self.assertRaisesRegex(FlowctlError, "INVALID_CONTROLLER"):
                    load_state(state_path)

    def test_authorization_load_rejects_unhashable_and_boolean_enum_values(self):
        for field in ("status", "decision", "proposed_decision"):
            for malformed in ({"value": "GRANTED"}, ["GRANTED"], True):
                with (
                    self.subTest(field=field, malformed_type=type(malformed).__name__),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    root = Path(tmp)
                    state_path = root / "flow-state.json"
                    initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
                    state = decide_authorization(state_path, "external_review", "GRANTED", 0)
                    if field == "proposed_decision":
                        state = begin_authorization_amendment(
                            state_path, "external_review", "DENIED", state["state_revision"]
                        )
                    state["authorizations"]["external_review"][field] = malformed
                    state_path.write_text(json.dumps(state))

                    with self.assertRaisesRegex(FlowctlError, "INVALID_CONTROLLER"):
                        load_state(state_path)


class ResumeTests(unittest.TestCase):
    @staticmethod
    def _write_resume_prefix(root, *, integration_scenarios=None, legacy_plan=False):
        issue_dir = root / ".ai" / "issue" / "BCS-710"
        issue_dir.mkdir(parents=True)
        refs = {}
        paths = {}
        dependencies = {
            "requirement": (),
            "intent": ("requirement",),
            "roadmap": ("requirement", "intent"),
            "spec": ("requirement", "intent", "roadmap"),
            "plan": ("requirement", "intent", "roadmap", "spec"),
            "code": ("requirement", "intent", "roadmap", "spec", "plan"),
        }
        for kind in dependencies:
            options = {"milestone": "M1"} if kind in {"spec", "plan", "code"} else {}
            if kind == "plan":
                options.update({
                    "legacy_plan": legacy_plan,
                    "integration_scenarios": integration_scenarios,
                })
            paths[kind], refs[kind] = write_artifact(
                issue_dir, kind, upstream={name: refs[name] for name in dependencies[kind]},
                name=f"{kind}_fixture.md", **options,
            )
        return issue_dir, paths, refs

    def test_legacy_clean_integration_chain_resumes_without_replay_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue_dir, _, refs = self._write_resume_prefix(root, legacy_plan=True)
            integration, _ = write_artifact(
                issue_dir, "integration", milestone="M1", upstream=refs,
                name="integration_M1.md",
            )
            state_path = issue_dir / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            discovery = resume_flow("BCS-710", root)
            self.assertIn("integration:M1", discovery["valid_artifacts"])
            resumed = reconcile_resume(state_path, discovery, 0)
            self.assertEqual("complete", resumed["current_stage"])
            self.assertEqual([], resumed["open_gaps"])
            self.assertEqual(str(integration.resolve()), resumed["artifacts"]["integration:M1"]["path"])

    def test_resume_rejects_integration_result_not_exactly_bound_to_its_plan(self):
        production_dependency = IntegrationResultsTests.production_dependent()
        contract = IntegrationResultsTests.plan_contract(
            IntegrationResultsTests.unaffected("TESTCASE-1"), production_dependency,
        )
        mutations = {
            "forged-owner": lambda result: result["gaps"][0].update({"owner": "caller-forged"}),
            "forged-reason": lambda result: result["gaps"][0].update({"reason": "caller-forged"}),
            "missing-scenario": lambda result: (
                result["scenarios"].pop(0),
                result.update({"executed_count": 0, "warnings": ["ZERO_EXECUTED_SCENARIOS"]}),
            ),
            "extra-scenario": lambda result: (
                result["scenarios"].append({"scenario_id": "TESTCASE-EXTRA", "status": "PASSED"}),
                result.update({"executed_count": 2}),
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                issue_dir, paths, refs = self._write_resume_prefix(
                    root, integration_scenarios=contract,
                )
                from flowctl_lib.integration_results import aggregate_integration_results
                result = aggregate_integration_results([
                    {"scenario_id": "TESTCASE-1", "status": "PASSED"},
                    IntegrationResultsTests.authorized_production_replay_skip(),
                ], paths["plan"])
                mutate(result)
                integration, _ = write_artifact(
                    issue_dir, "integration", milestone="M1", upstream=refs,
                    approval_status="COMPLETE_WITH_DEFECT",
                    name="integration_M1.md", integration_results=result,
                )
                discovery = resume_flow("BCS-710", root)
                self.assertNotIn("integration:M1", discovery["valid_artifacts"])
                self.assertIn(
                    str(integration.resolve()),
                    {item["path"] for item in discovery["invalid_candidates"]},
                )

    def test_reconcile_revalidates_forged_integration_and_active_replay_authorization(self):
        contract = IntegrationResultsTests.plan_contract(
            IntegrationResultsTests.unaffected("TESTCASE-1"),
            IntegrationResultsTests.production_dependent(),
        )
        for case in ("forged", "unauthorized"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                issue_dir, paths, refs = self._write_resume_prefix(
                    root, integration_scenarios=contract,
                )
                from flowctl_lib.integration_results import aggregate_integration_results
                result = aggregate_integration_results([
                    {"scenario_id": "TESTCASE-1", "status": "PASSED"},
                    IntegrationResultsTests.authorized_production_replay_skip(),
                ], paths["plan"])
                if case == "forged":
                    result["gaps"][0]["owner"] = "caller-forged"
                integration, _ = write_artifact(
                    issue_dir, "integration", milestone="M1", upstream=refs,
                    approval_status="COMPLETE_WITH_DEFECT",
                    name="integration_M1.md", integration_results=result,
                )
                artifacts = {
                    (f"{kind}:M1" if kind in {"spec", "plan", "code"} else kind):
                    verify_artifact(path)
                    for kind, path in paths.items()
                }
                artifacts["integration:M1"] = verify_artifact(integration)
                state_path = issue_dir / "flow-state.json"
                initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
                revision = 0
                if case == "forged":
                    authorized = decide_authorization(
                        state_path, "production_replay", "SKIP_PRODUCTION_REPLAY", revision,
                    )
                    revision = authorized["state_revision"]
                discovery = {
                    "issue_id": "BCS-710", "valid_artifacts": artifacts,
                    "deepest_valid_stage": "flow-integration",
                    "invalid_candidates": [],
                }
                resumed = reconcile_resume(state_path, discovery, revision)
                self.assertNotIn("integration:M1", resumed["artifacts"])
                self.assertNotEqual("complete", resumed["current_stage"])
                self.assertEqual([], resumed["open_gaps"])

    def test_resumes_from_explicit_arbitrary_node_and_rejects_unbound_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue_dir = root / ".ai" / "issue" / "BCS-710"
            issue_dir.mkdir(parents=True)
            requirement, req = write_artifact(issue_dir, "requirement")
            intent, intent_ref = write_artifact(issue_dir, "intent", upstream={"requirement": req})
            roadmap, roadmap_ref = write_artifact(
                issue_dir, "roadmap", upstream={"requirement": req, "intent": intent_ref}
            )
            spec, _ = write_artifact(
                issue_dir, "spec", milestone="M1",
                upstream={"requirement": req, "intent": intent_ref, "roadmap": roadmap_ref},
            )
            inputs = root / "inputs.json"
            inputs.write_text(json.dumps({
                "requirement": str(requirement), "intent": str(intent),
                "roadmap": str(roadmap), "spec:M1": str(spec),
            }))
            result = resume_flow("BCS-710", root, inputs_path=inputs)
            self.assertEqual("flow-spec", result["deepest_valid_stage"])
            self.assertEqual("flow-plan", result["next_stage"])
            state_path = root / "flow-state.json"
            initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            state = reconcile_resume(state_path, result, 0)
            self.assertEqual("flow-spec", state["current_stage"])
            self.assertEqual("M1", state["active_milestone"])
            self.assertEqual("review:gpt", state["pending_action"])
            self.assertEqual({"requirement", "intent", "roadmap", "spec:M1"}, set(state["artifacts"]))

            unbound_root = root / "unbound"
            unbound_root.mkdir()
            lone_spec, _ = write_artifact(unbound_root, "spec", milestone="M1")
            lone_inputs = root / "lone.json"
            lone_inputs.write_text(json.dumps({"spec:M1": str(lone_spec)}))
            result = resume_flow("BCS-710", unbound_root, inputs_path=lone_inputs)
            self.assertEqual("flow-requirement", result["next_stage"])
            self.assertEqual("UNBOUND_ARTIFACT", result["invalid_candidates"][0]["code"])

    def test_equal_revision_different_digest_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, _ = write_artifact(root, "requirement", name="requirement_a.md")
            second, _ = write_artifact(root, "requirement", approval_status="READY_FOR_INTENT", name="requirement_b.md")
            inputs = root / "inputs.json"
            inputs.write_text(json.dumps({"requirement": [str(first), str(second)]}))
            with self.assertRaisesRegex(FlowctlError, "AMBIGUOUS_CHECKPOINT"):
                resume_flow("BCS-710", root, inputs_path=inputs)


class ReviewAndHandoffTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
    def test_review_round1_invalid_report_never_persists_lure(self):
        for report_fields in ({'extra':'LURE_MUST_NOT_PERSIST'}, {'findings':[{'summary':'LURE_MUST_NOT_PERSIST'}]},
                              {'status':['LURE_MUST_NOT_PERSIST']}):
            with self.subTest(report_fields=report_fields), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = self._state_with_spec(root)
                state = load_state(state_path)
                gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
                report = root / 'gpt.json'
                report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
                done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
                prompt = root / 'prompt.txt'
                prompt.write_text('Review spec_1.md')
                payload = {'status':'PASSED', 'findings':[], 'reviewed_digest':gpt['artifact_digest'], **report_fields}
                stdout = 'FLOW_REVIEW_REPORT_BEGIN\n' + json.dumps(payload) + '\nFLOW_REVIEW_REPORT_END'
                with patch('flowctl_lib.reviews._run_bound_package', return_value=(0, stdout, '', False)):
                    result = run_cursor_review(state_path, 'spec:M1', prompt, root / 'unused.py', 'fake', 'high', 5, done['state_revision'])
                self.assertEqual(result['classification'], 'UNCLASSIFIED')
                for path in (root / 'reviews').glob('*'):
                    self.assertNotIn('LURE_MUST_NOT_PERSIST', path.read_text())
                self.assertFalse(list((root / 'reviews').glob('*.report.json')))

    def test_review_round1_valid_report_credentials_redacted_before_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
            done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
            prompt = root / 'prompt.txt'
            prompt.write_text('Review spec_1.md')
            payload = {'status':'FAILED', 'reviewed_digest':gpt['artifact_digest'], 'findings':[{
                'id':'F-1', 'severity':'HIGH', 'summary':'credential exposure', 'blocking_status':'BLOCKING',
                'recurrence_key':'credential', 'evidence':'{"password":"LURE_CREDENTIAL"} token=LURE_TOKEN authorization: Bearer LURE_BEARER'}]}
            stdout = 'FLOW_REVIEW_REPORT_BEGIN\n' + json.dumps(payload) + '\nFLOW_REVIEW_REPORT_END'
            with patch('flowctl_lib.reviews._run_bound_package', return_value=(0, stdout, '', False)):
                result = run_cursor_review(state_path, 'spec:M1', prompt, root / 'unused.py', 'fake', 'high', 5, done['state_revision'])
            self.assertEqual(result['status'], 'FAILED')
            for path in [state_path, *(root / 'reviews').glob('*')]:
                self.assertNotIn('LURE_CREDENTIAL', path.read_text())
                self.assertNotIn('LURE_TOKEN', path.read_text())
                self.assertNotIn('LURE_BEARER', path.read_text())
            self.assertIn('[REDACTED]', Path(result['report_path']).read_text())

    def test_review_bound_process_evidence_records_digests_not_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
            done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
            prompt = root / 'prompt.txt'
            prompt.write_text('Review spec_1.md')
            with patch('flowctl_lib.reviews._run_bound_package', return_value=(2, 'private echoed material', '', False)):
                result = run_cursor_review(state_path, 'spec:M1', prompt, root / 'unused.py', 'fake', 'high', 5, done['state_revision'])
            evidence = Path(result['evidence_path']).read_text()
            self.assertNotIn('private echoed material', evidence)
            self.assertIn('stdout_digest', evidence)

    def test_unknown_nonzero_backend_failure_is_retryable_without_guessing_cause(self):
        self.assertEqual(
            ("RUN_ERROR", "UNKNOWN_BACKEND_FAILURE"),
            classify_process(2, "", "opaque vendor failure", False),
        )

    def test_normal_exit_without_terminal_report_is_protocol_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
            done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
            prompt = root / 'prompt.txt'
            prompt.write_text('Review spec_1.md')
            with patch('flowctl_lib.reviews._run_bound_package', return_value=(0, 'Done.', '', False)):
                result = run_cursor_review(state_path, 'spec:M1', prompt, root / 'unused.py', 'fake', 'high', 5, done['state_revision'])
            self.assertEqual('PROTOCOL_ERROR', result['classification'])
            self.assertEqual('INVALID_TERMINAL_REVIEW_REPORT', result['failure_reason'])
            self.assertEqual('review:cursor:retry', load_state(state_path)['pending_action'])

    def test_two_protocol_errors_activate_ibrain_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
            current = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
            prompt = root / 'prompt.txt'
            prompt.write_text('Review spec_1.md')
            for _ in range(2):
                with patch('flowctl_lib.reviews._run_bound_package', return_value=(0, 'Done.', '', False)):
                    current = run_cursor_review(
                        state_path, 'spec:M1', prompt, root / 'unused.py',
                        'fake', 'high', 5, current['state_revision'],
                    )
            self.assertEqual('review:ibrain', load_state(state_path)['pending_action'])
            fallback = begin_review(
                state_path, 'ibrain', 'flow-spec', 'spec:M1', 'glm-5.3', 'medium',
                current['state_revision'],
            )
            self.assertEqual('ibrain', fallback['backend'])

    def test_repair_known_historical_unknown_failure_is_append_only_and_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
            done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
            cursor = begin_review(state_path, 'cursor', 'flow-spec', 'spec:M1', 'cursor', 'high', done['state_revision'])
            evidence = root / 'reviews' / 'legacy.json'
            legacy = record_process_result(
                state_path, cursor['attempt_id'], 2, '', 'legacy cursor terminal failure', False,
                cursor['state_revision'], evidence,
                forced_classification='UNCLASSIFIED', forced_reason='BACKEND_TERMINAL_FAILURE',
            )
            original_digest = legacy['evidence_digest']
            repaired = repair_review_attempt(
                state_path, cursor['attempt_id'], 'unknown_backend_failure', legacy['state_revision'],
            )
            self.assertEqual('RUN_ERROR', repaired['classification'])
            self.assertEqual('UNKNOWN_BACKEND_FAILURE', repaired['failure_reason'])
            self.assertEqual(original_digest, repaired['evidence_digest'])
            self.assertEqual('UNCLASSIFIED', repaired['repair']['previous_classification'])
            event = json.loads((state_path.parent / 'flow-events.jsonl').read_text().splitlines()[-1])
            self.assertEqual('REVIEW_CLASSIFICATION_REPAIRED', event['event'])

    def test_review_cleanup_failure_is_recorded_and_never_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, 'gpt', 'flow-spec', 'spec:M1', 'fake', 'high', state['state_revision'])
            report = root / 'gpt.json'
            report.write_text(json.dumps({'status':'PASSED','findings':[], 'reviewed_digest':gpt['artifact_digest']}))
            done = submit_review(state_path, gpt['attempt_id'], report, gpt['state_revision'])
            prompt = root / 'prompt.txt'
            prompt.write_text('Review spec_1.md')
            from flowctl_lib.review_package import ReviewPackage
            cleanup = ReviewPackage.cleanup
            def failing_cleanup(package):
                cleanup(package)
                raise FlowctlError('REVIEW_PACKAGE_CLEANUP_FAILED')
            with patch.object(ReviewPackage, 'cleanup', failing_cleanup), patch('flowctl_lib.reviews._run_bound_package', return_value=(0, '', '', False)):
                with self.assertRaisesRegex(FlowctlError, 'REVIEW_PACKAGE_CLEANUP_FAILED'):
                    run_cursor_review(state_path, 'spec:M1', prompt, root / 'unused.py', 'fake', 'high', 5, done['state_revision'])
            attempts = load_state(state_path)['reviews']['attempts'].values()
            external = next(item for item in attempts if item['backend'] == 'cursor')
            self.assertEqual(external['failure_reason'], 'REVIEW_PACKAGE_CLEANUP_FAILED')
            self.assertEqual(external['status'], 'INCOMPLETE')

    def test_review_external_requires_authorization_before_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root, authorize=False)
            state = load_state(state_path)
            prompt = root / 'prompt.txt'
            artifact = state['artifacts']['spec:M1']
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            with patch('flowctl_lib.reviews.subprocess.run') as run:
                with self.assertRaisesRegex(FlowctlError, 'EXTERNAL_REVIEW_AUTHORIZATION_REQUIRED'):
                    run_cursor_review(state_path, 'spec:M1', prompt, root / 'runner.py',
                                      'fake', 'high', 5, state['state_revision'])
                run.assert_not_called()

    def _state_with_spec(self, root, authorize=True):
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        state_path = root / "flow-state.json"
        initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
        requirement, req = write_artifact(root, "requirement")
        state = register_artifact(state_path, requirement, "requirement", None, 0)
        handoff = root / "seed-handoff.json"
        def advance(kind, next_stage, key):
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": f"flow-{kind}",
                "next_stage": next_stage, "artifact_key": key,
            }))
            accept_handoff(state_path, handoff, load_state(state_path)["state_revision"])
        advance("requirement", "flow-intent", "requirement")
        intent, intent_ref = write_artifact(root, "intent", upstream={"requirement": req})
        register_artifact(state_path, intent, "intent", None, load_state(state_path)["state_revision"])
        advance("intent", "flow-roadmap", "intent")
        roadmap, roadmap_ref = write_artifact(root, "roadmap", upstream={"requirement": req, "intent": intent_ref})
        register_artifact(state_path, roadmap, "roadmap", None, load_state(state_path)["state_revision"])
        advance("roadmap", "flow-spec", "roadmap")
        spec, _ = write_artifact(root, "spec", milestone="M1", upstream={
            "requirement": req, "intent": intent_ref, "roadmap": roadmap_ref,
        })
        register_artifact(state_path, spec, "spec", "M1", load_state(state_path)["state_revision"])
        if authorize:
            decide_authorization(state_path, "external_review", "GRANTED", load_state(state_path)["state_revision"])
        return state_path

    def test_review_attempt_is_bound_and_stale_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            attempt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "report.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": attempt["artifact_digest"]}))
            submitted = submit_review(state_path, attempt["attempt_id"], report, attempt["state_revision"])
            self.assertEqual("CALLER_ATTESTED", submitted["execution_assurance"])
            self.assertEqual("PASSED", submitted["status"])
            with self.assertRaisesRegex(FlowctlError, "REVIEW_ATTEMPT_TERMINAL"):
                submit_review(state_path, attempt["attempt_id"], report, submitted["state_revision"])

            attempt2 = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", submitted["state_revision"])
            state = load_state(state_path)
            Path(state["artifacts"]["spec:M1"]["path"]).write_text("changed")
            with self.assertRaisesRegex(FlowctlError, "ARTIFACT_DRIFT"):
                submit_review(state_path, attempt2["attempt_id"], report, attempt2["state_revision"])

    def test_cursor_failed_report_with_valid_finding_stays_review_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            gpt_result = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "cursor.py"
            write_bound_runner(runner,
                'import json, re, pathlib, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]).group(0)\n'
                'finding = {"id":"F-1","severity":"HIGH","summary":"broken","blocking_status":"BLOCKING","recurrence_key":"broken","evidence":"line 1"}\n'
                'print("FLOW_REVIEW_REPORT_BEGIN")\n'
                'print(json.dumps({"status":"FAILED","reviewed_digest":digest,"findings":[finding]}))\n'
                'print("FLOW_REVIEW_REPORT_END")\n'
            )
            cursor = run_cursor_review(state_path, "spec:M1", prompt, runner, "fake", "high", 5, gpt_result["state_revision"])
            self.assertEqual("FAILED", cursor["status"])
            self.assertEqual("REVIEW_RESULT", cursor["classification"])
            with self.assertRaisesRegex(FlowctlError, "CURSOR_REVIEW_FAILED"):
                handoff = root / "failed-handoff.json"
                handoff.write_text(json.dumps({
                    "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                    "run_id": "run-bcs-710", "from_stage": "flow-spec",
                    "next_stage": "flow-plan", "artifact_key": "spec:M1",
                }))
                accept_handoff(state_path, handoff, cursor["state_revision"])

    def test_incomplete_report_with_blocking_findings_is_not_degradable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            gpt_report = root / "gpt-incomplete.json"
            gpt_report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            gpt_result = submit_review(state_path, gpt["attempt_id"], gpt_report, gpt["state_revision"])
            cursor = begin_review(state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high", gpt_result["state_revision"])
            cursor_report = root / "cursor-incomplete.json"
            cursor_report.write_text(json.dumps({
                "status": "INCOMPLETE", "reviewed_digest": cursor["artifact_digest"],
                "findings": [{
                    "id": "F-INCOMPLETE", "severity": "HIGH", "summary": "blocking evidence",
                    "blocking_status": "BLOCKING", "recurrence_key": "incomplete-blocking",
                    "evidence": "specific evidence",
                }],
            }))
            result = submit_review(
                state_path, cursor["attempt_id"], cursor_report,
                cursor["state_revision"], controller_executed=True,
            )
            self.assertEqual("REVIEW_RESULT", result["classification"])
            with self.assertRaisesRegex(FlowctlError, "ARTIFACT_REVISION_REQUIRED"):
                begin_review(
                    state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high",
                    result["state_revision"],
                )

    def test_empty_incomplete_model_report_is_not_a_runtime_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            gpt_report = root / "gpt-empty-incomplete.json"
            gpt_report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], gpt_report, gpt["state_revision"])
            cursor = begin_review(state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high", reviewed["state_revision"])
            cursor_report = root / "cursor-empty-incomplete.json"
            cursor_report.write_text(json.dumps({
                "status": "INCOMPLETE", "reviewed_digest": cursor["artifact_digest"],
                "findings": [],
            }))
            result = submit_review(
                state_path, cursor["attempt_id"], cursor_report,
                cursor["state_revision"], controller_executed=True,
            )
            self.assertEqual("UNCLASSIFIED", result["classification"])
            self.assertEqual(0, result.get("retry_count", 0))

    def test_two_unclassified_results_exhaust_a_non_degradable_protocol_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            gpt_report = root / "gpt-pass.json"
            gpt_report.write_text(json.dumps({
                "status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"],
            }))
            reviewed = submit_review(state_path, gpt["attempt_id"], gpt_report, gpt["state_revision"])

            revision = reviewed["state_revision"]
            for index in range(2):
                attempt = begin_review(state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high", revision)
                report = root / f"cursor-incomplete-{index}.json"
                report.write_text(json.dumps({
                    "status": "INCOMPLETE", "findings": [],
                    "reviewed_digest": attempt["artifact_digest"],
                }))
                result = submit_review(
                    state_path, attempt["attempt_id"], report,
                    attempt["state_revision"], controller_executed=True,
                )
                revision = result["state_revision"]

            self.assertEqual("blocked:review:unclassified", load_state(state_path)["pending_action"])
            with self.assertRaisesRegex(FlowctlError, "UNCLASSIFIED_RETRY_EXHAUSTED"):
                begin_review(
                    state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high", revision,
                )
            handoff = root / "cursor-unclassified-handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-spec",
                "next_stage": "flow-plan", "artifact_key": "spec:M1",
            }))
            with self.assertRaisesRegex(FlowctlError, "UNCLASSIFIED_RETRY_EXHAUSTED"):
                accept_handoff(state_path, handoff, revision)

    def test_exhausted_unclassified_budget_blocks_other_backends_and_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            passed = root / "gpt-pass.json"
            passed.write_text(json.dumps({
                "status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"],
            }))
            result = submit_review(state_path, gpt["attempt_id"], passed, gpt["state_revision"])

            for index in range(2):
                attempt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", result["state_revision"])
                incomplete = root / f"gpt-incomplete-{index}.json"
                incomplete.write_text(json.dumps({
                    "status": "INCOMPLETE", "findings": [],
                    "reviewed_digest": attempt["artifact_digest"],
                }))
                result = submit_review(state_path, attempt["attempt_id"], incomplete, attempt["state_revision"])

            with self.assertRaisesRegex(FlowctlError, "UNCLASSIFIED_RETRY_EXHAUSTED"):
                begin_review(
                    state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high",
                    result["state_revision"],
                )
            handoff = root / "blocked-handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-spec",
                "next_stage": "flow-plan", "artifact_key": "spec:M1",
            }))
            with self.assertRaisesRegex(FlowctlError, "UNCLASSIFIED_RETRY_EXHAUSTED"):
                accept_handoff(state_path, handoff, result["state_revision"])

    def test_framed_terminal_report_allows_logs_after_the_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            gpt_report = root / "gpt-pass.json"
            gpt_report.write_text(json.dumps({
                "status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"],
            }))
            reviewed = submit_review(state_path, gpt["attempt_id"], gpt_report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "framed.py"
            write_bound_runner(runner,
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]).group(0)\n'
                'print("FLOW_REVIEW_REPORT_BEGIN")\n'
                'print(json.dumps({"status":"PASSED","reviewed_digest":digest,"findings":[]}))\n'
                'print("FLOW_REVIEW_REPORT_END")\n'
                'print("runner shutdown complete")\n'
            )
            result = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("REVIEW_RESULT", result["classification"])
            self.assertEqual("PASSED", result["status"])

    def test_framed_terminal_report_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            passed = root / "gpt-pass.json"
            passed.write_text(json.dumps({
                "status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"],
            }))
            reviewed = submit_review(state_path, gpt["attempt_id"], passed, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "duplicate.py"
            write_bound_runner(runner,
                'import pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]).group(0)\n'
                'print("FLOW_REVIEW_REPORT_BEGIN")\n'
                'print(\'{"status":"FAILED","status":"PASSED","reviewed_digest":"%s","findings":[{"id":"F"}],"findings":[]}\' % digest)\n'
                'print("FLOW_REVIEW_REPORT_END")\n'
            )
            result = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("UNCLASSIFIED", result["classification"])

    def test_direct_review_submission_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            attempt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "duplicate.json"
            report.write_text(
                '{"status":"FAILED","status":"PASSED","reviewed_digest":"'
                + attempt["artifact_digest"] + '","findings":[]}'
            )
            with self.assertRaisesRegex(FlowctlError, "INVALID_REVIEW_REPORT"):
                submit_review(state_path, attempt["attempt_id"], report, attempt["state_revision"])

    def test_direct_review_submission_rejects_nested_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            attempt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "nested-duplicate.json"
            report.write_text(
                '{"status":"FAILED","reviewed_digest":"' + attempt["artifact_digest"]
                + '","findings":[{"id":"F","id":"OVERRIDE"}]}'
            )
            with self.assertRaisesRegex(FlowctlError, "INVALID_REVIEW_REPORT"):
                submit_review(state_path, attempt["attempt_id"], report, attempt["state_revision"])

    def test_multiple_terminal_report_frames_are_unclassified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            passed = root / "gpt-pass.json"
            passed.write_text(json.dumps({
                "status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"],
            }))
            reviewed = submit_review(state_path, gpt["attempt_id"], passed, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "multiple.py"
            write_bound_runner(runner,
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]).group(0)\n'
                'report = json.dumps({"status":"PASSED","reviewed_digest":digest,"findings":[]})\n'
                'print("FLOW_REVIEW_REPORT_BEGIN\\n" + report + "\\nFLOW_REVIEW_REPORT_END")\n'
                'print("FLOW_REVIEW_REPORT_BEGIN\\n" + report + "\\nFLOW_REVIEW_REPORT_END")\n'
            )
            result = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("UNCLASSIFIED", result["classification"])

    def test_rejected_terminal_report_keywords_cannot_become_runtime_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt-terminal.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "terminal-prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "invalid-terminal.py"
            write_bound_runner(runner,
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]).group(0)\n'
                'finding = {"id":"F","severity":"HIGH","summary":"connection isolation broken","blocking_status":"BLOCKING","recurrence_key":"bad","evidence":"e"}\n'
                'print(json.dumps({"status":"PASSED","reviewed_digest":digest,"findings":[finding]}))\n'
            )
            rejected = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("UNCLASSIFIED", rejected["classification"])
            self.assertEqual("INVALID_TERMINAL_REVIEW_REPORT", rejected["failure_reason"])
            self.assertEqual("INCOMPLETE", rejected["status"])

    def test_wrong_digest_terminal_report_cannot_become_runtime_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt-wrong-digest.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "wrong-digest-prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "wrong-digest.py"
            write_bound_runner(runner,
                'import json\n'
                'finding = {"id":"F","severity":"HIGH","summary":"binding broken","blocking_status":"BLOCKING","recurrence_key":"bad-digest","evidence":"e"}\n'
                'print("FLOW_REVIEW_REPORT_BEGIN")\n'
                'print(json.dumps({"status":"FAILED","reviewed_digest":"sha256:' + ('0' * 64) + '","findings":[finding]}))\n'
                'print("FLOW_REVIEW_REPORT_END")\n'
            )
            rejected = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("UNCLASSIFIED", rejected["classification"])
            self.assertEqual("INVALID_TERMINAL_REVIEW_REPORT", rejected["failure_reason"])

    def test_nonzero_process_with_terminal_failed_report_stays_substantive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt-nonzero.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "nonzero-prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "nonzero-terminal.py"
            write_bound_runner(runner,
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]).group(0)\n'
                'finding = {"id":"F","severity":"HIGH","summary":"connection isolation broken","blocking_status":"BLOCKING","recurrence_key":"nonzero-report","evidence":"e"}\n'
                'print("FLOW_REVIEW_REPORT_BEGIN")\n'
                'print(json.dumps({"status":"FAILED","reviewed_digest":digest,"findings":[finding]}))\n'
                'print("FLOW_REVIEW_REPORT_END")\n'
                'sys.exit(1)\n'
            )
            result = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("REVIEW_RESULT", result["classification"])
            self.assertEqual("FAILED", result["status"])

    def test_timeout_bytes_with_complete_terminal_report_stays_substantive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt-timeout.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "timeout-prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            finding = {"id": "F", "severity": "HIGH", "summary": "timeout isolation broken", "blocking_status": "BLOCKING", "recurrence_key": "timeout-terminal", "evidence": "e"}
            output = (
                "FLOW_REVIEW_REPORT_BEGIN\n"
                + json.dumps({"status": "FAILED", "reviewed_digest": artifact["digest"], "findings": [finding]})
                + "\nFLOW_REVIEW_REPORT_END\n"
            ).encode()
            real_run = subprocess.run
            def timeout_runner(command, **kwargs):
                if command[0] == 'git':
                    return real_run(command, **kwargs)
                if '--check-capabilities' in command:
                    return subprocess.CompletedProcess([], 0, '{"local_tools":false,"implicit_indexing":false}', '')
                raise subprocess.TimeoutExpired([], 1, output=output, stderr=b'')
            with patch("flowctl_lib.reviews.subprocess.run", side_effect=timeout_runner):
                result = run_cursor_review(
                    state_path, "spec:M1", prompt, ROOT.parent / 'skills/cursor-review/scripts/cursor_review.py', "fake", "high", 5,
                    reviewed["state_revision"],
                )
            self.assertEqual("REVIEW_RESULT", result["classification"])
            self.assertEqual("FAILED", result["status"])

    def test_snapshot_cannot_be_replaced_after_review_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "flowctl@test.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Flowctl Test"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-m", "baseline"], check=True, capture_output=True)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            record_snapshot(state_path, "spec:M1", state["state_revision"])
            state = load_state(state_path)
            begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            (root / "unreviewed.py").write_text("changed = True\n")
            state = load_state(state_path)
            with self.assertRaisesRegex(FlowctlError, "SNAPSHOT_REVIEW_BINDING_EXISTS"):
                record_snapshot(state_path, "spec:M1", state["state_revision"])

    def test_code_review_resume_requires_same_recorded_and_actual_snapshot(self):
        artifact = {"type": "code", "digest": "sha256:artifact"}
        attempt = {
            "artifact_digest": "sha256:artifact",
            "snapshot_digest": "sha256:reviewed-code",
        }
        matching = {"snapshot_digest": "sha256:reviewed-code"}
        changed = {"snapshot_digest": "sha256:changed-code"}
        self.assertFalse(_review_eligible_after_resume(attempt, artifact, None, None))
        self.assertFalse(_review_eligible_after_resume(attempt, artifact, matching, changed))
        self.assertTrue(_review_eligible_after_resume(attempt, artifact, matching, matching))

    def test_cursor_backend_rejects_overlapping_open_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(
                state_path, "gpt", "flow-spec", "spec:M1",
                "gpt-6-astra", "medium", state["state_revision"],
            )
            report = root / "gpt-overlap.json"
            report.write_text(json.dumps({
                "status": "PASSED", "findings": [],
                "reviewed_digest": gpt["artifact_digest"],
            }))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            first = begin_review(
                state_path, "cursor", "flow-spec", "spec:M1",
                "cursor", "high", reviewed["state_revision"],
            )
            with self.assertRaisesRegex(FlowctlError, "REVIEW_ATTEMPT_IN_PROGRESS"):
                begin_review(
                    state_path, "cursor", "flow-spec", "spec:M1",
                    "cursor", "high", first["state_revision"],
                )

    def test_review_cycle_limit_survives_artifact_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            for revision in (1, 2, 3):
                state = load_state(state_path)
                attempt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
                report = root / f"failed-{revision}.json"
                report.write_text(json.dumps({
                    "status": "FAILED", "reviewed_digest": attempt["artifact_digest"],
                    "findings": [{
                        "id": f"F-{revision}", "severity": "HIGH", "summary": "blocking",
                        "blocking_status": "BLOCKING", "recurrence_key": "same-cause", "evidence": "test",
                    }],
                }))
                result = submit_review(state_path, attempt["attempt_id"], report, attempt["state_revision"])
                state = load_state(state_path)
                artifact = state["artifacts"]["spec:M1"]
                updated, _ = write_artifact(
                    root, "spec", revision=revision + 1, milestone="M1",
                    upstream=artifact["upstream"], name=Path(artifact["path"]).name,
                )
                register_artifact(state_path, updated, "spec", "M1", result["state_revision"])
            state = load_state(state_path)
            with self.assertRaisesRegex(FlowctlError, "REVIEW_CYCLE_LIMIT"):
                begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])

    def test_process_classifier_uses_process_facts(self):
        self.assertEqual(("RUN_ERROR", "UNKNOWN_BACKEND_FAILURE"), classify_process(2, "", "business connection timeout", False))
        structured = (
            'FLOW_REVIEW_ERROR_BEGIN\n'
            '{"schema_version":1,"code":"SDK_UNAVAILABLE"}\n'
            'FLOW_REVIEW_ERROR_END\n'
        )
        self.assertEqual(("RUN_ERROR", "SDK_UNAVAILABLE"), classify_process(2, "", structured, False))
        protocol = (
            'FLOW_REVIEW_ERROR_BEGIN\n'
            '{"schema_version":1,"code":"PROTOCOL_ERROR"}\n'
            'FLOW_REVIEW_ERROR_END'
        )
        self.assertEqual(("PROTOCOL_ERROR", "PROTOCOL_ERROR"), classify_process(2, "", protocol, False))
        self.assertEqual(("RUN_ERROR", "PROCESS_TIMEOUT"), classify_process(None, "", "", True))
        self.assertEqual(("REVIEW_RESULT", None), classify_process(0, "timeout discussed in finding", "", False))
        self.assertEqual(("RUN_ERROR", "UNKNOWN_BACKEND_FAILURE"), classify_process(2, "odd", "", False))

    def test_official_runner_frames_early_runtime_failure(self):
        runner = ROOT.parent / "skills" / "cursor-review" / "scripts" / "cursor_review.py"
        result = subprocess.run(
            [sys.executable, str(runner), "--check-capabilities"], text=True,
            capture_output=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertEqual(1, result.stderr.count("FLOW_REVIEW_ERROR_BEGIN"))
        self.assertIn('{"schema_version": 1, "code": "BACKEND_UNAVAILABLE"}', result.stderr)
        self.assertEqual(1, result.stderr.count("FLOW_REVIEW_ERROR_END"))
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("SDK_UNAVAILABLE", result.stderr)

    def test_handoff_requires_gpt_then_cursor_for_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            handoff = root / "handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710",
                "from_stage": "flow-spec", "next_stage": "flow-plan", "artifact_key": "spec:M1",
            }))
            with self.assertRaisesRegex(FlowctlError, "GPT_REVIEW_REQUIRED"):
                accept_handoff(state_path, handoff, state["state_revision"])

    def test_handoff_runtime_parser_rejects_duplicate_and_schema_invalid_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            duplicate = root / "duplicate-handoff.json"
            duplicate.write_text(
                '{"schema_version":1,"signal":"FLOW_RUN_HANDOFF","issue_id":"BCS-710",'
                '"run_id":"run-bcs-710","from_stage":"flow-spec","next_stage":"flow-plan",'
                '"next_stage":"flow-code","artifact_key":"spec:M1"}'
            )
            with self.assertRaisesRegex(FlowctlError, "INVALID_HANDOFF_JSON"):
                accept_handoff(state_path, duplicate, state["state_revision"])

            for field, value in (("issue_id", ""), ("from_stage", "flow-unknown"), ("next_stage", "flow-unknown")):
                payload = {
                    "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                    "run_id": "run-bcs-710", "from_stage": "flow-spec",
                    "next_stage": "flow-plan", "artifact_key": "spec:M1",
                }
                payload[field] = value
                path = root / f"invalid-{field}.json"
                path.write_text(json.dumps(payload))
                with self.assertRaisesRegex(FlowctlError, "HANDOFF_SCHEMA_INVALID"):
                    accept_handoff(state_path, path, state["state_revision"])

    def test_cursor_review_requires_gpt_and_two_runtime_failures_fall_back_to_ibrain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            with self.assertRaisesRegex(FlowctlError, "GPT_REVIEW_REQUIRED"):
                begin_review(state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high", state["state_revision"])

            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            result = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            for index in range(2):
                attempt = begin_review(state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high", result["state_revision"])
                result = record_process_result(
                    state_path, attempt["attempt_id"], 2, "", (
                        'FLOW_REVIEW_ERROR_BEGIN\n'
                        '{"schema_version":1,"code":"CONNECTION_ERROR"}\n'
                        'FLOW_REVIEW_ERROR_END\n'
                    ), False,
                    attempt["state_revision"], root / f"cursor-{index}.json",
                )
                self.assertEqual(index + 1, result["retry_count"])
            with self.assertRaisesRegex(FlowctlError, "CURSOR_RETRY_EXHAUSTED"):
                begin_review(
                    state_path, "cursor", "flow-spec", "spec:M1", "cursor", "high",
                    result["state_revision"],
                )
            fallback = begin_review(
                state_path, "ibrain", "flow-spec", "spec:M1", "glm-5.3", "medium",
                result["state_revision"],
            )
            fallback_report = root / "ibrain.json"
            fallback_report.write_text(json.dumps({
                "status": "FAILED",
                "findings": [{"id": "GLM-1", "severity": "HIGH", "summary": "fix fallback finding",
                              "blocking_status": "BLOCKING", "recurrence_key": "fallback", "evidence": "spec"}],
                "reviewed_digest": fallback["artifact_digest"],
            }))
            result = submit_review(
                state_path, fallback["attempt_id"], fallback_report,
                fallback["state_revision"], controller_executed=True,
            )
            current = load_state(state_path)["artifacts"]
            revised_path, _ = write_artifact(
                root, "spec", revision=2, milestone="M1",
                upstream={name: current[name] for name in ("requirement", "intent", "roadmap")},
                name="spec_fallback_2.md",
            )
            revised = register_artifact(state_path, revised_path, "spec", "M1", result["state_revision"])
            fallback = begin_review(
                state_path, "ibrain", "flow-spec", "spec:M1", "glm-5.3", "medium",
                revised["state_revision"],
            )
            fallback_report = root / "ibrain-pass.json"
            fallback_report.write_text(json.dumps({
                "status": "PASSED", "findings": [], "reviewed_digest": fallback["artifact_digest"],
            }))
            result = submit_review(
                state_path, fallback["attempt_id"], fallback_report,
                fallback["state_revision"], controller_executed=True,
            )
            self.assertEqual("review:consistency", load_state(state_path)["pending_action"])
            final = begin_review(
                state_path, "consistency", "flow-spec", "spec:M1",
                "gpt-6-astra", "medium", result["state_revision"],
            )
            final_report = root / "consistency.json"
            final_report.write_text(json.dumps({
                "status": "PASSED", "findings": [],
                "reviewed_digest": final["artifact_digest"],
            }))
            result = submit_review(
                state_path, final["attempt_id"], final_report, final["state_revision"],
            )
            handoff = root / "handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710",
                "from_stage": "flow-spec", "next_stage": "flow-plan", "artifact_key": "spec:M1",
            }))
            accepted = accept_handoff(state_path, handoff, result["state_revision"])
            self.assertEqual("flow-plan", accepted["current_stage"])
            self.assertEqual("COMPLETE", accepted["completion_quality"])

    def test_review_lanes_close_own_findings_then_astra_checks_final_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)

            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-5.6-sol", "high", state["state_revision"])
            report = root / "gpt-pass.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])

            cursor = begin_review(state_path, "cursor", "flow-spec", "spec:M1", "grok-4.6", "high", reviewed["state_revision"])
            report = root / "cursor-fail.json"
            report.write_text(json.dumps({
                "status": "FAILED", "reviewed_digest": cursor["artifact_digest"],
                "findings": [{"id": "CUR-1", "severity": "HIGH", "summary": "fix boundary",
                              "blocking_status": "BLOCKING", "recurrence_key": "boundary", "evidence": "spec"}],
            }))
            failed = submit_review(state_path, cursor["attempt_id"], report, cursor["state_revision"], controller_executed=True)

            current = load_state(state_path)["artifacts"]
            revised_path, _ = write_artifact(
                root, "spec", revision=2, milestone="M1",
                upstream={name: current[name] for name in ("requirement", "intent", "roadmap")},
                name="spec_2.md",
            )
            revised = register_artifact(state_path, revised_path, "spec", "M1", failed["state_revision"])
            cursor_retry = begin_review(
                state_path, "cursor", "flow-spec", "spec:M1", "grok-4.6", "high",
                revised["state_revision"],
            )
            self.assertEqual(2, cursor_retry["artifact_revision"])
            report = root / "cursor-pass.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": cursor_retry["artifact_digest"]}))
            cursor_passed = submit_review(
                state_path, cursor_retry["attempt_id"], report, cursor_retry["state_revision"], controller_executed=True,
            )
            self.assertEqual("review:consistency", load_state(state_path)["pending_action"])

            with self.assertRaisesRegex(FlowctlError, "CONSISTENCY_MODEL_REQUIRED"):
                begin_review(state_path, "consistency", "flow-spec", "spec:M1", "gpt-5.6-sol", "high", cursor_passed["state_revision"])
            final = begin_review(
                state_path, "consistency", "flow-spec", "spec:M1", "gpt-6-astra", "medium",
                cursor_passed["state_revision"],
            )
            self.assertEqual(cursor_retry["artifact_digest"], final["artifact_digest"])
            report = root / "consistency-fail.json"
            report.write_text(json.dumps({
                "status": "FAILED", "reviewed_digest": final["artifact_digest"],
                "findings": [{"id": "FINAL-1", "severity": "HIGH", "summary": "cross-lane conflict",
                              "blocking_status": "BLOCKING", "recurrence_key": "cross-lane", "evidence": "spec"}],
            }))
            failed_final = submit_review(state_path, final["attempt_id"], report, final["state_revision"])
            current = load_state(state_path)["artifacts"]
            revised_path, _ = write_artifact(
                root, "spec", revision=3, milestone="M1",
                upstream={name: current[name] for name in ("requirement", "intent", "roadmap")},
                name="spec_3.md",
            )
            revised = register_artifact(state_path, revised_path, "spec", "M1", failed_final["state_revision"])
            lane = load_state(state_path)["reviews"]["lanes"]["spec:M1"]
            self.assertEqual(1, lane["consistency_attempts"])
            with self.assertRaisesRegex(FlowctlError, "GPT_REVIEW_REQUIRED"):
                begin_review(
                    state_path, "consistency", "flow-spec", "spec:M1", "gpt-6-astra", "medium",
                    revised["state_revision"],
                )

    def test_route_back_is_schema_bound_and_invalidates_from_owner_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            original_paths = {key: item["path"] for key, item in state["artifacts"].items()}
            payload = root / "route.json"
            payload.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_ROUTE_BACK",
                "issue_id": "BCS-710", "run_id": "run-bcs-710",
                "stage": "flow-spec", "cause": "intent contradiction",
                "evidence": "TESTCASE-1", "resume_condition": "revise intent",
                "owner_stage": "flow-intent", "next_stage": "flow-intent",
            }))
            result = record_signal(state_path, payload, state["state_revision"])
            self.assertEqual("flow-intent", result["current_stage"])
            self.assertIn("spec:M1", result["invalidated_artifacts"])
            self.assertIn("roadmap", result["invalidated_artifacts"])
            state = load_state(state_path)
            self.assertIn("requirement", state["artifacts"])
            self.assertNotIn("intent", state["artifacts"])
            inputs = root / "resume-inputs.json"
            inputs.write_text(json.dumps({key: path for key, path in original_paths.items()}))
            discovery = resume_flow("BCS-710", root, inputs)
            resumed = reconcile_resume(state_path, discovery, state["state_revision"])
            self.assertEqual("flow-intent", resumed["current_stage"])
            self.assertEqual("revise:intent", resumed["pending_action"])
            self.assertEqual(["requirement"], sorted(resumed["artifacts"]))
            self.assertIn("intent", resumed["invalidated_checkpoints"])
            req = resumed["artifacts"]["requirement"]
            replacement, _ = write_artifact(
                root, "intent", revision=2, upstream={"requirement": req},
                name="intent_2.md",
            )
            replaced = register_artifact(
                state_path, replacement, "intent", None, resumed["state_revision"],
            )
            old_discovery = resume_flow("BCS-710", root, inputs)
            with self.assertRaisesRegex(FlowctlError, "CHECKPOINT_REVISION_ROLLBACK"):
                reconcile_resume(state_path, old_discovery, replaced["state_revision"])

    def test_pause_signal_blocks_resume_and_handoff_until_explicit_resume_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            inputs = root / "pause-inputs.json"
            inputs.write_text(json.dumps({key: item["path"] for key, item in state["artifacts"].items()}))
            pause = root / "pause.json"
            pause.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_BLOCKED", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "stage": "flow-spec", "cause": "dependency down",
                "evidence": "probe", "resume_condition": "dependency restored",
            }))
            paused = record_signal(state_path, pause, state["state_revision"])
            discovery = resume_flow("BCS-710", root, inputs)
            unchanged = reconcile_resume(state_path, discovery, paused["state_revision"])
            self.assertEqual(paused["state_revision"], unchanged["state_revision"])
            self.assertEqual("blocked", unchanged["pending_action"])
            handoff = root / "paused-handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-spec",
                "next_stage": "flow-plan", "artifact_key": "spec:M1",
            }))
            with self.assertRaisesRegex(FlowctlError, "FLOW_PAUSED"):
                accept_handoff(state_path, handoff, paused["state_revision"])
            route = root / "paused-route.json"
            route.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_ROUTE_BACK", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "stage": "flow-spec", "cause": "skip pause",
                "evidence": "none", "resume_condition": "revise intent",
                "owner_stage": "flow-intent", "next_stage": "flow-intent",
            }))
            with self.assertRaisesRegex(FlowctlError, "FLOW_PAUSED"):
                record_signal(state_path, route, paused["state_revision"])
            resumed_signal = root / "resumed.json"
            resumed_signal.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_RESUMED", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "stage": "flow-spec", "cause": "dependency restored",
                "evidence": "probe passed", "resume_condition": "satisfied",
            }))
            cleared = record_signal(state_path, resumed_signal, paused["state_revision"])
            self.assertEqual("resume", cleared["pending_action"])
            reconciled = reconcile_resume(state_path, discovery, cleared["state_revision"])
            self.assertEqual("review:gpt", reconciled["pending_action"])

    def test_route_back_owner_survives_human_gate_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            inputs = root / "route-pause-inputs.json"
            inputs.write_text(json.dumps({key: item["path"] for key, item in state["artifacts"].items()}))
            route = root / "route-before-gate.json"
            route.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_ROUTE_BACK", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "stage": "flow-spec", "cause": "intent decision",
                "evidence": "review", "resume_condition": "revise intent",
                "owner_stage": "flow-intent", "next_stage": "flow-intent",
            }))
            routed = record_signal(state_path, route, state["state_revision"])
            gate = root / "route-gate.json"
            gate.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HUMAN_GATE", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "stage": "flow-intent", "cause": "choose behavior",
                "evidence": "two options", "resume_condition": "human chooses", "gate": "intent-choice",
            }))
            gated = record_signal(state_path, gate, routed["state_revision"])
            resumed_payload = root / "route-resumed.json"
            resumed_payload.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_RESUMED", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "stage": "flow-intent", "cause": "choice received",
                "evidence": "human answer", "resume_condition": "satisfied",
            }))
            cleared = record_signal(state_path, resumed_payload, gated["state_revision"])
            discovery = resume_flow("BCS-710", root, inputs)
            reconciled = reconcile_resume(state_path, discovery, cleared["state_revision"])
            self.assertEqual("flow-intent", reconciled["current_stage"])
            self.assertEqual("revise:intent", reconciled["pending_action"])

    def test_missing_or_truncated_terminal_output_is_not_degradable(self):
        for output in (
            "INCOMPLETE: finished without terminal report\n",
            '{"status":"FAILED","findings":[{"summary":"connection isolation',
        ):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state_path = self._state_with_spec(root)
                state = load_state(state_path)
                gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
                report = root / "gpt-missing.json"
                report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
                reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
                artifact = load_state(state_path)["artifacts"]["spec:M1"]
                prompt = root / "missing-prompt.txt"
                prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
                runner = root / "missing-terminal.py"
                write_bound_runner(runner, f"import sys\nprint({output!r})\nsys.exit(2)\n")
                result = run_cursor_review(
                    state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                    reviewed["state_revision"],
                )
                self.assertEqual("UNCLASSIFIED", result["classification"])

    def test_missing_terminal_output_on_stderr_is_not_degradable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = self._state_with_spec(root)
            state = load_state(state_path)
            gpt = begin_review(state_path, "gpt", "flow-spec", "spec:M1", "gpt-6-astra", "medium", state["state_revision"])
            report = root / "gpt-missing-stderr.json"
            report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
            reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
            artifact = load_state(state_path)["artifacts"]["spec:M1"]
            prompt = root / "missing-stderr-prompt.txt"
            prompt.write_text(f"Review {Path(artifact['path']).name} at {artifact['digest']}")
            runner = root / "missing-stderr.py"
            write_bound_runner(runner,
                'import sys\n'
                'print("INCOMPLETE: finished without terminal report", file=sys.stderr)\n'
                'sys.exit(2)\n'
            )
            result = run_cursor_review(
                state_path, "spec:M1", prompt, runner, "fake", "high", 5,
                reviewed["state_revision"],
            )
            self.assertEqual("UNCLASSIFIED", result["classification"])


class EndToEndControllerTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
    def test_full_progression_requires_registered_artifacts_reviews_snapshot_and_handoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "flowctl@test.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Flowctl Test"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-m", "baseline"], check=True, capture_output=True)
            issue_dir = root / ".ai" / "issue" / "BCS-710"
            issue_dir.mkdir(parents=True)
            state_path = issue_dir / "flow-state.json"
            state = initialize_state(state_path, "BCS-710", root, "feature-BCS-710-flowctl")
            state = decide_authorization(state_path, 'external_review', 'GRANTED', state['state_revision'])
            refs = {}

            def handoff(kind, next_stage, key, revision):
                path = issue_dir / "handoff.json"
                path.write_text(json.dumps({
                    "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                    "run_id": "run-bcs-710", "from_stage": f"flow-{kind}",
                    "next_stage": next_stage, "artifact_key": key,
                }))
                return accept_handoff(state_path, path, revision)

            for kind, next_stage in (("requirement", "flow-intent"), ("intent", "flow-roadmap"), ("roadmap", "flow-spec")):
                upstream = {name: refs[name] for name in ("requirement", "intent") if name in refs}
                options = {}
                if kind == "roadmap":
                    options = {
                        "target_milestones": ["M1", "M2"],
                        "milestone_dependencies": {"M1": [], "M2": ["M1"]},
                    }
                path, refs[kind] = write_artifact(issue_dir, kind, upstream=upstream, **options)
                state = register_artifact(state_path, path, kind, None, state["state_revision"])
                result = handoff(kind, "auto" if kind == "roadmap" else next_stage, kind, state["state_revision"])
                state = load_state(state_path)
                self.assertEqual(next_stage, result["current_stage"])

            runner = root / "fake_cursor.py"
            write_bound_runner(runner,
                'import json, pathlib, re, sys\n'
                'prompt = json.loads(pathlib.Path(sys.argv[1]).read_text())["prompt"]\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", prompt).group(0)\n'
                'print("FLOW_REVIEW_REPORT_BEGIN")\n'
                'print(json.dumps({"status":"PASSED","reviewed_digest":digest,"findings":[]}))\n'
                'print("FLOW_REVIEW_REPORT_END")\n'
            )
            prompt = issue_dir / "review-prompt.txt"
            for milestone in ("M1", "M2"):
                milestone_refs = {name: refs[name] for name in ("requirement", "intent", "roadmap")}
                for kind, next_stage in (("spec", "flow-plan"), ("plan", "flow-code"), ("code", "flow-integration")):
                    path, milestone_refs[kind] = write_artifact(
                        issue_dir, kind, milestone=milestone, upstream=milestone_refs,
                        name=f"{kind}_{milestone}.md",
                    )
                    key = f"{kind}:{milestone}"
                    state = register_artifact(state_path, path, kind, milestone, state["state_revision"])
                    if kind == "code":
                        snapshot = record_snapshot(state_path, key, state["state_revision"])
                        state = load_state(state_path)
                        self.assertTrue(snapshot["snapshot"]["snapshot_digest"].startswith("sha256:"))
                    gpt = begin_review(state_path, "gpt", f"flow-{kind}", key, "gpt-6-astra", "medium", state["state_revision"])
                    report = issue_dir / f"{kind}-{milestone}-gpt.json"
                    report.write_text(json.dumps({"status": "PASSED", "findings": [], "reviewed_digest": gpt["artifact_digest"]}))
                    reviewed = submit_review(state_path, gpt["attempt_id"], report, gpt["state_revision"])
                    prompt.write_text(
                        f"Review exact artifact {path.name} bound to {milestone_refs[kind]['digest']} "
                        "and return the required JSON review report."
                    )
                    cursor = run_cursor_review(state_path, key, prompt, runner, "fake", "high", 5, reviewed["state_revision"])
                    self.assertEqual("PASSED", cursor["status"])
                    consistency = begin_review(
                        state_path, "consistency", f"flow-{kind}", key,
                        "gpt-6-astra", "medium", cursor["state_revision"],
                    )
                    consistency_report = issue_dir / f"{kind}-{milestone}-consistency.json"
                    consistency_report.write_text(json.dumps({
                        "status": "PASSED", "findings": [],
                        "reviewed_digest": consistency["artifact_digest"],
                    }))
                    final_review = submit_review(
                        state_path, consistency["attempt_id"], consistency_report,
                        consistency["state_revision"],
                    )
                    if milestone == "M2" and kind == "code":
                        discovery = resume_flow("BCS-710", root)
                        resumed = reconcile_resume(state_path, discovery, final_review["state_revision"])
                        self.assertEqual("flow-code", resumed["current_stage"])
                        self.assertEqual("M2", resumed["active_milestone"])
                        self.assertEqual("handoff:code", resumed["pending_action"])
                        final_review["state_revision"] = resumed["state_revision"]
                    result = handoff(kind, next_stage, key, final_review["state_revision"])
                    state = load_state(state_path)
                    self.assertEqual(next_stage, result["current_stage"])

                from flowctl_lib.integration_results import aggregate_integration_results
                integration_results = aggregate_integration_results(
                    [{'scenario_id':'TESTCASE-DEFAULT', 'status':'PASSED'}],
                    state['artifacts'][f'plan:{milestone}']['path'])
                integration, _ = write_artifact(
                    issue_dir, "integration", milestone=milestone, upstream=milestone_refs,
                    name=f"integration_{milestone}.md", integration_results=integration_results,
                )
                state = register_artifact(state_path, integration, "integration", milestone, state["state_revision"])
                result = handoff("integration", "auto", f"integration:{milestone}", state["state_revision"])
                state = load_state(state_path)
                expected = "flow-spec" if milestone == "M1" else "complete"
                self.assertEqual(expected, result["current_stage"])
            self.assertEqual("complete", result["current_stage"])
            self.assertIsNone(result["next_action"])
            replacement, _ = write_artifact(issue_dir, "requirement", revision=2, name="requirement_2.md")
            with self.assertRaisesRegex(FlowctlError, "FLOW_ALREADY_COMPLETE"):
                register_artifact(state_path, replacement, "requirement", None, state["state_revision"])
            reopen = issue_dir / "reopen.json"
            reopen.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_ROUTE_BACK",
                "issue_id": "BCS-710", "run_id": "run-bcs-710",
                "stage": "complete", "cause": "reopen code", "evidence": "manual",
                "resume_condition": "revise code", "owner_stage": "flow-code",
                "next_stage": "flow-code",
            }))
            with self.assertRaisesRegex(FlowctlError, "MILESTONE_NOT_ACTIVE"):
                record_signal(state_path, reopen, state["state_revision"])
            global_reopen = issue_dir / "reopen-roadmap.json"
            global_reopen.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_ROUTE_BACK",
                "issue_id": "BCS-710", "run_id": "run-bcs-710",
                "stage": "complete", "cause": "revise milestones", "evidence": "manual",
                "resume_condition": "revise roadmap", "owner_stage": "flow-roadmap",
                "next_stage": "flow-roadmap",
            }))
            reopened = record_signal(state_path, global_reopen, state["state_revision"])
            self.assertIn("spec:M1", reopened["invalidated_artifacts"])
            self.assertIn("integration:M2", reopened["invalidated_artifacts"])
            audited = load_state(state_path)
            self.assertEqual(["intent", "requirement"], sorted(audited["artifacts"]))
