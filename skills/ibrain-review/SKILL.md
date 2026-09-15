---
name: ibrain-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through the company iBrain service.
---

# iBrain Review

Own one bounded, read-only review through the company iBrain Responses API. The caller owns review timing, scope, brief, finding disposition, and gate outcome.

## Authorization and credentials

Sending code or documents to iBrain requires explicit selection or authorization. A verified workflow authorization bound to the issue, worktree, stage, and transmission manifest is sufficient; do not ask twice. Exclude anything outside that boundary or covered by sensitive-data exclusions.

Read the API key from `~/.ibrain-review/API_KEY` by default. Never place it in a repository, prompt, command argument, report, or log. `--api-key-file` may select another protected file.

## Check and model discovery

Run `scripts/ibrain_review.py --check` before the first review. It verifies the credential, live model discovery, availability of default model `glm-5.3`, and a minimal Responses request. Use `--list-models` to print live IDs from `GET http://ibrain.qiyi.domain/v1/models`; never maintain a static model list.

If a check fails, return its exact framed `INCOMPLETE` result. Do not substitute another model silently.

## Run

The caller supplies an absolute repository/worktree and a UTF-8 brief containing the approved scope, frozen version, evidence, review profile, and finding schema:

```bash
python /path/to/ibrain-review/scripts/ibrain_review.py \
  /absolute/path/to/repository /absolute/path/to/review-brief.md
```

The runner starts an ephemeral Codex session fixed to iBrain, model `glm-5.3`, the target worktree, read-only sandbox, and no interactive approvals. The key exists only in the child environment. Codex runtime logs are captured separately; only `--output-last-message` becomes the terminal report.

Success is enclosed exactly once by `FLOW_REVIEW_REPORT_BEGIN` and `FLOW_REVIEW_REPORT_END`. Failures use a JSON code between `FLOW_REVIEW_ERROR_BEGIN` and `FLOW_REVIEW_ERROR_END` and exit 2. Exit 0 means a non-empty framed report arrived, not that the reviewed artifact passed.

Return the report unchanged. Do not approve scope, resolve findings, edit files, implement fixes, commit, push, or reinterpret the report as approval.
