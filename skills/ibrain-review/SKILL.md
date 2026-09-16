---
name: ibrain-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through the company iBrain service.
---

# iBrain Review

Own one bounded read-only review through the company iBrain Responses API. The caller owns profile, brief, findings and gate outcome.

## Trust, scope and credentials

All iBrain models are organization-approved private deployments or confidentiality-bound trusted vendors. No human external-review authorization is required, and Cursor authorization never gates iBrain. Host sandbox/network permissions and sensitive-data exclusions still apply. Inside Flow, activation as Cursor backup still requires two controller-recorded retryable Cursor failures on the current artifact digest; findings never activate fallback.

Read ~/.ibrain-review/API_KEY by default; --api-key-file may select another protected file. Never put credentials in prompts, repositories, arguments or evidence.

## Diagnostics and live model discovery

Use scripts/ibrain_review.py --list-models for live GET http://ibrain.qiyi.domain/v1/models; do not hard-code a model list. Default review model is glm-5.3. --check verifies credential, live availability and a minimal Responses request. Do not silently substitute a model.

## Frozen-worktree exploration

The controller creates a schema-version-2 request and complete filtered private worktree view. The root brief is background, not sole evidence; reviewer independently explores callers, contracts, tests and contradictions. Exclude secrets, credentials, raw production data, external paths, symlinks, caches/dependencies, binaries and oversized inputs. Required target/upstream artifacts must remain readable; record exclusions as coverage limits.

```bash
python /path/to/ibrain-review/scripts/ibrain_review.py \
  /private/package/request.json --workspace /private/package/workspace \
  --expected-request-digest "$BOUND_REQUEST_DIGEST"
```

--check-capabilities returns exactly {"workspace_exploration":true,"write_tools":false}. The pinned captured runner verifies request and every declared file digest before API calls. It exposes only bounded list_files, read_file and literal search function tools over the frozen view. Function outputs continue through Responses input; no shell, writes, MCP, URL fetching or Codex subprocess exists. Overall timeout and call/round limits bound the review. Tool-call metadata is evidence of local reads, not proof that the model understood them.

Reviewer returns stdout/API only, never writes worktree or report documents. Controller freezes original HEAD/index/files/modes, checks original and private snapshots after review, and only then saves results. Unexpected changes reject the report without rollback. No automatic commit. Every attempt has a fresh single-use operation binding; cleanup in finally must succeed.

## Terminal protocol and convergence

Runner owns one FLOW_REVIEW_REPORT_BEGIN / FLOW_REVIEW_REPORT_END frame. Identical repeated framed JSON normalizes to one report; conflicting terminal signals remain non-degradable. Structured failures use FLOW_REVIEW_ERROR_BEGIN / FLOW_REVIEW_ERROR_END and exit 2. Exit 0 is report receipt, not approval.

Flow retries retryable RUN_ERROR/PROTOCOL_ERROR once; iBrain owns and rechecks its substantive findings. A fresh gpt-6-astra/medium final consistency review is still required. Historical duplicate-frame failures may only be invalidated by audited repair, preserving evidence and requiring a fresh review; never manufacture PASS.

Do not resolve findings, approve, edit, implement, commit or push.
