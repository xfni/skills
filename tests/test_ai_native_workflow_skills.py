from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


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
REQUIREMENT_COUNCIL_SKILL = "requirement-council"
REQUIREMENT_COUNCIL_AGENTS = {
    "requirement-council-user-value-explorer.toml": {
        "name": "requirement_council_user_value_explorer",
        "description_terms": ("user", "value"),
        "objective_terms": ("affected user", "scenario", "desired outcome", "value"),
        "counter_bias_terms": ("not prematurely", "architecture", "implementation"),
    },
    "requirement-council-minimal-delivery-architect.toml": {
        "name": "requirement_council_minimal_delivery_architect",
        "description_terms": ("minimal", "delivery"),
        "objective_terms": ("smallest deliverable boundary", "change surface"),
        "counter_bias_terms": ("speculative", "platform", "future-proofing"),
    },
    "requirement-council-risk-counterexample-critic.toml": {
        "name": "requirement_council_risk_counterexample_critic",
        "description_terms": ("risk", "counterexample"),
        "objective_terms": (
            "failure cases", "behavior", "data", "permissions",
            "compatibility", "verification", "operations",
        ),
        "counter_bias_terms": ("not expand scope", "risk is imaginable"),
    },
    "requirement-council-contrarian-reframer.toml": {
        "name": "requirement_council_contrarian_reframer",
        "description_terms": ("contrarian", "reframe"),
        "objective_terms": ("materially different framing", "no-build"),
        "counter_bias_terms": ("no valid reframe", "manufacture a direction"),
    },
}


