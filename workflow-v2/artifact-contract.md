# Artifact Contract

## Output path resolution

For every persisted Flow document, resolve its destination exactly once in this precedence order; the first applicable rule wins:

1. current human-specified directory or full path in the current stage invocation, or a still-explicitly-active human instruction that names this stage or artifact;
2. the applicable project `AGENTS.md` output convention, with the closest applicable project instruction winning inside the project;
3. the applicable global `AGENTS.md` output convention supplied by the runtime;
4. the default under the project root: `.ai/issue/<issue_id>/<flow_step>_<YYYYMMDD>_<subject>.md`.

Resolve the project root from the active repository/worktree, not the shell's arbitrary working directory. Use the local date at artifact creation as `YYYYMMDD`; keep it fixed for every later revision of the same artifact. Normalize `issue_id` to its canonical issue key. Normalize `subject` to a concise lowercase snake_case ASCII slug using letters, digits, and underscores; ask the human when a faithful subject cannot be derived. Each stage supplies its documented `flow_step`.

When the human specifies a directory, use that directory with the standard filename unless the human specifies a full file path. An `AGENTS.md` rule may likewise replace the directory, filename, or both. Resolve relative paths against the project root unless the governing `AGENTS.md` explicitly declares another base. Record the selected rule, source, and resolved absolute path in the non-hashed integrity/location region and handoff, never in the body. Keep the same path for every revision of the same artifact. Never overwrite a different artifact on collision; ask the human for a distinct subject or path.

Every workflow artifact has three physically delimited regions in this order:

```text
--- FLOW BODY BEGIN ---
<human-readable body, including content_revision>
--- FLOW BODY END ---
--- FLOW INTEGRITY BEGIN ---
content_digest: sha256:<lowercase hex>
path_rule: <human | project-agents | global-agents | default>
path_source: <source reference>
resolved_path: <absolute path>
--- FLOW INTEGRITY END ---
--- FLOW APPROVAL BEGIN ---
<status, approved_revision, approved_digest, confirmer, time>
--- FLOW APPROVAL END ---
```

`content_digest` is never inside the hashed body. Compute it from the exact bytes strictly between the body markers: UTF-8, LF line endings, no BOM, and exactly one final LF after the last body line. Preserve body order; do not sort fields or normalize whitespace. The integrity and approval regions are excluded. `approved_digest` must equal `content_digest`, and `approved_revision` must equal the body's `content_revision`.

`confirmer` is `HUMAN` for the Flow-level Requirement authorization and for a Direct invocation gate. Under a verified `FLOW_RUN_CONTEXT`, downstream artifacts may use `ORCHESTRATED` only when the approval envelope records the exact upstream Requirement authorization, controller/run ID, scope binding, revision, and digest. `ORCHESTRATED` is derivation authority, not permission to change product intent or bypass required reviews.

Any body-byte change increments `content_revision`, recomputes `content_digest`, and invalidates the approval region. Moving an artifact preserves the exact body bytes, integrity digest, and approval binding while regenerating only the excluded path metadata for the new location; recompute the body digest at the destination before accepting it.
