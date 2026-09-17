# Flow v2 Admission Contract

This contract is part of Flow v2 and does not depend on `AGENTS.md`. `$flow-run` and every directly invoked Flow stage must read and enforce it before reading or writing Flow artifacts.

For every admission, permission or recovery question, apply Human-readable interruption in `orchestration-contract.md`, including before a controller exists. Explain the smallest missing input and what follows; keep internal bindings as evidence. This adds no authorization gate.

## Issue identity

- Feature work requires a human-provided issue ID. The agent must not infer or invent it from a branch, path, repository, artifact, PMS result, or goal.
- `$flow-run` owns Flow admission. When the current conversation and a verified controller contain no human-provided issue ID, request it exactly once and stop. Record its human provenance in the controller.
- Ask in plain language: “还缺本次需求的议题编号，用于把文档、代码和测试归到同一项工作。请提供 issue 编号，例如 BCS-710 或项目已有的议题编号；收到后我会核验工作目录并继续。” Do not invent a number or ask for controller metadata.
- Every stage must verify silently that its input artifacts, controller, branch, and worktree carry that same issue ID. A valid inherited binding must not cause another prompt. A conflict returns `FLOW_ADMISSION_BLOCKED`; absence under direct invocation returns `FLOW_ADMISSION_GATE` for an issue ID.

## Controller and worktree admission

After accepting the issue, create or reuse the matching independent Git worktree from local `master` before artifact discovery. For a new controller, Agent may inspect admitted documents to choose an initial --stage/--milestone, then initialize before writing artifacts or execution. Existing controllers retain their recorded position:

```text
branch: feature-<issue>-<short-kebab-description>
path: <repository-parent>/feature-<issue>-<short-kebab-description>
```

The issue component is canonical and the description is concise, lowercase kebab-case. Reuse an existing worktree only after verifying its repository, branch, HEAD ancestry, issue binding, and absence of a conflicting controller. Never overwrite or repurpose an unrelated worktree or branch.

If the new path is outside the current Codex writable roots, report its absolute path and current session ID, provide a fully substituted `codex resume <session-id> --add-dir <absolute-worktree-path>` command, persist `FLOW_ADMISSION_GATE`, and wait for the resumed session. If the session ID cannot be determined, return `FLOW_ADMISSION_BLOCKED`; do not continue in the original checkout.

Explain that the isolated development directory exists but this session cannot yet write to it; tell the human to exit this session and run the verified copyable command, then resume the same work. If worktree/issue identity conflicts, show the current and intended non-secret directory/issue facts and ask only which actual task/directory is correct when the Agent cannot resolve it safely. Do not suggest resetting Git, overwriting another worktree or editing controller JSON.

Every stage, including direct invocation, must verify silently before work that the current repository, worktree path, branch, controller, and issue binding match. A valid controller means a stage must not ask for the issue ID again, must not recreate the worktree, and must not ask the human to select it. Safe deterministic metadata repair is allowed and recorded; ambiguity, dirty conflicting state, or an incorrect worktree returns `FLOW_ADMISSION_BLOCKED` with evidence and a precise recovery condition.

Direct invocation performs this same admission when no controller exists. It may request the missing issue, initialize the controller, and create or reuse the worktree, but it may not weaken the contract.

## Human interaction boundary

After controller/worktree admission and before requirement work, `$flow-run` asks whether production data may be acquired and used for local testing. Flow does not own sanitization or data deletion proofs; project policy and host permissions remain authoritative. External review is not an authorization gate. Production decisions persist through authorization IDs; resume reuses active scope and changed decisions use the amendment transition.

### Test infrastructure permission

At the initial interaction, explicitly disclose the common non-production test permission independently of the production-replay choice: either choice permits starting the temporary local application and using project-approved, verifiably isolated test dependencies for this issue. Common dependencies include SQL/Mongo databases, Redis, Elasticsearch/OpenSearch, queues/brokers and object storage. Permit only scenario-required reads/writes within the selected test database, namespace, index, queue, bucket/prefix or tenant; clean up only data/resources created by this run. No permission to use production or unknown endpoints, change shared/global configuration, or delete pre-existing data is implied.

Retain the actual human confirmation in the Requirement human-source context, or the confirmed Direct charter, and cite it in Integration evidence. The production_replay controller decision continues to represent production data only; do not invent a middleware authorization ID or treat a historical replay decision as acceptance of this newly disclosed permission. Existing project/Plan/charter permissions remain valid; ask once only when a necessary dependency or side effect is outside them. Missing optional permission metadata is not a controller gate.

For every supporting middleware (MongoDB, MySQL/PostgreSQL, Redis, Elasticsearch/OpenSearch, Kafka/RabbitMQ and object storage alike), resolve missing connection details before escalating to the human. First inspect project source/configuration, configuration loaders and precedence, test profiles, launch scripts, deployment templates and runbooks read-only. Identify the effective endpoint, database/namespace/index/queue/bucket scope, exact supported override names, permission source and startup side effects. Use targeted inspection, never dump environment/credential files, execute configuration code with possible startup/network side effects or make a trial connection to discover an unknown target. Keep credential values out of reports and permission justifications.

