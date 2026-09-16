# AI-Native Flow V2

An explicit-only, self-contained workflow with one continuous orchestrator and eight bounded stages. Flow itself owns issue admission, worktree isolation, artifact bindings, and orchestration; it remains complete without `AGENTS.md`.

```text
$flow-run          -> detect/resume the deepest valid checkpoint and orchestrate the flow
$flow-brainstorm   -> confirmed human brainstorming result
$flow-requirement  -> requirement.md
$flow-intent       -> intent.md
$flow-roadmap      -> roadmap.md
$flow-spec         -> spec.md for one milestone
$flow-plan         -> plan.md
$flow-code         -> code + unit-test evidence
$flow-integration  -> integration evidence
```

## Stage boundaries

| Skill | Responsibility | Human gate |
| --- | --- | --- |
| `flow-run` | Issue/worktree admission, starting-stage detection, verified handoffs, pause/resume, and failure routing | Requests missing admission or genuinely necessary authority only. |
| `flow-brainstorm` | Human exploration and option comparison | Human confirms the discussion summary, not final intent. |
| `flow-requirement` | Two-role autonomous agent swarm and final product boundary | Human authorizes the final Requirement once. |
| `flow-intent` | Normalize the authorized Requirement into authoritative intent | Autonomous under `flow-run`; unresolved product choices route back. |
| `flow-roadmap` | Milestones, dependencies, and acceptance direction | Autonomous under `flow-run`; milestones are selected deterministically. |
| `flow-spec` | Observable behavioral rules for that milestone | Independent GPT and external lanes, then Astra consistency review. |
| `flow-plan` | File-level executable tasks and verification contract | Independent GPT and external lanes, then Astra consistency review. |
| `flow-code` | TDD implementation and unit/regression evidence | No integration claim; blocking findings stop completion. |
| `flow-integration` | Cross-component and end-to-end validation | Missing environment or authority is reported as blocked. |

## Run authorization lifecycle

Requirement discussion remains the normal human product gate: brainstorming and final Requirement authorization establish what Flow may build. They do not authorize external transmission or production-derived replay. After admission and before Requirement work, `$flow-run` presents one consolidated run authorization gate containing separate `external_review` and `production_replay` decisions. Flowctl records each decision with a controller-generated authorization ID and revision; prompt wording and natural-language assent are not authority.

Spec, Plan, and Code consume the same active `external_review` authorization ID and revision. Every outbound review, revision, retry, and backend attempt still gets a fresh controller-validated, single-use operation manifest. A retry and iBrain fallback do not create another human gate: fallback keeps the same authorization revision and artifact snapshot but uses a new `backend=ibrain` manifest rather than the Cursor binding. A denied decision pauses once at the first required operation. A changed scope or decision uses `flowctl authorization amend`; no stage may broaden or reinterpret the stored decision.

The production replay decision reaches Integration as its controller authorization ID/revision. `SANITIZED_LOCAL_REPLAY` still requires a validated Plan-pinned replay manifest before acquisition, while `SKIP_PRODUCTION_REPLAY` executes unaffected scenarios and records authorized gaps. Resume reuses active decisions without prompting when identity and scope still match.

Direct invocation does not manufacture run-wide authority. When a required decision is absent, Spec, Plan, or Code presents one minimal stage-bound authorization gate and persists `allowed_stages` containing only its own stage; Integration requests only its replay decision when needed. Each operation manifest must match the persisted stage set. Expanding or changing that set uses amendment and invalidates the prior binding; the decision must not imply authority for another stage.

Integration runs the frozen worktree application as a temporary local system under test, sends real protocol requests, and records lifecycle and observation evidence. Supporting middleware may use authorized isolated test-environment dependencies and need not be started in local Docker; local containers are fallback or scenario-specific infrastructure. A remote deployment of the application is allowed only for explicitly authorized deployment behavior; an outdated remote deployment never replaces the required local attempt.

`flow-spec`, `flow-plan`, and `flow-code` use independently owned GPT and external review lanes. The selected GPT rechecks GPT findings; Cursor rechecks Cursor findings. A Cursor runtime or transport-protocol failure is retried once, then `$ibrain-review`/`glm-5.3` substitutes and likewise owns its findings. Unknown vendor errors are classified from observable process facts rather than quota/error-text guesses; conflicting review signals still fail closed. A fresh `gpt-6-astra`/`medium` performs final consistency review after lane convergence. If both external backends are unavailable, consistency must still pass and completion is marked with durable `EXTERNAL_REVIEW_GAP`. A stage consumes controller authority for necessary in-scope review material and excludes secrets and unrelated content; invoking a skill is not itself authorization.

`intent.md` is authoritative for product scope. `requirement.md` remains the evidence and alternatives record. Roadmap reads both. Later stages consume exact approved revision tuples and return upstream instead of silently changing an earlier decision.

Every stage must read and follow [`flow-contract.md`](flow-contract.md), [`artifact-contract.md`](artifact-contract.md), and [`flowctl-contract.md`](flowctl-contract.md). `flowctl` is the only writer of controller/event state and the only component allowed to accept a checkpoint, review binding, retry/degradation, or successful handoff. Flow admission obtains a human-provided issue and creates or reuses the isolated worktree before artifact discovery; every stage revalidates that binding through `flowctl status`. `AGENTS.md` may add stricter project safety and output rules but is not required for Flow correctness and must not duplicate Flow gates.

## Codex setup

Install the nine directories under `skills/` into `~/.codex/skills/`. Also copy `flowctl.py`, `flowctl_lib/`, and `schemas/` together to `~/.codex/flow-v2/`; skills resolve that packaged executable when they are not running from this repository. Invoke `$flow-run` for continuous orchestration or an individual stage for direct control. `flow-requirement` requires `flow-brainstorm` and also needs its two custom Agent TOMLs copied from `skills/flow-requirement/agents/` into `~/.codex/agents/`:

```text
flow-requirement-value.toml
flow-requirement-risk.toml
flow-coder.toml
```

Copy `skills/flow-code/agents/flow-coder.toml` to `~/.codex/agents/flow-coder.toml`. The coder is created lazily only after an approved Plan reaches `flow-code`, then the same session-scoped thread is reused for sequential `TASK-*` work; it is not started when a Codex session opens.

Restart Codex after installing or changing custom Agent TOMLs. Spec, Plan, and Code require `cursor-review`, with `ibrain-review`/`glm-5.3` as its controller-selected runtime backup, plus `independent-review` and the final Astra consistency review. Other stages assume `pms-issue-reader`, `grilling`, `test-driven-development`, and `coding-guidelines` where stated; each skill defines its fallback or blocking behavior.

All normal command results are JSON. Typical orchestration is `flowctl init`, `flowctl resume`, stage work, `flowctl artifact register`, review commands where required, and `flowctl handoff accept`. Always use the latest returned `state_revision` as the next mutation's `--expected-revision`.

## Validation

From the repository worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
```
