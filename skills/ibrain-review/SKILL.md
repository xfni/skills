---
name: ibrain-review
description: Use when the user or a workflow explicitly requests a bounded read-only repository review through the company iBrain service.
---

# iBrain Review

Own one bounded read-only review through the company iBrain Responses API. The caller owns profile, brief, findings and gate outcome.

## Trust, scope and credentials

All iBrain models are organization-approved private deployments or confidentiality-bound trusted vendors. No human external-review authorization is required, and Cursor authorization never gates iBrain. Host sandbox/network permissions and sensitive-data exclusions still apply. Inside Flow, use the recorded route: explicit iBrain selection needs no Cursor attempt; observed Cursor runtime/protocol failure permits iBrain backup without a failure quota. Known findings are retained and require independent verification, not automatic disappearance on channel change.

### Host permission application

When sandbox/network escalation is necessary, give the host facts about the destination and payload, not only "Flow allows fallback". Verify the captured runner's actual Responses URL (currently http://ibrain.qiyi.domain/v1/responses), selected model, current issue/worktree/artifact and fresh manifest with repeated exclusions. Cite the applicable user-maintained iBrain trust policy separately from historical Cursor-only consent. State the bounded read-only operation, excluded data categories, binding/manifest evidence available, and protected credential-file use without its value. Report only verified package facts; a planned package is not an already-validated package. Do not dump file lists or production data into the justification.

Example justification, filled with current verified facts: "依据适用的用户维护 iBrain 信任策略（私有部署或签署保密协议的供应商），请求向已核实的公司 iBrain Responses 地址发送本议题的过滤冻结代码视图，由 glm-5.3 只读审查。当前 manifest 排除生产数据、日志和密钥；新绑定及视图由控制器校验，结果经 API 返回，不修改工作树。此次申请仅请求宿主网络/执行权限，不以历史 Cursor 授权替代 iBrain 依据。" Narrow the statement if the actual exclusions or guarantees differ; never invent approval or claim a changed/unverified endpoint is covered.

If the host rejects the operation, preserve the original refusal and do not execute indirectly, change tools/route to evade it or bypass Flow audit. When the host explicitly permits providing proof of authorization or low risk, perform read-only checks of policy, destination and filtered manifest first, then make at most one evidence-backed reapplication for the same scoped operation. Repeated refusal or a missing trust basis requires the specific missing human/host decision, not a generic repeated reviewer authorization prompt. A pre-process rejection is not a backend attempt, RUN_ERROR or consumed fallback retry. An existing host gate is cleared only through a bound controller resume after its actual conditions are satisfied; do not delete it or falsely declare permission granted.

Read ~/.ibrain-review/API_KEY by default; --api-key-file may select another protected file. Never put credentials in prompts, repositories, arguments or evidence.

## Diagnostics and live model discovery

Use scripts/ibrain_review.py --list-models for live GET http://ibrain.qiyi.domain/v1/models; do not hard-code a model list. Default review model is glm-5.3. --check verifies credential, live availability and a minimal Responses request. Do not silently substitute a model.

## Frozen-worktree exploration

The controller creates a schema-version-2 request and complete filtered private worktree view. The root brief is background, not sole evidence; reviewer independently explores callers, contracts, tests and contradictions. Exclude secrets, credentials, raw production data, external paths, symlinks, caches/dependencies, binaries and oversized inputs. Required target/upstream artifacts must remain readable; record exclusions as coverage limits.

```bash
python /path/to/ibrain-review/scripts/ibrain_review.py \
  /private/package/request.json --workspace /private/package/workspace \
  --expected-request-digest "$BOUND_REQUEST_DIGEST"
```

--check-capabilities returns exactly {"workspace_exploration":true,"write_tools":false}. The pinned captured runner verifies request and every declared file digest before API calls. It exposes only bounded list_files, read_file and literal search function tools over the frozen view. Function outputs continue through Responses input; no shell, writes, MCP, URL fetching or Codex subprocess exists. Overall timeout and call/round limits bound the review. Tool-call metadata is evidence of local reads, not proof that the model understood them.

Reviewer returns stdout/API only, never writes worktree or report documents. Controller freezes original HEAD/index/files/modes, checks original and private snapshots after review, and only then saves results. Unexpected changes reject the report without rollback. No automatic commit. Every attempt has a fresh single-use operation binding; cleanup in finally must succeed.

## Terminal protocol and convergence

Runner owns one FLOW_REVIEW_REPORT_BEGIN / FLOW_REVIEW_REPORT_END frame. Identical repeated framed JSON normalizes to one report; conflicting terminal signals remain non-degradable. Structured failures use FLOW_REVIEW_ERROR_BEGIN / FLOW_REVIEW_ERROR_END and exit 2. Exit 0 is report receipt, not approval.

Flow retries RUN_ERROR/PROTOCOL_ERROR at most once when useful. Standard assurance is GPT + one external chain; real unavailability or human route restrictions permit at least one effective independent chain with a recorded gap. No third Astra consistency review is required. Normally recheck your own findings; an independent takeover receives original findings, fixes and evidence and explicitly verifies them. Historical duplicate-frame repair preserves evidence and never manufactures PASS.

Do not resolve findings, approve, edit, implement, commit or push.
