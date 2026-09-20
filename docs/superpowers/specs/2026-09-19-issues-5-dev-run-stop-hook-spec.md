# Issue 5：dev-run 有界续跑 Spec

版本：Spec r2，2026-09-20。状态：Astra/medium 独立核验通过；尚未实施。

上游设计：[Issue 5 dev-run Stop Hook 设计 r2](2026-09-19-issues-5-dev-run-stop-hook-design.md)。本文定义必须实现和验证的行为；上游设计保留背景、选型与取舍。发生冲突时，在 Spec 获人类批准后以本文为交付契约。

## 1. 范围

本次交付为 `$dev-run` 增加同一人类轮次内的有界自动续跑兜底：

1. 一个严格只读的 controller observation：`flowctl continuation inspect`。
2. 一个用户级 Codex Hook helper，处理 `UserPromptSubmit` marker、activation/deactivation 和根 `Stop` continuation。
3. 一个幂等 Hook 安装器，保留用户现有 Hook 并要求真实 trust。
4. `dev-run` 关于主循环、长期 Goal、activation 与降级的协议更新。

不在范围内：`exp-run` Stop Hook、通用调度平台、业务阶段推进命令、controller/schema migration、Goal host API、subagent Stop 控制、transcript/prompt 解析、远程服务、模型调用、项目脚本执行、自动部署或 Git push。

## 2. 术语与不变量

- **Controller**：现有 `.ai/issue/<issue>/flow-state.json`，是 Flow 事实记录。
- **Observation**：只读读取 controller 后生成的 continuation 判断；不是授权、状态迁移或 next 指令。
- **Turn marker**：`UserPromptSubmit` 写入的无正文 session/turn/cwd 记录。
- **Owner pointer**：由根 session 唯一定位当前 activation 的指针。
- **Sidecar**：某 controller 的临时续跑所有权、generation 和预算；不属于 Flow 权威状态。
- **Activation**：根 Agent 在当前 `$dev-run` turn 内显式开启续跑保护。
- **Progress fingerprint**：controller 中与当前可执行动作直接相关的稳定事实投影摘要。
- **Nudge**：Stop Hook 返回一次 `decision:block`，让当前 Codex turn 继续。

必须始终满足：

- INV-1：Hook、marker、owner、sidecar 都不能创造或修改 Flow 审批、阶段、review、artifact、权限、Goal 或业务结果。
- INV-2：无法确定应继续时必须允许停止。
- INV-3：一个 activation 只绑定一个根 session、一个 Codex turn、一个 controller generation。
- INV-4：同一 progress fingerprint 在一个 generation 内最多 nudge 一次；默认总 nudge 上限为 4。
- INV-5：Hook 不读取、保存或回显 prompt、assistant message、transcript、生产数据或凭证。
- INV-6：Stop 期间发生 deactivate/takeover 时，旧 Hook 不得恢复或覆盖新 generation。
- INV-7：Goal 表达长期业务结果；Goal active 不自动激活 Hook，Hook 也不完成、暂停或替换 Goal。

## 3. `flowctl continuation inspect`

### 3.1 CLI

```text
flowctl continuation inspect --state <absolute-or-resolvable-flow-state.json>
```

成功退出码为 0，stdout 只输出一个 JSON 对象：

```json
{
  "ok": true,
  "continuation": {
    "decision": "CONTINUE",
    "reason_code": "ACTIONABLE",
    "stage": "flow-code",
    "milestone_id": "MILESTONE-1",
    "pending_action": "produce:code",
    "state_revision": 42,
    "progress_fingerprint": "sha256:<64 lowercase hex>",
    "continuation_reason": "Continue the admitted dev-run loop from the current controller facts."
  }
}
```

`decision` 只有 `CONTINUE`、`ALLOW_STOP`。`reason_code` 只有：

- `ACTIONABLE`
- `HUMAN_WAIT`
- `BLOCKED`
- `COMPLETE`
- `INACTIVE`
- `UNKNOWN`

读取/解析/最小 schema 失败时使用现有 flowctl 结构化错误协议并非零退出；Hook 必须把所有此类结果映射为 allow-stop。CLI 不把损坏 controller 包装成成功的 `ALLOW_STOP`，以免隐藏诊断事实。

