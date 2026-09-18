# Resume Skill Design

## Goal

Provide an explicit-only global Codex skill named `resume` that produces a
copyable command block to resume the current primary conversation without
using `--last`.

## Scope

- Install as `~/.codex/skills/resume` after the source is verified.
- Bind the active primary conversation to the `CODEX_THREAD_ID` inherited by
  the helper; never select a session by recency or a subagent thread.
- Read that conversation's `session_id`, original `cwd`, explicit historical
  `--add-dir` arguments, and existing absolute `workdir` values.
- Print a shell block that first changes into the primary workspace, then
  invokes `codex resume <session-id>` with one quoted `--add-dir` line per
  recovered additional directory.
- Keep the skill explicit-only, for manual invocation as `$resume`.

## Non-goals

- Do not launch Codex, mutate session files, or use `codex resume --last`.
- Do not add non-existent paths or infer a directory from unstructured prose.
- Do not alter repository-local skills or unrelated configuration.

## Design

`SKILL.md` directs Codex to a small read-only Python helper, and
`agents/openai.yaml` sets `policy.allow_implicit_invocation: false`. The helper
requires `CODEX_THREAD_ID`; it scans the session store for exactly one file
whose `payload.id` equals that value, whose `payload.session_id` is a non-empty
string, whose `thread_source` is `user`, and whose `source` is `cli`. Missing,
duplicate, or unsupported metadata is an error; the helper does not fall back
to modification time or any other heuristic.

Scan only `custom_tool_call` records named `exec`. From their `input` source,
accept literal JSON-string values supplied to `tools.exec_command` as either
`"workdir"` fields or `"cmd"` fields containing a literal `codex resume`
command with literal `--add-dir` values. Skip dynamic expressions, malformed
calls, agent/user messages, outputs, and all other record types. Keep only
existing absolute directories, de-duplicate them, and exclude the primary
`cwd`.

The output is intentionally a multi-line block:

```sh
cd -- "/primary/workspace"
codex resume "session-id" \
  --add-dir "/additional/workspace"
```

Render double-quoted shell arguments by escaping backslash, double quote,
dollar sign, and backtick in that order. Reject a primary or added directory
containing a newline rather than render an ambiguous block. With zero added
directories, omit the continuation and all `--add-dir` lines; with one or more,
use one continuation backslash after every non-final resume argument line.

When the helper cannot identify exactly one suitable primary session or a
safe primary directory, exit non-zero with the candidate paths and a reason.
Do not guess or print an unsafe resume command.

## Verification

- Unit-test `CODEX_THREAD_ID` selection, absent/duplicate/mismatched metadata,
  subagent exclusion, accepted nested `exec` input shapes, dynamic and prose
  exclusion, directory de-duplication and filtering, zero/one/multiple output,
  shell metacharacter escaping, and the forbidden `--last` invariant against
  temporary JSONL fixtures.
- Run the skill validator and execute the helper against the current local
  session store without starting Codex.
