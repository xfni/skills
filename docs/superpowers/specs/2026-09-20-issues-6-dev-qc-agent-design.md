# Issue 6：长期 dev_qc 质量协调 Agent 设计

版本：设计 r1，2026-09-20。状态：人工审阅中，尚未实施。

## 1. 背景与目标

Flow v2 已经对 Spec、Plan 和 Code 实行 GPT 与外部通道审查，但审查路由、finding 归并、修复派发、原 reviewer 复核和降级说明分散在根 Agent 及多个阶段 Skill 中。随着产出物核查点增加，根 Agent 需要持续携带过多审查细节，也容易在跨阶段恢复时丢失未解决问题。

本设计新增一个在单次 Flow run 内长期存在的 `dev_qc` Agent。它负责质量核查计划、专项 Reviewer 派生、finding 归并、复核组织和跨阶段线索传递。它不是独立审查证据来源，不审批 Flow，不修改业务产出物，不替代控制器。

成功标准：

1. 对外形成 `dev_coder` 与 `dev_qc` 两个稳定角色：前者实现，后者组织核查。
2. `dev_qc` 可在同一 run 的不同阶段中复用，又不把旧推断当成当前事实。
3. 每个专项 Reviewer 都基于当前冻结对象独立核查，初审不继承其他 Reviewer 的结论。
4. QC 的协调结论不计入独立保证，不重复计数 Sol/Astra 或 Cursor/iBrain。
5. QC Ledger 只是可重建的索引，不新增状态机、审批、预算或推进门。
6. 第一批只迁移 Code 审查协调；其他阶段保留现有语义，为后续复用预留窄接口。

非目标：建立通用审批平台；为每个阶段新增强制审查；让 QC 代替 Root 推进 Flow；让 QC 直接修改代码、Spec 或 Plan；重写当前 review controller；把四个后端计为四票；为未经验证的未来核查点预建插件平台。

## 2. 不可突破的三条边界

### 2.1 QC 结论不是独立审查证据

`dev_qc` 可以提议 finding 归并、修复归属、route-back、接管或降级，但不能输出一份被计为 GPT 或 external PASS 的报告。控制器只认实际 Reviewer/runner 产生并与当前对象绑定的 receipt。

### 2.2 专项 Reviewer 从当前冻结对象独立开始

Reviewer 使用一次性、只读、不可继续委派的 clean-room 任务包。任务包可提供定位线索，但不得把 Root 或 QC 摘要当成原始证据。复核可额外获得原 finding、修复差异和未解决集合，但仍要检查当前对象。

### 2.3 QC Ledger 不是第二控制器

Ledger 只指向原始 finding、人类决定、产出物和处置证据。它不保存另一套 PASS/FAILED、阶段状态、审批、评审预算、调度 DAG、锁、租约或重试引擎。Ledger 丢失时从现有事实重建，不能使 Flow 停下等待人类解锁。

## 3. 角色和权限

| 角色 | 负责 | 不负责 |
| --- | --- | --- |
| Root Agent | 阶段调度、授权边界、修复任务绑定、争议处置、artifact 冻结、handoff | 伪造或豁免独立保证 |
| Controller | 对象身份、digest/snapshot/binding、attempt、receipt、有限预算、漂移检查、原子接受 | 业务正确性和 finding 语义裁决 |
| 阶段 Agent / `dev_coder` | 创作、修复、执行真实测试 | 证明自己的产出物独立审查通过 |
| `dev_qc` | 核查计划、通道路由、专项派发、finding 归并、复核组织、跨阶段线索、缺口说明 | 写业务产出物、审批、自造 PASS、直接推进 handoff |
| 专项 Reviewer | 根据冻结对象独立核查和复核 | 修改 worktree、再委派、自动扩大需求 |

`dev_qc` 可以使用既有 `flowctl review` 命令完成绑定和 runner 执行，但不能直接编辑 controller JSON。artifact 注册、Code snapshot 推进、修复派发和 handoff 仍归 Root。

## 4. 两条保证链和四个后端

标准审查仍是两条保证链：