### 3.2 只读保证

inspect 必须使用新的纯读取路径，不得调用或间接调用：

- `read_consistent_state`
- `_recover_transaction`
- schema migration/commit
- controller/file lock creation
- Git 命令
- artifact/review runner
- runtime sidecar helper

对成功和失败输入，执行前后 controller bytes、mtime 与 parent directory entries 必须一致。不得创建 `.lock`、transaction、event、marker、owner 或 sidecar。不得跟随 controller 最终路径本身的符号链接；非普通文件、超过实现明确上限的文件、非法 UTF-8/JSON 必须结构化失败。

### 3.3 最小 controller 输入

inspect 只要求并校验当前判断必需字段：

- `schema_version` 为现有支持版本；
- 非空字符串 `issue_id`、`run_id`、`controller_path`、`worktree_path`；
- 整数 `state_revision`；
- `current_stage`、`pending_action`；
- 可选 `active_milestone`、`pending_signal`、`artifacts`、`reviews`、`snapshots`、`coder_agent`。

它不校验 artifact 内容、digest 正确性、历史 event 链、完整审批或目录扫描。缺少可选进度字段不能伪造继续证据；无法形成稳定投影时返回 `ALLOW_STOP/UNKNOWN`。

### 3.4 判定规则

按顺序判定：

1. `current_stage == complete` → `ALLOW_STOP/COMPLETE`。
2. `pending_signal.signal` 为 `FLOW_RUN_HUMAN_GATE` 或 `FLOW_ADMISSION_GATE`，或 `pending_action == human_gate` → `ALLOW_STOP/HUMAN_WAIT`。
3. signal 为 `FLOW_RUN_BLOCKED` 或 `FLOW_ADMISSION_BLOCKED`，或 action 为 `blocked`/`blocked:*` → `ALLOW_STOP/BLOCKED`。
4. stage 不是当前 Flow stage 集合，signal 是未知非空枚举，action 是空字符串、非 `null` 的非字符串或未知形式 → `ALLOW_STOP/UNKNOWN`。route-back/resumed 也不能绕过本项 action 校验。
5. signal 为空、`FLOW_RUN_ROUTE_BACK` 或 `FLOW_RUN_RESUMED`，且 action 是下列已知形式 → `CONTINUE/ACTIONABLE`：
   - `produce:*`
   - `review:*`
   - `revise:*`
   - `repair:*`
   - `approve:*`
   - `handoff:*`
   - `inspect:*`
   - `execute:*`
   - `resume`
   - `snapshot:capture`
6. `pending_action` 为 JSON `null`，且不存在更高优先级的 complete/wait/blocked/unknown 条件 → `ALLOW_STOP/INACTIVE`。
7. 其他情况 → `ALLOW_STOP/UNKNOWN`。

stage 集合沿用现有 `flow-requirement`、`flow-intent`、`flow-roadmap`、`flow-spec`、`flow-plan`、`flow-code`、`flow-integration`。判定不声称 action 业务上正确，只表示根 Agent 应重新读取 Flow 事实并继续现有协议。

### 3.5 Progress fingerprint

fingerprint 为规范 JSON（UTF-8、key 排序、无多余空白）的 SHA-256，投影 schema 固定为 1。只投影当前 stage 和 active milestone 对应的 artifact key；无 milestone 的 requirement/intent/roadmap 使用其当前 artifact key。每个可选字段缺失时编码为 JSON `null`，不得因缺失而省略 key；字段存在但类型错误时返回 `ALLOW_STOP/UNKNOWN`。投影精确定义为：

