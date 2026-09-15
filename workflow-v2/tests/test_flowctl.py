import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flowctl_lib.artifacts import verify_artifact
from flowctl_lib.errors import FlowctlError
from flowctl_lib.handoff import accept_handoff
from flowctl_lib.resume import _review_eligible_after_resume, reconcile_resume, resume_flow
from flowctl_lib.reviews import begin_review, classify_process, record_process_result, run_cursor_review, submit_review
from flowctl_lib.snapshot import record_snapshot
from flowctl_lib.signals import record_signal
from flowctl_lib.state import initialize_state, load_state, read_consistent_state, register_artifact


def write_artifact(directory, kind, revision=1, issue="BCS-710", milestone=None,
                   upstream=None, approval_status="APPROVED", name=None,
                   target_milestones=None, milestone_dependencies=None):
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


class ResumeTests(unittest.TestCase):
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
    def _state_with_spec(self, root):
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

    def test_cursor_failed_report_with_nested_finding_stays_review_result(self):
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "cursor.py"
            runner.write_text(
                'import json, re, pathlib, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", pathlib.Path(sys.argv[2]).read_text()).group(0)\n'
                'finding = {"id":"F-1","severity":"HIGH","summary":"broken","blocking_status":"BLOCKING","recurrence_key":"broken","evidence":"line 1",'
                '"debug":{"status":"FAILED","reviewed_digest":digest,"findings":[]}}\n'
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
                "findings": [], "reason": "transmission denied",
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "framed.py"
            runner.write_text(
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", pathlib.Path(sys.argv[2]).read_text()).group(0)\n'
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "duplicate.py"
            runner.write_text(
                'import pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", pathlib.Path(sys.argv[2]).read_text()).group(0)\n'
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "multiple.py"
            runner.write_text(
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", pathlib.Path(sys.argv[2]).read_text()).group(0)\n'
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "invalid-terminal.py"
            runner.write_text(
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", pathlib.Path(sys.argv[2]).read_text()).group(0)\n'
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "wrong-digest.py"
            runner.write_text(
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "nonzero-terminal.py"
            runner.write_text(
                'import json, pathlib, re, sys\n'
                'digest = re.search(r"sha256:[0-9a-f]{64}", pathlib.Path(sys.argv[2]).read_text()).group(0)\n'
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            finding = {"id": "F", "severity": "HIGH", "summary": "timeout isolation broken", "blocking_status": "BLOCKING", "recurrence_key": "timeout-terminal", "evidence": "e"}
            output = (
                "FLOW_REVIEW_REPORT_BEGIN\n"
                + json.dumps({"status": "FAILED", "reviewed_digest": artifact["digest"], "findings": [finding]})
                + "\nFLOW_REVIEW_REPORT_END\n"
            ).encode()
            with patch("flowctl_lib.reviews.subprocess.run", side_effect=subprocess.TimeoutExpired([], 1, output=output, stderr=b"")):
                result = run_cursor_review(
                    state_path, "spec:M1", prompt, root / "unused.py", "fake", "high", 5,
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
        self.assertEqual(("UNCLASSIFIED", "UNKNOWN_FAILURE"), classify_process(2, "", "business connection timeout", False))
        structured = (
            'FLOW_REVIEW_ERROR_BEGIN\n'
            '{"schema_version":1,"code":"SDK_UNAVAILABLE"}\n'
            'FLOW_REVIEW_ERROR_END\n'
        )
        self.assertEqual(("RUN_ERROR", "SDK_UNAVAILABLE"), classify_process(2, "", structured, False))
        self.assertEqual(("RUN_ERROR", "PROCESS_TIMEOUT"), classify_process(None, "", "", True))
        self.assertEqual(("REVIEW_RESULT", None), classify_process(0, "timeout discussed in finding", "", False))
        self.assertEqual(("UNCLASSIFIED", "UNKNOWN_FAILURE"), classify_process(2, "odd", "", False))

    def test_official_runner_frames_early_runtime_failure(self):
        runner = ROOT.parent / "skills" / "cursor-review" / "scripts" / "cursor_review.py"
        env = dict(os.environ)
        env["CURSOR_REVIEW_RUNTIME_PYTHON"] = "/definitely/missing/cursor-review-python"
        result = subprocess.run(
            [sys.executable, str(runner), "--check"], text=True,
            capture_output=True, env=env,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("FLOW_REVIEW_ERROR_BEGIN", result.stderr)
        self.assertIn('{"schema_version": 1, "code": "SDK_UNAVAILABLE"}', result.stderr)
        self.assertIn("FLOW_REVIEW_ERROR_END", result.stderr)

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

    def test_cursor_review_requires_gpt_and_two_runtime_failures_degrade(self):
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
            handoff = root / "handoff.json"
            handoff.write_text(json.dumps({
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710",
                "from_stage": "flow-spec", "next_stage": "flow-plan", "artifact_key": "spec:M1",
            }))
            accepted = accept_handoff(state_path, handoff, result["state_revision"])
            self.assertEqual("flow-plan", accepted["current_stage"])
            self.assertEqual("COMPLETE_WITH_DEFECT", accepted["completion_quality"])

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
                prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
                runner = root / "missing-terminal.py"
                runner.write_text(f"import sys\nprint({output!r})\nsys.exit(2)\n")
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
            prompt.write_text(f"Review {artifact['path']} at {artifact['digest']}")
            runner = root / "missing-stderr.py"
            runner.write_text(
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
            runner.write_text(
                'import json, pathlib, re, sys\n'
                'prompt = pathlib.Path(sys.argv[2]).read_text()\n'
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
                        f"Review exact artifact {path.resolve()} bound to {milestone_refs[kind]['digest']} "
                        "and return the required JSON review report."
                    )
                    cursor = run_cursor_review(state_path, key, prompt, runner, "fake", "high", 5, reviewed["state_revision"])
                    self.assertEqual("PASSED", cursor["status"])
                    if milestone == "M2" and kind == "code":
                        discovery = resume_flow("BCS-710", root)
                        resumed = reconcile_resume(state_path, discovery, cursor["state_revision"])
                        self.assertEqual("flow-code", resumed["current_stage"])
                        self.assertEqual("M2", resumed["active_milestone"])
                        self.assertEqual("handoff:code", resumed["pending_action"])
                        cursor["state_revision"] = resumed["state_revision"]
                    result = handoff(kind, next_stage, key, cursor["state_revision"])
                    state = load_state(state_path)
                    self.assertEqual(next_stage, result["current_stage"])

                integration, _ = write_artifact(
                    issue_dir, "integration", milestone=milestone, upstream=milestone_refs,
                    name=f"integration_{milestone}.md",
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
