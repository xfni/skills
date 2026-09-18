---
name: resume
description: Use when the user explicitly invokes $resume to generate a copyable shell command for resuming the current primary Codex CLI session with its evidenced workspace directories.
---

# Resume

Invoke manually with `$resume`. Generate a command for the user to copy into a terminal after exiting the current Codex session.

Run `python3 scripts/resume.py` from this skill's directory. The helper requires `CODEX_THREAD_ID`, resolves exactly one matching primary CLI session under `~/.codex/sessions`, validates its original working directory, and collects existing absolute directories from literal executed tool arguments.

On success, present stdout unchanged in a shell code block, including the `cd --` line and all `--add-dir` lines. Tell the user to exit the current session and run the block manually. Do not automatically launch Codex or execute the generated command.

On failure, report the helper's stderr and stop. Do not guess a session ID or working directory, substitute the newest session, or use `--last`. Do not invent added directories from conversation prose or dynamic arguments.
