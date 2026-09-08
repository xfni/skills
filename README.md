# AI-Native Coding Skills

A collection of shared skills for Claude Code and Codex, focused on consistent, high-quality software development workflows.

English | [简体中文](./README.zh.md)

## Skills

| Skill | Description |
|-------|-------------|
| [git-commit-convention](./skills/git-commit-convention/) | Enforces a structured Chinese commit format: `prefix(ISSUE): summary` on the first line, typed body entries (`feat1:`, `fix1:`, ...), and strict file-scope rules |
| [init-claude](./skills/init-claude/) | Bootstraps Claude configuration for a new project — generates `CLAUDE.md`, merges a low-risk command allowlist into `settings.json`, and installs `git-commit-convention` locally |
| [coding-hard-constraints](./skills/coding-hard-constraints/) | Structural coding rules: Yoda conditions, defensive access, early returns, strong typing, function complexity limits, security boundaries, and concurrency safety |
| [coding-observability-errors](./skills/coding-observability-errors/) | Logging and exception governance: entry/exit tracing, structured error codes, resource cleanup, timeout requirements, and error propagation strategy |
| [coding-guidelines](./skills/coding-guidelines/) | Coding principles for simple, surgical, evidence-driven implementation that avoids speculative abstractions and premature platformization |
| [backend-module-discipline](./skills/backend-module-discipline/) | Backend architecture discipline: orchestration-only coordinators, subsystem facades, typed boundaries, enum-first state, symmetric-flow extraction, and completed migrations |
| [concurrent-design-review](./skills/concurrent-design-review/) | Independent two-perspective review for concurrent, lifecycle, and shared-state designs, including code-path reality and system failure modes |
| [requirements-to-roadmap](./skills/requirements-to-roadmap/) | Explicit-only workflow for investigating, discussing, stress-testing, and freezing a bounded requirement roadmap |
| [roadmap-to-spec-plan](./skills/roadmap-to-spec-plan/) | Explicit-only workflow for turning a confirmed roadmap into reviewed decision, specification, and executable plan artifacts |
| [spec-review-gate](./skills/spec-review-gate/) | Risk gate before planning that identifies concurrency and lifecycle designs and invokes the specialist review workflow |
| [spec-plan-to-code](./skills/spec-plan-to-code/) | Explicit-only workflow for implementing an approved plan with type-appropriate validation and evidence |

## Install in Claude Code

**Step 1 — Add this marketplace:**

```
/plugins add-marketplace github:xfni/skills
```

**Step 2 — Install the plugin:**

```
/plugins install nixiaofeng-skills@nixiaofeng-skills
```

**Step 3 — Initialize your project:**

```
/init-claude
```

All eleven skills are available immediately across every project. The three AI-native workflow skills activate only when explicitly invoked.

## Use in Codex

The same source files are packaged through `.codex-plugin/plugin.json`. Until this repository publishes a Codex marketplace entry, clone it and copy or link the desired directories from `skills/` into `~/.codex/skills/`. The three AI-native workflow skills remain explicit-only through their `agents/openai.yaml` metadata.

## Skill Overview

### git-commit-convention

Enforces a mandatory commit format before every `git commit`:

```
feat(BCS-448): redesign ask-user as three-channel architecture

feat1: split original single-channel ask-user into CLI, HTTP, and SDK entry points
fix1: fix HTTP channel returning 500 on empty request body
```

Rules enforced:
- Issue number required in the first line title
- At least one typed body entry (`feat1:`, `fix1:`, `refactor1:`, ...)
- Related docs under `.ai/` and `docs/` must be committed in the same batch
- Never commit mid-development; always ask the user first

### init-claude

One command to bootstrap any new project:

1. Asks: project-level or global scope?
2. Writes (or appends to) `CLAUDE.md` with commit and documentation conventions
3. Merges a curated low-risk command allowlist into `.claude/settings.json`
4. Copies `git-commit-convention` into the project's `.claude/skills/`

### coding-hard-constraints

Hard structural rules applied when writing, reviewing, or refactoring any code:

- **Yoda conditions** — constants on the left: `nil == err`, `None is value`
- **Defensive access** — no deep chaining; use optional chaining or null guards
- **Early returns** — guard clauses first, main logic stays at the leftmost indent
- **Strong typing** — no bare `dict`, `Map<String,Object>`, or `Record<string,any>` for business data
- **Complexity limits** — max 40 lines per function, 4 parameters, 3 nesting levels
- **Security boundaries** — parameterized queries only, input validation at system edges, no secrets in logs
- **Concurrency safety** — all shared mutable state must be explicitly protected

### coding-observability-errors

Logging and exception standards for service layer and external integrations:

- **Tracing** — entry (INFO), milestones (INFO), exit (INFO), debug details (DEBUG), expected errors (WARN), system failures (ERROR)
- **Comments** — explain *why*, not *what*; public functions require a standard docstring
- **Exception governance** — no empty catch blocks; exceptions map to standard `Code + Message`; resources must use `try-with-resources` / `with` / `defer`
- **Error propagation** — recoverable errors return result codes; unrecoverable errors propagate upward
- **Timeouts** — every cross-service call must set an explicit timeout (≥ P99 baseline)

### coding-guidelines

Five principles to reduce common LLM coding mistakes:

| Principle | Addresses |
|-----------|-----------|
| **Think Before Coding** | Wrong assumptions, hidden confusion, missing tradeoffs |
| **Simplicity First** | Overcomplication, bloated abstractions, speculative features |
| **Surgical Changes** | Orthogonal edits, touching code outside the task scope |
| **Goal-Driven Execution** | Verifiable success criteria, test-first loops |
| **Evidence-Driven Abstraction** | Framework-like layers without current consumers or variation |

## Requirements

- [Claude Code](https://claude.ai/code) with plugin support

## License

MIT
