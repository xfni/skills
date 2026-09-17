# AI-Native Flow V2

An explicit-only, self-contained workflow with one continuous orchestrator and eight bounded stages. Flow itself owns issue admission, worktree isolation, artifact bindings, and orchestration; it remains complete without `AGENTS.md`.

```text
$flow-run          -> choose an initial entry / resume recorded position and orchestrate the flow
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

Agent leads the workflow; flowctl checks and records only deterministic facts for the requested action. Registration does not move stages or delete downstream history; resume preserves position. Historical real guarantees may support an unchanged implementation through an optional caller-attested disposition, never by rewriting PASS. Tool uncertainty returns to the Agent for diagnosis, not an automatic human unlock. See [cooperation commands and guarantee limits](flowctl-contract.md).

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

## Review and replay lifecycle

Read and enforce [the frozen worktree review contract](review-contract.md). Review the complete filtered frozen worktree with independent exploration; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

The production-data decision reaches Integration by controller authorization ID/revision. `LOCAL_PRODUCTION_REPLAY` uses existing project runners for local tests without sanitizer/profile/manifest prerequisites. Flow does not own business-data sanitization; project policy remains authoritative. `SKIP_PRODUCTION_REPLAY` executes unaffected scenarios and records gaps. Resume reuses active scope, preserving historical decisions without inventing sanitization evidence.

Direct Spec/Plan/Code invocation uses the same frozen-worktree review policy without a human external-review gate. Direct Integration obtains only the minimal production_replay decision if its confirmed charter needs production-derived data; it never grants authority to another stage.

Integration runs the frozen worktree application as a temporary local system under test, sends real protocol requests, and records lifecycle and observation evidence. Supporting middleware may use authorized isolated test-environment dependencies and need not be started in local Docker; local containers are fallback or scenario-specific infrastructure. A remote deployment of the application is allowed only for explicitly authorized deployment behavior; an outdated remote deployment never replaces the required local attempt.

`flow-spec`, `flow-plan`, and `flow-code` use independently owned GPT and external review lanes. The selected GPT rechecks GPT findings; Cursor rechecks Cursor findings. A Cursor runtime or transport-protocol failure is retried once, then `$ibrain-review`/`glm-5.3` substitutes and likewise owns its findings. Unknown vendor errors are classified from observable process facts rather than quota/error-text guesses; conflicting review signals still fail closed. A fresh `gpt-6-astra`/`medium` performs final consistency review after lane convergence. If both external backends are unavailable, consistency must still pass and completion is marked with durable `EXTERNAL_REVIEW_GAP`. A stage binds a complete filtered view for independent exploration and excludes sensitive/runtime inputs. Explicit Flow/Cursor invocation establishes review scope; iBrain organization trust is independent of Cursor authorization. Neither grants production replay authority.

`intent.md` is authoritative for product scope. `requirement.md` remains the evidence and alternatives record. Later stages use available authorized context and actual controller receipts, not duplicate model-authored exact tuples. Explicit arbitrary-node entry may begin from an existing Spec or Plan without reconstructing historical stages; missing history is disclosed and current reviews still run.

The controller enforces the minimum next-step conditions: current identity/output, actual terminal review receipts and execution safety. It computes hashes, revisions, retry counters and test totals itself. Auxiliary fields, formatting differences, historical annotations and explanatory prose do not block progression. Two **or more** eligible runtime failures satisfy a two-failure threshold. `flowctl status` does not audit the entire history; use optional `flowctl audit` or strict `artifact verify` for diagnostics. A controller/bridge defect is a tool error to repair, not an automatic business BLOCKED or human unlock gate.

Every stage must read and follow [`flow-contract.md`](flow-contract.md), [`artifact-contract.md`](artifact-contract.md), and [`flowctl-contract.md`](flowctl-contract.md). `flowctl` is the only writer of controller/event state and the only component allowed to accept a checkpoint, review binding, retry/degradation, or successful handoff. Flow admission obtains a human-provided issue and creates or reuses the isolated worktree before artifact discovery; every stage revalidates that binding through `flowctl status`. `AGENTS.md` may add stricter project safety and output rules but is not required for Flow correctness and must not duplicate Flow gates.

## Codex setup

Production-data policy migration: existing `SANITIZED_LOCAL_REPLAY` decisions and old adapter bindings stay as historical records, not sanitization/deletion proof. Reuse their scoped local-use authority without broadening a narrower human/project instruction. Adapter-only pauses can be resumed with a bound signal after checking actual safety obstacles; do not rewrite controller history. `flowctl replay validate/run/cleanup` and production manifest validation are retired. Existing project runners provide real execution evidence; only temporary-service and test-side-effect cleanup is part of Flow completion.

Explicit `$flow-run` invocation requests creation/reuse of a matching runtime Goal through the host's real tools; no separate `/goal` is needed when those tools are available. Unrelated unfinished Goals and host pause/budget limits are never overridden. `flowctl goal record` persists observed recovery context only, not runtime activation or Flow approval. Without Goal tools, the same-turn controller loop remains usable, but durable continuation is not claimed.

Install the nine directories under `skills/` into `~/.codex/skills/`. Also copy `flowctl.py`, `flowctl_lib/`, and `schemas/` together to `~/.codex/flow-v2/`; skills resolve that packaged executable when they are not running from this repository. Invoke `$flow-run` for continuous orchestration or an individual stage for direct control. `flow-requirement` requires `flow-brainstorm` and also needs its two custom Agent TOMLs copied from `skills/flow-requirement/agents/` into `~/.codex/agents/`:

```text
flow-requirement-value.toml
flow-requirement-risk.toml
flow-coder.toml
```

Copy `skills/flow-code/agents/flow-coder.toml` to `~/.codex/agents/flow-coder.toml`. The coder is created lazily only after an approved Plan reaches `flow-code`, then the same session-scoped thread is reused for sequential `TASK-*` work; it is not started when a Codex session opens.

Restart Codex after installing or changing custom Agent TOMLs. Spec, Plan, and Code use `cursor-review` by default, with `ibrain-review`/`glm-5.3` as the runtime backup or explicitly human-selected external lane, plus `independent-review` and the final Astra consistency review. Record a direct iBrain choice through `flowctl review select-external`; no Cursor attempt is required on that route. Other stages assume `pms-issue-reader`, `grilling`, `test-driven-development`, and `coding-guidelines` where stated; each skill defines its fallback or blocking behavior.

All normal command results are JSON. Typical orchestration is `flowctl init`, `flowctl resume`, stage work, `flowctl artifact register`, review commands where required, and `flowctl handoff accept`. Always use the latest returned `state_revision` as the next mutation's `--expected-revision`.

## Validation

From the repository worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
```
