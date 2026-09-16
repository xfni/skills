# AI-Native Coding Skills

A small, cross-runtime skill set for moving from a bounded requirement to verified code without turning agents into framework generators. It supports Claude Code, Codex, and an optional read-only Cursor review step.

English | [简体中文](./README.zh.md)

## Start here

Use the AI-native workflow only when you explicitly want its full decision and review trail:

```mermaid
flowchart LR
    D["direct discussion"] --> I["$requirement-to-intent"]
    RC["$requirement-council<br/>optional, Codex-only"] --> I
    Q["$requirement-clarification<br/>optional grilling"] --> I
    RC --> Q
    I -. human-confirmed intent.md .-> R["$intent-to-roadmap"]
    R --> S["$roadmap-to-spec-plan"] --> C["$spec-plan-to-code"]
    S -. selected review profile .-> I["$independent-review"]
    C -. selected review profile .-> I
    C --> CG["coding-guidelines"]
    S -. optional read-only final review .-> CU["Cursor"]
    C -. optional read-only final review .-> CU
```

`requirement-to-intent` is the common gate before roadmap. The human may choose Council, clarification, both, or direct discussion. Council writes a candidate `requirement.md`; clarification wraps `grilling` when available and records human decisions in that artifact; only the intent gate writes a human-confirmed `intent.md`.

After an issue key is provided, the intent gate reads PMS once and shares that immutable snapshot with the selected route. If sandboxed network access fails, it requests permission for one read-only escalated retry; denial or failure is recorded as `PMS_UNAVAILABLE` without exposing credentials.

All workflow skills are explicit-only. Optional requirement methods are orchestrated only when selected; downstream stages never start automatically.

## Skills and dependencies

| Skill | Use it for | Dependencies and handoff |
|---|---|---|
| [git-commit-convention](./skills/git-commit-convention/) | Keeping a local commit scoped, documented, and in the required Chinese commit format. | Independent. Requires a Git repository and an issue identifier for a commit. |
| [coding-guidelines](./skills/coding-guidelines/) | Writing or reviewing code without speculative abstractions, scope creep, unsafe boundaries, or half-finished migrations. | Baseline for implementation and review. **Required** by `spec-plan-to-code`. |
| [independent-review](./skills/independent-review/) | Shared evidence, scope, finding, and re-review standard for design, implementation, and concurrency profiles. | The caller selects the profile, `subagent` or `cursor` backend, model, and effort. It never makes those routing decisions. |
| [cursor-review](./skills/cursor-review/) | Bounded independent exploration of a filtered frozen worktree through Cursor SDK. | Explicit invocation, digest guards, custom read-only tools and stdout/API-only reports. |
| [requirement-council](./skills/requirement-council/) | Running a contextual agent-to-agent requirement discussion and presenting evidence-backed choices, risks, and missing facts. | **Optional, Codex-only** stage with the root plus two child roles. It writes candidate `requirement.md`; `$requirement-to-intent` owns the handoff. |
| [requirement-clarification](./skills/requirement-clarification/) | Aligning an existing `requirement.md` with the human through `grilling` or a built-in fallback. | Optional before intent. It updates the requirement revision but never creates intent or roadmap. |
| [requirement-to-intent](./skills/requirement-to-intent/) | Choosing a requirement path and producing the authoritative, human-confirmed `intent.md`. | Required gate before roadmap. It can orchestrate Council, clarification, both, or direct discussion. |
| [intent-to-roadmap](./skills/intent-to-roadmap/) | Turning a confirmed intent into a roadmap with `REQ-*`, `DEC-*`, `AC-*`, and Phase IDs. | Requires `intent.md` with `status: CONFIRMED`; it may not reinterpret intent scope, non-goals, or invariants. |
| [roadmap-to-spec-plan](./skills/roadmap-to-spec-plan/) | Turning one confirmed roadmap phase into a Decision Package, Spec, executable Plan, acceptance matrix, and review ledger. | **Requires** a confirmed roadmap/Phase ID. It calls `independent-review` with `design` or `concurrency` profiles and explicitly selects Astra or Cursor. Its approved artifacts are the input to `spec-plan-to-code`. |
| [spec-plan-to-code](./skills/spec-plan-to-code/) | Implementing an approved Decision Package, Spec, and Plan with change-type-appropriate tests, independent reviews, probes, runtime checks, and evidence. | **Requires** approved artifacts from `roadmap-to-spec-plan` and `coding-guidelines`. It calls `independent-review` with implementation/concurrency profiles and explicitly selects the reviewer backend, model, and effort. |

Dependency terms:

