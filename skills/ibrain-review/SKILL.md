---
name: ibrain-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through the company iBrain service.
---

# iBrain Review

Own one bounded, read-only review through the company iBrain Responses API. The caller owns review timing, scope, brief, finding disposition, and gate outcome.

## Authorization and credentials

Sending code or documents to iBrain requires an active controller `external_review` authorization and controller-recorded Cursor runtime-fallback eligibility. Consume only its `authorization_id`, revision, and a controller-validated operation manifest for this exact iBrain request; invocation, prose, prompt wording, or a stage-created marker is not authorization. For an iBrain fallback, reuse the same active `authorization_id` and revision and the same artifact snapshot, but create a `backend=ibrain` new controller-validated, single-use operation manifest/binding; it must not reuse the Cursor binding. Continue without duplicate human confirmation only when the controller binding matches the issue, run, worktree, stage, iBrain backend, exact prompt, transmitted paths, and exclusions. A missing, pending, denied, invalidated, stale, consumed, drifted, expanded, or fallback-ineligible binding fails closed before review. Exclude anything outside that boundary or covered by sensitive-data exclusions.

Read the API key from `~/.ibrain-review/API_KEY` by default. Never place it in a repository, prompt, command argument, report, or log. `--api-key-file` may select another protected file.

## Check and model discovery

Run `scripts/ibrain_review.py --check` before the first review. It verifies the credential, live model discovery, availability of default model `glm-5.3`, and a minimal Responses request. Use `--list-models` to print live IDs from `GET http://ibrain.qiyi.domain/v1/models`; never maintain a static model list.

If a check fails, return its exact framed `INCOMPLETE` result. Do not substitute another model silently.

## Run

The controller supplies a private materialized JSON request containing the exact bound UTF-8 prompt, declared file content, relative input names, and digest manifest. Before transmission, `--check-capabilities` must report exactly `{"local_tools":false,"implicit_indexing":false}`:

```bash
python /path/to/ibrain-review/scripts/ibrain_review.py \
  /private/package/request.json --no-tools \
  --expected-request-digest "$BOUND_REQUEST_DIGEST"
```

The runner sends the materialized request directly to the Responses endpoint with model `glm-5.3`, no tools, no local executor, no workspace, no conversation continuation, and no implicit indexing. It never starts a Codex subprocess. Filesystem, shell, search, MCP and URL-fetch calls are unavailable. The credential is used only in the HTTP authorization header. The controller rehashes the private package before invocation, consumes its authorization binding once even on failure, and removes the package in `finally`; a cleanup failure cannot become success.

The controller accepts only the backend's pinned adapter content digest, independent of installation path, and executes the same captured code in isolated Python for capability checking and review. The runner reads the canonical absolute request path once through descriptor-relative, no-follow file opens, verifies its bytes against the controller's expected digest, and sends those same bytes. A replaced file, symlink, mismatch or untrusted adapter fails before transmission.

Success is enclosed exactly once by runner-owned `FLOW_REVIEW_REPORT_BEGIN` and `FLOW_REVIEW_REPORT_END`. If the model repeats identical framed JSON reports, the runner collapses them to one canonical frame; conflicting, incomplete, or malformed frames emit `PROTOCOL_ERROR` and exit 2. Other failures use a JSON code between `FLOW_REVIEW_ERROR_BEGIN` and `FLOW_REVIEW_ERROR_END` and exit 2. Exit 0 means a non-empty framed report arrived, not that the reviewed artifact passed.

Preserve the report semantics while normalizing transport framing. Do not approve scope, resolve findings, edit files, implement fixes, commit, push, or reinterpret the report as approval.
