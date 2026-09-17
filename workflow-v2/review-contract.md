# Frozen worktree review contract

Read this contract before Spec, Plan or Code external review. It supersedes legacy byte-only review and external_review authorization prompts.

## Authority and review scope

Explicit Flow or Cursor review invocation permits review of the current admitted worktree; no separate human external-review gate exists. All iBrain models are organization-approved private deployments or confidentiality-bound trusted vendors and require no human authorization, independently of Cursor decisions. Historical external_review records are retained only for audit. Applicable stricter host/network restrictions still apply.

For iBrain host escalation, follow `ibrain-review`'s Host permission application: supply the applicable trust-policy source, verified captured-runner destination/model, current issue/artifact scope, actual exclusion/manifest evidence and read-only safeguards in the justification. Historical Cursor-only consent is not the iBrain trust basis. Never assert that filtering proves all data safe or that an unbuilt package already passed validation. The brief and justification must not reintroduce excluded data or credentials.

A genuine host refusal remains binding. Only if its response permits evidence-backed reconsideration, verify authorization/destination/payload facts read-only and reapply once for the same operation with those facts; never retry blindly or invoke a standalone runner to evade the controller. Pre-process refusal is not a recorded backend failure and does not consume its initial runtime attempt or single retry. Preserve any existing gate and use bound `FLOW_RUN_RESUMED` only after the actual host/human conditions are met. If reconsideration is unavailable or still refused, report the exact unresolved restriction and request only the necessary decision. This adds no controller fields or new Flow authorization gate.

Render a necessary reviewer/host/runner interruption using Human-readable interruption in `orchestration-contract.md`: name the blocked review operation, actual progress/checks and remaining unverified assurance, then the permitted host or maintainer action. Raw classifications, frames, counts and binding IDs go in optional diagnostics. Existing trusted-review policy does not release a host refusal, and ordinary user consent cannot fix a malformed report or manufacture PASS. Automatic retry/fallback remains a progress notice, not a new approval request.

The root supplies purpose, approved scope/non-goals, changed boundary, known risks and reproduction leads. Its brief is navigation, not sole evidence or a claim that omitted files are irrelevant. Reviewer independently explores the complete filtered frozen worktree and tests contradictions. Legacy manifest paths are hints, never transmission limits.

## Frozen view and binding

### Declared data exclusions

If known production/test datasets would enter the reviewer view, the root must exclude them mechanically and continue review, not ask for data-transfer authorization or stop solely because data transfer is prohibited. Use the existing review `--manifest` with optional `exclusions`:

```json
{"backend":"cursor","stage":"flow-plan","artifact_key":"plan:MILESTONE-1","prompt_path":"/absolute/worktree/review_prompt.md","exclusions":[{"path":"tests/data","kind":"directory","reason":"production-derived test inputs"},{"path":"tests/test_legacy_replay.py","kind":"file","reason":"embedded production samples; test logic omitted"}]}
```

Paths are relative to the admitted worktree; file matching is exact, directory matching includes descendants by path components, never glob matching. Root/absolute/parent-escape paths are invalid. Only exclusion paths and data-free reasons enter metadata; excluded bytes never enter the copied view or read/search tools. The normalized declaration and actual excluded-file list bind the request digest. Repeat the current declaration in every fresh retry/revision/backend manifest, including iBrain fallback; `paths` remains exploration hints, not an exclusion mechanism.

Production data outside the worktree remains preferred. For existing embedded samples, exclude the whole mixed file without changing its contents and disclose the omitted test logic; leave other source/tests available. Split data from test logic only when needed and authorized, not as a universal prerequisite. Never exclude the current target or claim an excluded test/data result was independently inspected. Reviewer records coverage limits; data exclusion alone is non-blocking. Only demonstrably missing approval-critical evidence warrants a finding/repair, and it never authorizes data transfer. Keep exclusions out of original source-snapshot filtering: all excluded source files still participate in mutation detection.

flowctl creates a private snapshot with schema-version-2 request, relative whole-view file manifest, per-file source/content digests, exclusions, prompt digest and source snapshot digest/HEAD/index facts. Only the current target must be registered, content-current and readable in the view. Available historical documents remain context; missing or changed history is a disclosed coverage limit, not a package-wide gate.

Exclude credentials, secrets, raw production data, external paths, symlinks, Git metadata/pointers, caches/dependencies, binaries and oversized files. Also exclude executable reviewer settings (.cursor and .mcp.json); Cursor loads only project settings from this configuration-free view, not user/team/plugin settings. Current limits: 4 MiB per file, 256 MiB eligible view; exceeding total limits blocks rather than selecting convenient evidence. Content/path filtering is a conservative safety screen, not proof that all sensitive data can be recognized. Never deliberately place production datasets or secrets in ordinary source names to bypass exclusions. Note every exclusion and material missing evidence as coverage limits.

