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
        forbidden = ("/Users/nixiaofeng",)
        scripts = []
        for name in CURSOR_SKILLS:
            script = ROOT / name / "scripts" / "cursor_review.py"
            text = script.read_text()
            scripts.append(text)
            self.assertTrue(script.is_file())
            self.assertIn("--api-key-file", text)
            self.assertIn('DEFAULT_API_KEY_FILE = Path.home() / ".cursor-review" / "API_KEY"', text)
            self.assertIn('DEFAULT_MODEL = "grok-4.6"', text)
            self.assertIn('DEFAULT_EFFORT = "high"', text)
            self.assertIn("default=DEFAULT_API_KEY_FILE", text)
            self.assertIn("default=DEFAULT_MODEL", text)
            self.assertIn("default=DEFAULT_EFFORT", text)
            self.assertNotIn('"--api-key-file", required=True', text)
            self.assertIn("Cursor API key is not configured", text)
            self.assertIn("INCOMPLETE: Cursor API key is not configured", text)
            self.assertNotIn("raise RuntimeError(", text)
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

    def test_cursor_workflows_document_the_default_configuration(self):
        for name in CURSOR_SKILLS:
            text = (ROOT / name / "SKILL.md").read_text()
            self.assertIn("`~/.cursor-review/API_KEY`", text)
            self.assertIn("`grok-4.6`", text)
            self.assertIn("`high`", text)
            self.assertIn("Cursor API key is not configured at `~/.cursor-review/API_KEY`", text)

    def test_code_workflow_requires_independent_task_and_milestone_reviews(self):
        text = (ROOT / "spec-plan-to-code" / "SKILL.md").read_text()
        required = (
            "each independent Task and each completed milestone",
            "primary agent's self-check does not count as independent review",
            "gpt-5.5-sol` with `high`",
            "gpt-5.5-sol` with `xhigh`",
            "gpt-6-astra` with `medium`",
            "under-review",
            "read-only consultation agent",
        )
        for value in required:
            self.assertIn(value, text)

    def test_karpathy_guidelines_require_evidence_for_abstractions(self):
        text = (ROOT / "coding-guidelines" / "SKILL.md").read_text().lower()
        required = (
            "evidence-driven abstraction",
            "local, explicit, linear orchestration",
            "two current independent consumers",
            "future flexibility is not evidence",
            "pipeline, context, registry, executor, manager, or factory",
            "abstraction receipt",
        )
        for value in required:
            self.assertIn(value, text)

    def test_coding_guidelines_is_registered_and_required_for_implementation(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        skill = (ROOT / "coding-guidelines" / "SKILL.md").read_text()
        code_workflow = (ROOT / "spec-plan-to-code" / "SKILL.md").read_text()
        self.assertIn('"./coding-guidelines"', manifest)
        self.assertNotIn('"./karpathy-guidelines"', manifest)
        self.assertIn("name: coding-guidelines", skill)
        self.assertIn("coding-guidelines", code_workflow)


if __name__ == "__main__":
    unittest.main()
