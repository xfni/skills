---
name: cursor-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through Cursor.
---

# Cursor Review

Own the Cursor connection, dependency diagnostics, and one bounded read-only review. The caller owns review timing, profile, brief content, finding disposition, and whether the report satisfies its gate.

## Preconditions

External review must be explicitly selected or authorized. A verified `FLOW_CURSOR_AUTHORIZATION` from `$flow-run`, `$flow-spec`, `$flow-plan`, or `$flow-code` is already explicit authorization for its bound transmission; inherit it and must not request duplicate human confirmation. Recompute the proposed manifest and continue only when every transmitted item stays within the bound issue, worktree, stage, or manifest scope. Anything outside the bound issue, worktree, stage, or manifest, or anything covered by its sensitive-data exclusions, requires new authority or removal from the transmission.

This skill uses the dedicated runtime `~/.codex/runtime/cursor-review`; the runner automatically re-executes itself with that interpreter so the calling shell's Python cannot change dependency resolution. If the runtime is missing or its pinned SDK import fails, run `python scripts/install_cursor_sdk.py`, then repeat the check. Installing or upgrading packages is an external mutation and requires the human's authorization.

Use `scripts/cursor_review.py --check` before the first review. It checks `cursor_sdk` and `~/.cursor-review/API_KEY` without printing the key. If either remains unavailable, report the exact `INCOMPLETE` message and stop; never simulate equivalent coverage or retry automatically.

Generate an API key in Cursor and save only the key to `~/.cursor-review/API_KEY`. Keep credentials out of repositories, prompts, logs, evidence, and commits. An explicit `--api-key-file` changes both the lookup path and the remediation message.

## Run

The caller supplies an absolute repository/worktree path and a UTF-8 review brief containing the approved scope, frozen version, evidence, review profile, and finding schema:

```bash
python /path/to/cursor-review/scripts/cursor_review.py \
  /absolute/path/to/repository /absolute/path/to/review-brief.md
```

Defaults are model `grok-4.6`, effort `high`, timeout 960 seconds, and poll interval 10 seconds. Override them only when the calling workflow explicitly chooses different values. An optional positional agent ID resumes a finished agent in the same workspace.

The runner fixes Cursor to plan mode, the target worktree, and exactly `read`, `grep`, `glob`, and `ls`; it grants no shell or editing tool. It prints agent/run IDs and the terminal report. Exit 0 means only that a non-empty report arrived. Missing dependencies, missing/empty key, invalid input, bridge failure, empty report, terminal failure, or timeout returns `INCOMPLETE` with exit 2 and no traceback.

Return the report and identifiers unchanged to the caller. Do not approve scope, resolve findings, edit files, implement fixes, commit, push, or interpret receipt of a report as review approval.