| 保证链 | 可用后端 | 计数原则 |
| --- | --- | --- |
| GPT lane | `gpt-5.6-sol/high` 或 `gpt-6-astra/medium` | 替换、重试、接管仍属于一条 GPT 保证 |
| External lane | Cursor 或 iBrain | 回退、接管仍属于一条 external 保证 |

Sol + Astra 不等于 GPT + external，Cursor + iBrain 也不产生两条独立保证。原 reviewer 默认拥有自己的 finding 复核；它真实不可用时，接管者必须获得原报告、未解决 ledger、修复差异和当前证据，并显式处置原 findings。

## 5. dev_qc 生命周期

### 5.1 创建与复用

`dev_qc` 按需创建，不在 Codex 会话启动时预启动。第一个真实核查点到达后，Root 创建一个与 `run_id + admitted worktree` 绑定的 QC 线程。同一 run 的阶段和 milestone 可复用它；不同 run 不共用。

推荐配置：

```toml
name = "dev_qc"
description = "Coordinate independent quality checks across one admitted Flow run."
model = "gpt-5.6-luna"
model_reasoning_effort = "high"
```

Luna/high 只承担结构化协调。对 finding 阻断性争议、安全/兼容/数据损失/并发风险、跨阶段契约矛盾和难以判断的 route-back，QC 应派生 Sol/Astra 专项 Reviewer，不自行得出权威结论。

### 5.2 恢复与替换

线程只是工作上下文，不是事实库。可选恢复提示只需：

```yaml
qc_agent:
  thread_id: ...
  generation: 1
  last_checkpoint_ref: ...
```

这些字段不能成为推进门。等待超时不证明线程不可用。确认失联后，Root 根据当前 controller receipt、产出物和 QC Ledger 创建替代 QC。已有有效审查不重跑，finding、预算和宿主限制不重置。

QC 自身不可用时，Root 可临时按同一契约组织审查；Root 自检仍不算独立保证。QC 不可用本身不应成为业务 Flow 的永久 blocker。

## 6. 阶段切换和 clean-room Reviewer

Root 每次调用 QC 时提供新的 `QCRequest`。阶段切换时，QC 明确整理：

1. 当前核查对象。
2. 由当前证据重新确认的事实。
3. 需继续核查的历史问题。
4. 已失效或不适用的旧推断。

旧结论默认是导航线索，不是当前事实。专项 Reviewer 不继承 Root/QC 的完整对话，只接收：

- 当前冻结对象与只读入口；
- 已批准的目标、非目标和作用域；
- 本次核查问题与风险触发证据；
- 原始证据入口、覆盖限制和排除声明；
- 复核时的原报告、修复差异和未解决 finding。

专项 Reviewer 禁止继续委派。初审 packet 不能携带“前面已经通过，请确认”式的导向性结论。

## 7. 统一接口

### 7.1 QCRequest

```yaml
schema_version: 1
request_id: QC-...
run_ref: ...
stage: flow-spec | flow-plan | flow-code | ...
current_object_ref: ...
authorized_boundary_ref: ...
quality_contract_refs: [...]
changed_boundary: ...
evidence_refs: [...]
carryover_refs: [...]
route_constraints: [...]
```

Request 以控制器/产出物引用为主，不要求模型复制大量 digest 和历史 tuple。

### 7.2 QCCheckpoint

```yaml
schema_version: 1
request_ref: QC-...
checked_object_ref: ...
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
reason: ...
```

`handoff_candidate` 只是 QC 建议 Root 检查当前事实，不是审批 receipt。Root 只能依据 Checkpoint 引用的原始证据和现有契约推进。

## 8. Finding 所有权和修复闭环

一个 finding 有三类所有权：

- **发现与复核所有者**：产生 finding 的原 Reviewer。
- **处置组织者**：`dev_qc`，负责建议重复归并、影响范围和修复归属。
- **修改所有者**：Code 为 `dev_coder`；Spec/Plan 为对应阶段作者。

标准链路：

