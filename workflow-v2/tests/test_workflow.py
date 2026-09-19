from pathlib import Path
import hashlib
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "dev-run",
    "dev-brainstorm",
    "dev-requirement",
    "dev-intent",
    "dev-roadmap",
    "dev-spec",
    "dev-plan",
    "dev-code",
    "dev-integration",
)


class WorkflowV2Tests(unittest.TestCase):
    def test_dev_entry_names_do_not_change_controller_stage_ids(self):
        contract = (ROOT / "flowctl-contract.md").read_text()
        for suffix in (
            "run", "brainstorm", "requirement", "intent", "roadmap",
            "spec", "plan", "code", "integration",
        ):
            public = f"dev-{suffix}"
            self.assertTrue((ROOT / "skills" / public / "SKILL.md").is_file())
            self.assertFalse((ROOT / "skills" / f"flow-{suffix}").exists())
        for suffix in ("requirement", "intent", "roadmap", "spec", "plan", "code", "integration"):
            self.assertIn(f"| `$dev-{suffix}` | `flow-{suffix}` |", contract)
        schema = json.loads((ROOT / "schemas" / "handoff.schema.json").read_text())
        self.assertEqual(
            [f"flow-{suffix}" for suffix in (
                "requirement", "intent", "roadmap", "spec", "plan", "code", "integration",
            )],
            schema["properties"]["from_stage"]["enum"],
        )
        self.assertIn("caller: flow-run", (ROOT / "orchestration-contract.md").read_text())

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

    def test_flow_run_discovers_issue_then_artifacts_or_asks_for_paths(self):
        text = self.skill("dev-run")
        for value in (
            "human-provided issue ID",
            "must not infer",
            "resolved standard issue location",
            "If one or more candidate documents exist",
            "If no candidate document exists",
            "提供已有文档位置，继续之前的工作",
            "使用当前明确需求开始，跳过需求讨论",
            "暂停，暂不启动流程",
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

    def test_flow_run_uses_non_terminal_stage_return_protocol(self):
        runner = self.skill("dev-run")
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
            "dev-requirement", "dev-intent", "dev-roadmap", "dev-spec",
            "dev-plan", "dev-code", "dev-integration",
        ):
            stage = self.skill(name)
            self.assertIn("orchestration-contract.md", stage, name)
            self.assertIn("FLOW_RUN_CONTEXT", stage, name)

        integration = self.skill("dev-integration")
        self.assertIn("aggregate result is `FAILED`", integration)
        self.assertIn("FLOW_RUN_ROUTE_BACK", integration)
        self.assertIn("owner_stage", integration)

    def test_requirement_discussion_contract(self):
        text = self.skill("dev-requirement")
        for value in (
            "brainstorming", "human", "agent swarm", "conversation_context",
            "issue_context", "two independent roles", "three and at most twelve",
            "two or three", "requirement.md", "READY_FOR_INTENT",
            "must not create intent.md", "$dev-intent",
        ):
            self.assertIn(value, text)

    def test_dev_run_forecasts_authority_and_preflights_before_unattended_execution(self):
        runner = self.skill("dev-run")
        requirement = self.skill("dev-requirement")
        contract = (ROOT / "flow-contract.md").read_text()
        for value in (
            "Authorization Forecast",
            "production read sources and data classes",
            "private model or external endpoint",
            "bounded calls, retries, and cost",
            "non-destructive authorization preflight",
            "before unattended downstream execution",
            "delta authorization",
            "does not replace host sandbox, network, credential",
            "UNRESOLVED(runtime:<source-or-key>)",
            "inherited confirmed decision",
        ):
            self.assertIn(value, runner)
        for value in (
            "Authorization Forecast",
            "same final Requirement confirmation",
            "authorization source and exclusions",
            "UNRESOLVED(runtime:<source-or-key>)",
            "inherited confirmed decision",
            "after confirmation, first run the safe preflight",
        ):
            self.assertIn(value, requirement)
        self.assertIn("authorization forecast is Agent-maintained evidence", contract)
        self.assertIn("must not become a new controller schema", contract)
        self.assertIn("UNRESOLVED(runtime:<source-or-key>)", contract)

    def test_requirement_swarm_rejects_unjustified_platformization(self):
        requirement = self.skill("dev-requirement")
        brainstorm = self.skill("dev-brainstorm")
        for value in (
            "smallest scope that satisfies the current success boundary",
            "Scope Ledger",
            "PLATFORM_RECEIPT-*",
            "current NEED-*",
            "measurable current benefit",
            "smallest non-platform alternative",
            "Future Considerations",
            "must not enter the selected scope",
            "Future flexibility, architectural symmetry, and hypothetical consumers are not evidence",
            "must not enlarge candidates merely to make them different",
        ):
            self.assertIn(value, requirement)
        for value in (
            "current demand point",
            "concrete present benefit",
            "future extensibility alone",
        ):
            self.assertIn(value, brainstorm)

        value_agent = (ROOT / "skills" / "dev-requirement" / "agents" / "dev-requirement-value.toml").read_text()
        risk_agent = (ROOT / "skills" / "dev-requirement" / "agents" / "dev-requirement-risk.toml").read_text()
        for text in (value_agent, risk_agent):
            self.assertIn("PLATFORM_RECEIPT-*", text)
            self.assertIn("current NEED-*", text)
            self.assertIn("smallest non-platform alternative", text)
        self.assertIn("default recommendation", value_agent)
        self.assertIn("reject platformization", risk_agent)

    def test_requirement_risk_simulates_constraint_interactions_before_authorization(self):
        requirement = self.skill("dev-requirement")
        risk_agent = (ROOT / "skills" / "dev-requirement" / "agents" / "dev-requirement-risk.toml").read_text()
        for value in (
            "Constraint Interaction",
            "all individual constraints are satisfied",
            "trigger condition",
            "interacting constraints",
            "emergent behavior",
            "harmed stakeholder",
            "feedback loop",
            "detection signal",
            "residual risk",
            "Decision Brief",
            "full Requirement remains evidence",
        ):
            self.assertIn(value, requirement)
        for value in (
            "CONSTRAINT_SCENARIO-*",
            "all stated constraints are locally satisfied",
            "proxy metrics",
            "irreversible harm",
            "feedback amplification",
            "abnormal load",
        ):
            self.assertIn(value, risk_agent)

    def test_reviewers_audit_evidence_and_converge_by_finding_weight(self):
        review = (ROOT.parent / "skills" / "independent-review" / "SKILL.md").read_text()
        for value in (
            "Evidence audit",
            "CLAIM-*",
            "raw source",
            "selective evidence",
            "contradictory evidence",
            "independently reproduce",
            "evidence_strength",
            "blocking_status",
            "recurrence_key",
            "No new evidence",
            "three review cycles",
            "must not silently pass",
        ):
            self.assertIn(value, review)

        for skill in ("dev-spec", "dev-plan", "dev-code"):
            text = self.skill(skill)
            self.assertIn("finding-weight convergence", text)
            self.assertIn("non-blocking finding must not trigger another review cycle", text)
            self.assertIn("same recurrence_key", text)
            self.assertIn("three review cycles", text)

    def test_brainstorm_adapter_contract(self):
        text = self.skill("dev-brainstorm")
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
            "return control to `$dev-requirement`",
            "must not write requirement.md",
            "must not create a Spec",
            "must not invoke `writing-plans`",
        ):
            self.assertIn(value, text)

        requirement = self.skill("dev-requirement")
        self.assertIn("**REQUIRED SUB-SKILL:** Use dev-brainstorm", requirement)
        self.assertIn("BLOCKED_DEPENDENCY", requirement)

    def test_intent_confirmation_contract(self):
        text = self.skill("dev-intent")
        for value in (
            "requirement.md", "grilling", "Decision Card",
            "one high-leverage question", "without another human confirmation",
            "intent-changing", "FLOW_RUN_ROUTE_BACK", "intent.md", "status: CONFIRMED",
            "ORCHESTRATED", "Requirement authorization",
            "must not create roadmap", "$dev-roadmap",
        ):
            self.assertIn(value, text)

    def test_roadmap_contract(self):
        text = self.skill("dev-roadmap")
        for value in (
            "requirement.md", "intent.md", "intent is authoritative",
            "milestones", "dependencies", "acceptance direction", "roadmap.md",
            "must not include file-level tasks", "$dev-spec",
        ):
            self.assertIn(value, text)

    def test_spec_contract(self):
        text = self.skill("dev-spec")
        for value in (
            "one selected milestone", "behavioral contract", "inputs and outputs",
            "state transitions", "errors", "permissions", "compatibility",
            "acceptance criteria", "spec.md", "must not include implementation tasks",
            "$dev-plan",
        ):
            self.assertIn(value, text)

    def test_plan_contract(self):
        text = self.skill("dev-plan")
        for value in (
            "approved spec.md", "executable tasks", "files and modules",
            "test-first", "verification commands", "rollback", "traceability",
            "flow_step `plan`", "$dev-code",
        ):
                self.assertIn(value, text)

    def test_flow_initial_gate_is_production_replay_only(self):
        runner = self.skill("dev-run")
        for value in ("开始前请确认测试范围", "允许使用生产数据进行本地测试（推荐）",
                      "不进行依赖生产数据的集成测试", "LOCAL_PRODUCTION_REPLAY",
                      "SKIP_PRODUCTION_REPLAY", "flowctl authorization decide", "flowctl authorization amend"):
            self.assertIn(value, runner)
        self.assertNotIn("不允许外部审查", runner)
        self.assertNotIn("允许最小必要范围的外部审查", runner)
        self.assertIn("production_replay", runner)
        self.assertIn("no external-review authorization gate", runner)

    def test_external_review_surfaces_require_frozen_view_not_human_authorization(self):
        for name in ("dev-spec", "dev-plan", "dev-code"):
            text = self.skill(name)
            for value in ("review-contract.md", "complete filtered frozen worktree", "stdout/API",
                          "no automatic commit", "no external-review authorization gate"):
                self.assertIn(value, text, name)
        for name in ("cursor-review", "ibrain-review"):
            text = (ROOT.parent / "skills" / name / "SKILL.md").read_text()
            self.assertIn("--workspace", text)
            self.assertNotIn("--no-tools", text)

    def test_review_and_replay_authority_remain_separate(self):
        contract = (ROOT / "review-contract.md").read_text()
        artifact = (ROOT / "artifact-contract.md").read_text()
        for value in ("Historical external_review records", "trusted vendors",
                      "Production-data use requires", "single-use", "snapshot", "finally"):
            self.assertIn(value, contract)
        self.assertIn("must not be treated as replay authority", artifact)
        self.assertIn("scoped authorization ID/revision", artifact)

    def test_spec_plan_code_share_frozen_review_policy(self):
        for name in ("dev-spec", "dev-plan", "dev-code"):
            text = self.skill(name)
            self.assertIn("review-contract.md", text)
            self.assertIn("single-use package binding", text)
            self.assertIn("Legacy paths are", text)
            # Review-route behavior is covered by test_review_lifecycle, not prose matching.
            self.assertNotIn("same active `external_review` authorization ID", text)

    def test_replay_decision_reaches_integration_as_controller_binding(self):
        plan = self.skill("dev-plan")
        integration = self.skill("dev-integration")
        for value in (
            "production_replay",
            "LOCAL_PRODUCTION_REPLAY",
        ):
            self.assertIn(value, plan)
            self.assertIn(value, integration)
        self.assertIn("LOCAL_PRODUCTION_REPLAY", integration)
        self.assertIn("SKIP_PRODUCTION_REPLAY", integration)
        self.assertIn("must not ask for replay authorization again", integration)
        self.assertIn("flowctl authorization amend", integration)

    def test_direct_review_has_no_human_gate_but_direct_replay_does(self):
        for name in ("dev-spec", "dev-plan", "dev-code"):
            text = self.skill(name)
            self.assertIn("Direct invocation review scope", text)
            self.assertIn("no external-review authorization gate", text)
            self.assertNotIn("minimal stage-bound authorization gate for only `external_review`", text)
        text = self.skill("dev-integration")
        for value in ("Direct invocation authorization", "minimal stage-bound authorization gate",
                      "production_replay", "controller-generated authorization ID"):
            self.assertIn(value, text)

    def test_ibrain_fallback_reuses_snapshot_not_cursor_authority(self):
        contract = (ROOT / "review-contract.md").read_text()
        self.assertIn("independently of Cursor decisions", contract)
        self.assertIn("Every retry/revision/backend has a fresh single-use package binding", contract)
        # Finding preservation/takeover is exercised against the controller in test_review_lifecycle.
        orchestration = (ROOT / "orchestration-contract.md").read_text()
        # Runtime fallback is observable behavior, not a required failure quota.
        self.assertNotIn("If external review is denied", orchestration)

    def test_code_and_unit_test_contract(self):
        text = self.skill("dev-code")
        for value in (
            "approved plan.md", "TDD", "failing unit test", "minimal implementation",
            "refactor", "independent-review", "unit-test evidence",
            "must not claim integration coverage", "$dev-integration",
        ):
            self.assertIn(value, text)

    def test_flow_code_uses_one_lazy_session_scoped_luna_coder(self):
        text = self.skill("dev-code")
        for value in (
            "dev_coder",
            "gpt-5.6-luna",
            "max",
            "only after the Plan handoff passes admission",
            "must not spawn it at session start",
            "one coder thread for this Session",
            "one dependency-ready `TASK-*` at a time",
            "reuse that same thread",
            "coder_thread_id",
            "active_task",
            "completed_tasks",
            "last_checkpoint",
            "waiting timeout is not task failure",
            "must never interrupt or replace the coder solely because a wait timed out",
            "300 seconds",
            "two consecutive wait windows",
            "non-interrupting progress inquiry",
            "No output, elapsed time, or absence of filesystem changes",
            "confirmed unavailable",
            "replacement_generation",
            "replacement_reason",
            "prior_coder_thread_id",
            "CODER_THREAD_REPLACED",
            "must not implement the same task in parallel",
            "must not delegate",
            "return to `$dev-plan`",
            "close the coder thread",
        ):
            self.assertIn(value, text)

        agent = ROOT / "skills" / "dev-code" / "agents" / "dev-coder.toml"
        self.assertTrue(agent.is_file())
        config = agent.read_text()
        for value in (
            'name = "dev_coder"',
            'model = "gpt-5.6-luna"',
            'model_reasoning_effort = "max"',
            "Do not delegate",
            "Implement only the assigned TASK-*",
            "Do not change Requirement, Intent, Roadmap, Spec, or Plan",
            "Return a checkpoint",
        ):
            self.assertIn(value, config)

    def test_flow_run_controller_persists_coder_thread_state(self):
        runner = self.skill("dev-run")
        for value in (
            "coder_agent",
            "coder_thread_id",
            "coder_model",
            "coder_effort",
            "active_task",
            "completed_tasks",
            "last_checkpoint",
            "replacement_generation",
            "replacement_reason",
            "prior_coder_thread_id",
        ):
            self.assertIn(value, runner)

        readme = (ROOT / "README.md").read_text()
        self.assertIn("dev-coder.toml", readme)
        self.assertIn("created lazily", readme)

    def test_flow_run_reports_observable_stage_transitions(self):
        runner = self.skill("dev-run")
        code = self.skill("dev-code")
        for value in (
            "Observable status",
            "current stage",
            "just completed",
            "next action",
            "waiting for",
            "blocking or non-blocking",
            "before each material transition",
        ):
            self.assertIn(value, runner)
        for value in (
            "before dispatching a coder task",
            "before waiting for the coder",
            "after receiving its checkpoint",
            "before GPT review",
            "before Cursor review",
            "sending review findings back",
        ):
            self.assertIn(value, code)

    def test_integration_contract(self):
        text = self.skill("dev-integration")
        for value in (
            "available Plan", "current milestone", "snapshot",
            "cross-component", "end-to-end", "permissions", "failure recovery",
            "Success Signals", "integration evidence", "route every failure",
        ):
            self.assertIn(value, text)

    def test_integration_supports_direct_real_service_testing(self):
        text = self.skill("dev-integration")
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
            "production implementation", "minimal runtime cleanup",
            "observed implementation or contract contradiction is `FAILED`",
            "insufficient evidence to distinguish them is `BLOCKED`",
            "every direct `TESTCASE-*`",
        ):
            self.assertIn(value, text)
        self.assertNotIn("INT-*", text)
        self.assertNotIn("DIRECT-INT", text)

        for name in ("dev-plan", "dev-code"):
            stage = self.skill(name)
            self.assertIn("TESTCASE-*", stage)
            self.assertNotIn("INT-*", stage)

    def test_integration_starts_a_temporary_local_service_before_remote_fallback(self):
        integration = self.skill("dev-integration")
        for value in (
            "temporary local service",
            "current worktree",
            "default execution target",
            "ephemeral port",
            "local readiness",
            "local execution is technically impossible",
            "explicitly requires deployment-environment behavior",
            "does not prove the frozen code is untestable",
            "must not immediately become `BLOCKED`",
            "stop the local service",
            "process or container identity",
            "actual request URL",
        ):
            self.assertIn(value, integration)

        plan = self.skill("dev-plan")
        self.assertIn("temporary local service", plan)
        self.assertIn("remote test deployment is an explicit exception", plan)

    def test_integration_preserves_real_test_environment_writes_and_only_cleans_runtime(self):
        integration = self.skill("dev-integration")
        contract = (ROOT / "flow-contract.md").read_text()
        for value in (
            "minimal cleanup boundary",
            "stop processes or containers started by this run",
            "must remain after the run",
            "Do not delete, roll back, truncate, expire, or restore",
            "MongoDB, SQL databases, Elasticsearch/OpenSearch, Redis",
            "record their test-environment namespace and identifiers",
        ):
            self.assertIn(value, integration)
        self.assertNotIn("clean its isolated data", integration)
        for value in (
            "Persistent business writes produced by real test requests are retained",
            "must not delete or roll back those writes",
        ):
            self.assertIn(value, contract)
        self.assertNotIn("clean up only data/resources created by this run", contract)
        for stage_name in ("dev-run", "dev-plan"):
            stage = self.skill(stage_name)
            self.assertIn("retain real test-environment business writes", stage)

    def test_integration_scripts_prove_connectivity_but_agent_judges_correctness_from_evidence(self):
        integration = self.skill("dev-integration")
        plan = self.skill("dev-plan")
        for value in (
            "connectivity and evidence-collection harness",
            "must not determine business correctness",
            "exit code `0` proves only",
            "must not emit a business `PASSED` or `FAILED` verdict",
            "Agent owns the semantic verdict",
            "response, logs, audit records, database state",
            "Evidence missing from a successful harness run remains unverified",
        ):
            self.assertIn(value, integration)
        for value in (
            "connectivity harness",
            "evidence oracle",
            "Agent decision rule",
            "must not encode the business verdict",
        ):
            self.assertIn(value, plan)

    def test_local_service_may_use_authorized_isolated_test_dependencies(self):
        integration = self.skill("dev-integration")
        for value in (
            "system under test",
            "supporting dependencies",
            "authorized isolated non-production test dependencies",
            "test database",
            "Redis namespace",
            "Elasticsearch index prefix",
            "does not require local containers",
            "Docker or OrbStack",
            "must not by itself become `BLOCKED`",
            "isolation, retained test-data namespaces/identifiers",
            "local dependency process or container",
        ):
            self.assertIn(value, integration)

        plan = self.skill("dev-plan")
        self.assertIn("system under test", plan)
        self.assertIn("authorized isolated test-environment dependencies", plan)
        self.assertIn("must not require local containers by default", plan)

    def test_required_dependencies_and_worktree_gate_fail_closed(self):
        requirement = self.skill("dev-requirement")
        code = self.skill("dev-code")
        contract = (ROOT / "flow-contract.md").read_text()
        self.assertIn("BLOCKED_DEPENDENCY", requirement)
        self.assertIn("BLOCKED_DEPENDENCY", code)
        self.assertIn("FLOW_ADMISSION_BLOCKED", contract)
        self.assertIn("do not continue in the original checkout", contract)

    def test_digest_contract_is_non_self_referential_and_detects_tampering(self):
        contract = (ROOT / "artifact-contract.md").read_text()
        self.assertIn('Declared digest, revision and approval tuples are advisory', contract)
        self.assertIn('tolerates BOM/line-ending differences', contract)
        self.assertIn('strict checks for explicit diagnostics', contract)

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
            "dev-requirement": "requirement",
            "dev-intent": "intent",
            "dev-roadmap": "roadmap",
            "dev-spec": "spec",
            "dev-plan": "plan",
            "dev-code": "code",
            "dev-integration": "integration",
        }
        for name, step in stages.items():
            text = self.skill(name)
            self.assertIn('artifact-contract.md', text, name)
            self.assertIn(f"flow_step `{step}`", text, name)
        all_text = "\n".join(self.skill(name) for name in stages)
        for obsolete in (".ai/requirements/", ".ai/intents/", ".ai/roadmaps/", ".ai/specs/", ".ai/plans/", ".ai/evidence/"):
            self.assertNotIn(obsolete, all_text)
        plan = self.skill("dev-plan")
        integration = self.skill("dev-integration")
        self.assertIn("exactly one canonical absolute output directory", plan)
        self.assertIn("glob/regex patterns are not allowed", plan)
        self.assertIn("current-stage instructions", integration)
        self.assertIn("requires a Plan revision and approval", plan)
        self.assertIn("realpath semantics", integration)
        self.assertIn("reject `..` or symlink traversal", integration)

    def test_intent_uses_pre_admitted_worktree_and_orchestrated_approval(self):
        text = self.skill("dev-intent")
        for value in (
            "Verify the admitted worktree",
            "Never create or migrate a worktree in this stage",
            "ORCHESTRATED",
            "without another human confirmation",
            "approved_revision",
            "approved_digest",
        ):
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
