# Flow v2 Admission Contract

This contract is part of Flow v2 and does not depend on `AGENTS.md`. `$flow-run` and every directly invoked Flow stage must read and enforce it before reading or writing Flow artifacts.

## Issue identity

- Feature work requires a human-provided issue ID. The agent must not infer or invent it from a branch, path, repository, artifact, PMS result, or goal.
- `$flow-run` owns Flow admission. When the current conversation and a verified controller contain no human-provided issue ID, request it exactly once and stop. Record its human provenance in the controller.
- Every stage must verify silently that its input artifacts, controller, branch, and worktree carry that same issue ID. A valid inherited binding must not cause another prompt. A conflict returns `FLOW_ADMISSION_BLOCKED`; absence under direct invocation returns `FLOW_ADMISSION_GATE` for an issue ID.

## Controller and worktree admission

After accepting the issue and before artifact discovery, initialize the controller and create or reuse the matching independent Git worktree from local `master`:

```text
branch: feature-<issue>-<short-kebab-description>
path: <repository-parent>/feature-<issue>-<short-kebab-description>
```

The issue component is canonical and the description is concise, lowercase kebab-case. Reuse an existing worktree only after verifying its repository, branch, HEAD ancestry, issue binding, and absence of a conflicting controller. Never overwrite or repurpose an unrelated worktree or branch.

If the new path is outside the current Codex writable roots, report its absolute path and current session ID, provide a fully substituted `codex resume <session-id> --add-dir <absolute-worktree-path>` command, persist `FLOW_ADMISSION_GATE`, and wait for the resumed session. If the session ID cannot be determined, return `FLOW_ADMISSION_BLOCKED`; do not continue in the original checkout.

Every stage, including direct invocation, must verify silently before work that the current repository, worktree path, branch, controller, and issue binding match. A valid controller means a stage must not ask for the issue ID again, must not recreate the worktree, and must not ask the human to select it. Safe deterministic metadata repair is allowed and recorded; ambiguity, dirty conflicting state, or an incorrect worktree returns `FLOW_ADMISSION_BLOCKED` with evidence and a precise recovery condition.

Direct invocation performs this same admission when no controller exists. It may request the missing issue, initialize the controller, and create or reuse the worktree, but it may not weaken the contract.

## Human interaction boundary

After controller and worktree admission and before requirement work, `$flow-run` presents only the production_replay human decision for sanitized local production replay. External review is not an authorization gate. Replay decisions persist through controller-generated authorization IDs. Resume reuses an active ID while operation manifests remain inside its recorded scope; natural-language assent and stage-local phrases are not authorization. A changed decision follows the controller amendment transition instead of overwriting the prior record.

Read and enforce [the frozen worktree review contract](review-contract.md). Review the complete filtered frozen worktree with independent exploration; the root brief is not sole evidence. iBrain is organization-trusted; no external-review authorization gate. Reviewer returns stdout/API only and never writes worktree. Freeze by digest (no automatic commit); source/private snapshot verification and single-use package binding are controller-owned.

Requirement brainstorming and the final requirement authorization are the other normal human decision points. That authorization binds the requirement revision/digest, scope, non-goals, success boundary, target milestones, and permission for downstream Flow stages to make implementation decisions and continue autonomously.

After authorization, interrupt the human only for a decision or authority that cannot be safely derived within that binding: changing product scope or success criteria; production/customer-data or irreversible action; credentials or sandbox authority; conflicting authoritative inputs; or a high-risk blocker that cannot be resolved safely. Reviews, artifact handoffs, milestone traversal, recoverable validation failures, and non-production governed tests are not human gates.

## Relationship to AGENTS.md

Flow remains complete when no `AGENTS.md` exists. Applicable `AGENTS.md` files may choose output locations and impose stricter safety constraints, repository commands, protected paths, or external-operation boundaries. They must not add duplicate Flow gates merely because Flow already performs issue admission, worktree management, artifact approval, review, or stage orchestration. When a higher-priority runtime instruction explicitly conflicts, obey it and report the incompatibility rather than silently weakening either rule.
