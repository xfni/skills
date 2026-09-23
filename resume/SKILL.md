---
name: resume
description: Use when the user explicitly invokes $resume to generate a copyable shell command for resuming the current primary Codex CLI session with its evidenced workspace directories.
---

# Resume

Invoke manually with `$resume`. Generate a command for the user to copy into a terminal after exiting the current Codex session.

Run `python3 scripts/resume.py` from this skill's directory. The helper requires `CODEX_THREAD_ID`, resolves exactly one matching primary CLI session under `~/.codex/sessions`, validates its original working directory, and collects existing absolute directories from literal executed tool arguments.

The generated command always uses Codex `-C` to set the workspace that should become current after resume. It preserves the original primary workspace as `--add-dir` when a selected added worktree becomes current. The leading `cd -- <original-workspace>` intentionally lets the human run the block while remaining in the original checkout; `-C`, not the shell's starting directory, selects the resumed Codex workspace.

With no directory candidate, the original workspace remains current. With exactly one candidate, the helper makes that candidate current automatically and retains the original workspace as an added directory.

When more than one directory candidate exists, first run `python3 scripts/resume.py --list-candidates`. Present the numbered historical candidates to the user and ask both which numbers to load and which one should be current. Then run, for example, `python3 scripts/resume.py --include 1,3 --current 3`. `--current` must identify exactly one directory included by `--include`. Current-session attached directories are used when an authoritative list is available; otherwise the helper labels candidates as historical. Do not include every candidate or choose the current worktree by recency.

On success, present stdout unchanged in a shell code block, including the `cd --`, `-C`, and all `--add-dir` lines. Tell the user which path will be the resumed current workspace, then tell them to exit the current session and run the block manually. Do not automatically launch Codex or execute the generated command.

On failure, report the helper's stderr and stop. Do not guess a session ID or working directory, substitute the newest session, or use `--last`. Do not invent added directories from conversation prose or dynamic arguments.
