# AI-Native Coding Skills

A collection of shared skills for Claude Code and Codex, focused on consistent, high-quality software development workflows.

English | [简体中文](./README.zh.md)

## Skills

| Skill | Description |
|-------|-------------|
| [git-commit-convention](./skills/git-commit-convention/) | Enforces a structured Chinese commit format: `prefix(ISSUE): summary` on the first line, typed body entries (`feat1:`, `fix1:`, ...), and strict file-scope rules |
| [coding-guidelines](./skills/coding-guidelines/) | Coding principles for simple, surgical, evidence-driven implementation, including reliability, module boundaries, and complete migrations |
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

All eight skills are available immediately across every project. The three AI-native workflow skills activate only when explicitly invoked.

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

### coding-guidelines

Six principles to reduce common LLM coding mistakes:

| Principle | Addresses |
|-----------|-----------|
| **Think Before Coding** | Wrong assumptions, hidden confusion, missing tradeoffs |
| **Simplicity First** | Overcomplication, bloated abstractions, speculative features |
| **Surgical Changes** | Orthogonal edits, touching code outside the task scope |
| **Goal-Driven Execution** | Verifiable success criteria, test-first loops |
| **Evidence-Driven Abstraction** | Framework-like layers without current consumers or variation |
| **Module Boundaries and Migrations** | Coordinators absorbing subsystem behavior, loose cross-module contracts, and half-finished migrations |
| **Reliability Boundaries** | Untrusted input, executable interfaces, resources, privacy, and concurrency risks |

## Requirements

- [Claude Code](https://claude.ai/code) with plugin support

## License

MIT
