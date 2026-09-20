# Issue 5：dev-run 有界 Stop Hook 与长期 Goal 设计

版本：设计 r2，2026-09-19。状态：Astra 定向复审通过；尚未实施。

## 1. 目标与成功边界

`$dev-run` 已能在同一 Agent 轮次内自动承接阶段，但根 Agent 偶尔会在一个非终态阶段完成后直接结束回答。当前 Runtime Goal 能保存长期业务目标，却不应承担每个 Flow 节点的驱动职责。本设计增加一个 Codex `Stop` Hook 作为同轮次的有界兜底：当已激活的 dev-run 控制器明确还有可执行动作时，提醒根 Agent继续；遇到人工等待、真实阻塞、完成、未知状态或工具错误时允许停止。

成功标准：

1. `dev-run` 的正常同轮次循环仍是主路径，Hook 只是遗漏兜底。
2. Goal 表达需要持续达成的业务结果，Flow 控制器记录流程事实，Hook 只保证有限的运行活性；三者不互相伪造权限或完成结论。
3. Hook 不能审批 Requirement、推进阶段、写 Flow controller、重跑外部操作或判断业务正确性。
4. 同一进度最多提醒一次；一次显式激活默认最多提醒四次。无进展、异常或歧义必须释放当前轮次。
5. Hook 只作用于明确激活它的根会话和 controller，不影响其他项目、会话、普通问答或 subagent。

非目标：为所有工作流建立通用调度平台；让 `exp-run` 改用 Stop Hook；替代 Runtime Goal；恢复被中断的进程；从 transcript 推导业务状态；自动解决人工/宿主权限；复制 AWS AI-DLC 的完整状态机。

## 2. 事实依据

### 2.1 Codex 官方契约