- canonical controller path、issue、run；
- current stage、active milestone、pending action；
- pending signal 的 `signal`、`stage`、`owner_stage`、`next_stage`、`gate`，不含自由文本 cause/explanation/timestamp；
- 当前 artifact：`key`、`type`、`digest`、`revision`、`milestone_id`，以及 approval 的 `valid`、`status`、`approved_revision`、`approved_digest`、`confirmer`；
- 与当前 artifact key 和 digest 绑定的 review attempts：`attempt_id`、`backend`、`status`、`classification`、`artifact_digest`、`snapshot_digest`、raw `eligible`（缺失按 `true`）、raw `revoked`（缺失按 `false`）、`invalidated_by`，按 `attempt_id` 排序。`classification`、`snapshot_digest`、`invalidated_by` 的合法缺失或 JSON `null` 均编码为 `null`；布尔字段必须是 JSON boolean，不接受整数代替。这里不重新实现 review 通过算法，只记录影响现有算法的绑定、撤销和失效事实；
- 当前 artifact 的 snapshot：`snapshot_digest`、`head`、`status_digest`、`tracked_diff_digest`、按路径 key 排序后的 `untracked`、`evidence_exclusion`；
- code 阶段 coder：`coder_thread_id`、`coder_model`、`coder_effort`、`active_task`、按协议原顺序保留的 `completed_tasks`、`last_checkpoint`、`replacement_generation`；非 code 阶段整项为 `null`；
- 投影 schema version。

明确排除：controller `state_revision`、`updated_at`、event head、runtime Goal/history、错误自然语言、review 原始输出、时间戳、纯统计计数和无关阶段记录。

实现必须用真实 controller fixture 构造投影，而不是复制 Spec 中的 action 列表作为唯一测试来源。fixture 必须证明：重复 Goal 记录、时间戳/revision 更新、无关 milestone/artifact/review 更新不改变 fingerprint；stage/action、相关 artifact digest、相关 review terminal result、撤销/失效、snapshot 和 coder task/checkpoint 的真实变化会改变 fingerprint。

## 4. Hook runtime storage

安装根目录统一记作 `<codex-home>/flow-v2/`；`<codex-home>` 由安装器显式参数优先，其次 `CODEX_HOME`，最后 `~/.codex` 确定。运行时从已安装 `continuation_hook.py` 的已解析父目录定位 `runtime/`，不再重新读取环境变量，也不接受项目环境变量改写 runtime root。

文件布局：

```text
runtime/turns/<sha256(session-id)>.json
runtime/owners/<sha256(session-id)>.json
runtime/owners/<sha256(session-id)>.lock
runtime/continuations/<sha256(canonical-controller-path)>.json
runtime/continuations/<sha256(canonical-controller-path)>.lock
```

文件名哈希只用于定位；每个 JSON 都必须重新核对原始 identity。目录权限应为 0700，JSON/lock 为 0600。JSON 使用同目录临时文件、flush/fsync、原子 replace；不得写 worktree。

### 4.1 Turn marker schema

```json
{
  "schema_version": 1,
  "session_id": "...",
  "turn_id": "...",
  "cwd": "/canonical/path"
}
```

UserPromptSubmit handler 只验证并写上述字段，忽略输入的 `prompt`、model、transcript 和其他内容。失败时退出 0 且无阻止输出；不能影响用户提示进入模型。

### 4.2 Owner schema

```json
{
  "schema_version": 1,
  "session_id": "...",
  "controller_path": "/canonical/.../flow-state.json",
  "sidecar_path": "/canonical/.../continuations/<hash>.json",
  "generation": 3
}
```

每个根 session 最多一个 active owner。owner 只在对应 sidecar 成功提交后原子更新。owner 缺失/损坏/身份不符时 Stop 直接放行。

### 4.3 Sidecar schema

```json
{
  "schema_version": 1,
  "controller_path": "/canonical/.../flow-state.json",
  "worktree_path": "/canonical/worktree",
  "issue_id": "BCS-123",
  "owner_session_id": "...",
  "activation_turn_id": "...",
  "generation": 3,
  "active": true,
  "max_nudges": 4,
  "nudge_count": 1,
  "nudged_fingerprints": ["sha256:..."],
  "last_reason_code": "ACTIONABLE"
}
```

`max_nudges` 范围 1–8，`dev-run` 默认且正常只使用 4；更高值不由 Hook 自行选择。集合长度不得超过 max。sidecar 不保存 activation 时间作为权限或 takeover 依据。

## 5. Helper command contract

### 5.1 Activate

```text
python <codex-home>/flow-v2/continuation_hook.py activate \
  --state <controller> --session-id <root-session> [--max-nudges 4]
```

