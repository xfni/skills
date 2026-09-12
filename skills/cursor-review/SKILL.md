---
name: cursor-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through Cursor.
---

# Cursor Review

Own the Cursor connection, dependency diagnostics, and one bounded read-only review. The caller owns review timing, profile, brief content, finding disposition, and whether the report satisfies its gate.

## Preconditions

External review must be explicitly selected or authorized. Use `scripts/cursor_review.py --check` before the first run. It checks `cursor_sdk` and `~/.cursor-review/API_KEY` without printing the key. If either is unavailable, report the exact `INCOMPLETE` message and stop; never simulate equivalent coverage or retry automatically.

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
