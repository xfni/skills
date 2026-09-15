import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "flowctl.py"


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
            self.assertTrue(status["audit"]["event_head"].startswith("sha256:"))
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
