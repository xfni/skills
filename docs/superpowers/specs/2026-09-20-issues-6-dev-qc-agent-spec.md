# Issue 6：dev_qc 质量协调 Agent Spec

版本：Spec r2，2026-09-20。状态：人类已批准；实施与针对性修复已通过 Astra/medium 独立复核。

上游设计：[Issue 6 长期 dev_qc 质量协调 Agent 设计 r1](2026-09-20-issues-6-dev-qc-agent-design.md)。本文定义第一批可交付行为；背景和后续阶段设想保留在上游设计中。

## 1. 交付范围

第一批建立一个 run-scoped 长期 `dev_qc` Agent 和通用协调契约，并将 Code 阶段现有 GPT/external 审查组织职责交给该 Agent。

交付内容：

1. `dev_qc` 自定义 Agent，使用 `gpt-5.6-luna/high`。
2. 一份精简 QC 协调 Skill，定义长期协调、一层专项委派、clean-room reviewer、finding 所有权和可重建 Ledger。
3. `dev-run`/orchestration 对 QC 按需创建、复用、播报、恢复和替换的约定。
4. `dev-code` 改为由 Root 向 QC 提交核查请求，由 QC 组织真实 GPT 与 external 通道，Root 仍掌握冻结、修复派发和 handoff。
5. 可重建 QC Ledger 的最小文档契约。
6. 契约测试与必要的行为测试。

不在范围：迁移 Spec/Plan 的审查协调；为 Requirement/Intent/Roadmap/Integration 新增默认独立审查；新增 QC 审批；新增完整 QC 控制器状态机；修改现有两条保证链政策；更改 Cursor/iBrain runner、review package 或生产数据政策。

## 2. 术语与不变量

- **QC Agent**：`dev_qc`，负责组织质量核查，不是独立审查证据来源。
- **QCRequest**：Root 向 QC 发送的当前核查对象、授权边界、证据和历史线索引用。
- **QCCheckpoint**：QC 返回的收据引用、finding 处置建议、修复建议、缺口和下一动作建议。
- **Specialist Reviewer**：QC 派生的一次性、只读、不可再委派的独立 GPT Reviewer。
- **External runner**：通过现有 `flowctl review cursor/ibrain` 执行的外部审查。
- **QC Ledger**：跨核查点的可重建线索索引，不是 Flow 事实源。

必须始终满足：

- INV-01：QC 的摘要、归并或 `handoff_candidate` 不计入 GPT/external 独立保证。
- INV-02：专项 Reviewer 必须从当前冻结对象和原始证据入口独立核查。
- INV-03：QC Ledger 不存储第二套阶段状态、审批、PASS/FAILED、评审预算或调度状态机。
- INV-04：Sol/Astra 始终只能提供一条 GPT lane；Cursor/iBrain 始终只能提供一条 external lane。
- INV-05：Root 是修复任务、artifact 冻结和 handoff 的唯一协调者；QC 不直接命令 `dev_coder` 或阶段作者修改。
- INV-06：原始 finding、attempt、receipt 和证据不被 QC 改写、删除或降级。
- INV-07：QC 失联、Ledger 丢失或协调 Skill 不可用，都不会自动变成业务 BLOCKED。
- INV-08：新风险不自动转化为需求、验收条件、配置开关或平台化工作。

## 3. `dev_qc` Agent 配置

仓库必须提供一份可安装到 `~/.codex/agents/dev-qc.toml` 的 Agent 定义：

```toml
name = "dev_qc"
description = "Coordinate independent quality checks across one admitted Flow run."
model = "gpt-5.6-luna"
model_reasoning_effort = "high"
```

Agent developer instructions 必须规定：

1. 一个线程只绑定一个 `run_id + canonical admitted worktree`，不在 run 间复用。
2. 可跨该 run 的阶段和 milestone 长期存在；每次核查以新 QCRequest 为准。
3. 可一次派生一个 Specialist Reviewer，委派深度只有一层；必须使用 `fork_turns="none"` 或宿主等价的无历史继承机制，Specialist 必须禁止再委派。
4. 可通过现有 flowctl 命令触发 Cursor/iBrain runner，不直接运行 standalone adapter 绕过 binding/receipt。
5. 不编辑 worktree 业务源码、Requirement、Intent、Roadmap、Spec、Plan、Code 报告或 Integration 证据。
6. 不编辑 controller JSON，不接受 handoff，不生成审批或自造 receipt。
7. 只返回 QCCheckpoint 和必要的进度消息，不绕过 Root 向人类重复播报。
8. 不使用自身 Luna 结论解决阻断性争议、安全/数据损失/并发/兼容风险或跨契约矛盾；这些问题交给 Sol/Astra 专项 Reviewer。

