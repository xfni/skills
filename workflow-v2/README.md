# AI-Native Flow V2

An explicit-only workflow with one continuous orchestrator and eight bounded stages. Each stage owns one artifact or evidence boundary and returns control at its boundary; `$flow-run` validates the handoff and continues after satisfied human gates.

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
| `flow-run` | Starting-stage detection, verified handoffs, pause/resume, and failure routing | Preserves the gate owned by each selected stage. |
| `flow-brainstorm` | Human exploration and option comparison | Human confirms the discussion summary, not final intent. |
| `flow-requirement` | Two-role autonomous agent swarm | Human brainstorming is frozen as input; uncertainty may remain. |
| `flow-intent` | Grilling-based reverse questioning | Human explicitly confirms the complete intent. |
| `flow-roadmap` | Milestones, dependencies, and acceptance direction | Human approves the roadmap and selects one milestone. |
| `flow-spec` | Observable behavioral rules for that milestone | Human approves the complete Spec revision. |
| `flow-plan` | File-level executable tasks and verification contract | Human approves the complete Plan revision. |
| `flow-code` | TDD implementation and unit/regression evidence | No integration claim; blocking findings stop completion. |
| `flow-integration` | Cross-component and end-to-end validation | Missing environment or authority is reported as blocked. |

`flow-spec`, `flow-plan`, and `flow-code` use a GPT → Cursor review gate. The root selects either `gpt-5.6-sol`/`high` or `gpt-6-astra`/`medium` by requirement difficulty; after GPT passes, `$cursor-review` performs the final review. A revision caused by Cursor restarts the full gate. A Cursor runtime failure is retried exactly once; a second runtime failure may continue only as `APPROVED_WITH_DEFECT` or `COMPLETE_WITH_DEFECT`, with a durable `CURSOR_REVIEW_GAP` propagated and shown to the human. Invoking one of these three stages authorizes sending only its necessary in-scope code and documents to Cursor; secrets, credentials, unnecessary personal data, secret-bearing generated files, and unrelated content remain excluded.

`intent.md` is authoritative for product scope. `requirement.md` remains the evidence and alternatives record. Roadmap reads both. Later stages consume exact approved revision tuples and return upstream instead of silently changing an earlier decision.

Every stage must read and follow [`artifact-contract.md`](artifact-contract.md). It defines non-self-referential SHA-256 body boundaries and byte canonicalization; approval envelopes bind the approved revision and digest without mutating the body. Follow the enclosing repository's feature-worktree rules before `flow-intent` writes confirmed feature artifacts. When the gate moves work into a new worktree, `flow-intent` re-homes and verifies the approved requirement before creating intent. A missing required dependency produces the stage's documented blocked status rather than silent substitution.

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
