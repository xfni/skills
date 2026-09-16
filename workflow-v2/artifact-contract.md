# Artifact Contract

## Output path resolution

For every persisted Flow document, resolve its destination exactly once in this precedence order; the first applicable rule wins:

1. current human-specified directory or full path in the current stage invocation, or a still-explicitly-active human instruction that names this stage or artifact;
2. the applicable project `AGENTS.md` output convention, with the closest applicable project instruction winning inside the project;
3. the applicable global `AGENTS.md` output convention supplied by the runtime;
4. the default under the project root: `.ai/issue/<issue_id>/<flow_step>_<YYYYMMDD>_<subject>.md`.

Resolve the project root from the active repository/worktree, not the shell's arbitrary working directory. Use the local date at artifact creation as `YYYYMMDD`; keep it fixed for every later revision of the same artifact. Normalize `issue_id` to its canonical issue key. Normalize `subject` to a concise lowercase snake_case ASCII slug using letters, digits, and underscores; ask the human when a faithful subject cannot be derived. Each stage supplies its documented `flow_step`.

When the human specifies a directory, use that directory with the standard filename unless the human specifies a full file path. An `AGENTS.md` rule may likewise replace the directory, filename, or both. Resolve relative paths against the project root unless the governing `AGENTS.md` explicitly declares another base. Record the selected rule, source, and resolved absolute path in the non-hashed integrity/location region and handoff, never in the body. Keep the same path for every revision of the same artifact. Never overwrite a different artifact on collision; ask the human for a distinct subject or path.

Default checkpoint discovery reads artifact type metadata inside `.ai/issue/<issue_id>/`; a custom filename is valid. For a custom location, pass an artifact-key-to-path map through `flowctl resume --inputs <json>`. Missing historical inputs are reported, not invented, and do not invalidate an otherwise usable current-stage document.

Prefer three physically delimited regions in this order when writing new artifacts:

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

The three-region layout is a writing convention, not a daily progression gate. Registration reads UTF-8, tolerates BOM/line-ending differences, and computes the actual BODY digest (whole document when no BODY region exists). Declared digest, revision and approval tuples are advisory; missing/stale declarations produce warnings. Controller-issued revisions and actual content digests bind review receipts. `flowctl artifact verify` and `flowctl audit` retain strict checks for explicit diagnostics; do not require them before normal handoff.

`confirmer` is `HUMAN` for the Flow-level Requirement authorization. Downstream artifacts may use `ORCHESTRATED`; the controller records available input bindings rather than demanding duplicate exact tuples in prose. This does not authorize changing product intent, bypassing reviews or fabricating consent. Arbitrary-node invocation uses the human's stated task boundary and never fabricates missing historical approval.

A content change creates a new controller revision and invalidates affected review receipts and downstream artifacts, even when the model forgets to update `content_revision`. Moving unchanged content preserves its identity. An unchanged checkpoint explicitly invalidated by route-back cannot be reactivated merely by increasing a declared revision.

Roadmap BODY includes exactly one JSON-array field `target_milestones` in delivery order and one JSON-object field `milestone_dependencies`, whose keys and dependency values are members of that array. These fields contain every non-deferred milestone required by Intent. Flowctl validates the graph, chooses the first dependency-ready milestone, records completion from accepted Integration evidence, and alone decides whether to return to Spec or complete the run.

## Authorization references

Requirement authorization is product-scope approval. It must not be treated as review authority and must not be treated as replay authority. Likewise, an artifact's approval envelope, digest, path, or presence is never evidence of permission to transmit files or acquire production-derived data.

External review evidence records the controller-issued package binding ID, backend/stage/artifact, prompt/view digests and frozen source snapshot. It does not carry or depend on a human external_review authorization. Every retry/revision/backend attempt gets a fresh binding. Production replay still records its controller-issued authorization_id, authorization revision and exact replay manifest binding or active skip decision. Artifact prose and reviewer output cannot broaden replay authority. Read review-contract.md for the invocation/trusted-provider review policy.
