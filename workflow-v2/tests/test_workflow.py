from pathlib import Path
import hashlib
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "flow-run",
    "flow-brainstorm",
    "flow-requirement",
    "flow-intent",
    "flow-roadmap",
    "flow-spec",
    "flow-plan",
    "flow-code",
    "flow-integration",
)


class WorkflowV2Tests(unittest.TestCase):
    def skill(self, name):
        path = ROOT / "skills" / name / "SKILL.md"
        self.assertTrue(path.is_file(), f"missing {path.relative_to(ROOT)}")
        return path.read_text()

    def test_all_skills_are_explicit_only(self):
        for name in SKILLS:
            text = self.skill(name)
            metadata = ROOT / "skills" / name / "agents" / "openai.yaml"
            self.assertIn(f"name: {name}", text)
            self.assertTrue(metadata.is_file())
            self.assertIn("allow_implicit_invocation: false", metadata.read_text())

    def test_isolated_codex_plugin_exposes_skill_directory(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        self.assertEqual("./skills/", manifest["skills"])
        for name in SKILLS:
            self.assertIn(f"${name}", "\n".join(manifest["interface"]["defaultPrompt"]))

    def test_flow_run_orchestrates_from_deepest_valid_checkpoint(self):
        text = self.skill("flow-run")
        for value in (
            "active goal", "issue ID", "explicit start override",
            "deepest valid checkpoint", "revision", "digest", "approval",
            "raw requirement bootstrap", "must not invent product decisions",
            "$flow-brainstorm", "$flow-requirement", "$flow-intent",
            "$flow-roadmap", "$flow-spec", "$flow-plan", "$flow-code",
            "$flow-integration", "automatically invoke the next stage",
            "necessary human gate", "resume from the same checkpoint",
            "route backward", "do not bypass", "mark the goal complete",
            "target_milestones", "pending", "completed", "deferred",
            "standalone Spec is non-authoritative source evidence",
            "must not call `$flow-plan` or `$flow-spec`",
            "goal ID", "issue and objective", "must not replace",
            "clear affected completed handoffs",
        ):
            self.assertIn(value, text)

        self.assertIn("approved spec.md", text)
        self.assertIn("start at `$flow-plan`", text)
        self.assertIn("confirmed intent.md", text)
        self.assertIn("start at `$flow-roadmap`", text)
        self.assertIn("COMPLETE_WITH_DEFECT", text)
        self.assertIn("CURSOR_REVIEW_GAP", text)

    def test_flow_run_discovers_issue_then_artifacts_or_asks_for_paths(self):
        text = self.skill("flow-run")
        for value in (
            "human-provided issue ID",
            "must not infer",
            "resolved standard issue location",
            "If one or more candidate documents exist",
            "If no candidate document exists",
            "Provide existing document paths",
            "Use the current requirement without requirement discussion",
            "Pause Flow",
            "artifact path map",
            "single document path",
            "validate every supplied path",
            "explicit bootstrap authorization",
            "for each artifact type and the controller",
            "scan the union",
        ):
            self.assertIn(value, text)

        issue_pos = text.index("human-provided issue ID")
        default_pos = text.index("resolved standard issue location")
        interaction_pos = text.index("If no candidate document exists")
        self.assertLess(issue_pos, default_pos)
        self.assertLess(default_pos, interaction_pos)

    def test_flow_is_self_contained_for_issue_and_worktree_admission(self):
        contract = (ROOT / "flow-contract.md").read_text()
        for value in (
            "does not depend on `AGENTS.md`",
            "human-provided issue ID",
            "must not infer",
            "controller",
            "independent Git worktree",
            "local `master`",
            "codex resume",
            "verify silently",
            "FLOW_ADMISSION_GATE",
            "FLOW_ADMISSION_BLOCKED",
            "stricter safety constraints",
            "must not add duplicate Flow gates",
        ):
            self.assertIn(value, contract)

        for name in SKILLS:
            text = self.skill(name)
            self.assertIn("flow-contract.md", text, name)
            self.assertIn("issue", text.lower(), name)
            self.assertIn("worktree", text.lower(), name)

    def test_flow_run_owns_admission_once_and_stages_revalidate_without_reprompting(self):
        text = self.skill("flow-run")
        for value in (
            "owns Flow admission",
            "request it exactly once",
            "Initialize the controller",
            "create or reuse the matching worktree",
            "before artifact discovery",
            "must not ask for the issue ID again",
            "must not recreate the worktree",
        ):
            self.assertIn(value, text)

    def test_flow_run_uses_non_terminal_stage_return_protocol(self):
        runner = self.skill("flow-run")
        for value in (
            "orchestration-contract.md",
            "FLOW_RUN_CONTEXT",
            "FLOW_RUN_HANDOFF",
            "FLOW_RUN_HUMAN_GATE",
            "FLOW_RUN_BLOCKED",
            "FLOW_RUN_ROUTE_BACK",
            "FLOW_RUN_COMPLETE",
            "non-terminal",
            "same active turn",
            "must not surface",
        ):
            self.assertIn(value, runner)

        contract = (ROOT / "orchestration-contract.md").read_text()
        for value in (
            "caller: flow-run",
            "Direct invocation",
            "Orchestrated invocation",
            "FLOW_RUN_HANDOFF",
            "FLOW_RUN_HUMAN_GATE",
            "FLOW_RUN_BLOCKED",
            "FLOW_RUN_ROUTE_BACK",
            "must not suggest",
            "same active turn",
        ):
            self.assertIn(value, contract)

        for name in (
            "flow-requirement", "flow-intent", "flow-roadmap", "flow-spec",
            "flow-plan", "flow-code", "flow-integration",
        ):
            stage = self.skill(name)
            self.assertIn("orchestration-contract.md", stage, name)
            self.assertIn("FLOW_RUN_CONTEXT", stage, name)

        integration = self.skill("flow-integration")
        self.assertIn("aggregate result is `FAILED`", integration)
        self.assertIn("FLOW_RUN_ROUTE_BACK", integration)
        self.assertIn("owner_stage", integration)

    def test_flow_run_repairs_obsolete_manual_stage_gates(self):
        text = self.skill("flow-run")
        for value in (
            "explicit_stage_invocation",
            "obsolete orchestration state",
            "must not ask the human to copy",
            "migrate the controller",
            "FLOW_RUN_HANDOFF",
            "milestone selection is already recorded",
            "immediately continue",
        ):
            self.assertIn(value, text)

    def test_requirement_discussion_contract(self):
        text = self.skill("flow-requirement")
        for value in (
            "brainstorming", "human", "agent swarm", "conversation_context",
            "issue_context", "two independent roles", "three and at most eight",
            "two or three", "requirement.md", "READY_FOR_INTENT",
            "must not create intent.md", "$flow-intent",
        ):
            self.assertIn(value, text)

    def test_brainstorm_adapter_contract(self):
        text = self.skill("flow-brainstorm")
        for value in (
            "one question at a time",
            "two or three",
            "recommendation",
            "success criteria",
            "human confirmation",
            "brainstorm_result",
            "status: DRAFT | CONFIRMED",
            "confirmed_by",
            "issue_context_ref",
            "return control to `$flow-requirement`",
            "must not write requirement.md",
            "must not create a Spec",
            "must not invoke `writing-plans`",
        ):
            self.assertIn(value, text)

        requirement = self.skill("flow-requirement")
        self.assertIn("**REQUIRED SUB-SKILL:** Use flow-brainstorm", requirement)
        self.assertIn("BLOCKED_DEPENDENCY", requirement)

    def test_intent_confirmation_contract(self):
        text = self.skill("flow-intent")
        for value in (
            "requirement.md", "grilling", "Decision Card",
            "one high-leverage question", "without another human confirmation",
            "intent-changing", "FLOW_RUN_ROUTE_BACK", "intent.md", "status: CONFIRMED",
            "ORCHESTRATED", "Requirement authorization",
            "must not create roadmap", "$flow-roadmap",
        ):
            self.assertIn(value, text)

    def test_roadmap_contract(self):
        text = self.skill("flow-roadmap")
        for value in (
            "requirement.md", "intent.md", "intent is authoritative",
            "milestones", "dependencies", "acceptance direction", "roadmap.md",
            "must not include file-level tasks", "$flow-spec",
        ):
            self.assertIn(value, text)

    def test_spec_contract(self):
        text = self.skill("flow-spec")
        for value in (
            "one selected milestone", "behavioral contract", "inputs and outputs",
            "state transitions", "errors", "permissions", "compatibility",
            "acceptance criteria", "spec.md", "must not include implementation tasks",
            "$flow-plan",
        ):
            self.assertIn(value, text)

    def test_spec_plan_code_use_gpt_then_mandatory_cursor_review(self):
        for name in ("flow-spec", "flow-plan", "flow-code"):
            text = self.skill(name)
            for value in (
                "**REQUIRED SUB-SKILL:** Use independent-review",
                "**REQUIRED SUB-SKILL:** Use cursor-review",
                "gpt-5.6-sol", "high", "gpt-6-astra", "medium",
                "root agent", "difficulty", "GPT → Cursor",
                "mandatory final review", "automatically authorizes",
                "in-scope code and documents", "secrets",
                "BLOCKED_REVIEW", "rerun the GPT review",
                "review_binding", "immediately before dispatch and after receipt",
                "missing/mismatched binding", "stale or unbound report",
            ):
                self.assertIn(value, text, f"{name} missing {value}")
            self.assertNotIn("gpt-5.6-sol` with `medium", text)
            self.assertNotIn("gpt-6-astra` with `high", text)

    def test_cursor_runtime_failure_has_one_retry_and_durable_defect_handoff(self):
        expected_status = {
            "flow-spec": "APPROVED_WITH_DEFECT",
            "flow-plan": "APPROVED_WITH_DEFECT",
            "flow-code": "COMPLETE_WITH_DEFECT",
        }
        for name, status in expected_status.items():
            text = self.skill(name)
            for value in (
                "retry exactly once",
                "not a review finding",
                status,
                "CURSOR_REVIEW_GAP",
                "final completion report",
                "handoff",
                "full `review_binding` and binding ID",
            ):
                self.assertIn(value, text, f"{name} missing {value}")
            self.assertNotIn("`INCOMPLETE`, drift", text)

        self.assertIn("only when no gap is open", self.skill("flow-plan"))
        self.assertIn("even when this stage's own Cursor review succeeds", self.skill("flow-code"))

        integration = self.skill("flow-integration")
        self.assertIn("COMPLETE_WITH_DEFECT", integration)
        self.assertIn("CURSOR_REVIEW_GAP", integration)
        self.assertIn("final report", integration)
        self.assertIn("regardless of the claimed Code status", integration)
        self.assertIn("reject the inconsistent tuple `COMPLETE` plus an open gap", integration)

    def test_plan_contract(self):
        text = self.skill("flow-plan")
        for value in (
            "approved spec.md", "executable tasks", "files and modules",
            "test-first", "verification commands", "rollback", "traceability",
            "flow_step `plan`", "$flow-code",
        ):
            self.assertIn(value, text)

    def test_code_and_unit_test_contract(self):
        text = self.skill("flow-code")
        for value in (
            "approved plan.md", "TDD", "failing unit test", "minimal implementation",
            "refactor", "independent-review", "unit-test evidence",
            "must not claim integration coverage", "$flow-integration",
        ):
            self.assertIn(value, text)

    def test_integration_contract(self):
        text = self.skill("flow-integration")
        for value in (
            "intent.md", "roadmap.md", "spec.md", "plan.md",
            "cross-component", "end-to-end", "permissions", "failure recovery",
            "Success Signals", "integration evidence", "route every failure",
        ):
            self.assertIn(value, text)

    def test_integration_supports_direct_real_service_testing(self):
        text = self.skill("flow-integration")
        for value in (
            "Governed mode", "Direct mode", "TESTCASE-*",
            "direct_test_charter", "explicit human confirmation",
            "human-readable test points", "Do not ask for another confirmation",
            "approved `TESTCASE-*` integration outline",
            "start the real service", "send real requests",
            "bounded readiness", "probe", "logs", "audit",
            "wait for returned or persisted data",
            "Observability is evidence, not a substitute",
            "test-only code", "must not change business-logic semantics",
            "production implementation", "safe cleanup",
            "observed implementation or contract contradiction is `FAILED`",
            "insufficient evidence to distinguish them is `BLOCKED`",
            "every direct `TESTCASE-*`",
        ):
            self.assertIn(value, text)
        self.assertNotIn("INT-*", text)
        self.assertNotIn("DIRECT-INT", text)

        for name in ("flow-plan", "flow-code"):
            stage = self.skill(name)
            self.assertIn("TESTCASE-*", stage)
            self.assertNotIn("INT-*", stage)

    def test_artifact_chain_is_revision_and_digest_bound(self):
        for name in SKILLS:
            if name == "flow-brainstorm":
                continue
            text = self.skill(name)
            self.assertIn("SHA-256", text, name)
            self.assertIn("digest", text, name)

        for name in ("flow-intent", "flow-roadmap", "flow-spec", "flow-plan"):
            text = self.skill(name)
            self.assertIn("approved_revision", text, name)
            self.assertIn("approved_digest", text, name)

        expected_sources = {
            "flow-roadmap": ("requirement", "intent"),
            "flow-spec": ("requirement", "intent", "roadmap"),
            "flow-plan": ("requirement", "intent", "roadmap", "spec"),
            "flow-code": ("requirement", "intent", "roadmap", "spec", "plan"),
            "flow-integration": ("requirement.md", "intent.md", "roadmap.md", "spec.md", "plan.md"),
        }
        for name, sources in expected_sources.items():
            text = self.skill(name)
            for source in sources:
                self.assertIn(source, text, f"{name} missing {source}")
            self.assertIn("Recompute", text, name)

    def test_required_dependencies_and_worktree_gate_fail_closed(self):
        requirement = self.skill("flow-requirement")
        code = self.skill("flow-code")
        contract = (ROOT / "flow-contract.md").read_text()
        self.assertIn("BLOCKED_DEPENDENCY", requirement)
        self.assertIn("BLOCKED_DEPENDENCY", code)
        self.assertIn("FLOW_ADMISSION_BLOCKED", contract)
        self.assertIn("do not continue in the original checkout", contract)

    def test_digest_contract_is_non_self_referential_and_detects_tampering(self):
        contract = (ROOT / "artifact-contract.md").read_text()
        self.assertIn("`content_digest` is never inside the hashed body", contract)
        self.assertIn("UTF-8, LF line endings, no BOM", contract)
        self.assertIn("exactly one final LF", contract)

        body = "content_revision: 1\nProblem: Preserve exact bytes\n".encode("utf-8")
        original = hashlib.sha256(body).hexdigest()
        tampered = hashlib.sha256(body.replace(b"exact", b"changed")).hexdigest()
        self.assertEqual(64, len(original))
        self.assertNotEqual(original, tampered)

    def test_all_document_outputs_follow_one_location_precedence(self):
        contract = (ROOT / "artifact-contract.md").read_text()
        ordered = (
            "current human-specified directory",
            "project `AGENTS.md`",
            "global `AGENTS.md`",
            ".ai/issue/<issue_id>/<flow_step>_<YYYYMMDD>_<subject>.md",
        )
        positions = [contract.index(value) for value in ordered]
        self.assertEqual(sorted(positions), positions)
        for value in (
            "project root", "local date", "lowercase snake_case",
            "human specifies a full file path", "same path for every revision",
            "non-hashed integrity/location region", "Resolve relative paths against the project root",
        ):
            self.assertIn(value, contract)

        stages = {
            "flow-requirement": "requirement",
            "flow-intent": "intent",
            "flow-roadmap": "roadmap",
            "flow-spec": "spec",
            "flow-plan": "plan",
            "flow-code": "code",
            "flow-integration": "integration",
        }
        for name, step in stages.items():
            text = self.skill(name)
            self.assertIn("Resolve the output path through the artifact contract", text, name)
            self.assertIn(f"flow_step `{step}`", text, name)
        all_text = "\n".join(self.skill(name) for name in stages)
        for obsolete in (".ai/requirements/", ".ai/intents/", ".ai/roadmaps/", ".ai/specs/", ".ai/plans/", ".ai/evidence/"):
            self.assertNotIn(obsolete, all_text)
        plan = self.skill("flow-plan")
        integration = self.skill("flow-integration")
        self.assertIn("exactly one canonical absolute output directory", plan)
        self.assertIn("glob/regex patterns are not allowed", plan)
        self.assertIn("current-stage instructions", integration)
        self.assertIn("requires a Plan revision and approval", plan)
        self.assertIn("realpath semantics", integration)
        self.assertIn("reject `..` or symlink traversal", integration)

    def test_intent_uses_pre_admitted_worktree_and_orchestrated_approval(self):
        text = self.skill("flow-intent")
        for value in (
            "worktree was admitted before artifact discovery",
            "Never create or migrate a worktree in this stage",
            "ORCHESTRATED",
            "without another human confirmation",
            "approved_revision",
            "approved_digest",
        ):
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