[Codex Hooks 官方文档](https://developers.openai.com/zh-Hans/docs/hooks)说明：

- 用户级 `~/.codex/hooks.json` 可在不同项目中加载，且不依赖项目受信任状态；非托管 Hook 的当前定义仍需用户通过 `/hooks` 审查并信任。
- `Stop` 收到 `session_id`、`turn_id`、`stop_hook_active` 和 `last_assistant_message`。
- `Stop` 返回 `{ "decision": "block", "reason": "..." }` 时，不是拒绝操作，而是自动创建一条继续提示，让同一轮次继续运行。
- `Stop` 与 `SubagentStop` 是不同事件；本设计只给根 `Stop` 配置 continuation，并另用 `UserPromptSubmit` 记录不含正文的 turn marker，不注册 `SubagentStop`。
- Hook command 以会话 `cwd` 运行；多个配置来源会合并而非相互覆盖。

### 2.2 本机 0.155.0 探针

2026-09-19 在临时目录以只读、ephemeral `codex exec` 验证，未修改仓库或全局 Hook。实际顺序为：

1. 原始提示触发 `UserPromptSubmit`。
2. 首次模型结束触发 `Stop(stop_hook_active=false)`。
3. Hook 返回一次 `decision:block` 后，模型在同一 `session_id`、同一 `turn_id` 继续。
4. 续跑不会再次触发 `UserPromptSubmit`。
5. 第二次结束触发 `Stop(stop_hook_active=true)`。

因此防循环与预算不能依赖新的用户提示；必须由 Stop Hook 的运行时 sidecar 维护。`stop_hook_active` 是递归信号，不单独证明已有进展。

### 2.3 AWS AI-DLC 借鉴范围

[AWS AI-DLC Hooks and Tools](https://awslabs.github.io/aidlc-workflows/reference/06-hooks-and-tools/)的 Stop Hook 通过只读 engine probe 查询下一动作，对 done/parked/等待/失败放行，对 pending 动作有限次注入继续提示，并明确 fail-open。其设计还包含 transcript 分类、后台 subagent ledger、复杂 directive identity 和多 harness 适配。

本工作流只采纳“只读观察、进度指纹、有界提醒、fail-open”。Flow v2 没有 AWS 的 engine directive 系统，也不需要为一个当前需求引入 transcript 解析、跨 harness adapter 或通用任务调度层。

## 3. 方案比较

### A. 仅依赖 Goal

优点是无需 Hook。缺点是 Goal 是跨轮次业务承诺，不保证某次 Agent 回复前继续执行下一 Flow 节点；实践中已出现“Goal 仍 active，但 Agent 正常结束当前回复”。不采用。

### B. Stop Hook 直接调用可写的 `status/resume/next`

它可以强制更多动作，但会把恢复、迁移、锁文件、阶段推进甚至外部执行放进终止边界。Hook 出错可能改变权威状态或重复执行，违背“控制器为流程服务”。不采用。

### C. 根 Agent 主循环 + 只读 inspect + 有界 Stop Hook（采用）

Agent 正常执行所有语义动作；新增纯只读 `flowctl continuation inspect` 只报告“当前是否明确可继续”和进度指纹。用户级 Hook 在已显式激活的根会话终止时调用 inspect，并仅生成一条 on-task 继续提示。运行时 sidecar 保存所有权和有限预算，不进入 Flow 权威状态。

该方案代码边界较小，未知情况自然放行，也不会把 Goal、controller 或 Hook 变成第二套工作流引擎。

## 4. 组件与职责

### 4.1 `flowctl continuation inspect`

新增只读命令：

```text
flowctl continuation inspect --state <flow-state.json>
```

它直接只读解析指定 controller，不调用 `read_consistent_state`、`resume`、schema migration、文件锁、Git、artifact verify 或 reviewer。命令不得创建目录、`.lock`、transaction、event 或 sidecar。

输出固定为：

```json
{
  "ok": true,
  "continuation": {
    "decision": "CONTINUE|ALLOW_STOP",
    "reason_code": "ACTIONABLE|HUMAN_WAIT|BLOCKED|COMPLETE|INACTIVE|UNKNOWN",
    "stage": "flow-code",
    "milestone_id": "MILESTONE-1",
    "pending_action": "produce:code",
    "state_revision": 42,
    "progress_fingerprint": "sha256:...",
    "continuation_reason": "..."
  }
}
```

只有 controller 可读、最小身份字段有效、阶段属于已知 Flow 阶段、未完成、无人工/阻塞信号且存在明确 `pending_action` 时返回 `CONTINUE`。`FLOW_RUN_ROUTE_BACK` 是可执行修复路径，不是人工等待；`FLOW_RUN_HUMAN_GATE`、`FLOW_RUN_BLOCKED`、`complete`、空动作、未知枚举和任何解析错误均返回/退化为 `ALLOW_STOP`。

`progress_fingerprint` 只包含当前 controller 路径、stage、milestone、pending action、pending signal identity，以及当前动作直接绑定的 artifact/review/coder 摘要。它排除时间戳、event head、纯 revision 和运行时 Goal 记录，避免无业务进展的记账刷新伪造进展。

inspect 不声明下一条具体 CLI 命令，不执行动作，也不保证 pending action 仍适合业务；其含义仅是“根 Agent 应重新读取当前事实并继续 dev-run 主循环”。

### 4.2 运行时 helper 与 sidecar

新增 `workflow-v2/continuation_hook.py`，安装到固定用户路径：

```text
~/.codex/flow-v2/continuation_hook.py
~/.codex/flow-v2/runtime/continuations/<controller-path-sha256>.json
~/.codex/flow-v2/runtime/owners/<session-id-sha256>.json
~/.codex/flow-v2/runtime/turns/<session-id-sha256>.json
```

helper 提供三个窄入口：

- `activate`：由 `$dev-run` 根 Agent 在 controller admission 与 Runtime Goal 核对后显式调用；从本 session 的最新 `UserPromptSubmit` marker 取得并核实当前 `turn_id`，再绑定 controller、规范化 worktree、根 `session_id`、该 activation turn、新 generation 和默认总预算 4。marker 缺失、session/cwd/worktree 不符时拒绝激活并按降级路径继续，不允许等到 Stop 再猜测 turn。
- `deactivate`：由 `$dev-run` 在完成、人工等待、阻塞或显式停止时调用；只能关闭匹配 session/generation 的 sidecar。
- `hook`：由 Codex `UserPromptSubmit` 或 `Stop` 事件调用。前者只原子记录 session/turn/cwd marker且永不激活 Flow；后者通过 session owner 指针读取唯一 sidecar、调用只读 inspect，并决定是否输出 block。

sidecar 是运行活性记录，不是 Flow controller：它不能记录审批、阶段完成、review PASS、权限或业务结果。文件使用 0600、文件锁与原子替换，损坏或不可读时 Hook 直接放行。

sidecar 最小字段：schema、controller/worktree、issue、owner session、activation turn、generation、active、budget、已提醒 fingerprint 集合、最后原因。turn marker 只含 schema、session、turn 和 canonical cwd；owner 指针只含 session、controller-sidecar path 和 generation。禁止保存 prompt、assistant 正文、生产数据、凭证或 transcript。

每个 controller 使用一个路径稳定的 0600 lock 文件。Hook 可以在锁外运行只读 inspect，但最终提交 block 前必须重新加锁、重读 sidecar，并逐项核对 owner、generation、active、activation turn、fingerprint 集合和 budget 与观察快照仍兼容；任何不匹配都放行且不得关闭、覆盖或恢复新的 generation。两个并发 Stop 只能有一个成功登记同一 fingerprint。deactivate/显式接管与 Hook 使用相同锁顺序，owner 指针只在 sidecar 成功提交后原子更新。

### 4.3 Stop Hook 决策

Hook 依次执行：

1. 校验 stdin 是 `Stop` 且含非空 session/turn/cwd；否则放行。
2. 由 `session_id` 的 SHA-256 定位唯一 owner 指针，再读取其 controller sidecar；缺失、歧义、路径或 generation 不匹配均放行，不扫描项目或全局 sidecar 集合。
3. 要求 Stop 的 `turn_id` 与 activate 时保存的 `activation turn` 完全一致。不同 turn 表示上轮在首次 Stop 前中断/崩溃或已经结束：仅关闭仍匹配的旧 generation并放行，绝不把新 turn 绑定给旧 activation。
4. 调用 `continuation inspect`。任何异常、超时、非零退出、非法 JSON 或 `ALLOW_STOP` 都关闭 sidecar并放行。
5. 若 fingerprint 已提醒过，说明上次提醒后没有可观察进展：关闭 sidecar并放行。
6. 若总预算已达上限，关闭 sidecar并放行。
7. 原子记录 fingerprint 与计数，输出一次 `decision:block`。reason 只要求重新读取 controller、执行当前授权范围内下一安全动作、在等待/阻塞/完成时登记并停止；不得携带新的业务指令。

“同一 fingerprint 最多一次”比固定连续四次更重要：一个懒惰或卡死的 Agent 最多被提醒一次；只有 controller 的真实可观察动作变化，才可消费下一次预算。`stop_hook_active=true` 时仍执行相同规则，它不是无限续跑许可。

### 4.4 Goal 的定位

保留现有 Runtime Goal 流程，但修改文字边界：

- Goal 是长期业务结果，例如“完成 BCS-xxx 既定范围并得到集成证据”，可跨阶段、压缩和恢复。
- Flow 主循环负责正常阶段承接。
- Stop Hook 仅保护一个已激活的人类轮次，不负责达成 Goal，也不因 Goal active 自动激活。
- Goal blocked/paused/预算限制优先；root 在进入该状态前关闭 Hook。即使遗漏关闭，Hook 最多提醒一次同 fingerprint，随后放行。
- Hook 激活、generation 或 budget 重置不重置 Goal token/时间使用量，不创建新 Goal，也不能替换冲突 Goal。

`exp-run` 继续采用已设计的独立实验 Goal：讨论完成并由人类确认后，Goal 覆盖数据摘取、多轮实验、评测和报告。本次不为 `exp-run` 安装 Stop Hook。

## 5. 会话、并发与生命周期

- **根会话限定**：注册 `UserPromptSubmit` marker 和 `Stop` continuation，不注册 `SubagentStop`。UserPromptSubmit 永不激活或阻止普通提示；subagent 完成和等待仍由根 Agent 的现有 300 秒轮询策略管理。
- **一个 controller 一个 owner**：同一 sidecar 同时只有一个 owner session。其他 session 的 Stop 无条件放行。
- **不做 TTL 抢占**：时间经过不能证明旧 session 已死。另一 session 显式运行同一 `$dev-run` 时，如发现 active owner 冲突，显示旧/新 session 和 controller，要求一次明确接管；接管创建新 generation，不继承旧预算。
- **中断**：Codex `Interrupt` 不触发 Stop。activation 已绑定原 turn；残留 sidecar 遇到下一不同 turn 时自动关闭并放行。崩溃同理，不依赖 Interrupt 清理。
- **压缩**：同一活跃 turn 的 compact 不改变 sidecar 所有权；Codex 0.155.0 已满足 AWS 指出的 compact-source SessionStart 修复版本下限。本设计不额外注册 SessionStart。
- **恢复**：干净停止时 sidecar 已关闭；恢复后只有新的显式 `$dev-run` 可以重新激活。controller 与 Goal 继续按现有恢复协议处理。
- **后台工作**：inspect 仍可返回 actionable，但 reason 要求检查已有 coder/reviewer handle并等待/复用，禁止仅因提醒启动 replacement。若 controller 无可观察进展，第二次 Stop 会因相同 fingerprint 放行。

## 6. 安装与信任

仓库增加幂等安装 helper，负责：

1. 把 continuation helper 与 controller 包同步到 `~/.codex/flow-v2/`。
2. 读取现有 `~/.codex/hooks.json`，只合并本工作流拥有的精确 `UserPromptSubmit` 与 `Stop` command handler，保留现有 `SessionStart` 和其他用户 Hook；不自动迁移用户已有的内联 Hook。
3. 重复安装不产生重复 handler；升级只替换本工作流拥有的 handler。
4. 写前保存可恢复备份，原文件非法 JSON 时拒绝覆盖并给出可读修复说明。
5. 只读检查 `~/.codex/config.toml` 是否已有非 trust-state 的内联 Hook；若存在仍保留双方配置并明确提示 Codex 会合并且可能警告，不声称通过新增 hooks.json 消除了同层双配置。不自动修改 `[hooks.state]` 或伪造信任。安装后明确提示用户在新 Codex 会话运行 `/hooks`，审阅并信任发生变化的 Hook 定义。

Hook command 使用已安装脚本的绝对路径和短超时。全局 Stop Hook 在没有 active owner 指针时只做按 session 定位的有限次固定文件读取；不得扫描项目或 runtime 目录，也不调用 flowctl。UserPromptSubmit 只更新当前 session 的无正文 turn marker。

## 7. dev-run 协议变化

`dev-run/SKILL.md` 增加“Continuation activation”段：

1. 保持当前 controller admission、Goal 核对和授权逻辑不变。
2. 在即将进入可自动执行的阶段循环前，用真实根 session ID 激活 continuation。helper 还必须从已发生的 UserPromptSubmit marker 核实当前 turn；无法核实时不激活。session 优先使用宿主 Goal/thread 返回；仅在能够核实等价 thread identity 时使用宿主环境值，不猜测。
3. 每次 child handoff 后仍由根 Agent立即执行下一阶段；不得等待 Hook。
4. 在人工 gate、业务/安全 blocked、Goal pause/budget limit、Flow complete 或本轮明确停止前先 deactivate，再输出人类可读说明。
5. helper 不存在、Hook 未信任、激活失败或 inspect 错误只降低“防意外停顿”保证，不构成业务 BLOCKED；同轮次主循环继续可执行工作并一次性披露缺口。

不新增 Flow 状态/结果枚举，不把 Hook receipt 加入 artifact 或 handoff 必填字段，不要求旧运行补历史 sidecar。

## 8. 安全与故障处理

- 默认 fail-open：任何不能确定“应继续”的情况都允许停止。
- Hook 不读取或回显 prompt/transcript；不使用 `last_assistant_message` 做语义判断。
- Hook 不访问网络、不调用模型、不执行项目脚本、不写 worktree。
- reason 是 on-task 提醒，不是越权提示；它明确服从现有用户、Flow、Goal、沙箱及权限约束。
- Hook 写 sidecar 失败时不返回 block；inspect 若意外产生文件，测试视为阻断缺陷。
- controller sidecar path 由 controller 绝对路径 SHA-256 得到；turn/owner path 由 session ID SHA-256 得到。读取后分别核对内含原始 session、canonical controller/worktree 和 generation，防止碰撞或路径替换。
- 对符号链接、非普通 controller、超大/非法 JSON、未知 schema、owner/cwd 歧义全部放行。
- 安装器不得删除、重排或覆盖不属于本工作流的 Hook。

## 9. 测试与验收

采用 TDD，至少覆盖：

1. inspect 对 actionable、route-back、human gate、blocked、complete、空/未知动作的分类。
2. inspect 前后 controller bytes、mtime、目录清单一致，不创建 lock/transaction/event/sidecar。
3. 相同 fingerprint 只 block 一次；progress 改变后可再次 block；总数达到 4 后放行。
4. 不同 session、不同 turn、失效 generation、损坏 marker/owner/sidecar、inspect 超时/错误全部放行。必须覆盖：T1 activate 后在首次 Stop 前 Interrupt/崩溃，随后同 session 的 T2 普通问答更新 turn marker；T2 Stop 不得 block，并关闭旧 generation。
5. Hook 不读取 prompt/assistant/transcript，不写 worktree；reason 不包含新的业务动作。
6. owner 冲突不自动接管；显式接管产生新 generation 且不继承预算。覆盖 inspect 与 deactivate/takeover、两个 Stop 交错时的重读校验，旧 Hook 不得覆盖新 generation或重复登记 fingerprint。
7. hooks.json 合并保留已有 SessionStart/其他 handler，重复安装幂等，非法 JSON 不覆盖；已有内联 Hook 时不修改 config.toml并准确提示合并警告。
8. dev-run contract 明确主循环优先、Goal 长期化、Stop Hook 降级不阻塞、各终态 deactivate。
9. 全量 workflow-v2 测试保持通过。

可执行验收场景：同一 UserPromptSubmit turn 内，在临时 controller 上激活后，模型若在 `produce:spec` 停止，Hook 提醒一次；Agent 完成交接使 fingerprint 变为 `produce:plan` 后可再提醒；若 Agent 只重复说明而 controller 不变，第二次 Stop 直接结束；人工 gate、blocked 或 complete 第一次 Stop 就结束。若 activate 后在首次 Stop 前中断或崩溃，下一普通 turn 即使 session/cwd/controller 相同也必须直接结束，不能继承旧 activation。

## 10. 文件范围与迁移

预计只涉及：

- `workflow-v2/flowctl_lib/continuation.py`
- `workflow-v2/flowctl_lib/cli.py`
- `workflow-v2/continuation_hook.py`
- `workflow-v2/scripts/install_codex_hooks.py`
- `workflow-v2/skills/dev-run/SKILL.md`
- `workflow-v2/README.md` 与必要 contract
- 对应单元/契约测试

不修改现有业务 controller 文件、artifact schema、review runner、Goal host API 或 `exp-run`。旧 controller 无迁移；未安装/未信任 Hook 时行为与当前版本一致。卸载只删除本工作流拥有的 UserPromptSubmit/Stop handler、helper 和非活跃 runtime marker/owner/sidecar，保留其他用户 Hook；任何批量清理必须显式执行而非安装时隐含发生。

## 11. 已知限制

Hook 不能保证模型一定执行正确动作，也不能在同一 fingerprint 上无限纠正。它不感知宿主 Goal 的实时状态、不恢复崩溃进程、不唤醒已经干净结束的历史轮次。四次总预算只是防止一次 Flow 交接链被偶发提前结束；长任务仍依靠根 Agent 主循环与长期 Goal。

当 Agent 忘记登记人工等待/阻塞时，Hook 可能额外提醒一次；相同 fingerprint 保护会随后释放。选择这一偏差，是为了避免 Hook 成为新的全局阻塞器。

## 12. 下一步

人类审阅并批准本文后，使用 `writing-plans` 编写实施计划；随后按 TDD 实现、运行全量测试，再提交 Astra/medium 进行实现复审。全局 Hook 安装与信任属于部署步骤，不在单元测试中隐式修改 `~/.codex/hooks.json`。

## 13. Astra 设计审查记录

首轮配置：`profile=design`、`backend=subagent`、`model=gpt-6-astra`、`effort=medium`。审阅 r1 SHA-256 为 `15d2833261c390145e702ddff558376b0f14ad9754e4104f8ed40d9155579571`，只读审查，未修改文件。

| Finding | r2 处置 |
|---|---|
| F-01 activation 在首次 Stop 才绑定 turn，首次 Stop 前中断会污染下一普通轮次（blocking） | 新增无正文 `UserPromptSubmit` turn marker；activate 必须在当前 turn 内读取并绑定，Stop 只接受完全相同 turn，无法核实则不激活；增加中断/崩溃负向验收 |
| F-02 inspect 与 takeover/deactivate 存在 generation 交错窗口 | 明确稳定 controller lock、inspect 锁外观察、提交前锁内重读 owner/generation/turn/fingerprint/budget；不匹配只放行且不写新 generation |
| F-03 已有 inline Hook 与 hooks.json 仍可能产生宿主合并警告 | 安装器只读检测并披露警告，不迁移或覆盖 config.toml，不再承诺仅新增 hooks.json 即消除警告 |
| F-04 按全局目录扫描 sidecar 与常数级 no-op 矛盾 | 新增按 session hash 定位的 owner 指针；Stop 只做固定文件读取，不扫描 runtime 或项目目录 |

r2 定向复审范围限定为 F-01 的 turn 身份来源和首次 Stop 前中断反例，并确认 F-02 至 F-04 的处置没有新增平台化边界。复审 SHA-256 为 `0791b9df26a476d49ef7e3c0a54c5498d40bbfc918c8556ee4844e7cf2f36a84`；结论为 F-01 已解决、无新增阻塞、可以进入正式 Spec。该 SHA 对应本段状态回填前的完整 r2，规则正文未再修改。设计审查通过不等于实现或测试通过。
