# Goal 目标冲突恢复：修改与复审

## 本轮边界

人类批准与 Astra 收敛的方案，并要求实施后 Astra 复审。修改 flow-run Runtime Goal 和冲突指引、README 说明，新增既有 Goal 记录行为的 characterization 测试。不新增 controller 逻辑、宿主代理或 schema，不调用真实 Goal、不部署/提交/推送；其他未提交批次保留。

发生真实目标冲突时说明旧/新任务和保留的未完成工作，确认一次；明确替换指令已经是确认。真实可用的宿主替换能力才允许条件自动化，当前仅有 get/create/update 时在同一提示给当前会话 `/goal clear` 与继续指定任务的方法。清除后读取确认空目标，再创建并验证新目标、记录真实引用。

同任务恢复不清除；超时/错误先读回，已成功则复用，第三目标或读取不确定时不盲清。新目标的用量统计重置不等于恢复已发生的费用/预算，不清除安全暂停，不继承无关任务授权。缺持久能力本身不阻断明确授权的安全当前轮工作。

## 验证

- Goal 记录测试 10 项通过；新增测试覆盖同线程 objective 替换、createdAt 不变/改变、旧引用历史、artifacts/reviews/authorizations 和 Flow pause 保留。它首次就通过，属于现有记录能力验证，不是 runtime 控制代码的 RED/GREEN，也不是真实宿主激活证据。
- 全套 `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -q`：277 项，276 项通过、1 项跳过，22.677 秒。随后测试断言修正为实际 authorizations 字段并避免缺字段伪通过，10 项 Goal 测试重新通过（0.473 秒）。
- flow-run 的 skill-creator quick_validate 成功；git diff --check 成功；flowctl.py、flowctl_lib、schemas 无修改。
- 隔离上下文 `goal_recovery_forward` 读取实际 skill 后纸面应用四场景：无 set 能力且已有明确替换指令，不重复询问；set 超时但新 active 目标可读，不 clear；原 blocker 已修复的同任务 blocked Goal，按现有规则安全当前轮继续；写前出现第三目标且跨任务预算余量未知，不盲替换或默认获得新额度。均符合方案。单样本推演，不是故障注入、并发保证或真实宿主测试。

## Astra 复审

`astra_goal_replacement_design`，`implementation / subagent / gpt-6-astra / medium`，审查 `de5ec0a` 上当前本轮修改，独立运行 Goal 10 项测试及 diff 空白检查成功。结论：符合已批准设计，无阻断问题。

I1 / `readme-unconditional-goal-replacement-prohibition` 为非阻断措辞矛盾：旧 README 绝对禁止覆盖未完成目标，与新授权替换路径冲突。已按建议改为“没有明确人类指令不得替换；宿主暂停/预算仍有效”。Astra 明确无需为该措辞修复再开周期。

该审查确认提示规则及记录机制，不证明当前 Agent 已获得宿主 set/clear 能力。实际协议可用性、并发原子性及远程调用不在本轮实现范围。
