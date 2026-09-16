---
name: cursor-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through Cursor.
---

# Cursor Review

Own the Cursor connection, dependency diagnostics, and one bounded read-only review. The caller owns timing, profile, brief, finding disposition, and approval.

## Scope and credentials

Explicit Cursor review or Flow invocation permits review of the current admitted worktree. Do not ask for a separate external-review authorization or require a legacy external_review decision. Stricter host/network permissions still apply.

Use the controller's complete filtered frozen worktree view, not root-selected excerpts. The root brief is navigation and background, not primary proof. Exclude credentials, secret-bearing files, raw production data, external paths, symlinks, dependencies, caches, binaries and oversized files. Required target/upstream artifacts must remain available or the attempt fails. Record coverage limits, never claim excluded content was checked.

Read the API key from ~/.cursor-review/API_KEY. Keep it out of repository, prompt, arguments, logs and reports. For a missing runtime, create ~/.codex/runtime/cursor-review with python -m venv and install cursor-sdk using that runtime's python -m pip; request host permission where required. Use --check for SDK/credential diagnostics; installed Cursor SDK runtime is preferred by the controller.

## Execute

The controller binds the exact prompt, whole-view manifest and digests into a private schema-version-2 request, verifies both original worktree and private view, and consumes a fresh single-use operation binding for each attempt. Legacy paths are hints only, not transmission limits.

```bash
python /path/to/cursor-review/scripts/cursor_review.py \
  /private/package/request.json --workspace /private/package/workspace \
  --expected-request-digest "$BOUND_REQUEST_DIGEST"
```

Defaults: grok-4.6/high, 960 seconds. The pinned adapter executes through isolated Python. --check-capabilities returns exactly {"workspace_exploration":true,"write_tools":false}. Cursor SDK receives only the filtered frozen view as cwd, plan mode and bounded list_files/read_file/search custom tools; built-in filesystem tools are disabled. No shell, write, MCP, URL-fetch or original-worktree access is offered. This is a deliberate frozen-workspace policy, not a claim that SDK indexing is disabled.

Reviewer never writes the worktree, even a review-result document. Return only stdout/API. After receipt the controller verifies original HEAD/index/files/modes and private input digests before saving the result; unexpected changes reject the report without automatic rollback. Freeze by digest, never automatically commit. Package cleanup runs in finally and a failed cleanup cannot become success.

## Result

Runner emits exactly one FLOW_REVIEW_REPORT_BEGIN / FLOW_REVIEW_REPORT_END frame. Identical repeated model frames normalize to one report without changing semantics. Conflicting signals are non-degradable. Structured failures use FLOW_REVIEW_ERROR_BEGIN / FLOW_REVIEW_ERROR_END; exit 0 is receipt, not approval.

Do not resolve findings, edit, implement, commit, push or approve. The caller retains independent GPT, external-lane repair/recheck and fresh Astra final consistency rules.
