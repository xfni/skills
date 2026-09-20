import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from unittest import mock


class HookInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "custom codex home"
        self.package = self.home / "flow-v2"
        self.package.mkdir(parents=True)
        source = Path(__file__).parents[1]
        shutil.copy2(source / "continuation_hook.py", self.package / "continuation_hook.py")
        shutil.copy2(source / "flowctl.py", self.package / "flowctl.py")
        shutil.copytree(source / "flowctl_lib", self.package / "flowctl_lib")
        (self.package / "scripts").mkdir()
        shutil.copy2(source / "scripts" / "install_codex_hooks.py",
                     self.package / "scripts" / "install_codex_hooks.py")
        self.installer = self.package / "scripts" / "install_codex_hooks.py"

    def run_installer(self):
        return subprocess.run([sys.executable, str(self.installer), "--codex-home", str(self.home)],
                              text=True, capture_output=True, check=False)

    def test_merges_handlers_preserves_existing_and_is_idempotent(self):
        existing = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}
        (self.home / "hooks.json").write_text(json.dumps(existing))
        first = self.run_installer()
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        first_bytes = (self.home / "hooks.json").read_bytes()
        value = json.loads(first_bytes)
        self.assertEqual(existing["hooks"]["SessionStart"], value["hooks"]["SessionStart"])
        self.assertIn("UserPromptSubmit", value["hooks"])
        self.assertIn("Stop", value["hooks"])
        self.assertNotIn("SubagentStop", value["hooks"])
        commands = [group["hooks"][0]["command"] for name in ("UserPromptSubmit", "Stop") for group in value["hooks"][name]]
        self.assertTrue(all(str(self.package / "continuation_hook.py") in item for item in commands))
        second = self.run_installer()
        self.assertEqual(0, second.returncode)
        self.assertEqual(first_bytes, (self.home / "hooks.json").read_bytes())

    def test_invalid_json_is_not_overwritten(self):
        path = self.home / "hooks.json"
        path.write_text("{broken")
        before = path.read_bytes()
        result = self.run_installer()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, path.read_bytes())

    def test_rejects_installer_not_deployed_under_selected_home(self):
        other = self.root / "other"
        result = subprocess.run([sys.executable, str(self.installer), "--codex-home", str(other)],
                                text=True, capture_output=True, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((other / "hooks.json").exists())

    def test_reports_inline_hook_warning_without_modifying_config(self):
        config = self.home / "config.toml"
        config.write_text('[hooks]\nStop = "legacy"\n[hooks.state]\ntrusted = true\n')
        result = self.run_installer()
        self.assertEqual(0, result.returncode)
        self.assertIn("INLINE_HOOK_WARNING", result.stdout)
        self.assertEqual('[hooks]\nStop = "legacy"\n[hooks.state]\ntrusted = true\n', config.read_text())

    def test_malformed_non_target_hook_is_rejected_without_rewrite(self):
        path = self.home / "hooks.json"
        path.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": "invalid"}]}}))
        before = path.read_bytes()
        result = self.run_installer()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, path.read_bytes())

    def test_atomic_replace_failure_preserves_original_hooks(self):
        path = self.home / "hooks.json"
        path.write_text(json.dumps({"hooks": {}}))
        before = path.read_bytes()
        spec = importlib.util.spec_from_file_location("isolated_hook_installer", self.installer)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.os, "replace", side_effect=OSError("injected replace failure")):
            with self.assertRaises(OSError):
                module.install(str(self.home))
        self.assertEqual(before, path.read_bytes())

    def test_invalid_toml_is_rejected_before_hooks_publication(self):
        path = self.home / "hooks.json"
        path.write_text(json.dumps({"hooks": {}}))
        before = path.read_bytes()
        (self.home / "config.toml").write_text("[broken")
        result = self.run_installer()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("CONFIG_TOML_INVALID", result.stdout)
        self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
