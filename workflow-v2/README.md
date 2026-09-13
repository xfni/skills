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

`flow-spec`, `flow-plan`, and `flow-code` use a GPT → Cursor review gate. The root selects either `gpt-5.6-sol`/`high` or `gpt-6-astra`/`medium` by requirement difficulty; after GPT passes, `$cursor-review` performs the final review. A revision caused by Cursor restarts the full gate. A Cursor runtime failure is retried exactly once; a second runtime failure may continue only as `APPROVED_WITH_DEFECT` or `COMPLETE_WITH_DEFECT`, with a durable `CURSOR_REVIEW_GAP` propagated and shown to the human. Invoking one of these three stages authorizes sending only its necessary in-scope code and documents to Cursor; secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content remain excluded.

`intent.md` is authoritative for product scope. `requirement.md` remains the evidence and alternatives record. Roadmap reads both. Later stages consume exact approved revision tuples and return upstream instead of silently changing an earlier decision.

Every stage must read and follow [`flow-contract.md`](flow-contract.md) and [`artifact-contract.md`](artifact-contract.md). Flow admission obtains a human-provided issue and creates or reuses the isolated worktree before artifact discovery; every stage silently revalidates that binding. `AGENTS.md` may add stricter project safety and output rules but is not required for Flow correctness and must not duplicate Flow gates. A missing required dependency produces the stage's documented blocked status rather than silent substitution.

## Codex setup

Link the nine directories under `skills/` into `~/.codex/skills/`. Invoke `$flow-run` for continuous orchestration or an individual stage for direct control. `flow-requirement` requires `flow-brainstorm` and also needs its two custom Agent TOMLs copied from `skills/flow-requirement/agents/` into `~/.codex/agents/`:

```text
flow-requirement-value.toml
flow-requirement-risk.toml
```

Restart Codex after installing or changing custom Agent TOMLs. The workflow requires `cursor-review` for Spec, Plan, and Code final review, and assumes `pms-issue-reader`, `grilling`, `test-driven-development`, `coding-guidelines`, and `independent-review` where stated; each skill defines its fallback or blocking behavior.

## Validation

From the repository worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
```