activate 必须：

1. 规范化 state/worktree，读取最小 controller identity，并调用只读 inspect；只有 `CONTINUE` 可激活。
2. 读取 session turn marker；marker session 必须完全相等，marker cwd 必须位于 canonical worktree 内。
3. 把 marker 的当前 `turn_id` 保存为 activation turn；不能留空或延迟到 Stop。
4. 按 session owner lock、controller lock 的固定顺序处理 owner/sidecar并返回 JSON：`ok`、controller、session、turn、generation、max_nudges、active。
5. 同 controller/session/turn 的重复 activate 幂等返回原 generation，不重置已消耗预算。
6. 同 session 新 turn 对同 controller 的显式 `$dev-run` 可创建新 generation；旧 generation 失效且预算不继承。
7. 不同 session 已持有同 controller，或同 session 已持有另一 active controller时返回 owner conflict，不自动抢占。

显式人类决定接管后，root 可增加 `--replace-owner --reason <non-empty>`。helper 记录 reason digest而非自然语言正文，创建新 generation且预算清零；代码只验证显式参数和 identity，不声称已验证人类语义。

marker 缺失/损坏、无法确认 session/turn/cwd、inspect 非 CONTINUE 时不得创建 active owner/sidecar。失败不成为 Flow BUSINESS BLOCKED。

### 5.2 Deactivate

```text
python <codex-home>/flow-v2/continuation_hook.py deactivate \
  --state <controller> --session-id <root-session> --generation <n> \
  --reason <complete|human_wait|blocked|explicit_stop|goal_pause|budget_limit>
```

只关闭 identity 完全匹配的 generation；旧 generation 的 deactivate 是成功 no-op，不得影响新 owner。关闭按 session owner lock、controller lock 顺序，重读 identity 后先把 sidecar 标为 inactive，再仅删除仍指向该 generation 的 owner。保留最小 sidecar诊断，不删除其他 session marker。

### 5.3 Hook mode

```text
python <codex-home>/flow-v2/continuation_hook.py hook
```

stdin 为 Codex Hook JSON。stdout 契约：

- UserPromptSubmit 成功或失败：空输出或 `{}`，绝不 block。
- Stop 决定继续：只输出 `{"decision":"block","reason":"<bounded on-task reason>"}`。
- Stop 允许结束或任何错误：空输出或 `{}`，退出 0。

Hook 不把内部路径、raw controller、prompt、last assistant message 或异常堆栈放进模型可见 reason。

## 6. Stop 线性化与决策

收到 Stop 时：

1. 校验 event name、session、turn、cwd；否则 allow。
2. 获取当前 session owner lock，通过 session hash 读取一个 owner；再获取对应 controller lock，读取 sidecar并核对 identity/generation/active/canonical cwd∈worktree；否则 allow。
3. Stop turn 必须等于 sidecar activation turn。不同则在 lock 内只关闭仍匹配的旧 generation，然后 allow。
4. 在两个 lock 内读取 owner/sidecar snapshot，释放两个 lock；运行只读 inspect，内部超时不超过 2 秒。
5. inspect 错误/超时/非法输出/ALLOW_STOP：按同一锁顺序重读；仅当 owner/generation/turn仍匹配时 deactivate；无论清理是否成功都 allow。
6. inspect 返回 CONTINUE 后按同一锁顺序重新加锁并重读。owner、generation、active、turn 任一变化则 allow 且不写；fingerprint 已存在或 budget 已满则关闭匹配 generation并 allow。
7. 否则原子添加 fingerprint、nudge_count+1并提交；提交成功后才输出 block。提交失败 allow。

所有同时触碰 owner 与 sidecar 的路径，包括 activate、deactivate、replace-owner 和 Stop 清理，都采用固定顺序：一个 session owner lock → 一个 controller lock；绝不同时持有两个 session lock或两个 controller lock。同 session 的 A/B controller 激活由 session lock 串行化；不同 session竞争同 controller由 controller lock串行化。跨 session接管只锁新 session和目标 controller并提交新 sidecar/new owner，不同步删除旧 session owner（否则需要第二把 session lock）；旧指针在原 session下次 hook/activate 时发现 sidecar owner/generation 不匹配后惰性自清理并 allow。任何删除 owner 的动作都必须持有该 session lock并再次核对完整 generation。发生交错时安全结果必须是额外 allow，而不是额外 block或旧状态复活。

