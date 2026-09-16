# Frozen worktree review contract

Read this contract before Spec, Plan or Code external review. It supersedes legacy byte-only review and external_review authorization prompts.

## Authority and review scope

Explicit Flow or Cursor review invocation permits review of the current admitted worktree; no separate human external-review gate exists. All iBrain models are organization-approved private deployments or confidentiality-bound trusted vendors and require no human authorization, independently of Cursor decisions. Historical external_review records are retained only for audit. Applicable stricter host/network restrictions still apply.

The root supplies purpose, approved scope/non-goals, changed boundary, known risks and reproduction leads. Its brief is navigation, not sole evidence or a claim that omitted files are irrelevant. Reviewer independently explores the complete filtered frozen worktree and tests contradictions. Legacy manifest paths are hints, never transmission limits.

## Frozen view and binding

flowctl creates a private snapshot with schema-version-2 request, relative whole-view file manifest, per-file source/content digests, exclusions, prompt digest and source snapshot digest/HEAD/index facts. Only the current target must be registered, content-current and readable in the view. Available historical documents remain context; missing or changed history is a disclosed coverage limit, not a package-wide gate.

Exclude credentials, secrets, raw production data, external paths, symlinks, Git metadata/pointers, caches/dependencies, binaries and oversized files. Also exclude executable reviewer settings (.cursor and .mcp.json); Cursor loads only project settings from this configuration-free view, not user/team/plugin settings. Current limits: 4 MiB per file, 256 MiB eligible view; exceeding total limits blocks rather than selecting convenient evidence. Content/path filtering is a conservative safety screen, not proof that all sensitive data can be recognized. Never deliberately place production datasets or secrets in ordinary source names to bypass exclusions. Note every exclusion and material missing evidence as coverage limits.

Both backends use bounded list_files/read_file/search over declared relative paths with no-follow digest-checked reads. Built-in filesystem/shell/write/MCP/URL-fetch tools are not available. Cursor SDK receives only the private view and explicitly registered custom read tools, not the original worktree. iBrain executes Responses function tools locally without a Codex process. Tool-call metadata proves a local operation returned a result, not model comprehension. Controller stores operation names, read paths/source digests and result digests, never raw tool-return contents or vendor logs.

The historical flowctl authorization validate command for an external manifest now validates package binding only. It does not request or infer human authorization. Every retry/revision/backend has a fresh single-use package binding. Pinned captured adapter bytes execute through isolated Python; Cursor uses its installed SDK runtime when present.

## Receipt and mutation handling

Freeze by digest, never automatically commit. Original source snapshot covers HEAD, raw Git index bytes, source/artifact files and file modes, including untracked files. Exclude only declared caches/dependencies and the exact controller/transaction/lock/event/review-output bookkeeping; do not exempt all .ai documents.

Verify original and private snapshots before launch and after receipt. Persist the frozen source snapshot/manifest to the attempt and recheck source under the result-acceptance lock immediately before saving the report. Unexpected mutation rejects the report as non-degradable UNCLASSIFIED; retain observable state and failure evidence without automatic rollback.

Reviewer never writes the worktree, including review documents. Return stdout/API only; controller saves verified reports and audit metadata. Private-view cleanup runs in finally; failed cleanup cannot become success. This detects observable drift, not hostile writes that are undone before verification or host-level isolation failures.

## Independent lanes and terminal transport

Preserve GPT convergence -> Cursor convergence (or mechanically eligible iBrain glm-5.3 backup) -> fresh gpt-6-astra/medium consistency review. Each reviewer owns and rechecks its substantive findings; non-blocking findings alone do not cause iteration. Findings never activate fallback.

Runner owns exactly one FLOW_REVIEW_REPORT_BEGIN/END frame. Identical repeated model-owned framed JSON normalizes without semantic changes; conflicting reports or report/error signals are non-degradable. Only controller-observed timeout/structured errors/opaque failure facts activate bounded runtime retries. Exit zero means report receipt, not approval.

Known historical iBrain duplicate-frame failures may be invalidated through audited flowctl review repair-classification, preserving classification and evidence and excluding those bridge-bug attempts from retry counts. This is operator-attested diagnosis when old evidence is digest-only, not recovered PASS; a fresh independent report is required. Do not reinterpret unrelated protocol or substantive failures.

Production-data use requires its independent scoped decision and applicable project/host permissions. Flow does not validate sanitization. Review trust never authorizes production acquisition, production mutation or transfer of test datasets. Keep production-derived inputs out of reviewer views and Git regardless of whether they were sanitized.
