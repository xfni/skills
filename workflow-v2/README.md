# AI-Native Flow V2

The public development skills are now `dev-*`. Start with `$dev-run`; old `flow-*` skill aliases are not installed. The package directory, `flowctl` executable, internal `flow-*` stage IDs and existing controller/artifact formats remain unchanged. See the [skill-to-stage mapping](flowctl-contract.md#public-skills-and-stable-controller-stages) before constructing CLI or handoff inputs. Resume existing issues with `$dev-run` without rewriting their state or restarting a healthy coder thread.

An explicit-only, self-contained workflow with one continuous orchestrator and eight bounded stages. Flow itself owns issue admission, worktree isolation, artifact bindings, and orchestration; it remains complete without `AGENTS.md`.

```text
$dev-run          -> choose an initial entry / resume recorded position and orchestrate the flow
$dev-brainstorm   -> confirmed human brainstorming result
$dev-requirement  -> requirement.md
$dev-intent       -> intent.md
$dev-roadmap      -> roadmap.md
$dev-spec         -> spec.md for one milestone
$dev-plan         -> plan.md
$dev-code         -> code + unit-test evidence
$dev-integration  -> integration evidence
```

## Stage boundaries

Agent leads the workflow; flowctl checks and records only deterministic facts for the requested action. Registration does not move stages or delete downstream history; resume preserves position. Historical real guarantees may support an unchanged implementation through an optional caller-attested disposition, never by rewriting PASS. Tool uncertainty returns to the Agent for diagnosis, not an automatic human unlock. See [cooperation commands and guarantee limits](flowctl-contract.md).

| Skill | Responsibility | Human gate |
| --- | --- | --- |
| `dev-run` | Issue/worktree admission, starting-stage detection, verified handoffs, pause/resume, and failure routing | Requests missing admission or genuinely necessary authority only. |
| `dev-brainstorm` | Human exploration and option comparison | Human confirms the discussion summary, not final intent. |
| `dev-requirement` | Inherit human discussion; moderator-led, two-view exploration and boundary challenges over 3–12 rounds | Reuse confirmed brainstorming records; human resolves remaining product choices and authorizes the final Requirement once. |
| `dev-intent` | Normalize the authorized Requirement into authoritative intent | Autonomous under `dev-run`; unresolved product choices route back. |
| `dev-roadmap` | Milestones, dependencies, and acceptance direction | Autonomous under `dev-run`; milestones are selected deterministically. |
| `dev-spec` | Observable behavioral rules for that milestone | Standard GPT + external; permitted single independent chain with a gap. |
| `dev-plan` | File-level executable tasks and verification contract | Standard GPT + external; permitted single independent chain with a gap. |
| `dev-code` | TDD implementation and unit/regression evidence | No integration claim; blocking findings stop completion. |
| `dev-integration` | Cross-component and end-to-end validation | Missing environment or authority is reported as blocked. |

## Review and replay lifecycle

Read and enforce [the frozen worktree review contract](review-contract.md). Review the complete filtered frozen worktree with independent exploration; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

The production-data decision reaches Integration by controller authorization ID/revision. `LOCAL_PRODUCTION_REPLAY` uses existing project runners for local tests without sanitizer/profile/manifest prerequisites. Flow does not own business-data sanitization; project policy remains authoritative. `SKIP_PRODUCTION_REPLAY` executes unaffected scenarios and records gaps. Resume reuses active scope, preserving historical decisions without inventing sanitization evidence.

Direct Spec/Plan/Code invocation uses the same frozen-worktree review policy without a human external-review gate. Direct Integration obtains only the minimal production_replay decision if its confirmed charter needs production-derived data; it never grants authority to another stage.

Integration runs the frozen worktree application as a temporary local system under test, sends real protocol requests, and records lifecycle and observation evidence. Supporting middleware may use authorized isolated test-environment dependencies and need not be started in local Docker; local containers are fallback or scenario-specific infrastructure. A remote deployment of the application is allowed only for explicitly authorized deployment behavior; an outdated remote deployment never replaces the required local attempt.

Spec, Plan and Code prefer GPT (Sol/high or Astra/medium) + one external independent review chain (Cursor or iBrain). Actual unavailability or explicit human route limits permit at least one effective independent chain, with 有条件通过 and a recorded missing-lane gap. No mandatory third Astra consistency or failure quota. Known findings survive versions and route changes; an available independent reviewer may take over and explicitly verify repairs. Tests and author self-review do not replace independent review. Frozen views, data exclusions and host boundaries remain enforced.

`intent.md` is authoritative for product scope. `requirement.md` remains the evidence and alternatives record. Later stages use available authorized context and actual controller receipts, not duplicate model-authored exact tuples. Explicit arbitrary-node entry may begin from an existing Spec or Plan without reconstructing historical stages; missing history is disclosed and current reviews still run.

New optional behavior/configuration is justified by current value or concrete safety needs, not future flexibility. The decision flows through Spec, Plan and coder TASK packets with risk-weighted testing and maintenance cost; it adds no controller fields or human gates. Every substantive Requirement discussion exit presents a complete Decision Brief, including scope/non-goals, recommendation versus human decisions, tradeoffs, important residual risks and next action—not only a conflict menu. Existing final authorization remains the only scope-confirmation gate.

The controller enforces the minimum next-step conditions: current identity/output, actual terminal review receipts and execution safety. It computes hashes, revisions, retry counters and test totals itself. Auxiliary fields, formatting differences, historical annotations and explanatory prose do not block progression. Two **or more** eligible runtime failures satisfy a two-failure threshold. `flowctl status` does not audit the entire history; use optional `flowctl audit` or strict `artifact verify` for diagnostics. A controller/bridge defect is a tool error to repair, not an automatic business BLOCKED or human unlock gate.

Every stage must read and follow [`flow-contract.md`](flow-contract.md), [`artifact-contract.md`](artifact-contract.md), and [`flowctl-contract.md`](flowctl-contract.md). `flowctl` is the only writer of controller/event state and the only component allowed to accept a checkpoint, review binding, retry/degradation, or successful handoff. Flow admission obtains a human-provided issue and creates or reuses the isolated worktree before artifact discovery; every stage revalidates that binding through `flowctl status`. `AGENTS.md` may add stricter project safety and output rules but is not required for Flow correctness and must not duplicate Flow gates.

## Codex setup

Production-data policy migration: existing `SANITIZED_LOCAL_REPLAY` decisions and old adapter bindings stay as historical records, not sanitization/deletion proof. Reuse their scoped local-use authority without broadening a narrower human/project instruction. Adapter-only pauses can be resumed with a bound signal after checking actual safety obstacles; do not rewrite controller history. `flowctl replay validate/run/cleanup` and production manifest validation are retired. Existing project runners provide real execution evidence. Integration retains business writes made through real requests in the named test environment; automatic cleanup is limited to run-owned services/processes, ports, locks, and transient non-evidence files unless a human or applicable project rule explicitly requires more.

Explicit `$dev-run` invocation requests creation/reuse of a matching runtime Goal through the host's real tools; no separate `/goal` is needed when those tools are available. Unrelated unfinished Goals are never replaced without explicit human direction; host pause/budget limits remain binding. `flowctl goal record` persists observed recovery context only, not runtime activation or Flow approval. Without Goal tools, the same-turn controller loop remains usable, but durable continuation is not claimed.

For a real Goal/task conflict, Flow explains the old/new tasks and asks for direction once; an explicit replacement instruction already supplies it. Automatic replacement requires an actually available host-permitted capability. Otherwise the same message supplies `/goal clear` for the current conversation, followed by continuation of the chosen task; Flow verifies an empty Goal before creating the new one. Timeout/error requires readback, not blind clearing. Old work stays unfinished and preserved, scope/permissions are not inherited, and replacement does not waive budgets or host restrictions. Same-task recovery does not normally require clearing.

Install the nine directories under `skills/` into `~/.codex/skills/`. Also copy `flowctl.py`, `flowctl_lib/`, and `schemas/` together to `~/.codex/flow-v2/`; skills resolve that packaged executable when they are not running from this repository. Invoke `$dev-run` for continuous orchestration or an individual stage for direct control. `dev-requirement` requires `dev-brainstorm` and also needs its two custom Agent TOMLs copied from `skills/dev-requirement/agents/` into `~/.codex/agents/`:

```text
dev-requirement-value.toml
dev-requirement-risk.toml
dev-coder.toml
```

Copy `skills/dev-code/agents/dev-coder.toml` to `~/.codex/agents/dev-coder.toml`. The coder is created lazily only after an approved Plan reaches `dev-code`, then the same session-scoped thread is reused for sequential `TASK-*` work; it is not started when a Codex session opens.

Copy the shared `*-contract.md` files to `~/.codex/flow-v2/` as well. In the separately installed skill entry copies, rewrite `../../<contract>.md` to `../../flow-v2/<contract>.md`; keep repository and packaged `flow-v2/skills/` copies unchanged. Move previous `flow-*` skill directories and the three old role TOMLs outside Codex's discoverable skill/agent directories after validating the new installation. Update any global workflow routing trigger from `$flow-run` to `$dev-run`, preserving stricter safety rules and unrelated instructions.

For bounded same-turn continuation, deploy `continuation_hook.py` and `scripts/install_codex_hooks.py` with the same package, then run the installed `install_codex_hooks.py --codex-home <resolved-home>`. The installer merges owned `UserPromptSubmit` and root `Stop` handlers without replacing other hooks. Start a new Codex session, run `/hooks`, review the exact commands and trust them. Without installation or trust, dev-run keeps its ordinary same-turn loop and reports only a runtime capability gap; Flow is not business-blocked.

Restart Codex after updating custom Agent TOMLs. Review uses independent-review, cursor-review and ibrain-review as available under review-contract.md. Record human-selected iBrain with review select-external and route restrictions/unavailability with review degrade. Other stages retain their stated skill dependencies.

All normal command results are JSON. Typical orchestration is `flowctl init`, `flowctl resume`, stage work, `flowctl artifact register`, review commands where required, and `flowctl handoff accept`. Always use the latest returned `state_revision` as the next mutation's `--expected-revision`.

## Validation

From the repository worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v
```