```text
原始报告 -> QC 归并建议 -> Root 确认任务范围
-> 所属作者修复 -> Root 验证并冻结新版本
-> QC 请求原 Reviewer 复核 -> Controller 保存真实 receipt
```

QC 可以建议一个 finding 为重复、非阻断或不成立，但不能删除原 ID、attempt 和证据。同一 `recurrence_key` 的展示归并不会把不同 Reviewer 的独立担忧自动关闭。

## 9. 可重建 QC Ledger

Ledger 固定保存为 `<controller-dir>/reviews/qc-ledger.yaml`，复用现有 frozen-review bookkeeping 排除子树，不放入 Spec/Plan/Code BODY，避免 QC 进度更新改变被审对象或触发源码漂移。第一版只由 Root 根据 QC Checkpoint 写入，不得覆盖同目录的原始 review 报告，不为它增加控制器命令或推进校验。实施必须用现有 snapshot 函数证明 Ledger 的创建、更新和删除不改变 source snapshot，同时普通源码变更仍会被检出。

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

`source_ref` 是事实来源；`question` 是短的待核查问题；`carry_to` 是建议核查位置，不是 handoff 依赖；`resolution_ref` 必须指向真实处置或复核证据。Ledger 与原始事实冲突时，以原始事实为准。

## 10. 跨阶段线索和范围控制

跨阶段传递的是“问题 + 来源 + 待验证条件”，不是新需求。

新发现的风险只有在下列任一条成立时才能影响当前验收范围：

1. 它直接影响已批准的目标、非目标、验收条件或安全边界。
2. 它提供了当前方案无法实现的具体证据。
3. 它是已选方案必然引入的回归、数据损失、安全或兼容性问题。

否则只能作为非阻断建议或 Scope Delta 交给人类，不能自动要求新建平台、开关、配置中心或抽象层。

问题关闭的证据层级必须匹配问题：静态实现问题可以由代码与单测关闭；端到端恢复能力需 Integration 证据；产品边界冲突需 route-back 或人类决定。

## 11. 阶段核查策略

长期 QC 不代表所有阶段都增加独立审查门：

| 阶段 | 默认 QC 工作 | 专项 Reviewer 触发 |
| --- | --- | --- |
| Requirement | 整理未决选择、授权边界和已有风险线索 | 具体事实冲突或高风险可行性问题 |
| Intent | 检查人类选择的目标/非目标是否保持 | 新解释改变验收含义 |
| Roadmap | 检查里程碑覆盖和依赖 | 跨系统、迁移顺序或不可逆风险 |
| Spec | 协调现有独立设计审查 | 安全、并发、兼容等专项范围 |
| Plan | 协调现有独立设计审查 | 可执行性、测试方法、资源或迁移风险 |
| Code | 协调现有 GPT + external 实现审查 | 实际变更触发的高风险专项核查 |
| Integration | 将实际证据与验收条件对照 | 证据矛盾、跨边界效果不明或重大运行风险 |

“至少一条有效独立保证”仍只适用于现有 Spec/Plan/Code 门槛。Integration 必须依靠真实 TESTCASE 执行、日志、审计、数据和业务结果；Reviewer PASS 不能替代未执行测试或消除已知失败。

## 12. 并发、等待和状态播报

建议 Codex 配置为每会话 8 个线程、派生深度 2。典型 Code 结构为 Root + `dev_coder` + `dev_qc` + 当前 GPT Reviewer。QC 默认一次只派生一个专项 Agent，不因为槽位增加就同时打开多个重复 Reviewer。

Root 负责对人播报；QC 只向 Root 返回结构化进度，避免两个协调者重复输出。Reviewer/QC 等待参考现有 coder 规则：完成消息应立即唤醒 Root；等待超时只触发状态检查和有界进度询问，不得因沉默自动替换线程。

## 13. 故障和降级