## 4. QC 协调 Skill

仓库必须增加一个短的显式调用 Skill，推荐名称 `dev-qc`。它是 `dev_qc` 的运行契约，不是另一个 Reviewer，不自动吸附所有普通开发任务。

Skill 必须：

- 要求 QCRequest 存在当前对象、授权边界和证据引用，但不要求 Root 复制控制器已有的全部 tuple。
- 根据现有 `independent-review` 定义 Specialist Reviewer packet，并保留其只读、不委派、证据核验和 finding-weight convergence 要求。`dev_qc` 自身使用 QC 协调 Skill，不把 `independent-review` 的 Reviewer 身份套在协调者身上。
- 专项 Reviewer 必须以 `fork_turns="none"` 或等价 clean-room 方式创建；宿主不具备该能力时，Root 使用同一精简 packet 组织实际 Reviewer，QC 自评仍不计票。
- 区分 GPT lane 和 external lane，并沿用 `review-contract.md` 的最小独立保证和降级规则。
- 保留原 finding ID、attempt/receipt 引用和 `recurrence_key`；归并只影响展示和修复建议。
- 生成修复建议时指定 owner stage、受影响范围和必需验证，不直接修改任务。
- 在原 Reviewer 不可用时，要求接管 Reviewer 显式处置原未解决 findings，不允许普通 PASS 自动关闭。
- 当线索与当前需求缺少关联时，标记为非阻断建议或 Scope Delta，不扩大 coder 范围。
- 当原始证据与 QC 建议冲突时，显示冲突并以原始事实为准。

## 5. QCRequest 契约

QCRequest 至少包含：

```yaml
schema_version: 1
request_id: QC-<stable-id>
run_ref: <controller/run reference>
stage: <current Flow stage>
current_object_ref: <artifact/snapshot/binding reference>
authorized_boundary_ref: <Requirement/Intent/Spec/Plan scope reference>
quality_contract_refs: [<applicable contracts>]
changed_boundary: <current changed/reviewed scope>
evidence_refs: [<raw evidence entry points>]
carryover_refs: [<unresolved source refs>]
route_constraints: [<actual model/backend/host constraints>]
```

规则：

- RULE-REQ-01：`current_object_ref` 必须指向当前冻结对象，不接受 QC 自行选择的旧版本。
- RULE-REQ-02：`evidence_refs` 提供原始证据入口；Root/QC 摘要只是导航，不能是唯一证据。
- RULE-REQ-03：初审 packet 不携带其他 Reviewer 的 PASS 作为结论导向；复核/接管 packet 必须携带原 findings、修复差异和未解决集合。
- RULE-REQ-04：未知、不可读或与当前 binding 不符的引用不得被 QC 推测成已通过事实。

## 6. QCCheckpoint 契约

QCCheckpoint 至少包含：

```yaml
schema_version: 1
request_ref: QC-<stable-id>
checked_object_ref: <same current object or explicit newer binding>
receipt_or_evidence_refs: [...]
open_question_refs: [...]
repair_proposals:
  - owner_stage: flow-code
    affected_scope: [...]
    required_verification: [...]
route_back_proposals: [...]
missing_assurance: [...]
ledger_delta: [...]
suggested_next_action: repair | rereview | route_back | handoff_candidate
reason: <short explanation>
```

规则：

- RULE-CP-01：Checkpoint 必须引用真实 receipt/evidence，不得包含 QC 自造 PASS。
- RULE-CP-02：`checked_object_ref` 发生漂移时，旧报告不得重绑到新对象。
- RULE-CP-03：`repair_proposals` 只是建议。Root 核对授权与范围后才能向修改所有者派发。
- RULE-CP-04：`handoff_candidate` 只表示建议 Root 重读 controller 与原始证据，不是 handoff 或审批。
- RULE-CP-05：finding 展示归并必须保留每个原 finding ID、原 attempt/receipt 和 evidence refs。
- RULE-CP-06：非门禁专项 Reviewer 不可用时，只记录未确认范围；已有具体验收风险仍按实际证据处理。

