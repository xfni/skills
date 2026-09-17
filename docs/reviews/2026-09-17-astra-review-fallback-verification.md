# 外部审查不可用时的 Astra 续跑

人类明确允许 Cursor/iBrain 都不可用时由 Astra 复审。本轮核实为已有 controller 能力的指令澄清，不宣称特定项目状态已恢复，也不修改 flowctl/schema 或真实 Goal。

review-contract 新增 Astra continuation，flowctl-contract 及 Run/Spec/Plan/Code 引用它：当前外部路由可重试运行失败耗尽后，实际 fresh gpt-6-astra/medium consistency 通过则保留 EXTERNAL_REVIEW_GAP、有条件交接。若缺 GPT 主审保证，先恢复真实收据；确需主审而选定模型不可用，可用 Astra backend=gpt 获取真实结果，然后单独新线程 consistency。不能将一份报告用于两角色或把外部不可用视为实质审查通过；现有次数、未分类冲突、已知缺陷和宿主限制仍有效。

新 characterization 测试验证已有 Spec 控制器路径：缺主审／consistency 均阻止相应动作；Astra 主审与一致性是两个 attempt；Cursor/iBrain 各两次 fixture 进程失败后接受 consistency，再以 COMPLETE_WITH_DEFECT／有条件通过交接，保留四条失败及 OPEN gap，没有外部 PASS。测试首次通过，不是 controller bug 的 RED/GREEN，也非真实供应商调用证据。

验证：完整 unittest 278 项，277 项通过、1 项跳过，22.913 秒；lifecycle 23 项通过；Run/Spec/Plan/Code quick_validate 成功；diff check 成功。flowctl.py、flowctl_lib 和 schemas 无 diff。

Astra 独立 implementation/subagent/gpt-6-astra/medium 复核：通过，无阻断问题；独立运行 lifecycle 23 项和 diff check 成功。只确认规则及现有接受路径，不证明特定项目失败原因、真实供应商可用性或实际线程独立性。

本轮尚未部署至 Codex、提交或推送。对于已 blocked 的项目，仍需按实际证据解除原对应暂停；不能因规则修改自动假称宿主 Goal 已恢复。