Separate discoverability from authority: finding an address in code is not permission to use it or proof of isolation. When project evidence establishes an approved isolated target, apply existing scope and request the specific host permission without asking the human to re-supply discoverable addresses or variable names. For a dependency outside the tested boundary, inspect existing local mode/optional-feature switches and use them only when they preserve required behavior; do not replace a required real boundary with a mock. If facts remain missing or contradictory after the relevant read-only checks, ask only for the unresolved target/isolation/authority, citing checked sources and known non-secret facts. Pause the affected operation, continue safe independent checks, and record substantive BLOCKED only when no safe in-scope path remains. Apply this discovery-first rule to recovery from a host refusal as well; existing refusals and their reconsideration limits remain binding.

Before startup, resolve the application's effective configuration, including overrides, defaults and startup hooks, and verify non-production identity, access scope and isolation. Check automatic initialization, migrations and background jobs before launching any process, not only before HTTP requests; disable optional jobs through existing supported configuration or ensure their effects fit the approved test scope. Use launch-time environment/configuration overrides rather than changing production defaults. A configured hostname or a variable named TEST alone is not proof of isolation. Prevent automatic fallback to an unverified Mongo or other remote dependency; if an unused dependency is unavoidable at startup, configure an approved test instance or an existing supported test-only seam without changing the boundary under test. Do not launch or send requests while dependency identity is unverified.

Workflow permission never supplies sandbox or network permission. On the first sandbox denial of scoped loopback startup or approved test-dependency access, request the host's permitted escalation and retry once if granted; do not mark the first denial terminal or ask again for already-confirmed business permission. A rejected escalation, unavailable escalation mechanism or failed authorized retry may become an evidenced environment BLOCKED. Do not bypass host refusals; preserve the exact cause and safe resume condition.

Read and enforce [the frozen worktree review contract](review-contract.md). Review the complete filtered frozen worktree with independent exploration; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

Requirement brainstorming and the final requirement authorization are the other normal human decision points. That authorization binds the requirement revision/digest, scope, non-goals, success boundary, target milestones, and permission for downstream Flow stages to make implementation decisions and continue autonomously.

After authorization, interrupt the human only for a decision or authority that cannot be safely derived within that binding: changing product scope or success criteria; production/customer-data or irreversible action; credentials or sandbox authority; conflicting authoritative inputs; or a high-risk blocker that cannot be resolved safely. Reviews, artifact handoffs, milestone traversal, recoverable validation failures, and non-production governed tests are not human gates.

## Necessary configuration and optional behavior

This is Agent judgment for scope, design and review, not an admission/controller prerequisite or a new approval gate. Default to directly delivering confirmed behavior rather than adding variability for future flexibility. Judge new optional behavior branches by effect, whether controlled by configuration, environment variables or API parameters; normal business inputs and fixed implementation constants are not automatically operational configuration. Preserve necessary connection, credential, test-isolation and safety controls.

For a proposed new switch or mode, briefly explain in the existing scope/design rationale its current actor/scenario or concrete safety need, why changing behavior is needed now, why the smallest direct alternative or existing rollout/operations mechanism is insufficient, and the default behavior plus risk-weighted verification and maintenance cost. These are judgment dimensions, not mandatory fields, exact metrics, a new receipt or a platformization test for every switch. A single user's genuine safety need can justify a control; hypothetical future users or "safer to make it configurable" cannot.

Verify only the actual mechanism's relevant states, missing/invalid values, effective switching time and important interactions; do not demand hot switching or exhaustive combinations. Disabling future effects, reverting a version and recovering affected data are different controls. A default-off rollout must make clear which approved delivery phase produces value and how it will be accepted. For temporary switches, state the removal trigger, owner role and whether removal belongs to this task or later maintenance; a recorded trigger does not authorize future deletion.

Carry the decision through Spec behavior/defaults, Plan tasks/checks and the coder's task packet, including an explicit no-new-switch boundary when none is needed. Coder reports a newly necessary branch to the root instead of silently adding it; the root makes bounded technical decisions and updates/reviews the affected Spec/Plan as needed. Only material product/success/authority/risk changes need human involvement. Direct-stage entry uses its available authorized task boundary; absent historical configuration records are not a gate. Reviewers check necessity and delivery against this same principle, without reopening a settled decision absent new evidence.

## Relationship to AGENTS.md

Flow remains complete when no `AGENTS.md` exists. Applicable `AGENTS.md` files may choose output locations and impose stricter safety constraints, repository commands, protected paths, or external-operation boundaries. They must not add duplicate Flow gates merely because Flow already performs issue admission, worktree management, artifact approval, review, or stage orchestration. When a higher-priority runtime instruction explicitly conflicts, obey it and report the incompatibility rather than silently weakening either rule.