## 7. QC Ledger 契约

Ledger 固定保存为 `<controller-dir>/reviews/qc-ledger.yaml`，使用现有 `review_workspace._bookkeeping()` 已排除的 `reviews/` 子树。它不是 Requirement/Intent/Roadmap/Spec/Plan/Code BODY，不参与这些产出物的 digest，也不得通过扩大整个 `.ai` 目录的排除范围实现。第一版只有 Root 可以根据 QCCheckpoint 写入该文件；QC 只返回 `ledger_delta`，不写文件。Ledger 不得覆盖、重命名或删除同目录的原始 review 报告。

最小结构：

```yaml
schema_version: 1
run_ref: ...
items:
  - id: QC-...
    source_ref: ...
    last_checked_object_ref: ...
    carry_to: [flow-plan, flow-code]
    question: ...
    resolution_ref: null
```

- RULE-LEDGER-01：`source_ref` 是原始 finding、人类决定或证据的引用；无 source 的 item 不允许写入。
- RULE-LEDGER-02：`carry_to` 是建议核查位置，不是 controller pending action 或 handoff 依赖。
- RULE-LEDGER-03：`resolution_ref` 只指向已存在的处置/复核证据，不复制其 PASS/FAILED 或解释。
- RULE-LEDGER-04：Ledger 不存储原始报告副本、完整对话、生产数据、凭证、隐含推理或无出处的“已验证”。
- RULE-LEDGER-05：Ledger 缺失、损坏或与原始证据冲突时，Root/QC 以原始事实为准并可重建，不生成人类门或 BUSINESS BLOCKED。
- RULE-LEDGER-06：使用现有 `capture_review_snapshot`/`verify_review_snapshot` 的测试必须证明 Ledger 创建、更新和删除均不改变 source snapshot，同时普通源码变更仍产生 `REVIEW_WORKTREE_MUTATED`。

## 8. Code 阶段协调

### 8.1 启动

Code 的 TASK-* 与单测完成、Root 核对里程碑并冻结当前 Code snapshot 后：

1. Root 查找同一 run/worktree 已绑定的 `dev_qc`。
2. 无线程时懒创建 `dev_qc`；已存在且可用时复用。
3. Root 提交包含 Code snapshot/binding、Plan/Spec 范围、单测证据、排除项、路由约束和未解决线索的 QCRequest。
4. QC 首先组织 GPT lane，再根据现有 review contract 组织 external lane；不为同一 lane 默认并行多个重复 Reviewer。

### 8.2 GPT lane

- Root/QC 仍按复杂度选择 Sol/high 或 Astra/medium，选中模型以一次性 Specialist Reviewer 执行。
- Specialist 使用 `independent-review` 的 implementation 或 concurrency profile，不可委派。
- QC 不使用自身 Luna 报告充当 GPT lane。
- Sol/Astra 真实不可用时可互换，但不产生第二条 GPT 保证，也不重置未解决 finding。

### 8.3 External lane

- Cursor 与 iBrain 继续通过现有 frozen review binding 和 `flowctl review cursor/ibrain` 执行。
- 人类已选 iBrain 或已有真实路由限制时，QC 不制造 Cursor 失败额度。
- Cursor/iBrain 是同一 external lane 的候选后端，不将两者 receipt 重复计票。
- 真实 runner/protocol 失败、重试与单链降级沿用现有 `review-contract.md` 和 controller 规则，QC 不维护另一套计数。

### 8.4 Finding 修复

1. QC 保留原报告和 finding 引用，生成绑定 TASK/AC/文件范围的 repair proposal。
2. Root 校验建议没有扩大授权边界，然后将已接受的修复交回同一 `dev_coder`。
3. Coder 修复并返回单测/差异证据；Root 核对实际 worktree 并冻结新 snapshot。
4. QC 使用原 Reviewer 组织复核；原 Reviewer 不可用时，接管者获得全部未解决 findings 并显式处置。
5. 修复造成的新 binding 必须由控制器重新绑定，旧 PASS 不自动携带。

### 8.5 结束

