import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "ibrain-review" / "scripts" / "ibrain_review.py"


class IbrainReviewTests(unittest.TestCase):
    def run_runner(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(RUNNER), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_missing_key_is_framed_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_runner("--check", "--api-key-file", Path(temp_dir) / "missing")
        self.assertEqual(2, result.returncode)
        self.assertIn('"code": "CREDENTIAL_UNAVAILABLE"', result.stderr)
        self.assertNotIn("Traceback", result.stderr + result.stdout)

    def test_list_models_uses_discovery_endpoint_and_prints_ids_only(self):
        source = RUNNER.read_text()
        self.assertIn('MODELS_URL = "http://ibrain.qiyi.domain/v1/models"', source)
        self.assertIn('RESPONSES_BASE_URL = "http://ibrain.qiyi.domain/v1"', source)
        self.assertIn('DEFAULT_MODEL = "glm-5.3"', source)
        self.assertIn("Authorization", source)
        self.assertNotIn("print(api_key", source)
        self.assertIn("start_new_session=True", source)

    def test_review_runs_ephemeral_read_only_codex_and_frames_last_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            repo = temp / "repo"
            repo.mkdir()
            brief = temp / "brief.md"
            brief.write_text("Review this boundary", encoding="utf-8")
            key = temp / "API_KEY"
            key.write_text("secret-test-key", encoding="utf-8")
            capture = temp / "capture.json"
            fake_codex = temp / "codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, sys\n"
                "out = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
                "out.write_text('review-result', encoding='utf-8')\n"
                "pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps({"
                "'argv': sys.argv[1:], 'key': os.environ.get('IQIYI_IBRAIN_API_KEY')}))\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            env = dict(os.environ, CAPTURE=str(capture))
            result = self.run_runner(
                repo,
                brief,
                "--api-key-file",
                key,
                "--codex-bin",
                fake_codex,
                env=env,
            )
            recorded = json.loads(capture.read_text())

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("FLOW_REVIEW_REPORT_BEGIN\nreview-result\nFLOW_REVIEW_REPORT_END", result.stdout)
        self.assertEqual("secret-test-key", recorded["key"])
        argv = recorded["argv"]
        for expected in ("exec", "--ephemeral", "read-only", "glm-5.3"):
            self.assertIn(expected, argv)
        self.assertNotIn("secret-test-key", " ".join(argv))

    def test_timeout_terminates_the_entire_codex_process_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            repo = temp / "repo"
            repo.mkdir()
            brief = temp / "brief.md"
            brief.write_text("review", encoding="utf-8")
            key = temp / "API_KEY"
            key.write_text("secret-test-key", encoding="utf-8")
            orphan_marker = temp / "orphan"
            fake_codex = temp / "codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import os, subprocess, sys, time\n"
                "subprocess.Popen([sys.executable, '-c', "
                "'import pathlib,time; time.sleep(1.5); pathlib.Path(' + repr(os.environ['MARKER']) + ').write_text(\"orphan\")'])\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            env = dict(os.environ, MARKER=str(orphan_marker))
            result = self.run_runner(
                repo, brief, "--api-key-file", key, "--codex-bin", fake_codex,
                "--timeout-seconds", "1", env=env,
            )
            time.sleep(2)

        self.assertEqual(2, result.returncode)
        self.assertIn('"code": "PROCESS_TIMEOUT"', result.stderr)
        self.assertFalse(orphan_marker.exists())


if __name__ == "__main__":
    unittest.main()