- **专项 Reviewer 不可用**：按允许路由选替代者。非门禁专项只记录未确认范围，不把“QC 想再看一眼”升级为 blocker。
- **Cursor/iBrain 不可用**：沿用现有真实失败、有限重试、合法回退和单链缺口规则。
- **QC 不可用**：Root 临时承担协调并恢复/替换 QC，不降低真实独立保证。
- **所有必需通道不可用**：不能完成对应门槛，返回准确缺失保证和可执行恢复动作。
- **QC 结论与原始证据冲突**：以原始证据为准；Root 可纠正 QC 归类，正式 blocker 由原 Reviewer 或接管者复核。
- **修复期间晚到报告**：控制器根据当前 binding 拒绝将旧报告重绑到新版本。

## 14. 第一批交付边界

第一批建立跨阶段薄骨架，但只迁移 Code 的真实协调职责：

1. 新增 `dev_qc` Agent 定义，固定 Luna/high，允许一层只读专项委派。
2. 新增简短 QC 协调 Skill/契约，定义 Request、Checkpoint、Ledger 和三条硬边界。
3. `dev-code` 改为由 Root 调用长期 QC；QC 组织 GPT lane、external lane、finding 归并和复核建议。
4. Root 仍是 coder 的唯一调度者，仍负责 artifact 冻结、实际变更验证和 handoff。
5. 控制器暂不增加 QC 状态机。如现有 coder-state 模式能以非门禁形式记录线程提示，可增加最小 `qc_agent` 观察字段；否则第一版仅保存在当前会话和 Ledger。
6. Spec/Plan 仅验证接口可复用，本批不迁移其审查语义；Requirement/Intent/Roadmap/Integration 不新增门。

后续迭代顺序：Code 稳定 -> Spec/Plan 迁移并删除重复规则 -> Requirement/Intent/Roadmap 接入轻量线索 -> Integration 接入证据差距分析。

## 15. 验收场景

第一批至少验证：

1. Code 正常 GPT + external 双链审查，QC 自身不产生 receipt。
2. GPT finding 返回原 coder 修复，新快照由原 GPT Reviewer 复核。
3. 原 Reviewer 真实不可用后，接管者显式处置原 findings。
4. Cursor 不可用后使用 iBrain，不伪造第二条 external 保证。
5. 合法单链降级产生持久缺口，零有效保证不推进。
6. 修复后 snapshot 漂移使旧报告失效，QC 不重绑旧 PASS。
7. QC 线程失联并恢复时复用有效 receipts，不重置 finding 和预算。
8. QC Ledger 丢失/损坏不阻断 Flow，且可从真实事实重建。
9. QC 把非必需配置/平台化风险转换为 Scope Delta，不直接扩大 coder 任务。
10. 一次只派生一个专项 Reviewer，并发槽不成为默认多审路由。

## 16. 已知风险

- Luna 归并 finding 出错：原报告与 ID 保留，归并只影响展示；高风险争议派生 Sol/Astra。
- 长期上下文污染：阶段切换重新提供 `QCRequest`，专项 Reviewer 使用 clean-room packet。
- QC 成为单点：Root 可临时协调，Ledger 可重建，线程提示不是门。
- Ledger 膨胀：只允许短问题和原始引用，禁止报告副本、状态机和无出处结论。
- 两个协调者反复沟通：Root 对人播报，QC 只返回结构化 Checkpoint。
- 过度核查：只保留现有 Spec/Plan/Code 门禁；额外专项必须有未被当前核查覆盖的具体问题。

## 17. 下一步

人类审阅并批准本设计后，书写行为 Spec，明确 `dev_qc` Agent 约束、QCRequest/QCCheckpoint/Ledger 契约、Code 审查协调迁移和恢复行为；Spec 再经 Astra/medium 定向审查。批准 Spec 后使用 `writing-plans` 编写实施计划，随后按 TDD 实现并运行全量 workflow-v2 测试。

## 18. 设计讨论记录

本设计在人类确认三条硬边界后，与 `gpt-6-astra/medium` 完成两轮设计讨论。Astra 赞同 run-scoped 长期 QC，并强调四个后端实为两条保证链、Requirement/Intent/Roadmap 不新增通用 PASS 门、Integration 的实际证据不能被 Reviewer PASS 替代。本文已吸收该边界；该讨论结论不等于对本文 r1 的独立审查。