QC 只在当前对象存在现有契约要求的有效 receipt、已知 blocker 全部得到独立处置，且缺失 lane 已按现有政策记录时，返回 `handoff_candidate`。Root 重读 controller 后决定 approve/register/handoff。

## 9. 跨阶段线索与 Scope Delta

- RULE-SCOPE-01：Ledger 传递“问题 + source_ref + 待验证条件”，不传递自动新需求。
- RULE-SCOPE-02：风险只在直接影响已批准 AC/安全边界、证明方案不可实现，或是已选方案必然引入的回归/损失/安全/兼容问题时，才能要求当前阶段处理。
- RULE-SCOPE-03：只为未来扩展、架构对称或假设消费者提供的变更必须作为非阻断建议或 Scope Delta，不进入 coder 任务。
- RULE-SCOPE-04：关闭证据层级必须与问题相匹配；代码分支不能单独关闭端到端能力风险，Reviewer PASS 不能替代 Integration 真实执行。

## 10. 生命周期与恢复

- RULE-LIFE-01：`dev_qc` 在第一个真实核查点懒创建，不在新 Codex 会话启动时预创建。
- RULE-LIFE-02：Root 复用与当前 run/worktree 匹配的可用 QC，不因 Agent idle/completed 标记就新建替代线程。
- RULE-LIFE-03：等待超时和暂时没有输出不是替换证据。确认线程终止/不存在/无法继续后才能替换。
- RULE-LIFE-04：替代 QC 必须获得当前 controller facts、有效 receipts、未解决 findings 和 Ledger 线索；旧 receipt 不因协调线程更换而失效或重跑。
- RULE-LIFE-05：QC 不可用时 Root 可临时执行相同协调，但 Root 自评不能变成独立 receipt。
- RULE-LIFE-06：Flow complete、显式放弃、run/worktree 绑定失效时关闭 QC；普通阶段交接不关闭。

Root 可以保存 `thread_id`/`generation`/`last_checkpoint_ref` 作为恢复提示。第一批不要求控制器为它新建强制命令或校验；任何新增 controller 字段都必须是可选观察信息，不影响 resume/handoff。

## 11. 并发与进度

- RULE-CONC-01：QC 同一时刻最多派生一个 Specialist Reviewer；更多 Agent 槽位不是默认并行多审的理由。
- RULE-CONC-02：根 Agent 对人播报当前核查标识、已验证结果、下一动作、正在等待的 Agent 和是否存在阻断缺口；QC 不另向人类发送重复播报。
- RULE-CONC-03：Specialist/QC 完成或发送消息时 Root 立即处理；定时等待超时只触发检查和有界非中断询问。
- RULE-CONC-04：已有 Reviewer 运行时不得因 snapshot 修复并行修改后将晚到报告当成新版本证据；Root 修复前确认当前 attempt 终态或可隔离。

## 12. 失败与降级

- RULE-FAIL-01：实质 FAILED 保持 finding，不能被 QC 重分类为运行不可用。
- RULE-FAIL-02：通道运行错误、重试和降级以现有 controller receipt/budget 为准，QC 不另行计数。
- RULE-FAIL-03：至少一条真实独立保证仍是 Spec/Plan/Code 现有最低线；单链完成仍为有条件通过并记录 durable gap。
- RULE-FAIL-04：零有效保证不能因 QC 综述、Root 自检或测试通过而推进。
- RULE-FAIL-05：QC 自身不可用优先 Root 临时协调/恢复，不要求人类理解内部线程 ID 或编辑状态。

## 13. 验收条件

