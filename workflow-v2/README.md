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
| `flow-spec` | Observable behavioral rules for that milestone | GPT → Cursor review, then orchestrated approval. |
| `flow-plan` | File-level executable tasks and verification contract | GPT → Cursor review, then orchestrated approval. |
| `flow-code` | TDD implementation and unit/regression evidence | No integration claim; blocking findings stop completion. |
| `flow-integration` | Cross-component and end-to-end validation | Missing environment or authority is reported as blocked. |

Integration runs the frozen worktree application as a temporary local system under test, sends real protocol requests, and records lifecycle and observation evidence. Supporting middleware may use authorized isolated test-environment dependencies and need not be started in local Docker; local containers are fallback or scenario-specific infrastructure. A remote deployment of the application is allowed only for explicitly authorized deployment behavior; an outdated remote deployment never replaces the required local attempt.

`flow-spec`, `flow-plan`, and `flow-code` use a GPT → Cursor review gate. The root selects either `gpt-5.6-sol`/`high` or `gpt-6-astra`/`medium` by requirement difficulty; after GPT passes, `$cursor-review` performs the final review. A revision caused by Cursor restarts the full gate. A Cursor runtime failure is retried exactly once; a second runtime failure may continue only as `APPROVED_WITH_DEFECT` or `COMPLETE_WITH_DEFECT`, with a durable `CURSOR_REVIEW_GAP` propagated and shown to the human. Invoking one of these three stages authorizes sending only its necessary in-scope code and documents to Cursor; secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content remain excluded.

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

Restart Codex after installing or changing custom Agent TOMLs. The workflow requires `cursor-review` for Spec, Plan, and Code final review, and assumes `pms-issue-reader`, `grilling`, `test-driven-development`, `coding-guidelines`, and `independent-review` where stated; each skill defines its fallback or blocking behavior.

All normal command results are JSON. Typical orchestration is `flowctl init`, `flowctl resume`, stage work, `flowctl artifact register`, review commands where required, and `flowctl handoff accept`. Always use the latest returned `state_revision` as the next mutation's `--expected-revision`.

## Validation

From the repository worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
```
