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

    def test_flowctl_is_the_only_mechanical_progression_authority(self):
        contract = (ROOT / "flowctl-contract.md").read_text()
        for value in (
            "sole writer", "must not edit", "flowctl status", "artifact register",
            "review begin", "review submit", "review cursor", "handoff accept",
            "signal record",
            "expected-revision", "STATE_CONFLICT", "structured JSON",
            "Actual hashes, receipts and counters are controller-owned", "resume",
        ):
            self.assertIn(value, contract)
        for name in SKILLS:
            text = self.skill(name)
            self.assertIn("flowctl-contract.md", text, name)
            self.assertIn("flowctl status", text, name)
            self.assertIn("must not edit the controller", text, name)
        runner = self.skill("flow-run")
        self.assertIn("flowctl resume", runner)
        for name in ("flow-requirement", "flow-intent", "flow-roadmap", "flow-spec", "flow-plan", "flow-code", "flow-integration"):
            self.assertIn("flowctl artifact register", self.skill(name), name)
            self.assertIn("flowctl handoff accept", self.skill(name), name)
        for name in ("flow-spec", "flow-plan", "flow-code"):
            text = self.skill(name)
            self.assertIn("flowctl review begin", text, name)
            self.assertIn("flowctl review submit", text, name)
            self.assertIn("flowctl review cursor", text, name)

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
            "necessary human gate", "FLOW_RUN_RESUMED",
            "route backward", "do not bypass", "mark the goal complete",
            "target_milestones", "pending", "completed", "deferred",
            "explicit arbitrary-node start", "disclose missing history",
            "clear affected completed handoffs",
        ):
            self.assertIn(value, text)

        self.assertIn("approved spec.md", text)
        self.assertIn("start at `$flow-plan`", text)
        self.assertIn("confirmed intent.md", text)
        self.assertIn("start at `$flow-roadmap`", text)
        self.assertIn("COMPLETE_WITH_DEFECT", text)
        self.assertIn("EXTERNAL_REVIEW_GAP", text)
        for value in (
            "valid terminal `COMPLETE_WITH_DEFECT`", "PRODUCTION_REPLAY_GAP",
            "every open gap", "must not claim clean completion",
        ):
            self.assertIn(value, text)

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

    def test_requirement_swarm_rejects_unjustified_platformization(self):
        requirement = self.skill("flow-requirement")
        brainstorm = self.skill("flow-brainstorm")
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

        value_agent = (ROOT / "skills" / "flow-requirement" / "agents" / "flow-requirement-value.toml").read_text()
        risk_agent = (ROOT / "skills" / "flow-requirement" / "agents" / "flow-requirement-risk.toml").read_text()
        for text in (value_agent, risk_agent):
            self.assertIn("PLATFORM_RECEIPT-*", text)
            self.assertIn("current NEED-*", text)
            self.assertIn("smallest non-platform alternative", text)
        self.assertIn("default recommendation", value_agent)
        self.assertIn("reject platformization", risk_agent)

    def test_requirement_risk_simulates_constraint_interactions_before_authorization(self):
        requirement = self.skill("flow-requirement")
        risk_agent = (ROOT / "skills" / "flow-requirement" / "agents" / "flow-requirement-risk.toml").read_text()
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

        for skill in ("flow-spec", "flow-plan", "flow-code"):
            text = self.skill(skill)
            self.assertIn("finding-weight convergence", text)
            self.assertIn("non-blocking finding must not trigger another review cycle", text)
            self.assertIn("same recurrence_key", text)
            self.assertIn("three review cycles", text)

    def test_review_transport_and_discovery_contracts_are_explicit(self):
        flowctl = (ROOT / "flowctl-contract.md").read_text()
        for value in (
            "FLOW_REVIEW_REPORT_BEGIN",
            "FLOW_REVIEW_REPORT_END",
            "FLOW_REVIEW_ERROR_BEGIN",
            "FLOW_REVIEW_ERROR_END",
            "two `UNCLASSIFIED`",
            "BLOCKED_REVIEW",
            "never fallback conditions",
            "UNKNOWN_BACKEND_FAILURE",
            "PROTOCOL_ERROR",
        ):
            self.assertIn(value, flowctl)
        self.assertIn("cannot force the host Agent to invoke flowctl", flowctl)
        self.assertIn("detectable non-progression", flowctl)

        artifact = (ROOT / "artifact-contract.md").read_text()
        self.assertIn("custom filename", artifact)
        self.assertIn("--inputs", artifact)

        orchestration = (ROOT / "orchestration-contract.md").read_text()
        self.assertIn("context-independent", orchestration)
        self.assertIn("context-dependent transition", orchestration)

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

    def test_spec_plan_code_use_independent_lanes_and_astra_consistency_review(self):
        for name in ("flow-spec", "flow-plan", "flow-code"):
            text = self.skill(name)
            for value in (
                "**REQUIRED SUB-SKILL:** Use independent-review",
                "**REQUIRED SUB-SKILL:** Use cursor-review",
                "**REQUIRED SUB-SKILL:** Use ibrain-review",
                "gpt-5.6-sol", "high", "gpt-6-astra", "medium",
                "root agent", "difficulty", "GPT Lane", "Cursor Lane",
                "final consistency review", "complete filtered frozen worktree",
                "organization-trusted", "no automatic commit", "secrets",
                "BLOCKED_REVIEW", "glm-5.3",
                "terminal receipt", "auxiliary fields", "controller",
            ):
                self.assertIn(value, text, f"{name} missing {value}")
            self.assertNotIn("gpt-5.6-sol` with `medium", text)
            self.assertNotIn("gpt-6-astra` with `high", text)

    def test_cursor_runtime_failure_falls_back_to_ibrain_before_defect_handoff(self):
        expected_status = {
            "flow-spec": "APPROVED_WITH_DEFECT",
            "flow-plan": "APPROVED_WITH_DEFECT",
            "flow-code": "COMPLETE_WITH_DEFECT",
        }
        for name, status in expected_status.items():
            text = self.skill(name)
            for value in (
                "bounded retry behavior",
                "not degradable",
                status,
                "EXTERNAL_REVIEW_GAP",
                "ibrain-review",
                "glm-5.3",
                "final completion report",
                "handoff",
                "full `review_binding` and binding ID",
            ):
                self.assertIn(value, text, f"{name} missing {value}")
            self.assertNotIn("`INCOMPLETE`, drift", text)

        self.assertIn("only when no gap is open", self.skill("flow-plan"))
        self.assertIn("both Cursor and iBrain", self.skill("flow-code"))

        integration = self.skill("flow-integration")
        self.assertIn("COMPLETE_WITH_DEFECT", integration)
        self.assertIn("EXTERNAL_REVIEW_GAP", integration)
        self.assertIn("final report", integration)
        self.assertIn('derive defect completion', integration)
        self.assertIn('Propagate gaps', integration)

    def test_plan_contract(self):
        text = self.skill("flow-plan")
        for value in (
            "approved spec.md", "executable tasks", "files and modules",
            "test-first", "verification commands", "rollback", "traceability",
            "flow_step `plan`", "$flow-code",
        ):
                self.assertIn(value, text)

    def test_flow_initial_gate_is_production_replay_only(self):
        runner = self.skill("flow-run")
        for value in ("生产数据回放授权", "允许使用生产数据进行本地测试（推荐）",
                      "不进行依赖生产数据的集成测试", "LOCAL_PRODUCTION_REPLAY",
                      "SKIP_PRODUCTION_REPLAY", "flowctl authorization decide", "flowctl authorization amend"):
            self.assertIn(value, runner)
        self.assertNotIn("不允许外部审查", runner)
        self.assertNotIn("允许最小必要范围的外部审查", runner)
        self.assertIn("production_replay", runner)
        self.assertIn("no external-review authorization gate", runner)

    def test_external_review_surfaces_require_frozen_view_not_human_authorization(self):
        for name in ("flow-spec", "flow-plan", "flow-code"):
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
        for name in ("flow-spec", "flow-plan", "flow-code"):
            text = self.skill(name)
            self.assertIn("review-contract.md", text)
            self.assertIn("single-use package binding", text)
            self.assertIn("Legacy paths are", text)
            self.assertIn("final consistency review", text)
            self.assertNotIn("same active `external_review` authorization ID", text)

    def test_replay_decision_reaches_integration_as_controller_binding(self):
        plan = self.skill("flow-plan")
        integration = self.skill("flow-integration")
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
        for name in ("flow-spec", "flow-plan", "flow-code"):
            text = self.skill(name)
            self.assertIn("Direct invocation review scope", text)
            self.assertIn("no external-review authorization gate", text)
            self.assertNotIn("minimal stage-bound authorization gate for only `external_review`", text)
        text = self.skill("flow-integration")
        for value in ("Direct invocation authorization", "minimal stage-bound authorization gate",
                      "production_replay", "controller-generated authorization ID"):
            self.assertIn(value, text)

    def test_ibrain_fallback_reuses_snapshot_not_cursor_authority(self):
        contract = (ROOT / "review-contract.md").read_text()
        self.assertIn("independently of Cursor decisions", contract)
        self.assertIn("Every retry/revision/backend has a fresh single-use package binding", contract)
        self.assertIn("Findings never activate fallback", contract)
        orchestration = (ROOT / "orchestration-contract.md").read_text()
        self.assertIn("two controller-recorded retryable Cursor process failures", orchestration)
        self.assertNotIn("If external review is denied", orchestration)

    def test_code_and_unit_test_contract(self):
        text = self.skill("flow-code")
        for value in (
            "approved plan.md", "TDD", "failing unit test", "minimal implementation",
            "refactor", "independent-review", "unit-test evidence",
            "must not claim integration coverage", "$flow-integration",
        ):
            self.assertIn(value, text)

    def test_flow_code_uses_one_lazy_session_scoped_luna_coder(self):
        text = self.skill("flow-code")
        for value in (
            "flow_coder",
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
            "return to `$flow-plan`",
            "close the coder thread",
        ):
            self.assertIn(value, text)

        agent = ROOT / "skills" / "flow-code" / "agents" / "flow-coder.toml"
        self.assertTrue(agent.is_file())
        config = agent.read_text()
        for value in (
            'name = "flow_coder"',
            'model = "gpt-5.6-luna"',
            'model_reasoning_effort = "max"',
            "Do not delegate",
            "Implement only the assigned TASK-*",
            "Do not change Requirement, Intent, Roadmap, Spec, or Plan",
            "Return a checkpoint",
        ):
            self.assertIn(value, config)

    def test_flow_run_controller_persists_coder_thread_state(self):
        runner = self.skill("flow-run")
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
        self.assertIn("flow-coder.toml", readme)
        self.assertIn("created lazily", readme)

    def test_flow_run_reports_observable_stage_transitions(self):
        runner = self.skill("flow-run")
        code = self.skill("flow-code")
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
        text = self.skill("flow-integration")
        for value in (
            "available Plan", "current milestone", "snapshot",
            "cross-component", "end-to-end", "permissions", "failure recovery",
            "Success Signals", "integration evidence", "route every failure",
        ):
            self.assertIn(value, text)

    def test_production_replay_skip_contract_runs_unaffected_scenarios_and_reports_gaps(self):
        plan = self.skill("flow-plan")
        integration = self.skill("flow-integration")
        runner = self.skill("flow-run")
        for value in (
            "SKIP_PRODUCTION_REPLAY", "acceptance claim", "production-derived data",
            "synthetic or isolated test data", "integration_scenarios",
            "Prefer `integration_scenarios", "Extra descriptive fields",
        ):
            self.assertIn(value, plan)
        for value in (
            "SKIP_PRODUCTION_REPLAY", "SKIPPED_AUTHORIZED_REPLAY",
            "PRODUCTION_REPLAY_GAP", "unaffected", "COMPLETE_WITH_DEFECT",
            "zero-executed warning", "final report", "FAILED", "BLOCKED",
            "Plan digest", "complete expected scenario set", "integration_results",
            "controller derives", "status must match the signal",
        ):
            self.assertIn(value, integration)
        for value in (
            "legacy Plan checkpoint", "Plan revision and re-review",
            "active `SKIP_PRODUCTION_REPLAY` authorization",
        ):
            self.assertIn(value, runner)

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

    def test_integration_starts_a_temporary_local_service_before_remote_fallback(self):
        integration = self.skill("flow-integration")
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

        plan = self.skill("flow-plan")
        self.assertIn("temporary local service", plan)
        self.assertIn("remote test deployment is an explicit exception", plan)

    def test_local_service_may_use_authorized_isolated_test_dependencies(self):
        integration = self.skill("flow-integration")
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
            "isolation and cleanup",
            "local dependency process or container",
        ):
            self.assertIn(value, integration)

        plan = self.skill("flow-plan")
        self.assertIn("system under test", plan)
        self.assertIn("authorized isolated test-environment dependencies", plan)
        self.assertIn("must not require local containers by default", plan)

    def test_artifact_chain_is_revision_and_digest_bound(self):
        contract = (ROOT / 'flowctl-contract.md').read_text()
        self.assertIn('actual required terminal review receipts', contract)
        self.assertIn('actual content digests bind review receipts', (ROOT / 'artifact-contract.md').read_text())
        for name in SKILLS:
            if name == "flow-brainstorm":
                continue
            text = self.skill(name)
            self.assertIn('artifact-contract.md', text, name)

        expected_sources = {
            "flow-roadmap": ("requirement", "intent"),
            "flow-spec": ("requirement", "intent", "roadmap"),
            "flow-plan": ('Spec', 'Plan', 'available inputs'),
            "flow-code": ('Plan', 'snapshot', 'allowed change surface'),
            "flow-integration": ('Plan', 'snapshot'),
        }
        for name, sources in expected_sources.items():
            text = self.skill(name)
            for source in sources:
                self.assertIn(source.lower(), text.lower(), f"{name} missing {source}")

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
            self.assertIn('artifact-contract.md', text, name)
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