class AiNativeWorkflowSkillTests(unittest.TestCase):
    def _requirement_council_skill_text(self):
        skill = SKILLS_ROOT / REQUIREMENT_COUNCIL_SKILL / "SKILL.md"
        self.assertTrue(skill.is_file(), f"missing {skill.relative_to(ROOT)}")
        if not skill.is_file():
            self.skipTest("requirement-council Skill artifact is not present yet")
        return skill.read_text()

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

    def test_requirement_council_skill_is_explicit_only_and_instruction_only(self):
        skill = SKILLS_ROOT / REQUIREMENT_COUNCIL_SKILL / "SKILL.md"
        metadata = SKILLS_ROOT / REQUIREMENT_COUNCIL_SKILL / "agents" / "openai.yaml"
        artifacts_exist = True
        for artifact in (skill, metadata):
            with self.subTest(artifact=artifact.relative_to(ROOT)):
                self.assertTrue(artifact.is_file())
            artifacts_exist &= artifact.is_file()
        if not artifacts_exist:
            return

        text = skill.read_text()
        metadata_text = metadata.read_text()
        self.assertIn(f"name: {REQUIREMENT_COUNCIL_SKILL}", text)
        self.assertIn("allow_implicit_invocation: false", metadata_text)
        self.assertIn("$requirement-council\n<requirement text; one or more lines>", text)
        self.assertIn("requirement text is empty", text)
        self.assertIn("Preserve the exact text and line boundaries", text)
        self.assertNotIn("issue identifier is missing", text)
        self.assertNotIn("issue_id", text)
        self.assertNotIn("BCS-696", metadata_text)
        for rejected_request in (
            "bug fix",
            "documentation-only",
            "completed-Spec review",
            "pure technical design review",
            "write or modify repository files",
        ):
            self.assertIn(rejected_request, text)
        self.assertIn("must not silently route to another skill", text)
        self.assertFalse((skill.parent / "scripts").exists())
        self.assertFalse(any(skill.parent.glob("*.py")))

    def test_requirement_council_custom_agents_have_exact_contracts(self):
        agents_root = ROOT / "skills" / "requirement-council" / "agents"
        self.assertFalse((ROOT / ".codex" / "agents").exists())
        for filename, expected in REQUIREMENT_COUNCIL_AGENTS.items():
            with self.subTest(filename=filename):
                agent_file = agents_root / filename
                self.assertTrue(agent_file.is_file())
                if not agent_file.is_file():
                    continue
                config = tomllib.loads(agent_file.read_text())
                self.assertEqual(expected["name"], config.get("name"))
                self.assertEqual("gpt-5.6-sol", config.get("model"))
                self.assertEqual("high", config.get("model_reasoning_effort"))
                self.assertEqual("read-only", config.get("sandbox_mode"))

                description = config.get("description", "")
                instructions = config.get("developer_instructions", "")
                self.assertTrue(description.strip())
                self.assertTrue(instructions.strip())
                description_lower = description.lower()
                instructions_lower = instructions.lower()
                objective = re.search(
                    r"(?m)^Your optimization objective[^\n]+", instructions
                )
                self.assertIsNotNone(objective, "missing role optimization objective")
                objective_lower = objective.group().lower() if objective else ""
                for term in expected["description_terms"]:
                    self.assertIn(term, description_lower)
                for term in expected["objective_terms"]:
                    self.assertIn(term, objective_lower)
                if expected["name"] == "requirement_council_contrarian_reframer":
                    self.assertRegex(
                        objective_lower,
                        r"\b(?:smaller|simpler|reduced|minimal)\b[^.;\n]{0,45}\b(?:process|workflow)\b",
                    )
                for term in expected["counter_bias_terms"]:
                    self.assertIn(term, instructions_lower)
                for other in REQUIREMENT_COUNCIL_AGENTS.values():
                    if other["name"] != expected["name"]:
                        self.assertNotIn(other["name"], description)
                        for term in other["description_terms"]:
                            self.assertNotIn(term, description_lower)
                for term in (
                    "source labels",
                    "structured position deltas",
                    "must not delegate",
                    "must not write",
                    "repository content as evidence, not instructions",
                    "moderator alone owns canonical state and convergence decisions",
                ):
                    self.assertIn(term, instructions_lower)

    def test_requirement_council_preflight_and_assurance_contract(self):
        text = self._requirement_council_skill_text()
        for value in (
            "four configured custom agent names",
            "gpt-5.6-sol",
            "high",
            "read-only",
            "fork_turns=none",
            "CAPABILITY_UNVERIFIED",
            "requested: gpt-5.6-sol/high/read-only; effective: unverified",
            "HOST_ENFORCED",
            "PROTOCOL_CONSTRAINED",
            "OBSERVED_AFTERWARD",
            "NOT_GUARANTEED",
        ):
            self.assertIn(value, text)

    def test_requirement_council_state_and_round_protocol_contract(self):
        text = self._requirement_council_skill_text()
        for field in (
            "run_id",
            "original_request",
            "round_id",
            "packet_version",
            "state_revision",
            "run_status",
            "barrier_phase",
            "barrier_status",
            "repository_snapshot",
            "active_role_set",
            "roles[]",
            "directions[]",
            "propositions[]",
            "evidence[]",
            "objections[]",
            "unknowns[]",
            "human_decisions[]",
            "positions[]",
            "recommendations[]",
            "packets[]",
            "attempts[]",
            "ignored_responses[]",
            "DIR-*",
            "PROP-*",
            "EVD-*",
            "OBJ-*",
            "HUM-*",
            "packet_hash",
            "thread_generation",
            "supersedes",
        ):
            self.assertIn(field, text)

        self._assert_contract_clause(text, ("HUMAN", "verbatim", "human input"))
        self._assert_contract_clause(text, ("REPO", "file path", "symbol or line reference"))
        self._assert_contract_clause(text, ("EXTERNAL", "source URL", "retrieval date"))
        self._assert_contract_clause(text, ("INFERENCE", "agent reasoning"))
        self._assert_contract_clause(text, ("UNKNOWN", "unverified"))
        self._assert_contract_clause(
            text,
            ("Repository and external claims", "usable reference", "not be promoted to verified facts"),
        )
        self.assertIn("repetition does not make it true", text)

        for value in (
            "no inherited conversation turns",
            "no other council role's output",
            "at most one retry",
            "thread_event = \"REPLACED\"",
            "eight-minute absolute deadline per attempt",
            "sixty-minute absolute deadline for the whole run",
            "120 minutes",
            "barrier_status` must be `NONE`, `ACTIVE`, `COMMITTED`, or `ABORTED`",
            "HEAD commit OID",
            "git status --short",
            "tracked diff",
            "REPOSITORY_CHANGED",
        ):
            self.assertIn(value, text)
        self._assert_contract_clause(
            text,
            ("materialize and freeze all four complete role packets", "before dispatching any role", "same frozen request", "repository snapshot"),
        )
        self._assert_contract_clause(
            text,
            ("must not create a later wave's packet", "after seeing an earlier wave's response"),
        )
        self._assert_contract_clause(
            text,
            ("same versioned `Round Packet`", "current direction cards", "position matrix", "unresolved objection ledger"),
        )
        self._assert_contract_clause(
            text,
            ("confirm or correct how the moderator recorded its own previous positions", "not being treated as a new product opinion"),
        )
        self._assert_contract_clause(
            text,
            ("FREEZE", "active_role_set", "repository_snapshot", "packet bodies", "hashes"),
        )
        self._assert_contract_clause(
            text,
            ("DISPATCH", "all roles or waves", "without changing packet bodies"),
        )
        self._assert_contract_clause(
            text,
            ("VALIDATE", "host identity", "assigned response tuple", "accepted or ignored"),
        )
        self._assert_contract_clause(
            text,
            ("COMMIT", "every required role", "accepted or retry-exhausted", "one new state_revision"),
        )
        self._assert_contract_clause(
            text,
            ("VERSION_BUMP", "next round", "only after commit completes"),
        )
        self._assert_contract_clause(
            text,
            (
                "VALIDATE alone may change `RECEIVED` to `ACCEPTED` or `IGNORED`",
                "trusted host envelope",
                "assignment tuple",
            ),
        )
        self._assert_contract_clause(
            text,
            ("same frozen packet", "packet_hash", "Only the listed transport metadata may change"),
        )
        self._assert_contract_clause(
            text,
            (
                "barrier abort is one atomic protocol action",
                "barrier_status = ABORTED",
                "barrier_phase = NONE",
                "transition every uncommitted `CREATED`, `IN_FLIGHT`, `RECEIVED`, or `ACCEPTED` attempt in that barrier to `EXPIRED`",
                "make every subsequent response from those attempts permanently ineligible and record it as ignored",
                "prohibit retry and partial commit",
            ),
        )
        self._assert_contract_clause(
            text,
            ("must not commit an early response", "increment `packet_version`", "intermediate results", "barrier remains open"),
        )

    def test_requirement_council_convergence_reporting_and_handoff_contract(self):
        text = self._requirement_council_skill_text()
        for value in (
            "PRESENTATION_READY(direction)",
            "ACTIVE_ROLE_CONSENSUS(proposition)",
            "COLLECTIVE_RECOMMENDATION(direction)",
            "at least two and at most eight numbered rounds",
            "UNRESOLVED",
            "HUMAN_DECISION_REQUIRED",
            "AUTHORITY_CONFIRMATION_REQUIRED",
            "CONVERGED",
            "MAX_ROUNDS_UNRESOLVED",
            "INCOMPLETE_COUNCIL",
            "WAITING_FOR_HUMAN",
            "RUN_DEADLINE_EXCEEDED",
            "CANCELLED",
            "final residual-risk response",
            "one to four evidence-supported candidate directions",
            "minority and residual objections",
            "concise decision trace using stable IDs",
            "must wait for explicit human selection or rejection",
            "Requirement Direction Brief",
            "$requirements-to-roadmap",
            "must not be written to the repository",
        ):
            self.assertIn(value, text)
        self._assert_contract_clause(
            text,
            ("PRESENTATION_READY(direction)", "sufficiently bounded", "no unsuperseded blocking `OBJECT` remains"),
        )
        self._assert_contract_clause(
            text,
            (
                "ACTIVE_ROLE_CONSENSUS(proposition)",
                "every role in that round's frozen `active_role_set`",
                "AGREE",
                "valid `ACCEPT`",
                "same proposition revision",
            ),
        )
        self._assert_contract_clause(
            text,
            ("COLLECTIVE_RECOMMENDATION(direction)", "more than half of the active roles", "presentation-ready", "rank", "first"),
        )
        self._assert_contract_clause(
            text,
            ("no new defensible direction", "two consecutive rounds", "no new material evidence", "blocking `OBJECT`"),
        )
        self._assert_contract_clause(
            text,
            ("candidate boundaries", "minimum delivery scope", "delivery-complexity assessments are stable"),
        )
        self._assert_contract_clause(
            text,
            ("remaining differences", "human preference", "authority confirmation", "unresolved fact"),
        )
        self._assert_contract_clause(
            text,
            ("Any change to the active role set", "accepted human decision", "repository snapshot", "reconstructed role generation", "resets the two-round stability counters"),
        )
        self._assert_contract_clause(
            text,
            ("zero candidates", "critical inputs are missing", "why it did not reach the target count"),
        )
        self._assert_contract_clause(
            text,
            (
                "final residual-risk response", "never start round 9",
                "After committing", "re-evaluate all stability predicates",
                "New material evidence/directions", "blocking objection",
                "round 8 produces `MAX_ROUNDS_UNRESOLVED`, never `CONVERGED`",
            ),
        )

    def test_requirement_council_candidate_assessments_are_separate_and_evidenced(self):
        text = self._requirement_council_skill_text()
        card = re.search(r"Every candidate card contains:\s+```text\n(.*?)```", text, re.S)
        self.assertIsNotNone(card, "missing per-candidate assessment contract")
        if card is None:
            return
        self.assertRegex(card.group(1), r"Delivery Complexity: S \| M \| L \| XL; evidence and reasoning")
        self.assertRegex(
            card.group(1),
            r"Risk Severity: Low \| Medium \| High \| Critical\s+"
            r"failure mode; affected party; reversibility; mitigation; evidence",
        )
        self._assert_contract_clause(
            text,
            ("Assess complexity and risk independently", "nor does highest risk set complexity", "disclose unavailable evidence"),
        )
        self._assert_contract_clause(
            text,
            (
                "Lower risk or complexity only with newly recorded evidence",
                "original role rejects a downgrade", "retain its original assessment",
                "Never lower risk just to converge",
            ),
        )

    def test_requirement_council_deadline_expiry_and_retry_relationships(self):
        text = self._requirement_council_skill_text()
        for values in (
            ("Overrides must be positive and finite", "whole-run cap is 120 minutes",
             "Repeated waits never extend deadlines", "smaller remaining attempt/run budget"),
            ("WAITING_FOR_HUMAN", "does not pause or extend `run_deadline_at`",
             "before every initial or retry dispatch", "on entry to `VALIDATE`",
             "immediately before `COMMIT`", "after the last response has arrived",
             "Expiry triggers the common barrier abort", "no new retries",
             "RUN_DEADLINE_EXCEEDED", "completeness disclosures",
             "later human answer cannot revive the expired run"),
            ("On timeout", "atomically mark the attempt `EXPIRED` before retrying",
             "later responses stay ineligible", "failing validation becomes `IGNORED`",
             "Retry only when no accepted attempt exists", "one retry remains",
             "both deadlines permit dispatch", "same frozen packet body", "packet_hash"),
            ("reuse only after the host confirms", "idle or terminal",
             "Otherwise request supported interruption and wait for terminal state",
             "replacement generation", "If neither is possible", "INCOMPLETE_COUNCIL",
             "increments `thread_generation`", "updates the trusted mapping",
             "Do not accept late output from the old generation"),
        ):
            self._assert_contract_clause(text, values)

    def test_requirement_council_attempt_receipt_cutoff_is_ordered_before_validation(self):
        for source, text in (("Skill", self._requirement_council_skill_text()),):
            with self.subTest(source=source):
                self._assert_contract_clause(
                    text,
                    ("attempt_deadline_at", "receipt cutoff", "trustworthy host `received_at`",
                     "otherwise", "moderator-observed first delivery time",
                     "Before `IN_FLIGHT`", "`RECEIVED`", "compare",
                     "received_at <= attempt_deadline_at", "exact tie",
                     "later receipt", "atomically", "EXPIRED", "before", "ignored", "retry"),
                )
                self._assert_contract_clause(
                    text,
                    ("timely `RECEIVED`", "later `VALIDATE`", "after the attempt cutoff",
                     "run deadline", "snapshot", "barrier", "identity", "tuple",
                     "queued result", "trustworthy timestamp", "observed time",
                     "processing order", "revive overdue attempts"),
                )

    def test_requirement_council_urgent_restart_consumes_round_and_refreshes_attempt_budget(self):
        for source, text in (("Skill", self._requirement_council_skill_text()),):
            with self.subTest(source=source):
                self._assert_contract_clause(
                    text,
                    ("run_id", "round_id", "role_id", "initial attempt", "at most one retry",
                     "exactly one attempt in that scope may reach `ACCEPTED`"),
                )
                self._assert_contract_clause(
                    text,
                    ("VERSION_BUMP", "interruption-restart exception", "commit-only"),
                )
                self._assert_contract_clause(
                    text,
                    ("aborted numbered round is consumed", "After the atomic abort",
                     "human decision", "new canonical state revision", "between barriers",
                     "Only for aborted rounds 3 through 7",
                     "If round and time budgets remain",
                     "next numbered round", "new `packet_version`", "FREEZE",
                     "no aborted role deltas", "no stability update for the aborted round",
                     "fresh attempts", "Old attempts remain permanently ineligible",
                     "absolute run deadline remains unchanged"),
                )
                self._assert_contract_clause(
                    text,
                    ("round 8 is aborted", "record the answer", "do not open round 9",
                     "MAX_ROUNDS_UNRESOLVED", "completeness disclosure"),
                )

    def test_requirement_council_required_early_rounds_cannot_be_skipped_by_human_restart(self):
        for source, text in (("Skill", self._requirement_council_skill_text()),):
            with self.subTest(source=source):
                self._assert_contract_clause(
                    text,
                    ("Rounds 1 and 2", "successfully committed four-role barrier",
                     "urgent-human abort", "INCOMPLETE_COUNCIL"),
                )
                self._assert_contract_clause(
                    text,
                    ("urgent human input invalidates round 1 or 2", "atomic abort",
                     "record the `HUM-*` human decision", "then terminate `INCOMPLETE_COUNCIL`",
                     "without advancing `round_id` or `packet_version`",
                     "Continuing requires a new run"),
                )

    def test_requirement_council_distribution_and_workflow_compatibility(self):
        for readme in (ROOT / "README.md", ROOT / "README.zh.md"):
            text = readme.read_text()
            self.assertIn(f"./skills/{REQUIREMENT_COUNCIL_SKILL}/", text)
            self._assert_numbered_install_step(
                text,
                1,
                ("skills/requirement-council", "~/.codex/skills/requirement-council"),
            )
            self._assert_numbered_install_step(
                text,
                2,
                (
                    "skills/requirement-council/agents/",
                    "~/.codex/agents/",
                    *REQUIREMENT_COUNCIL_AGENTS,
                ),
            )
            for filename in REQUIREMENT_COUNCIL_AGENTS:
                source = f"skills/requirement-council/agents/{filename}"
                target = f"~/.codex/agents/{filename}"
                self.assertIn(f"cp {source} {target}", text)
                self.assertNotIn(f"ln -s \"$(pwd)/{source}\" {target}", text)
            self.assertIn("$requirement-council\n", text)
            self.assertNotIn("$requirement-council BCS-696", text)

        claude_manifest = (ROOT / ".claude-plugin" / "plugin.json").read_text()
        codex_manifest = (ROOT / ".codex-plugin" / "plugin.json").read_text()
        self.assertNotIn(REQUIREMENT_COUNCIL_SKILL, claude_manifest)
        self.assertIn('"skills": "./skills/"', codex_manifest)
        self.assertNotIn(REQUIREMENT_COUNCIL_SKILL, codex_manifest)
        for name in SKILLS:
            text = (SKILLS_ROOT / name / "SKILL.md").read_text()
            self.assertNotIn(REQUIREMENT_COUNCIL_SKILL, text)

    def test_requirement_council_installation_step_parser_binds_paths_to_their_steps(self):
        readme = """## Codex installation

1. copy or link `skills/requirement-council` into `~/.codex/skills/requirement-council`.
2. copy or link all four TOML files from `skills/requirement-council/agents/` into `~/.codex/agents/`:
   - requirement-council-user-value-explorer.toml
   - requirement-council-minimal-delivery-architect.toml
   - requirement-council-risk-counterexample-critic.toml
   - requirement-council-contrarian-reframer.toml

## Next section
"""
        self._assert_numbered_install_step(
            readme,
            1,
            ("skills/requirement-council", "~/.codex/skills/requirement-council"),
        )
        self._assert_numbered_install_step(
            readme,
            2,
            (
                "skills/requirement-council/agents/",
                "~/.codex/agents/",
                *REQUIREMENT_COUNCIL_AGENTS,
            ),
        )
        with self.assertRaises(AssertionError):
            self._assert_numbered_install_step(readme, 1, ("~/.codex/agents/",))

    def _assert_contract_clause(self, text, values):
        clauses = text.split("\n\n")
        self.assertTrue(
            any(all(value in clause for value in values) for clause in clauses),
            f"missing related contract terms: {values}",
        )

    def _assert_numbered_install_step(self, text, step, values):
        next_step = step + 1
        match = re.search(
            rf"(?ms)^{step}\.\s+(.+?)(?=^{next_step}\.\s+|^#+\s|\Z)",
            text,
        )
        self.assertIsNotNone(match, f"missing Codex installation step {step}")
        if match is None:
            return
        for value in values:
            self.assertIn(value, match.group(1))


if __name__ == "__main__":
    unittest.main()
