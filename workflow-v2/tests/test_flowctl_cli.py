import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "flowctl.py"
sys.path.insert(0, str(ROOT))

from flowctl_lib.cli import dispatch
from flowctl_lib.errors import FlowctlError


def artifact(path, kind="requirement", issue="BCS-710"):
    body = f"artifact_type: {kind}\nissue_id: {issue}\ncontent_revision: 1\nstatus: APPROVED\n"
    digest = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    path.write_text(
        "--- FLOW BODY BEGIN ---\n" + body +
        "--- FLOW BODY END ---\n--- FLOW INTEGRITY BEGIN ---\n"+
        f"content_digest: {digest}\n--- FLOW INTEGRITY END ---\n"+
        "--- FLOW APPROVAL BEGIN ---\nstatus: APPROVED\napproved_revision: 1\n"+
        f"approved_digest: {digest}\nconfirmer: HUMAN\n--- FLOW APPROVAL END ---\n"
    )
    return digest


class FlowctlCliTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True, capture_output=True)
        self.assertEqual(expected, result.returncode, result.stderr or result.stdout)
        return json.loads(result.stdout or result.stderr)

    def test_init_verify_register_status_resume_and_error_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            result = self.run_cli("init", "--issue", "BCS-710", "--repo", root, "--branch", "feature-BCS-710-flowctl", "--state", state)
            self.assertTrue(result["ok"])
            doc = state.parent / "requirement_20260914_flowctl.md"
            digest = artifact(doc)
            verified = self.run_cli("artifact", "verify", "--path", doc, "--type", "requirement", "--issue", "BCS-710")
            self.assertEqual(digest, verified["artifact"]["digest"])
            registered = self.run_cli("artifact", "register", "--state", state, "--path", doc, "--type", "requirement", "--expected-revision", 0)
            self.assertEqual("handoff:requirement", registered["state"]["pending_action"])
            status = self.run_cli("status", "--state", state)
            self.assertEqual(1, status["state"]["state_revision"])
            self.assertEqual('进行中', status['stage_summary']['status'])
            self.assertIsNone(status['stage_summary']['result'])
            self.assertNotIn('audit', status)
            audited = self.run_cli('audit', '--state', state)
            self.assertTrue(audited['audit']['event_head'].startswith('sha256:'))
            resumed = self.run_cli(
                "resume", "--issue", "BCS-710", "--repo", root,
                "--state", state, "--expected-revision", 1,
            )
            self.assertEqual("flow-requirement", resumed["next_stage"])
            self.assertEqual("handoff:requirement", resumed["pending_action"])
            error = self.run_cli("status", "--state", root / "missing.json", expected=2)
            self.assertFalse(error["ok"])
            self.assertEqual("CONTROLLER_NOT_FOUND", error["error"]["code"])

    def test_handoff_schema_is_shipped(self):
        schema = json.loads((ROOT / "schemas" / "handoff.schema.json").read_text())
        self.assertEqual("FLOW_RUN_HANDOFF", schema["properties"]["signal"]["const"])

    def test_handoff_cli_rejects_non_object_and_boolean_schema_version_structurally(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            self.run_cli(
                "init", "--issue", "BCS-710", "--repo", root,
                "--branch", "feature-BCS-710-flowctl", "--state", state,
            )
            doc = state.parent / "requirement_20260914_flowctl.md"
            artifact(doc)
            self.run_cli(
                "artifact", "register", "--state", state, "--path", doc,
                "--type", "requirement", "--expected-revision", 0,
            )
            valid = {
                "schema_version": 1, "signal": "FLOW_RUN_HANDOFF", "issue_id": "BCS-710",
                "run_id": "run-bcs-710", "from_stage": "flow-requirement",
                "next_stage": "flow-intent", "artifact_key": "requirement",
            }
            payloads = [None, "not-an-object", [], {**valid, "schema_version": True}]
            for index, payload in enumerate(payloads):
                handoff = root / f"invalid-handoff-{index}.json"
                handoff.write_text(json.dumps(payload))
                result = self.run_cli(
                    "handoff", "accept", "--state", state, "--handoff", handoff,
                    "--expected-revision", 1, expected=2,
                )
                self.assertIn(
                    result["error"]["code"],
                    {"INVALID_HANDOFF_JSON", "HANDOFF_SCHEMA_INVALID"},
                )

    def test_authorization_decide_rejects_malformed_non_object_unknown_and_invalid_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            self.run_cli(
                "init", "--issue", "BCS-710", "--repo", root,
                "--branch", "feature-BCS-710-flowctl", "--state", state,
            )

            invalid_cases = (
                ("external_review", "not-json", "INVALID_AUTHORIZATION_JSON"),
                ("external_review", json.dumps("GRANTED"), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps(["GRANTED"]), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps({"decision": "GRANTED"}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps({"decision": "GRANTED", "allowed_stages": []}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps({"decision": "GRANTED", "allowed_stages": ["flow-spec", "flow-spec"]}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps({"decision": "GRANTED", "allowed_stages": ["flow-integration"]}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps({"decision": "GRANTED", "extra": True}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("external_review", json.dumps({"decision": True}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("production_replay", json.dumps({"decision": "GRANTED"}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("production_replay", json.dumps({"decision": "RAW_REPLAY"}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
                ("production_replay", json.dumps({"decision": "SKIP_PRODUCTION_REPLAY", "allowed_stages": ["flow-integration"]}), "AUTHORIZATION_DECISION_SCHEMA_INVALID"),
            )
            for kind, decision, expected_code in invalid_cases:
                with self.subTest(kind=kind, decision=decision):
                    result = self.run_cli(
                        "authorization", "decide", "--state", state,
                        "--kind", kind, "--decision", decision,
                        "--expected-revision", 0, expected=2,
                    )
                    self.assertEqual(expected_code, result["error"]["code"])

    def test_authorization_dispatch_rejects_boolean_expected_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            self.run_cli(
                "init", "--issue", "BCS-710", "--repo", root,
                "--branch", "feature-BCS-710-flowctl", "--state", state,
            )
            args = SimpleNamespace(
                command="authorization",
                authorization_command="decide",
                state=str(state),
                kind="external_review",
                decision=json.dumps({"decision": "GRANTED"}),
                expected_revision=False,
            )
            with self.assertRaisesRegex(FlowctlError, "INVALID_EXPECTED_REVISION"):
                dispatch(args)

    def test_authorization_decide_is_idempotent_and_returns_authorization_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            self.run_cli(
                "init", "--issue", "BCS-710", "--repo", root,
                "--branch", "feature-BCS-710-flowctl", "--state", state,
            )
            decision = json.dumps({"decision": "SANITIZED_LOCAL_REPLAY"})

            decided = self.run_cli(
                "authorization", "decide", "--state", state,
                "--kind", "production_replay", "--decision", decision,
                "--expected-revision", 0,
            )
            authorization_id = decided["authorization"]["authorization_id"]
            self.assertTrue(authorization_id)
            self.assertEqual(authorization_id, decided["authorization_id"])
            self.assertEqual("SANITIZED_LOCAL_REPLAY", decided["authorization"]["decision"])
            self.assertEqual(1, decided["state"]["state_revision"])

            repeated = self.run_cli(
                "authorization", "decide", "--state", state,
                "--kind", "production_replay", "--decision", decision,
                "--expected-revision", 1,
            )
            self.assertEqual(authorization_id, repeated["authorization_id"])
            self.assertEqual(1, repeated["state"]["state_revision"])

    def test_external_review_cli_persists_stage_scope_and_requires_amendment_to_change_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            self.run_cli(
                "init", "--issue", "BCS-710", "--repo", root,
                "--branch", "feature-BCS-710-flowctl", "--state", state,
            )
            direct_spec = json.dumps({"decision": "GRANTED", "allowed_stages": ["flow-spec"]})
            granted = self.run_cli(
                "authorization", "decide", "--state", state,
                "--kind", "external_review", "--decision", direct_spec,
                "--expected-revision", 0,
            )
            self.assertEqual(["flow-spec"], granted["authorization"]["allowed_stages"])
            expanded = json.dumps({
                "decision": "GRANTED",
                "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
            })
            rejected = self.run_cli(
                "authorization", "decide", "--state", state,
                "--kind", "external_review", "--decision", expanded,
                "--expected-revision", 1, expected=2,
            )
            self.assertEqual("AUTHORIZATION_AMENDMENT_REQUIRED", rejected["error"]["code"])

    def test_authorization_amend_opens_bound_gate_then_decide_creates_new_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "feature-BCS-710-flowctl", str(root)], check=True, capture_output=True)
            state = root / ".ai" / "issue" / "BCS-710" / "flow-state.json"
            self.run_cli(
                "init", "--issue", "BCS-710", "--repo", root,
                "--branch", "feature-BCS-710-flowctl", "--state", state,
            )
            granted = self.run_cli(
                "authorization", "decide", "--state", state,
                "--kind", "external_review", "--decision", json.dumps({
                    "decision": "GRANTED", "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
                }),
                "--expected-revision", 0,
            )
            old_id = granted["authorization_id"]

            pending = self.run_cli(
                "authorization", "amend", "--state", state,
                "--kind", "external_review", "--decision", json.dumps({
                    "decision": "DENIED", "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
                }),
                "--expected-revision", 1,
            )
            self.assertEqual(old_id, pending["authorization_id"])
            self.assertEqual("AMENDMENT_PENDING", pending["authorization"]["status"])
            self.assertEqual({
                "decision": "DENIED", "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
            }, pending["authorization"]["proposed_decision"])

            amended = self.run_cli(
                "authorization", "decide", "--state", state,
                "--kind", "external_review", "--decision", json.dumps({
                    "decision": "DENIED", "allowed_stages": ["flow-spec", "flow-plan", "flow-code"],
                }),
                "--expected-revision", 2,
            )
            self.assertNotEqual(old_id, amended["authorization_id"])
            self.assertEqual("DENIED", amended["authorization"]["status"])
            self.assertEqual(2, amended["authorization"]["revision"])

    def test_authorization_decision_schema_is_shipped_with_exact_choices(self):
        schema = json.loads((ROOT / "schemas" / "authorization-decision.schema.json").read_text())
        self.assertEqual(2, len(schema["oneOf"]))
        external, replay = schema["oneOf"]
        self.assertEqual(["decision", "allowed_stages"], external["required"])
        self.assertEqual(["DENIED", "GRANTED"], external["properties"]["decision"]["enum"])
        self.assertEqual(["flow-spec", "flow-plan", "flow-code"],
                         external["properties"]["allowed_stages"]["items"]["enum"])
        self.assertTrue(external["properties"]["allowed_stages"]["uniqueItems"])
        self.assertEqual(1, external["properties"]["allowed_stages"]["minItems"])
        self.assertEqual(["decision"], replay["required"])
        self.assertEqual(["LOCAL_PRODUCTION_REPLAY", "SANITIZED_LOCAL_REPLAY", "SKIP_PRODUCTION_REPLAY"],
                         replay["properties"]["decision"]["enum"])
