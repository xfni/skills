# Artifact Contract

## Output path resolution

For every persisted Flow document, resolve its destination exactly once in this precedence order; the first applicable rule wins:

1. current human-specified directory or full path in the current stage invocation, or a still-explicitly-active human instruction that names this stage or artifact;
2. the applicable project `AGENTS.md` output convention, with the closest applicable project instruction winning inside the project;
3. the applicable global `AGENTS.md` output convention supplied by the runtime;
4. the default under the project root: `.ai/issue/<issue_id>/<flow_step>_<YYYYMMDD>_<subject>.md`.

Resolve the project root from the active repository/worktree, not the shell's arbitrary working directory. Use the local date at artifact creation as `YYYYMMDD`; keep it fixed for every later revision of the same artifact. Normalize `issue_id` to its canonical issue key. Normalize `subject` to a concise lowercase snake_case ASCII slug using letters, digits, and underscores; ask the human when a faithful subject cannot be derived. Each stage supplies its documented `flow_step`.

When the human specifies a directory, use that directory with the standard filename unless the human specifies a full file path. An `AGENTS.md` rule may likewise replace the directory, filename, or both. Resolve relative paths against the project root unless the governing `AGENTS.md` explicitly declares another base. Record the selected rule, source, and resolved absolute path in the non-hashed integrity/location region and handoff, never in the body. Keep the same path for every revision of the same artifact. Never overwrite a different artifact on collision; ask the human for a distinct subject or path.

Default checkpoint discovery may infer an artifact kind only from the standard `<flow_step>_...` filename inside `.ai/issue/<issue_id>/`. A custom filename or location remains valid, but `$flow-run` must pass an explicit artifact-key-to-path map through `flowctl resume --inputs <json>`; filename inference is never workflow evidence. The controller verifies the artifact body, type, issue, approval, digest, upstream tuple, and milestone after receiving that map.

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

`content_digest` is never inside the hashed body. `flowctl artifact verify` and `flowctl artifact register` compute it from the exact bytes strictly between the body markers: UTF-8, LF line endings, no BOM, and exactly one final LF after the last body line. An Agent may render a candidate value but it is never authoritative until flowctl recomputes it. Preserve body order; do not sort fields or normalize whitespace. The integrity and approval regions are excluded. `approved_digest` must equal `content_digest`, and `approved_revision` must equal the body's `content_revision`.

`confirmer` is `HUMAN` for the Flow-level Requirement authorization and for a Direct invocation gate. Under a verified `FLOW_RUN_CONTEXT`, downstream artifacts may use `ORCHESTRATED` only when the approval envelope records the exact upstream Requirement authorization, controller/run ID, scope binding, revision, and digest. `ORCHESTRATED` is derivation authority, not permission to change product intent or bypass required reviews.

Any body-byte change increments `content_revision`, recomputes `content_digest`, and invalidates the approval region. Registration enforces monotonic revision and invalidates bound downstream artifacts and reviews. Moving an artifact preserves the exact body bytes, integrity digest, and approval binding while regenerating only the excluded path metadata for the new location; flowctl recomputes the body digest at the destination before accepting it.

Roadmap BODY includes exactly one JSON-array field `target_milestones` in delivery order and one JSON-object field `milestone_dependencies`, whose keys and dependency values are members of that array. These fields contain every non-deferred milestone required by Intent. Flowctl validates the graph, chooses the first dependency-ready milestone, records completion from accepted Integration evidence, and alone decides whether to return to Spec or complete the run.

## Authorization references

Requirement authorization is product-scope approval. It must not be treated as review authority and must not be treated as replay authority. Likewise, an artifact's approval envelope, digest, path, or presence is never evidence of permission to transmit files or acquire production-derived data.

Where a handoff or evidence record refers to an authorized external operation, record only the controller-issued `authorization_id`, authorization revision, and controller-validated operation manifest/binding ID. These references are audit links, not editable authority inside the artifact. Spec, Plan, and Code reuse the active external-review authorization revision but receive a fresh single-use manifest for each retry, revision, or backend attempt. Integration carries the active production-replay authorization reference and the exact replay manifest binding or the active skip decision. Artifact prose, reviewer output, or a copied manifest must not expand either authorization.