- **Requires**: do not begin without the listed input or skill.
- **Conditionally invoked**: use only when its trigger is present.
- **Optional**: improves coverage or interaction quality but has a stated fallback.

## Runtime requirements

| Runtime or capability | Needed for |
|---|---|
| [Claude Code](https://claude.ai/code) with plugin support | Installing this repository as a Claude Code plugin. |
| [Codex](https://openai.com/codex/) | Installing or linking selected directories into `~/.codex/skills/`. Explicit-only workflow metadata is included. |
| A controller-approved external-review backend | `$cursor-review` is optional and currently unavailable until Cursor can prove both disabled local tools and disabled implicit indexing. Flow may use its authorized runtime fallback. |
| `grilling` skill | Optional engine used by `requirement-clarification`; that skill provides a built-in fallback when it is absent. |
| `brainstorming` guidance | Optional source for richer alternative generation; Requirement Council includes the required comparison core and does not depend on it. |
| `pms-issue-reader` skill and PMS access | Used once by `requirement-to-intent` after issue validation; sandboxed environments may prompt for read-only network permission. |
| Configured reviewer models | The workflow references Astra and other independent-review models. Make equivalent authorized reviewer capacity available in the host runtime. |
| Requirement Council (Codex only) | Requires two custom Agent TOMLs installed globally. At each run, the moderator selects one offered model/effort profile and passes it at child creation; read-only behavior is protocol-constrained unless the host attests enforcement. |

Requirement Council defaults to a standard before/after repository snapshot and can use an audited mode on request. Where the host cannot attest read-only enforcement, results are protocol-constrained rather than treated as a failed discussion; a detected repository change ends the run.

## Install

### Claude Code

```text
/plugins add-marketplace github:xfni/skills
/plugins install nixiaofeng-skills@nixiaofeng-skills
```

### Codex

The repository exposes the shared `skills/` directory through `.codex-plugin/plugin.json`. Until a marketplace entry is available, clone this repository and copy or link the skills you want into `~/.codex/skills/`.

```bash
ln -s "$(pwd)/skills/intent-to-roadmap" ~/.codex/skills/intent-to-roadmap
```

Repeat for each desired skill. Keep the workflow skills explicit-only; invoke them by name, for example `$intent-to-roadmap`.

#### Requirement Council (personal Codex installation)

Requirement Council uses personal Codex Agents rather than project-scoped Agents. Complete both installation steps:

1. Copy or link `skills/requirement-council` to `~/.codex/skills/requirement-council`.
2. Copy both standalone Agent TOMLs from `skills/requirement-council/agents/` to `~/.codex/agents/`:
   - `requirement-council-value-boundary-explorer.toml`
   - `requirement-council-risk-counterexample-critic.toml`

For example, from the repository root:

```bash
mkdir -p ~/.codex/skills ~/.codex/agents
ln -s "$(pwd)/skills/requirement-council" ~/.codex/skills/requirement-council
cp skills/requirement-council/agents/requirement-council-value-boundary-explorer.toml ~/.codex/agents/requirement-council-value-boundary-explorer.toml
cp skills/requirement-council/agents/requirement-council-risk-counterexample-critic.toml ~/.codex/agents/requirement-council-risk-counterexample-critic.toml
```

Start a fresh Codex session after installing or updating the Agent TOMLs so personal-Agent discovery reloads them.

Invoke it explicitly with a feature topic. The root uses relevant prior conversation as the requirement context, so the invocation need not repeat the complete requirement:

```text
$requirement-council
Support agents need to save common filter combinations and reopen them later.
The initial idea is a personal saved-filter list; team sharing is not yet decided.
Existing permissions must continue to control which records are visible.
```

This Skill is intentionally absent from the Claude Code plugin. Its two child Agents are not installed globally through `.codex-plugin/plugin.json`; install them through the two personal Codex steps above. Council writes only a candidate `requirement.md`; use `$requirement-to-intent` for the explicit handoff into the workflow.

### Cursor review setup (optional)

`$cursor-review` uses a controller-bound schema-version-2 request, `--workspace` private filtered view and `--expected-request-digest`. Install cursor-sdk in `~/.codex/runtime/cursor-review` and store its key in `~/.cursor-review/API_KEY`. The controller executes pinned captured bytes in isolated Python and verifies original/private snapshots before accepting stdout/API reports. Only bounded custom list/read/search tools are available; no automatic commit or reviewer writes. Flow invocation needs no separate Cursor authorization; trusted iBrain needs none independently. Host permissions and production-replay authorization remain separate. See [review contract](workflow-v2/review-contract.md).

## License

MIT
