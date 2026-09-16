import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills/ibrain-review/scripts/ibrain_review.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("ibrain_review", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IbrainReviewTests(unittest.TestCase):
    def test_missing_key_is_framed_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(RUNNER), "--check",
                "--api-key-file", str(Path(tmp) / "missing")], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('"code": "CREDENTIAL_UNAVAILABLE"', result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_list_models_uses_discovery_endpoint_and_prints_ids_only(self):
        runner = load_runner()
        with patch.object(runner, "request_json", return_value={"data":[{"id":"glm-5.3"},{"id":"other"}]}) as get:
            self.assertEqual(runner.discover_models("secret-key", 30), ["glm-5.3", "other"])
        self.assertEqual(get.call_args.args[0], "http://ibrain.qiyi.domain/v1/models")

    def request_args(self, root):
        path = root.resolve() / "request.json"
        path.write_text(json.dumps({"schema_version":1, "manifest":{}, "prompt":"review",
            "files":[{"path":"spec.md","content":"approved"}],
            "capabilities":{"local_tools":False,"implicit_indexing":False}}))
        return SimpleNamespace(request_file=str(path), no_tools=True, model="glm-5.3", timeout_seconds=1,
            expected_request_digest='sha256:' + hashlib.sha256(path.read_bytes()).hexdigest())

    def test_review_direct_responses_exact_input_auth_header_and_report_frame(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            args = self.request_args(Path(tmp))
            output = io.StringIO()
            response = io.BytesIO(json.dumps({"status":"completed","output":[
                {"type":"message", "content":[{"type":"output_text", "text":"review-result"}]}]}).encode())
            with patch.object(runner.urllib.request, "urlopen", return_value=response) as send, \
                    patch("subprocess.Popen", side_effect=AssertionError("no subprocess")), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(runner.run_review(args, "secret-key"), 0)
            request = send.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
            payload = json.loads(request.data)
            self.assertEqual(payload, {"model":"glm-5.3", "stream":False,
                                      "input":Path(args.request_file).read_text()})
            self.assertNotIn("secret-key", request.data.decode())
        self.assertEqual(output.getvalue(), "FLOW_REVIEW_REPORT_BEGIN\nreview-result\nFLOW_REVIEW_REPORT_END\n")

    def test_review_collapses_identical_model_frames_to_one_runner_frame(self):
        runner = load_runner()
        report = json.dumps({"status":"PASSED", "reviewed_digest":"sha256:" + "a" * 64,
                             "findings":[]})
        framed = ("FLOW_REVIEW_REPORT_BEGIN\n" + report + "\nFLOW_REVIEW_REPORT_END\n") * 2
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(runner.emit_report(framed))
        self.assertEqual(output.getvalue().count("FLOW_REVIEW_REPORT_BEGIN"), 1)
        self.assertEqual(output.getvalue().count("FLOW_REVIEW_REPORT_END"), 1)
        self.assertEqual(json.loads(output.getvalue().splitlines()[1]), json.loads(report))

    def test_review_rejects_conflicting_model_frames(self):
        runner = load_runner()
        first = json.dumps({"status":"PASSED", "reviewed_digest":"sha256:" + "a" * 64,
                            "findings":[]})
        second = json.dumps({"status":"INCOMPLETE", "reviewed_digest":"sha256:" + "a" * 64,
                             "findings":[]})
        raw = ("FLOW_REVIEW_REPORT_BEGIN\n" + first + "\nFLOW_REVIEW_REPORT_END\n"
               "FLOW_REVIEW_REPORT_BEGIN\n" + second + "\nFLOW_REVIEW_REPORT_END\n")
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            self.assertFalse(runner.emit_report(raw))
        self.assertEqual(output.getvalue(), "")
        self.assertIn('"code": "PROTOCOL_ERROR"', error.getvalue())

    def test_review_rejects_framed_report_with_prose_or_duplicate_json_keys(self):
        runner = load_runner()
        for raw in (
            'Done.\nFLOW_REVIEW_REPORT_BEGIN\n{"status":"PASSED"}\nFLOW_REVIEW_REPORT_END',
            'FLOW_REVIEW_REPORT_BEGIN\n{"status":"PASSED","status":"FAILED"}\nFLOW_REVIEW_REPORT_END',
        ):
            with self.subTest(raw=raw):
                output = io.StringIO()
                error = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    self.assertFalse(runner.emit_report(raw))
                self.assertEqual('', output.getvalue())
                self.assertIn('"code": "PROTOCOL_ERROR"', error.getvalue())

    def test_timeout_has_redacted_frame_and_never_starts_process(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as tmp:
            args = self.request_args(Path(tmp))
            error = io.StringIO()
            with patch.object(runner.urllib.request, "urlopen", side_effect=TimeoutError("secret diagnostic")), \
                    patch("subprocess.Popen", side_effect=AssertionError("no subprocess")), \
                    contextlib.redirect_stderr(error):
                self.assertEqual(runner.run_review(args, "secret-key"), 2)
        self.assertIn('"code": "PROCESS_TIMEOUT"', error.getvalue())
        self.assertNotIn("secret", error.getvalue())


if __name__ == "__main__":
    unittest.main()
