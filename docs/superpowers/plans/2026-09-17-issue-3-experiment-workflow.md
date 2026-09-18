# 数据实验工作流实施计划

目标：实现概要约定的两个技能与三个 subagent 角色；无控制器，无生产访问。本次工作只在 `feature-ISSUE-3-exp-flow` 内进行。

设计依据：[工作流概要](../../2026-09-17-issue-3-experiment-workflow-outline.md)。本计划只描述交付与验证，不增加详细 Spec 或新人工门。

## TASK-1：数据能力

- [x] 无技能场景观察数据摘取基线，记录真实决策，不以假想缺陷替代 RED。
- [x] 创建 `experiment-workflow/skills/exp-data/SKILL.md`、UI 元数据与 `agents/exp-data.toml`。
- [x] 独立新线程读取技能，核对脱敏、有效性、信号保真、输出泄露和访问范围；明确干跑输入修正。
- [x] 保留真实生产采集/脱敏未验证限制，不伪造安全失败或执行通过。

## TASK-2：实验编排

- [x] 无技能场景观察方案/配额、复验样本复用、worktree 污染与前后归因基线。
- [x] 创建 `experiment-workflow/skills/exp-run/SKILL.md`、UI 元数据、`references/experiment.md`、`references/agents.md`、`agents/exp-worker.toml` 与 `agents/exp-reviewer.toml`。
- [x] 提供开始协商、2–4 轮自主方案讨论、当前 EXP 明确确认、优先复用正确 feature worktree、多轮执行、结果审阅及恢复的直接提示词流程。
- [x] 把讨论与独立实验 Goal 分开：确认后成功替换/建立 Goal 才执行；替换失败不伪造终态，恢复只接续同一 EXP Goal。
- [x] 在一次性执行范围中明确接收者、数据类别、端点/模型、样本/成本边界；完整脱敏集范围内评测不重复授权，原始正文例外须在首次确认精确列出。
- [x] 用隔离线程与虚构场景验证前期/后期/预算/中断处理，禁止真实生产访问；不写只匹配措辞的单测。

## TASK-3：交付与审阅

- [x] 写 `experiment-workflow/README.md`：使用方法、两个技能和三个角色的安装位置、边界及模拟验证命令。
- [x] 使用 skill-creator 自带验证器校验两个技能，解析角色 TOML，检查本地引用可发现性。
- [x] 让 Astra/medium 独立审阅实现与验证证据，定向核查新增说明；无阻塞发现，披露证据限制，不为风格建议循环。
- [x] 重跑现有 Flow 回归，记录真实结果；不修改原有 Flow。

提交、合并、推送和全局部署不在本次默认执行范围内。技能的真实生产验证留给后续明确授权的项目实践。