Block reason 的语义固定：重新读取当前 controller；继续当前已授权的 dev-run 主循环；复用/等待已有 worker；遇到人类 gate、真实阻塞、完成或权限边界时先记录并停止；不得伪造结果或扩大范围。reason 可包含 stage、milestone、pending action 的非敏感标识，不包含具体业务指令。

## 7. Hook 安装契约

`workflow-v2/scripts/install_codex_hooks.py` 接收明确的 Codex home（未传时按 `CODEX_HOME`、`~/.codex` 顺序解析），执行以下操作：

1. 验证 helper/controller 包已先部署到目标 `<codex-home>/flow-v2`，且安装器自身解析到的 package root正是该目标；不允许把 Hook command 指向源码 worktree或另一 Codex home。
2. 解析 `<codex-home>/hooks.json`；不存在时从空 hooks 对象开始，非法 JSON/shape 时拒绝写入。
3. 在 `hooks.UserPromptSubmit` 与 `hooks.Stop` 各合并一个 command handler。handler command 使用安装器当前 `sys.executable` 的解析后绝对路径、安装后 helper 的绝对路径、固定 `hook` 子命令、同步运行和不超过 5 秒 timeout。
4. 只识别/替换 exact owned command；不删除、重排或改写其他 matcher group/handler/event/description。
5. 重复安装得到语义相同文件，不追加重复 handler。
6. 写前创建一份明确报告路径的可恢复备份，使用原子替换；任一步失败保持原 hooks.json。
7. 只读检测 config.toml 中除 `[hooks.state]` 外的 inline Hook 定义；不修改它们，输出 Codex 会合并来源并可能警告的提示。
8. 不写 `[hooks.state]`、不自动信任。成功输出必须提示在新会话运行 `/hooks` 审阅和信任。

卸载不是默认安装动作。若提供 uninstall，只能移除 exact owned handlers；删除 runtime/helper需要单独显式选项且不得删除 active sidecar或任何非 owned Hook。

## 8. dev-run 与 Goal 协议

`workflow-v2/skills/dev-run/SKILL.md` 必须规定：

1. 正常 stage handoff 仍在根 Agent 当前 turn 内立即继续，不能等待 Stop Hook。
2. Runtime Goal 仍按当前协议创建/复用/冲突恢复，作为长期业务结果；Goal 不作为 stage transition receipt。
3. controller admission、Goal readback和本轮权限可执行后，root 使用与当前选定 `flowctl` 同一已安装 package root相邻的 helper，在进入自动阶段循环前 activate并保留 generation；不得硬编码另一个默认 Codex home。
4. helper 缺失、Hook 未信任、marker 缺失、activation/inspect 失败只产生一次可读降级说明；不形成 controller signal、业务 BLOCKED 或重复人工授权。
5. 人工 gate、真实 blocked、Goal paused/blocked、宿主 budget limit、Flow complete、本轮显式停止前，root 用匹配 generation deactivate；deactivate 失败仍允许停止并报告运行时清理缺口。
6. 新 session owner conflict 时展示旧/新 session 与 controller，只有人类明确选择接管才使用 replace-owner；无 TTL 自动接管。
7. Hook reason 到达时重新运行 controller status/必要诊断并复用已有 worker，不根据 reason 直接声明 handoff、review或测试通过。
8. `exp-run` 不受本次协议影响。

## 9. 安全与兼容

- SEC-1：Hook 和 inspect 不访问网络、模型或项目可执行代码。
- SEC-2：所有未知/错误/冲突/超时路径 fail-open。
- SEC-3：路径 canonicalization 后必须核对普通文件、worktree 包含关系和 identity；不得接受 controller/owner/sidecar 的最终符号链接替换。
- SEC-4：所有输出不含 secret、数据正文、prompt/transcript或堆栈。
- SEC-5：外部传入 `last_assistant_message` 永不参与判断。
- SEC-6：旧 controller 无迁移；Hook 未安装/未信任时现有 Flow 行为不变。
- SEC-7：不新增 Flow 状态/结果、artifact/review/handoff 必填字段或人类审批门。
- SEC-8：一次 nudge 不扩大用户授权、沙箱权限、Goal预算或 Git/部署权限。