- AC-01：仓库包含 `dev_qc` TOML，其模型为 Luna、effort 为 high，且明确允许一层 Specialist 委派、禁止 Specialist 再委派。
- AC-02：`dev-qc` Skill 明确三条硬边界、两条保证链、不编辑产出物/控制器、Root 仍掌握修复和 handoff。
- AC-03：指令契约测试验证 QCRequest/QCCheckpoint、`handoff_candidate` 非 receipt 和 clean-room 派生规则已写入 Skill/Agent；该测试不宣称证明真实模型必然服从。
- AC-04：指令契约测试验证 QC Ledger 的可重建/非状态机规则；真实 snapshot 函数测试验证 `<controller-dir>/reviews/qc-ledger.yaml` 创建、更新和删除不引起 source drift，且普通源码变更仍被拒绝。
- AC-05：`dev-code` 明确审查通过长期 QC 组织，自身 Luna 不计入 GPT lane，真实 GPT/external receipt 仍由现有 flowctl 绑定。
- AC-06：Code finding 修复仍由 Root 发回同一 coder；QC 不直接修改或派发。
- AC-07：原 Reviewer 复核和不可用后接管都保留未解决 finding 与真实 receipt，替换线程/模型/快照不重置问题。
- AC-08：Cursor 不可用转 iBrain 仍只是 external lane；显式 iBrain 路由不制造 Cursor 失败。
- AC-09：QC 恢复/替换复用有效 receipt，等待超时不替换，QC 不可用时 Root 可临时协调。
- AC-10：新风险如无当前需求/验收/安全证据，被保留为非阻断线索或 Scope Delta，不生成新配置/平台化任务。
- AC-11：Requirement/Intent/Roadmap/Integration 不因安装 QC 增加新独立 PASS 门，Integration 真实证据契约不变。
- AC-12：Spec/Plan 现有审查语义本批不迁移，仅通过共享接口设计保证后续可迁移。
- AC-13：QC 默认同时只派生一个 Specialist，Root 按现有进度播报规则向人类说明正在等待的对象和下一动作。
- AC-14：现有 workflow-v2 全量测试保持通过，新测试不调用真实 Cursor/iBrain/模型，不修改 `~/.codex`。

验收证据分为三类：指令文本测试只证明契约存在；现有 controller/snapshot 单测证明机械约束；离线场景走查证明 packet/checkpoint 按 Spec 处置典型输入。离线走查不宣称证明真实模型服从性，本批不建设新的模型测试平台。

## 14. 预期文件边界

预期修改/新增：

- `workflow-v2/skills/dev-qc/SKILL.md`
- `workflow-v2/skills/dev-qc/agents/openai.yaml`
- `workflow-v2/skills/dev-qc/agents/dev-qc.toml` 或等价的单一 Agent 源文件
- `workflow-v2/skills/dev-code/SKILL.md`
- `workflow-v2/skills/dev-run/SKILL.md`
- `workflow-v2/orchestration-contract.md`
- `workflow-v2/review-contract.md` 仅在需要补充 coordinator/reviewer 角色边界时修改
- `workflow-v2/README.md`
- `workflow-v2/tests/test_workflow.py`
- 必要时新增窄的 QC 契约测试

如实施必须修改 review runner、review package、controller progression/review state machine、Requirement/Intent/Roadmap/Integration 门禁或生产数据策略，必须停止并作为 Scope Delta 返回人类。

## 15. 审查与下一步

本 Spec 必须先由 `gpt-6-astra/medium` 按 design profile 独立核验，重点检查：QC 与 Reviewer 独立性、长期上下文污染、Ledger 第二控制器风险、Code 审查迁移的所有权、恢复/接管和 AC 可执行性。Astra finding 修复并复核后，再由人类批准 Spec。

人类批准后使用 `writing-plans` 编写实施计划；本次已获实施授权并完成编码与回归，但该授权仍不包含全局 Codex 部署或 Git 提交/推送。

### Astra 首轮审阅处置

- `QC-DES-001`（BLOCKING）：Ledger 固定到 `<controller-dir>/reviews/qc-ledger.yaml`，只由 Root 写入，禁止覆盖原始报告；增加真实 snapshot 函数级创建/更新/删除与源码变更对照验收。
- `QC-DES-002`（NON_BLOCKING）：明确区分指令文本、机械函数和离线场景走查三类证据，不将 `assertIn` 宣称为真实模型行为证明。
- `QC-DES-003`（NON_BLOCKING）：明确 QC 使用协调 Skill，Specialist 才使用 `independent-review`；Specialist 以 `fork_turns="none"` 或等价 clean-room 机制创建。

定向复核针对 SHA-256 `e0bc59c752be73ade84506b20acc282594e9ec029c5f5ddb0b04f53ad7a67a31`，结论为 PASS：三项 finding 全部关闭，无新增实质 finding，可提交人类批准并在批准后进入 Plan。当前仅追加版本/审阅元数据，未改变已复核的行为契约。