Both backends use bounded list_files/read_file/search over declared relative paths with no-follow digest-checked reads. Built-in filesystem/shell/write/MCP/URL-fetch tools are not available. Cursor SDK receives only the private view and explicitly registered custom read tools, not the original worktree. iBrain executes Responses function tools locally without a Codex process. Tool-call metadata proves a local operation returned a result, not model comprehension. Controller stores operation names, read paths/source digests and result digests, never raw tool-return contents or vendor logs.

The historical flowctl authorization validate command for an external manifest now validates package binding only. It does not request or infer human authorization. Every retry/revision/backend has a fresh single-use package binding. Pinned captured adapter bytes execute through isolated Python; Cursor uses its installed SDK runtime when present.

## Receipt and mutation handling

Freeze by digest, never automatically commit. Original source snapshot covers HEAD, raw Git index bytes, source/artifact files and file modes, including untracked files. Exclude only declared caches/dependencies and the exact controller/transaction/lock/event/review-output bookkeeping; do not exempt all .ai documents.

Verify original and private snapshots before launch and after receipt. Persist the frozen source snapshot/manifest to the attempt and recheck source under the result-acceptance lock immediately before saving the report. Unexpected mutation rejects the report as non-degradable UNCLASSIFIED; retain observable state and failure evidence without automatic rollback.

Reviewer never writes the worktree, including review documents. Return stdout/API only; controller saves verified reports and audit metadata. Private-view cleanup runs in finally; failed cleanup cannot become success. This detects observable drift, not hostile writes that are undone before verification or host-level isolation failures.

## Independent lanes and terminal transport

Default route: GPT convergence -> Cursor convergence (or mechanically eligible iBrain glm-5.3 backup) -> fresh gpt-6-astra/medium consistency review. If the human explicitly selects iBrain for the current run, record that choice through `flowctl review select-external --state <controller> --backend ibrain --reason <brief human instruction> --expected-revision <current>`. The selected route is GPT -> iBrain glm-5.3 -> fresh Astra consistency, with no required Cursor call/failure and no new authorization prompt. Selection applies to subsequent reviewed stages in this run; it is not an external PASS or a fabricated transport failure. Preserve valid GPT/test/snapshot evidence and real historical findings. Use a fresh iBrain package and retain data exclusions. Do not select iBrain merely to escape Cursor findings, unresolved protocol ambiguity, or a host refusal that also covers iBrain. Host restrictions remain authoritative. A route change while a review is running waits for its actual result; changed route requires fresh current-stage consistency evidence, not reusing a conclusion about another lane.

Agent applies flowctl-contract.md historical-guarantee dispositions only when approved scope and reviewed implementation are unchanged, without rebinding original receipts. Material changes require necessary fresh reviews and consistency. Each reviewer owns and rechecks its substantive findings; non-blocking findings alone do not cause iteration. Findings never activate fallback. A valid old Cursor INCOMPLETE report without blocking findings is retained as history, but does not prevent handoff once the explicitly selected iBrain lane and fresh consistency actually pass. Failed/blocking/ambiguous conclusions remain governed by their existing repair rules. In the selected-iBrain route, its two retryable failures permit the existing degraded path through Astra with EXTERNAL_REVIEW_GAP, without testing forbidden Cursor; passing iBrain is ordinary completion, not degraded completion. Default-route failure thresholds are unchanged.

Runner owns exactly one FLOW_REVIEW_REPORT_BEGIN/END frame. Identical repeated model-owned framed JSON normalizes without semantic changes; conflicting reports or report/error signals are non-degradable. Only controller-observed timeout/structured errors/opaque failure facts activate bounded runtime retries. Exit zero means report receipt, not approval.

Known historical iBrain duplicate-frame failures may be invalidated through audited flowctl review repair-classification, preserving classification and evidence and excluding those bridge-bug attempts from retry counts. This is operator-attested diagnosis when old evidence is digest-only, not recovered PASS; a fresh independent report is required. Do not reinterpret unrelated protocol or substantive failures.

Production-data use requires its independent scoped decision and applicable project/host permissions. Flow does not validate sanitization. Review trust never authorizes production acquisition, production mutation or transfer of test datasets. Keep production-derived inputs out of reviewer views and Git regardless of whether they were sanitized.
