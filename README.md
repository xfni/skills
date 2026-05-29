# Claude Code Skills

A collection of Claude Code skills for consistent, high-quality software development workflows.

English | [简体中文](./README.zh.md)

## Skills

| Skill | Description |
|-------|-------------|
| [git-commit-convention](./git-commit-convention/) | Enforces a structured Chinese commit format: `prefix(ISSUE): summary` on the first line, typed body entries (`feat1:`, `fix1:`, ...), and strict file-scope rules |
| [init-claude](./init-claude/) | Bootstraps Claude configuration for a new project — generates `CLAUDE.md`, merges a low-risk command allowlist into `settings.json`, and installs `git-commit-convention` locally |
| [coding-hard-constraints](./coding-hard-constraints/) | Structural coding rules: Yoda conditions, defensive access, early returns, strong typing, function complexity limits, security boundaries, and concurrency safety |
| [coding-observability-errors](./coding-observability-errors/) | Logging and exception governance: entry/exit tracing, structured error codes, resource cleanup, timeout requirements, and error propagation strategy |
| [karpathy-guidelines](./karpathy-guidelines/) | Behavioral guidelines derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876): Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution |

## Install

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

All five skills are available immediately across every project.

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

### karpathy-guidelines

Four principles to reduce common LLM coding mistakes:

| Principle | Addresses |
|-----------|-----------|
| **Think Before Coding** | Wrong assumptions, hidden confusion, missing tradeoffs |
| **Simplicity First** | Overcomplication, bloated abstractions, speculative features |
| **Surgical Changes** | Orthogonal edits, touching code outside the task scope |
| **Goal-Driven Execution** | Verifiable success criteria, test-first loops |

## Requirements

- [Claude Code](https://claude.ai/code) with plugin support

## License

MIT
