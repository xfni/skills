from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
SKILLS = (
    "requirements-to-roadmap",
    "roadmap-to-spec-plan",
    "spec-plan-to-code",
)
SPECIALIST_SKILLS = (
    "concurrent-design-review",
    "spec-review-gate",
)
CURSOR_SKILLS = SKILLS[1:]


class AiNativeWorkflowSkillTests(unittest.TestCase):
    def test_skills_are_listed_and_explicit_only(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        for name in SKILLS:
            self.assertIn(f'"./skills/{name}"', manifest)
            skill = SKILLS_ROOT / name / "SKILL.md"
            metadata = SKILLS_ROOT / name / "agents" / "openai.yaml"
            self.assertTrue(skill.is_file())
            self.assertIn(f"name: {name}", skill.read_text())
            self.assertIn("allow_implicit_invocation: false", metadata.read_text())

    def test_cursor_review_scripts_are_portable_and_read_only(self):
        forbidden = ("/Users/nixiaofeng",)
        scripts = []
        for name in CURSOR_SKILLS:
            script = SKILLS_ROOT / name / "scripts" / "cursor_review.py"
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
                self.assertIn(f"./skills/{name}/", text)

    def test_cursor_workflows_document_the_default_configuration(self):
        for name in CURSOR_SKILLS:
            text = (SKILLS_ROOT / name / "SKILL.md").read_text()
            self.assertIn("`~/.cursor-review/API_KEY`", text)
            self.assertIn("`grok-4.6`", text)
            self.assertIn("`high`", text)
            self.assertIn("Cursor API key is not configured at `~/.cursor-review/API_KEY`", text)

    def test_code_workflow_requires_independent_task_and_milestone_reviews(self):
        text = (SKILLS_ROOT / "spec-plan-to-code" / "SKILL.md").read_text()
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

    def test_astra_precedes_cursor_in_final_review_order(self):
        expected = (
            "First use `gpt-6-astra` with `medium` effort for the independent final review. "
            "Only after its findings are resolved or dispositioned, use Cursor as the last external review."
        )
        for name in ("roadmap-to-spec-plan", "spec-plan-to-code"):
            text = (SKILLS_ROOT / name / "SKILL.md").read_text()
            self.assertIn(expected, text)

    def test_workflows_preserve_portable_review_governance(self):
        roadmap = (SKILLS_ROOT / "roadmap-to-spec-plan" / "SKILL.md").read_text()
        code = (SKILLS_ROOT / "spec-plan-to-code" / "SKILL.md").read_text()
        for value in (
            "same dispute remains unresolved for two review rounds",
            "review only the changed boundary, unresolved findings, and affected artifacts",
            "A reviewer label is evidence to assess, not approval",
        ):
            self.assertIn(value, roadmap)
        for value in (
            "existing user changes",
            "actual command, result, evidence location, remaining risk, and scope variance",
            "isolate test data",
            "return to the Astra → Cursor final-review sequence",
        ):
            self.assertIn(value, code)

    def test_workflow_handoff_preserves_requirement_phase_and_evidence_traceability(self):
        roadmap = (SKILLS_ROOT / "requirements-to-roadmap" / "SKILL.md").read_text()
        spec_plan = (SKILLS_ROOT / "roadmap-to-spec-plan" / "SKILL.md").read_text()
        code = (SKILLS_ROOT / "spec-plan-to-code" / "SKILL.md").read_text()
        self.assertIn("Requirement ID", roadmap)
        self.assertIn("selected Phase ID", spec_plan)
        self.assertIn("`REQ-*` → `DEC-*` → `AC-*`", spec_plan)
        self.assertIn("linked requirement, decision, and acceptance IDs", spec_plan)
        self.assertIn("linked `REQ-*`, `DEC-*`, and `AC-*` IDs", code)
        self.assertIn("`REQ-*` → `AC-*` → evidence", code)

    def test_karpathy_guidelines_require_evidence_for_abstractions(self):
        text = (SKILLS_ROOT / "coding-guidelines" / "SKILL.md").read_text().lower()
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        required = (
            "evidence-driven abstraction",
            "local, explicit, linear orchestration",
            "two current independent consumers",
            "future flexibility is not evidence",
            "pipeline, context, registry, executor, manager, or factory",
            "abstraction receipt",
            "coordinator should only orchestrate",
            "meaningful module boundary",
            "complete the migration or defer it",
            "contract or integration test",
        )
        for value in required:
            self.assertIn(value, text)
        self.assertNotIn('"./skills/backend-module-discipline"', manifest)
        self.assertFalse((SKILLS_ROOT / "backend-module-discipline").exists())

    def test_coding_guidelines_is_registered_and_required_for_implementation(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        skill = (SKILLS_ROOT / "coding-guidelines" / "SKILL.md").read_text()
        code_workflow = (SKILLS_ROOT / "spec-plan-to-code" / "SKILL.md").read_text()
        self.assertIn('"./skills/coding-guidelines"', manifest)
        self.assertNotIn('"./skills/karpathy-guidelines"', manifest)
        self.assertIn("name: coding-guidelines", skill)
        self.assertIn("coding-guidelines", code_workflow)

    def test_coding_guidelines_owns_risk_based_reliability_boundaries(self):
        guidelines = (SKILLS_ROOT / "coding-guidelines" / "SKILL.md").read_text().lower()
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()

        for value in (
            "risk-based reliability boundaries",
            "follow the language and repository convention",
            "trusted boundary",
            "review signals, not an automatic extraction rule",
            "concurrent-design-review",
        ):
            self.assertIn(value, guidelines)

        self.assertNotIn('"./skills/coding-hard-constraints"', manifest)
        self.assertNotIn('"./skills/coding-observability-errors"', manifest)
        self.assertNotIn('"./skills/privacy-coding-rule"', manifest)
        self.assertFalse((SKILLS_ROOT / "coding-hard-constraints").exists())
        self.assertFalse((SKILLS_ROOT / "coding-observability-errors").exists())
        self.assertFalse((SKILLS_ROOT / "privacy-coding-rule").exists())

    def test_codex_manifest_reuses_the_shared_skills_directory(self):
        manifest = ROOT / ".codex-plugin" / "plugin.json"
        self.assertTrue(manifest.is_file())
        self.assertIn('"skills": "./skills/"', manifest.read_text())
        for name in SKILLS:
            self.assertTrue((SKILLS_ROOT / name / "SKILL.md").is_file())

    def test_concurrency_gate_delegates_to_one_specialist_review_authority(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        concurrent = (SKILLS_ROOT / "concurrent-design-review" / "SKILL.md").read_text()
        gate = (SKILLS_ROOT / "spec-review-gate" / "SKILL.md").read_text()
        for name in SPECIALIST_SKILLS:
            self.assertIn(f'"./skills/{name}"', manifest)
        self.assertIn("唯一评审派发与覆盖判定入口", concurrent)
        self.assertIn("不得预先派发 reviewer", gate)
        self.assertIn("owns coverage", gate)

    def test_readmes_document_specialist_review_skills(self):
        for readme in (ROOT / "README.md", ROOT / "README.zh.md"):
            text = readme.read_text()
            for name in SPECIALIST_SKILLS:
                self.assertIn(f"./skills/{name}/", text)

    def test_readmes_document_runtime_and_workflow_dependencies(self):
        english = (ROOT / "README.md").read_text()
        chinese = (ROOT / "README.zh.md").read_text()
        for text in (english, chinese):
            for value in (
                "brainstorming",
                "grilling",
                "coding-guidelines",
                "concurrent-design-review",
                "spec-review-gate",
                "Cursor",
                "Codex",
            ):
                self.assertIn(value, text)

    def test_obsolete_init_claude_skill_and_its_docs_are_not_packaged(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        self.assertNotIn('"./skills/init-claude"', manifest)
        self.assertFalse((SKILLS_ROOT / "init-claude").exists())
        self.assertFalse((ROOT / ".ai" / "plans" / "2026-05-26-init-claude-skill.md").exists())
        self.assertFalse((ROOT / ".ai" / "specs" / "2026-05-26-init-claude-skill-design.md").exists())
        for readme in (ROOT / "README.md", ROOT / "README.zh.md"):
            self.assertNotIn("init-claude", readme.read_text())

    def test_declared_mit_license_has_a_root_license_file(self):
        manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        license_file = ROOT / "LICENSE"
        self.assertIn('"license": "MIT"', manifest)
        self.assertTrue(license_file.is_file())
        self.assertIn("MIT License", license_file.read_text())


if __name__ == "__main__":
    unittest.main()