## 10. 验收条件

- AC-01：inspect 分类覆盖每个 reason code、现有 controller 真实 fixture可产生的所有 action（含 `snapshot:capture`）、route-back/resumed与空/非字符串/未知 action；route-back/resumed 不绕过未知 action校验。
- AC-02：inspect 成功/失败均不改变 controller、mtime、目录条目且不创建任何文件。
- AC-03：fingerprint 按 §3.5 精确字段与 null 规则实现；对纯 revision/time/Goal及无关 milestone/review变化稳定，对当前 action/artifact/review撤销与失效/snapshot/coder真实进展敏感。
- AC-04：同 generation同 fingerprint 只 nudge一次；四个不同进度最多四次，第五次 allow。
- AC-05：T1 activate 后首次 Stop 前 Interrupt/崩溃；同 session/cwd 的 T2 普通问答 Stop 必须 allow并只关闭旧 generation。
- AC-06：两个并发 Stop 不能重复登记；inspect 与 deactivate/takeover交错时旧 Hook不能覆盖新 generation；barrier测试覆盖同 session并发激活 A/B controller，以及旧 generation删除 owner与新 generation发布 owner的竞态。
- AC-07：不同 session、错误 cwd、损坏 identity、symlink、超时、非法 JSON、写失败全部 allow且不写 worktree。
- AC-08：UserPromptSubmit marker 不保存 prompt，永不 block；Stop 不注册为 SubagentStop。
- AC-09：activate 幂等；同 session新 turn生成新 generation；跨 session/controller conflict不自动接管；跨 session接管后的旧 owner指针只能惰性自清理，不能删除新 owner。
- AC-10：hooks.json 合并保留现有 SessionStart和任意其他 handler；重复安装幂等；非法 JSON不覆盖；inline Hook只提示不改写；自定义且含空格的 Codex home 可正确安装/执行，package 未先部署时拒绝发布 handler。
- AC-11：dev-run contract 保持主循环优先、Goal长期化、终态deactivate、运行时能力失败不业务阻塞。
- AC-12：现有 workflow-v2 全量测试继续通过；新增测试不修改真实 `~/.codex`。
- AC-13：隔离宿主探针保存命令和事件证据，确认 Codex 0.155.0 的 UserPromptSubmit → Stop(false) → synthetic continue → Stop(true) 同 turn 行为；探针数据不含凭证/业务内容。

## 11. 交付物与审阅

预期实现文件限定为设计 §10 所列 controller module、CLI、helper、installer、dev-run、README/必要 contract和测试。若实现发现必须修改 controller schema、Goal host、exp-run、subagent生命周期或新增通用 runtime registry，属于 Scope Delta，必须返回人类确认。

实现前先由 Astra/medium 按 design profile核验本 Spec 的完整性、可实现性、并发/生命周期边界和 AC 可执行性。人类批准 Spec 后才能编写实施 Plan；Spec 审阅通过不等于实现、测试、安装或 Hook trust 已完成。

### Astra 首轮审阅处置

- `SPEC-F01`：已补齐 `snapshot:capture`，定义 `INACTIVE` 的唯一可达输入，并禁止 route-back/resumed 绕过 action 校验。
- `SPEC-F02`：已增加窄范围 session owner lock、固定双锁顺序、惰性旧指针清理及两类 barrier 并发验收。
- `SPEC-F03`：已统一 `<codex-home>` 解析、部署先于 handler 发布、解释器/helper绝对路径和 dev-run同 package root规则。
- `SPEC-F04`：已把 artifact/review/snapshot/coder 投影字段、null/type/排序与相关记录筛选写成封闭契约。

最终复核针对审阅前 SHA-256 `c17e56a5e7d364fbb56a8d286916e7317f63383ffc21e0753bd79752d593725e`，结论为 PASS：四项 finding 均关闭，无新增 BLOCKING finding。当前仅追加本条审阅元数据，未改变行为契约。
