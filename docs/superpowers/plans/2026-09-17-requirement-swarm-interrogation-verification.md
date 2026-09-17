# Requirement 蜂群技能修改验证

状态：修改完成，Astra/medium 实施复审及输入隔离定向复审通过；已同步 Codex，尚未 Git 提交。

## 修改范围

flow-requirement 及其 swarm-discussion 引用、两角色 TOML、flow-brainstorm 的历史继承/确认复用、README 阶段说明、原有测试轮次说明。未修改控制器、schema、安全授权或下游评审拓扑。

设计来源：[讨论稿](../specs/2026-09-17-requirement-swarm-interrogation-discussion.md)。人类后来补充的角色分责和历史讨论继承也已纳入。

## 旧版基线与修改后应用

旧版独立样本 requirement_swarm_baseline 在修改前读取当时技能；新版 requirement_swarm_forward 为独立新上下文，应用相同 A–E 场景，不提供预期答案。各角色只读演练，没有实际运行完整蜂群或调用控制器。

| 场景 | 旧版实质输出 | 修改后实质输出 |
| --- | --- | --- |
| A：已确认脑暴与未接受的框架建议 | 可直接独立分析；不把“我再想想”当选择 | 同样复用记录；R1 不排名，明确双方探索分责 |
| B：两次无增量但未检查失败边界 | 不结束，进入 R4 核对 | 不结束，回答指定遗漏问题，不以无增量替代覆盖 |
| C：双方提议存原始输入，违背人类旧约束 | 拒绝扩大留存，独立主题可继续 | 保留错误建议和纠正关系，定向探索合规最小控制 |
| D：罕见风险推动插件/多租户平台 | 无支持凭据不推荐 | 风险不成为 NEED，先检验当前损失与最小控制 |
| E：R8 仍有可核查失败边界与人类偏好 | “不启动第9轮”，改为轮外核查/人类提问 | 进入 R9，只推进可查问题；人类偏好留 DRAFT 后提问 |

观察到的旧版差异主要是 E 的八轮硬上限；A–D 已表现正确，不能宣称它们是已复现的旧版缺陷。新增机制将这些正确行为明确化，并减少摘要/轮次/依赖方面的歧义。

## 额外边界应用

requirement_swarm_edges 在独立上下文应用修改后技能，未读设计或前次报告：

- F：历史不全且无脑暴确认，只核对可见 CSV/单用户基线；无来源的平台记忆不作 HUMAN。
- G：仅一两个有效前沿问题时不凑数量；保留时长只能作条件分析，不能默认选导出。
- H：风险原结论含断网条件，root 摘要丢失条件时纠正摘要，不靠扩大持久化覆盖不保存约束。
- I：R12 之后人类选择引出新权限后果，保留 DRAFT，不开 R13 或静默清零。
- J：已有恢复能力的证据推翻未授权平台建议，撤回范围但不制造人工门禁。
- K：双方共同假设用户接受误拒，不可包装成人类已接受风险；需说明真实取舍。

这些是每组一次的有限行为应用样本，不是五次独立重复的统计对照，也不是对任意模型或真实长会话可靠性的保证。未执行完整 12 轮实际蜂群；不能用格式或字词测试声称机制效果已充分证明。

之后按人类要求追加一次真实 llm-qa-service 源码上的四轮假设需求讨论：主持人实际逐轮派发，同两个探索线程继续，观察到交叉来源纠正和新候选兼容断言纠偏，没有因风险增加平台需求。它使用新版源提示词而非尚未更新的已安装角色，未运行业务 admission/授权或真实服务；没有完整十二轮或统计对照。[追加验证记录](2026-09-17-requirement-swarm-real-project-validation.md)保留观察与限制。

## 机械验证

- Python 3.10 全套 unittest：首轮 276 tests，OK，skipped=1，22.598s；输入隔离修正后再次运行 276 tests，OK，skipped=1，23.851s。
- skill-creator quick_validate：flow-requirement 与 flow-brainstorm 均通过。
- Python tomllib：两份角色配置均解析成功。
- git diff --check：通过。
- 原有 test_requirement_discussion_contract 的八轮文本改为十二轮，仅为现有测试适配，不作为行为有效性证据。

## 实施复审

Astra/medium 只读实施复审结论为 PASS：覆盖历史继承、主题依赖、两角色分责、跨轮纠偏、范围控制、收敛/人工授权边界及打包引用可用性。独立复现 test_workflow.py 的 35 项测试及 diff check，未运行真实蜂群、部署或独立复现全部 276 项；行为演练仍是作者提供的有限观察。

- IMPL-N01（非阻塞 Note，recurrence_key: requirement-swarm-behavioral-evidence-boundary）：有限样本不证明真实长会话可靠性，已接受并保留验证限制，不以该 Note 开新审查。
- IMPL-A02（Ambiguity，recurrence_key: requirement-r1-input-isolation）：主技能直接传冻结 brainstorm_result（含推荐字段）以及默认继承 root 上下文，可能破坏首轮独立。Astra 给出最小修订：新探索隔离线程，提供来源绑定的无排名基线，人类明确选择仍保留，恢复探索不重置。已按建议修正主技能和 reference；Astra 定向复审 PASS，直接核对两处输入规则一致，结论 resolved，无新增问题。

## Codex 同步验证

人类恢复同步指令后，已备份再同步完整 workflow-v2 包、全局 flow-requirement/flow-brainstorm 目录（含新 reference），以及 ~/.codex/agents 中两个探索者 TOML。未修改 config.toml、API Key、AGENTS.md 或业务项目。

- 备份目录：`/Users/nixiaofeng/.codex/flow-requirement-backup-5QtACM`。
- 源目录与三个安装目录 rsync dry-run 无差异；两份全局角色配置 cmp 相同。
- 两个已安装技能 quick_validate 通过。
- 直接从已安装 `/Users/nixiaofeng/.codex/flow-v2/tests` 运行：276 tests，OK，skipped=1，22.788s。
- 以上验证安装文件与包测试，不代表当前会话已重载自定义角色或已完成安装版本的真实多轮运行。按仓库安装说明建议重新开启 Codex 会话后实践。
