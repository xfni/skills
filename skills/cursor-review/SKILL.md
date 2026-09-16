---
name: cursor-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through Cursor.
---

# Cursor Review

Own the Cursor connection, dependency diagnostics, and one bounded read-only review. The caller owns review timing, profile, brief content, finding disposition, and whether the report satisfies its gate.

## Preconditions

External review requires an active controller `external_review` authorization. Consume only its `authorization_id`, revision, and a controller-validated operation manifest for this exact Cursor request; invocation, prose, prompt wording, or a stage-created marker is not authorization. Recompute the proposed manifest and continue without duplicate human confirmation only when the controller binding matches the issue, run, worktree, stage, Cursor backend, exact prompt, transmitted paths, and exclusions. A missing, pending, denied, invalidated, stale, consumed, drifted, or expanded binding fails closed before review. Anything outside the binding or covered by sensitive-data exclusions requires a controller amendment or removal from the transmission. For an iBrain fallback, reuse the same active `authorization_id` and revision and the same artifact snapshot, but create a `backend=ibrain` new controller-validated, single-use operation manifest/binding; it must not reuse the Cursor binding.

The current Cursor SDK workspace bridge does not prove that implicit indexing is disabled. The adapter therefore reports `BACKEND_UNAVAILABLE` before reading review input or credentials or making a network call. Do not use `tools=[]`, plan mode, a read-only workspace, or a temporary working directory as a substitute for that guarantee. A future enabled adapter requires a verified SDK capability contract covering both disabled tools and disabled indexing.

Use `scripts/cursor_review.py --check-capabilities` before transmission. A successful adapter must emit exactly `{"local_tools":false,"implicit_indexing":false}`. The current adapter fails closed; return the framed result to the controller for its existing runtime-fallback policy.

Keep credentials out of repositories, prompts, logs, evidence, and commits. The unavailable adapter does not read an API key.

## Run

The controller supplies a private materialized JSON request containing only the exact bound UTF-8 prompt, declared file content, relative input names, and digest manifest:

```bash
python /path/to/cursor-review/scripts/cursor_review.py \
  /private/package/request.json --no-tools \
  --expected-request-digest "$BOUND_REQUEST_DIGEST"
```

Defaults are model `grok-4.6`, effort `high`, and timeout 960 seconds. There is no workspace or agent-resume parameter. The controller rehashes the package immediately before launch, consumes its binding once even on failure, and removes the package in `finally`. Cleanup failure blocks a successful result.

The controller accepts only the backend's pinned adapter content digest, independent of installation path. It executes the captured adapter bytes in isolated Python for both capability checking and review. Self-reported capabilities from an arbitrary script are not trusted.

No filesystem, shell, search, MCP, URL-fetch, or indexing tool may be registered. The eventual byte-only adapter must send only the materialized request as input, never a repository path or general workspace. Successful reports use `FLOW_REVIEW_REPORT_BEGIN` / `FLOW_REVIEW_REPORT_END`. Failures use a JSON envelope between `FLOW_REVIEW_ERROR_BEGIN` and `FLOW_REVIEW_ERROR_END`; classify only its allow-listed code or observed timeout. Exit 0 denotes receipt of a report, not review approval.

Return the report and identifiers unchanged to the caller. Do not approve scope, resolve findings, edit files, implement fixes, commit, push, or interpret receipt of a report as review approval.
