import json
import fcntl
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import unittest
import importlib.util
import io
import os
import threading
from unittest import mock

import test_flowctl as fixtures


class ContinuationHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.install = self.root / "codex home" / "flow-v2"
        self.install.mkdir(parents=True)
        source = Path(__file__).parents[1]
        shutil.copy2(source / "flowctl.py", self.install / "flowctl.py")
        shutil.copy2(source / "continuation_hook.py", self.install / "continuation_hook.py")
        shutil.copytree(source / "flowctl_lib", self.install / "flowctl_lib")
        self.helper = self.install / "continuation_hook.py"
        self.worktree = self.root / "worktree"
        self.worktree.mkdir()
        self.state = fixtures.ReviewAndHandoffTests()._state_with_spec(self.worktree)
        value = json.loads(self.state.read_text())
        value["pending_signal"] = None
        value["pending_action"] = "produce:spec"
        self.state.write_text(json.dumps(value))
        self.session = "session-one"
        self.turn = "turn-one"

    def run_helper(self, *args, event=None):
        return subprocess.run(
            [sys.executable, str(self.helper), *args],
            input=json.dumps(event) if event is not None else None,
            text=True, capture_output=True, check=False,
        )

    def event(self, name, **changes):
        value = {"hook_event_name": name, "session_id": self.session,
                 "turn_id": self.turn, "cwd": str(self.worktree)}
        value.update(changes)
        return value

    def load_helper_module(self):
        spec = importlib.util.spec_from_file_location(
            f"isolated_continuation_hook_{id(self)}_{time.time_ns()}", self.helper
        )
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(self.install))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        return module

    def activate(self, state=None, session=None, extra=()):
        return self.run_helper("activate", "--state", str(state or self.state),
                               "--session-id", session or self.session, *extra)

    def test_marker_omits_prompt_and_activation_binds_turn(self):
        marker = self.run_helper("hook", event=self.event("UserPromptSubmit", prompt="SECRET"))
        self.assertEqual(0, marker.returncode, marker.stderr)
        files = list((self.install / "runtime" / "turns").glob("*.json"))
        self.assertEqual(1, len(files))
        self.assertNotIn("SECRET", files[0].read_text())
        activated = self.activate()
        self.assertEqual(0, activated.returncode, activated.stderr)
        value = json.loads(activated.stdout)
        self.assertTrue(value["ok"])
        self.assertEqual(self.turn, value["turn_id"])
        self.assertEqual(1, value["generation"])

    def test_same_fingerprint_blocks_once_then_allows_and_deactivates(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        first = self.run_helper("hook", event=self.event("Stop", stop_hook_active=False))
        self.assertEqual("block", json.loads(first.stdout)["decision"])
        second = self.run_helper("hook", event=self.event("Stop", stop_hook_active=True))
        self.assertNotEqual("block", json.loads(second.stdout or "{}").get("decision"))

    def test_turn_mismatch_allows_and_old_generation_cannot_delete_new_owner(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        activation = json.loads(self.activate().stdout)
        result = self.run_helper("hook", event=self.event("Stop", turn_id="turn-two"))
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))
        stale = self.run_helper("deactivate", "--state", str(self.state), "--session-id", self.session,
                                "--generation", str(activation["generation"]), "--reason", "explicit_stop")
        self.assertEqual(0, stale.returncode)

    def test_same_session_cannot_activate_second_controller_without_replace(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        other_root = self.root / "other"
        other_root.mkdir()
        other = fixtures.ReviewAndHandoffTests()._state_with_spec(other_root)
        value = json.loads(other.read_text())
        value.update(pending_signal=None, pending_action="produce:spec")
        other.write_text(json.dumps(value))
        self.run_helper("hook", event=self.event("UserPromptSubmit", cwd=str(other_root)))
        conflict = self.activate(state=other)
        self.assertNotEqual(0, conflict.returncode)
        self.assertIn("OWNER_CONFLICT", conflict.stdout)

    def test_missing_marker_and_bad_event_fail_open(self):
        self.assertNotEqual(0, self.activate().returncode)
        result = self.run_helper("hook", event={"hook_event_name": "Stop"})
        self.assertEqual(0, result.returncode)
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))

    def test_two_concurrent_stops_record_only_one_nudge(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        lock_path = self.install / "runtime" / "owners" / f"{hashlib.sha256(self.session.encode()).hexdigest()}.lock"
        with lock_path.open("r+") as barrier:
            fcntl.flock(barrier, fcntl.LOCK_EX)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.run_helper, "hook", event=self.event("Stop")) for _ in range(2)]
                time.sleep(0.1)
                fcntl.flock(barrier, fcntl.LOCK_UN)
                results = [future.result() for future in futures]
        decisions = [json.loads(item.stdout or "{}").get("decision") for item in results]
        self.assertEqual(1, decisions.count("block"))

    def test_replace_owner_a_to_b_to_a_closes_superseded_sidecars(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        first = json.loads(self.activate().stdout)
        first_sidecar = Path(first["controller_path"])
        other_root = self.root / "other-replace"
        other_root.mkdir()
        other = fixtures.ReviewAndHandoffTests()._state_with_spec(other_root)
        value = json.loads(other.read_text())
        value.update(pending_signal=None, pending_action="produce:spec")
        other.write_text(json.dumps(value))
        self.run_helper("hook", event=self.event("UserPromptSubmit", cwd=str(other_root)))
        replaced = self.activate(state=other, extra=("--replace-owner", "--reason", "human chose B"))
        self.assertEqual(0, replaced.returncode, replaced.stdout + replaced.stderr)
        runtime = self.install / "runtime" / "continuations"
        records = [json.loads(path.read_text()) for path in runtime.glob("*.json")]
        a = next(item for item in records if item["controller_path"] == str(self.state.resolve()))
        self.assertFalse(a["active"])
        self.run_helper("hook", event=self.event("UserPromptSubmit", cwd=str(self.worktree)))
        back = self.activate(extra=("--replace-owner", "--reason", "human chose A"))
        self.assertEqual(0, back.returncode, back.stdout + back.stderr)

    def test_other_session_same_controller_requires_explicit_takeover(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        session_two = "session-two"
        self.run_helper("hook", event=self.event("UserPromptSubmit", session_id=session_two, turn_id="turn-two"))
        conflict = self.activate(session=session_two)
        self.assertNotEqual(0, conflict.returncode)
        self.assertIn("OWNER_CONFLICT", conflict.stdout)
        takeover = self.activate(session=session_two,
                                 extra=("--replace-owner", "--reason", "human chose session two"))
        self.assertEqual(0, takeover.returncode, takeover.stdout + takeover.stderr)
        old_stop = self.run_helper("hook", event=self.event("Stop"))
        self.assertNotEqual("block", json.loads(old_stop.stdout or "{}").get("decision"))

    def test_corrupted_sidecar_identity_fails_open(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        path = next((self.install / "runtime" / "continuations").glob("*.json"))
        value = json.loads(path.read_text())
        value["schema_version"] = 999
        value["controller_path"] = "/different/controller"
        value["issue_id"] = "BCS-999"
        path.write_text(json.dumps(value))
        result = self.run_helper("hook", event=self.event("Stop"))
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))

    def test_wrong_but_well_formed_sidecar_issue_fails_open(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        path = next((self.install / "runtime" / "continuations").glob("*.json"))
        value = json.loads(path.read_text())
        value["issue_id"] = "BCS-999"
        path.write_text(json.dumps(value))
        result = self.run_helper("hook", event=self.event("Stop"))
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))

    def test_activation_rejects_controller_final_symlink(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        link = self.root / "flow-state-link.json"
        link.symlink_to(self.state)
        result = self.activate(state=link)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("CONTINUATION_STATE_SYMLINK", result.stdout)

    def test_four_distinct_progresses_block_then_fifth_allows(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        decisions = []
        for index in range(5):
            value = json.loads(self.state.read_text())
            value["pending_action"] = f"produce:spec-{index}"
            self.state.write_text(json.dumps(value))
            result = self.run_helper("hook", event=self.event("Stop"))
            decisions.append(json.loads(result.stdout or "{}").get("decision"))
        self.assertEqual(["block"] * 4 + [None], decisions)

    def test_idle_stop_does_not_invoke_flowctl(self):
        sentinel = self.root / "flowctl-invoked"
        (self.install / "flowctl.py").write_text(
            "from pathlib import Path\nPath(%r).write_text('called')\n" % str(sentinel)
        )
        result = self.run_helper("hook", event=self.event("Stop"))
        self.assertEqual(0, result.returncode)
        self.assertFalse(sentinel.exists())

    def test_inspection_timeout_fails_open_within_hook_bound(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        (self.install / "flowctl.py").write_text("import time\ntime.sleep(10)\n")
        started = time.monotonic()
        result = self.run_helper("hook", event=self.event("Stop"))
        elapsed = time.monotonic() - started
        self.assertEqual(0, result.returncode)
        self.assertLess(elapsed, 3.5)
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))

    def test_runtime_write_failure_fails_open(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        module = self.load_helper_module()
        with mock.patch.object(module, "_write", side_effect=OSError("injected write failure")), \
                mock.patch.object(module.sys, "stdin", io.StringIO(json.dumps(self.event("Stop")))):
            self.assertIsNone(module.hook())

    def test_inconsistent_budget_record_fails_open(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        path = next((self.install / "runtime" / "continuations").glob("*.json"))
        value = json.loads(path.read_text())
        value.update(max_nudges=1, nudge_count=0,
                     nudged_fingerprints=["sha256:" + "a" * 64])
        path.write_text(json.dumps(value))
        result = self.run_helper("hook", event=self.event("Stop"))
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))

    def test_fifo_owner_record_fails_open_without_blocking(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        digest = hashlib.sha256(self.session.encode()).hexdigest()
        owner = self.install / "runtime" / "owners" / f"{digest}.json"
        owner.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(owner)
        started = time.monotonic()
        result = self.run_helper("hook", event=self.event("Stop"))
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertNotEqual("block", json.loads(result.stdout or "{}").get("decision"))

    def test_same_session_concurrent_a_b_activation_has_one_owner(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        other = self.state.with_name("other-flow-state.json")
        value = json.loads(self.state.read_text())
        value["controller_path"] = str(other.resolve())
        other.write_text(json.dumps(value))
        lock_path = self.install / "runtime" / "owners" / f"{hashlib.sha256(self.session.encode()).hexdigest()}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()
        with lock_path.open("r+") as barrier:
            fcntl.flock(barrier, fcntl.LOCK_EX)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.activate, state=target) for target in (self.state, other)]
                time.sleep(0.1)
                fcntl.flock(barrier, fcntl.LOCK_UN)
                results = [future.result() for future in futures]
        self.assertEqual([0, 2], sorted(item.returncode for item in results))
        owner = json.loads(next((self.install / "runtime" / "owners").glob("*.json")).read_text())
        self.assertIn(owner["controller_path"], {str(self.state.resolve()), str(other.resolve())})

    def test_old_stop_racing_new_session_takeover_cannot_delete_new_owner(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        session_two = "session-two-race"
        self.run_helper("hook", event=self.event("UserPromptSubmit", session_id=session_two, turn_id="turn-two"))
        digest = hashlib.sha256(str(self.state.resolve()).encode()).hexdigest()
        lock_path = self.install / "runtime" / "continuations" / f"{digest}.lock"
        with lock_path.open("r+") as barrier:
            fcntl.flock(barrier, fcntl.LOCK_EX)
            with ThreadPoolExecutor(max_workers=2) as pool:
                old_future = pool.submit(self.run_helper, "hook", event=self.event("Stop"))
                new_future = pool.submit(
                    self.activate, session=session_two,
                    extra=("--replace-owner", "--reason", "human chose new session"),
                )
                time.sleep(0.1)
                fcntl.flock(barrier, fcntl.LOCK_UN)
                old_result, new_result = old_future.result(), new_future.result()
        self.assertEqual(0, new_result.returncode, new_result.stdout + new_result.stderr)
        self.assertNotEqual("block", json.loads(old_result.stdout or "{}").get("decision"))
        owner_path = self.install / "runtime" / "owners" / f"{hashlib.sha256(session_two.encode()).hexdigest()}.json"
        owner = json.loads(owner_path.read_text())
        sidecar = json.loads(next((self.install / "runtime" / "continuations").glob("*.json")).read_text())
        self.assertEqual(session_two, owner["session_id"])
        self.assertEqual(session_two, sidecar["owner_session_id"])
        self.assertTrue(sidecar["active"])

    def test_deactivate_while_inspect_is_suspended_prevents_commit(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        activation = json.loads(self.activate().stdout)
        module = self.load_helper_module()
        entered, release = threading.Event(), threading.Event()
        observation = module.inspect_continuation(str(self.state))

        def suspended_inspect(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return subprocess.CompletedProcess(args[0], 0, json.dumps(observation), "")

        with mock.patch.object(module.subprocess, "run", side_effect=suspended_inspect):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(module.stop, self.event("Stop"))
                self.assertTrue(entered.wait(1))
                result = module.deactivate(str(self.state), self.session,
                                           activation["generation"], "explicit_stop")
                self.assertTrue(result["deactivated"])
                release.set()
                self.assertIsNone(future.result())

    def test_takeover_while_inspect_is_suspended_prevents_old_commit(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        self.assertEqual(0, self.activate().returncode)
        session_two = "session-inspect-takeover"
        self.run_helper("hook", event=self.event("UserPromptSubmit", session_id=session_two, turn_id="turn-two"))
        module = self.load_helper_module()
        entered, release = threading.Event(), threading.Event()
        observation = module.inspect_continuation(str(self.state))

        def suspended_inspect(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return subprocess.CompletedProcess(args[0], 0, json.dumps(observation), "")

        with mock.patch.object(module.subprocess, "run", side_effect=suspended_inspect):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(module.stop, self.event("Stop"))
                self.assertTrue(entered.wait(1))
                takeover = module.activate(str(self.state), session_two, replace_owner=True,
                                           reason="human chose new session")
                release.set()
                self.assertIsNone(future.result())
        self.assertEqual(session_two, takeover["owner_session_id"])

    def test_old_generation_delete_cannot_remove_new_same_session_owner(self):
        self.run_helper("hook", event=self.event("UserPromptSubmit"))
        activation = json.loads(self.activate().stdout)
        module = self.load_helper_module()
        module.marker(self.event("UserPromptSubmit", turn_id="turn-two"))
        entered, release = threading.Event(), threading.Event()
        original_write = module._write

        def suspended_inactive_write(path, value):
            if path.parent.name == "continuations" and value.get("active") is False:
                entered.set()
                self.assertTrue(release.wait(2))
            return original_write(path, value)

        with mock.patch.object(module, "_write", side_effect=suspended_inactive_write):
            with ThreadPoolExecutor(max_workers=2) as pool:
                old_future = pool.submit(module.deactivate, str(self.state), self.session,
                                         activation["generation"], "explicit_stop")
                self.assertTrue(entered.wait(1))
                new_future = pool.submit(module.activate, str(self.state), self.session)
                time.sleep(0.1)
                self.assertFalse(new_future.done())
                release.set()
                self.assertTrue(old_future.result()["deactivated"])
                replacement = new_future.result()
        owner_path = self.install / "runtime" / "owners" / f"{hashlib.sha256(self.session.encode()).hexdigest()}.json"
        owner = json.loads(owner_path.read_text())
        self.assertEqual(replacement["generation"], owner["generation"])
        self.assertGreater(replacement["generation"], activation["generation"])


if __name__ == "__main__":
    unittest.main()
