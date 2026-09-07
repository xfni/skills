from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "requirements-to-roadmap",
    "roadmap-to-spec-plan",
    "spec-plan-to-code",
)
CURSOR_SKILLS = SKILLS[1:]


class AiNativeWorkflowSkillTests(unittest.TestCase):
    def test_skills_are_listed_and_explicit_only(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        for name in SKILLS:
            self.assertIn(f'"./{name}"', manifest)
            skill = ROOT / name / "SKILL.md"
            metadata = ROOT / name / "agents" / "openai.yaml"
            self.assertTrue(skill.is_file())
            self.assertIn(f"name: {name}", skill.read_text())
            self.assertIn("allow_implicit_invocation: false", metadata.read_text())

    def test_cursor_review_scripts_are_portable_and_read_only(self):
        forbidden = ("/Users/nixiaofeng", "API_KEY", "grok-4.6")
        scripts = []
        for name in CURSOR_SKILLS:
            script = ROOT / name / "scripts" / "cursor_review.py"
            text = script.read_text()
            scripts.append(text)
            self.assertTrue(script.is_file())
            self.assertIn("--api-key-file", text)
            self.assertIn('mode="plan"', text)
            self.assertIn('tools=["read", "grep", "glob", "ls"]', text)
            for value in forbidden:
                self.assertNotIn(value, text)
        self.assertEqual(scripts[0], scripts[1])

    def test_readmes_document_all_workflow_skills(self):
        for readme in (ROOT / "README.md", ROOT / "README.zh.md"):
            text = readme.read_text()
            for name in SKILLS:
                self.assertIn(f"./{name}/", text)


if __name__ == "__main__":
    unittest.main()
