import json
import os
from pathlib import Path
import tempfile
import unittest

import test_flowctl as fixtures
from flowctl_lib.cli import _parser, dispatch
from flowctl_lib.continuation import inspect_continuation


class ContinuationInspectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = fixtures.ReviewAndHandoffTests()._state_with_spec(self.root)

    def state(self):
        return json.loads(self.path.read_text())

    def write(self, **changes):
        state = self.state()
        state.update(changes)
        self.path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True))

    def inspect(self):
        return inspect_continuation(self.path)["continuation"]

    def test_cli_exposes_read_only_inspect(self):
        args = _parser().parse_args(["continuation", "inspect", "--state", str(self.path)])
        result = dispatch(args)
        self.assertTrue(result["ok"])
        self.assertIn(result["continuation"]["decision"], {"CONTINUE", "ALLOW_STOP"})

    def test_classifies_terminal_wait_block_unknown_inactive_and_actionable(self):
        cases = [
            ({"current_stage": "complete", "pending_action": None}, "COMPLETE"),
            ({"pending_signal": {"signal": "FLOW_RUN_HUMAN_GATE"}}, "HUMAN_WAIT"),
            ({"pending_action": "blocked:environment"}, "BLOCKED"),
            ({"pending_action": ["produce:spec"]}, "UNKNOWN"),
            ({"pending_action": None, "pending_signal": None}, "INACTIVE"),
            ({"pending_action": "produce:spec", "pending_signal": None}, "ACTIONABLE"),
            ({"pending_action": "snapshot:capture", "pending_signal": None}, "ACTIONABLE"),
        ]
        original = self.state()
        for changes, expected in cases:
            with self.subTest(expected=expected):
                state = dict(original)
                state.update(changes)
                self.path.write_text(json.dumps(state))
                self.assertEqual(expected, self.inspect()["reason_code"])

    def test_route_back_does_not_make_unknown_action_actionable(self):
        self.write(pending_signal={"signal": "FLOW_RUN_ROUTE_BACK"}, pending_action="invent:stage")
        self.assertEqual("UNKNOWN", self.inspect()["reason_code"])

    def test_fingerprint_ignores_revision_goal_and_unrelated_review_but_tracks_relevant_facts(self):
        self.write(pending_signal=None, pending_action="review:gpt:await-result")
        first = self.inspect()["progress_fingerprint"]
        state = self.state()
        state["state_revision"] += 99
        state["runtime_goal"] = {"threadId": "x", "objective": "ignored", "status": "active", "createdAt": 1}
        state.setdefault("reviews", {}).setdefault("attempts", {})["unrelated"] = {
            "attempt_id": "unrelated", "artifact_key": "plan:M2", "artifact_digest": "sha256:x"
        }
        self.path.write_text(json.dumps(state))
        self.assertEqual(first, self.inspect()["progress_fingerprint"])
        key = "spec:M1"
        state = self.state()
        state["artifacts"][key]["digest"] = "sha256:" + "1" * 64
        self.path.write_text(json.dumps(state))
        self.assertNotEqual(first, self.inspect()["progress_fingerprint"])

    def test_relevant_review_revocation_changes_fingerprint(self):
        self.write(pending_signal=None, pending_action="review:gpt:await-result")
        state = self.state()
        artifact = state["artifacts"]["spec:M1"]
        attempt = {
            "attempt_id": "r1", "artifact_key": "spec:M1", "artifact_digest": artifact["digest"],
            "backend": "gpt", "status": "PASSED", "classification": "REVIEW_RESULT", "eligible": True,
        }
        state["reviews"]["attempts"]["r1"] = attempt
        self.path.write_text(json.dumps(state))
        first = self.inspect()["progress_fingerprint"]
        state["reviews"]["attempts"]["r1"]["revoked"] = True
        state["reviews"]["attempts"]["r1"]["invalidated_by"] = "spec:M1"
        self.path.write_text(json.dumps(state))
        self.assertNotEqual(first, self.inspect()["progress_fingerprint"])

    def test_success_is_byte_mtime_and_directory_stable(self):
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns, sorted(p.name for p in self.path.parent.iterdir())
        inspect_continuation(self.path)
        after = self.path.read_bytes(), self.path.stat().st_mtime_ns, sorted(p.name for p in self.path.parent.iterdir())
        self.assertEqual(before, after)

    def test_final_symlink_is_rejected_without_writes(self):
        link = self.root / "linked-state.json"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(Exception, "CONTINUATION_STATE_SYMLINK"):
            inspect_continuation(link)
        self.assertTrue(link.is_symlink())

    def test_boolean_is_not_accepted_as_revision(self):
        self.write(state_revision=True)
        with self.assertRaisesRegex(Exception, "CONTINUATION_STATE_SCHEMA_INVALID"):
            inspect_continuation(self.path)

    def test_controller_path_drift_is_unknown(self):
        self.write(controller_path=str(self.root / "different.json"),
                   pending_signal=None, pending_action="produce:spec")
        with self.assertRaisesRegex(Exception, "CONTINUATION_STATE_SCHEMA_INVALID"):
            self.inspect()

    def test_unknown_schema_is_structured_failure_and_optional_malformed_is_unknown(self):
        for invalid in (999, True, [], {}):
            with self.subTest(schema_version=invalid):
                self.write(schema_version=invalid)
                before = self.path.read_bytes()
                with self.assertRaisesRegex(Exception, "CONTINUATION_STATE_SCHEMA_INVALID"):
                    self.inspect()
                self.assertEqual(before, self.path.read_bytes())
        self.write(schema_version=2, artifacts=[])
        self.assertEqual("UNKNOWN", self.inspect()["reason_code"])
        self.write(artifacts={}, pending_signal={"signal": []})
        self.assertEqual("UNKNOWN", self.inspect()["reason_code"])

    def test_schema_one_is_observable_and_malformed_stage_is_unknown(self):
        self.write(schema_version=1, pending_signal=None, pending_action="produce:spec")
        self.assertEqual("ACTIONABLE", self.inspect()["reason_code"])
        self.write(current_stage=[])
        self.assertEqual("UNKNOWN", self.inspect()["reason_code"])

    def test_fifo_controller_is_rejected_without_blocking(self):
        fifo = self.root / "state.fifo"
        os.mkfifo(fifo)
        started = __import__("time").monotonic()
        with self.assertRaisesRegex(Exception, "CONTINUATION_STATE_NOT_REGULAR"):
            inspect_continuation(fifo)
        self.assertLess(__import__("time").monotonic() - started, 0.5)

    def test_malformed_coder_and_snapshot_are_unknown_not_actionable(self):
        state = self.state()
        state.update(current_stage="flow-code", active_milestone="M1", pending_action="produce:code",
                     pending_signal=None, coder_agent={"active_task": 42})
        self.path.write_text(json.dumps(state))
        self.assertEqual("UNKNOWN", self.inspect()["reason_code"])

    def test_code_snapshot_and_coder_progress_change_fingerprint(self):
        state = self.state()
        state.update(current_stage="flow-code", active_milestone="M1", pending_action="review:gpt",
                     pending_signal=None,
                     coder_agent={"coder_thread_id": "coder-1", "completed_tasks": ["TASK-1"],
                                  "replacement_generation": 0})
        state["artifacts"]["code:M1"] = {
            **state["artifacts"]["spec:M1"], "type": "code", "milestone_id": "M1",
        }
        state["snapshots"] = {"code:M1": {
            "snapshot_digest": "sha256:s1", "head": "abc", "status_digest": "sha256:status",
            "tracked_diff_digest": "sha256:diff", "untracked": {},
        }}
        self.path.write_text(json.dumps(state))
        first = self.inspect()["progress_fingerprint"]
        state["coder_agent"]["completed_tasks"].append("TASK-2")
        self.path.write_text(json.dumps(state))
        second = self.inspect()["progress_fingerprint"]
        self.assertNotEqual(first, second)
        state["snapshots"]["code:M1"]["snapshot_digest"] = "sha256:s2"
        self.path.write_text(json.dumps(state))
        self.assertNotEqual(second, self.inspect()["progress_fingerprint"])
        state["coder_agent"] = {}
        state["artifacts"]["code:M1"] = {
            **state["artifacts"]["spec:M1"], "type": "code", "milestone_id": "M1",
        }
        state["snapshots"] = {"code:M1": {"snapshot_digest": 42, "untracked": {}}}
        self.path.write_text(json.dumps(state))
        self.assertEqual("UNKNOWN", self.inspect()["reason_code"])


if __name__ == "__main__":
    unittest.main()
