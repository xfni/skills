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

Standard route: one independent GPT review chain (`gpt-5.6-sol`/high or `gpt-6-astra`/medium) plus one external chain (Cursor or iBrain glm-5.3). No mandatory third consistency review. Explicit iBrain selection uses `flowctl review select-external --backend ibrain --reason <human instruction> --expected-revision <current>`, without Cursor calls. Human restrictions or genuine unavailability permit a single effective independent chain; never manufacture failures to qualify. Model/route changes retain all findings, original receipts and host restrictions.

Material changes require targeted independent re-review of changed boundaries, unresolved findings and affected guarantees, not automatic full review of every byte change. Supported clarification-only applicability dispositions retain original receipts. Normally the original reviewer rechecks its findings; when unavailable another independent reviewer receives the original report, fixes and evidence. Its PASSED report explicitly lists `resolved_reviews: [{"attempt_id":"original-failed-attempt","evidence":"What was checked and why all its blockers are resolved"}]`. A generic PASS never erases another lane's findings. Same-lane successful repair review normally closes its earlier findings; reviewers must carry the full unresolved ledger across revisions.

### Minimum independent guarantee and degradation

A real runtime/protocol failure permits bounded retry or another allowed channel, but retry counts are ceilings, not prerequisites. Agent may record observed unavailability or a human route constraint with `flowctl review degrade --state <controller> --lane gpt|external --basis unavailable|human --reason <verified facts or human instruction> --expected-revision <current>`. This is CALLER_ATTESTED route evidence, not an approval. Human constraints persist for this run; observed unavailability binds the current artifact/snapshot. GPT-only requires no external calls. External-only requires a recorded unavailable/restricted GPT lane. At least one real independent PASSED chain must apply to the current object; no reports, author self-review or tests alone cannot qualify.

Sol/high and Astra/medium may replace each other when actually unavailable, preserving unresolved findings and repair budgets. Another available independent channel may take over a reviewer that became unavailable after issuing findings, explicitly rechecking those findings. Do not use model changes, new threads, new digests or route constraints to reset an unresolved issue or disguise FAILED as unavailable.

Normal dual assurance completes as 通过; one-chain completion records 有条件通过 with durable EXTERNAL_REVIEW_GAP identifying the missing lane (including GPT), actual reason, receipt and follow-up. Legacy consistency receipts remain original independent evidence and may support a single-chain degraded completion, but no new third review is required. Do not relabel or submit one report to multiple roles.

Invalid/conflicting reports provide no guarantee; retain any known substantive findings and let an allowed independent reviewer verify them. Source drift requires a fresh binding before review. Host refusals constrain the prohibited operation, not every unrelated allowed review path; never evade the refusal. Human intervention is needed only when no safe allowed independent review is possible, a finding requires a product/scope/risk decision, or repair has genuinely stopped progressing. Explain the real issue, not a requirement to reset counters.

Runner owns exactly one FLOW_REVIEW_REPORT_BEGIN/END frame. Identical repeated model-owned framed JSON normalizes without semantic changes; conflicting reports or report/error signals are non-degradable. Only controller-observed timeout/structured errors/opaque failure facts activate bounded runtime retries. Exit zero means report receipt, not approval.

Known historical iBrain duplicate-frame failures may be invalidated through audited flowctl review repair-classification, preserving classification and evidence and excluding those bridge-bug attempts from retry counts. This is operator-attested diagnosis when old evidence is digest-only, not recovered PASS; a fresh independent report is required. Do not reinterpret unrelated protocol or substantive failures.

Production-data use requires its independent scoped decision and applicable project/host permissions. Flow does not validate sanitization. Review trust never authorizes production acquisition, production mutation or transfer of test datasets. Keep production-derived inputs out of reviewer views and Git regardless of whether they were sanitized.
