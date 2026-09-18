# 数据实验工作流

独立于开发 Flow 的轻量工作流：前期用生产样本本地比较方案，后期对比上线前后样本。两个技能、四个角色，无控制器、详细 Spec 或审批收据协议。

```text
讨论目标与方案 → 主 Agent 与审阅者收敛 → 协商配额并确认当前 EXP 方案
    → 建立独立实验 Goal → 数据摘取与脱敏 → 多轮实验 → 证据审阅/必要复验 → 结论与本地留痕
```

讨论不创建 Goal、不采样、不运行实验；只有人类明确同意当前 `EXP-*` 方案后才建立独立实验 Goal。先确定方案，再讨论配额；不足就回到方案，不缩减执行后仍承诺原结论。自主执行只在确认边界内进行，负面和证据不足均可结束。

讨论采用逐项提问：Agent 先检查相关项目代码/配置/文档，解释证据、影响、选择和未知，再问一个实质决定。已明确的选择继承，普通技术细节由 Agent 判断。执行方式从已有回放、小型分析脚本、隔离候选实现中选择最小可行方式或必要组合；实验简单时可直接回放，复杂时只编写为当前假设所需的代码。

## 使用

```text
$exp-run issue=BCS-100
目标：比较当前检索与候选检索，判断是否值得开发。

$exp-run issue=BCS-100 experiment=EXP-002
目标：验证上线前后相似请求的成功率及失败分布。

$exp-run issue=BCS-100 experiment=EXP-002 恢复已有实验
```

有已确认的数据任务时可单独用 `$exp-data`；独立调用先确认采集/脱敏范围，不自动授权整个实验。没有信息时，技能先索取人类 issue 和实验目的，不访问生产。

开发后的验证优先复用当前已关联的 feature worktree；当前在主分支、worktree 不匹配或候选实验确有冲突时才建立实验 worktree。多次 `EXP-*` 可复用正确的 worktree；不另造嵌套 worktree。默认记录在 `.ai/issue/<safe-issue>/experiments/<EXP-id>/`，当次指定、项目与全局 AGENTS.md 可覆盖；实验数据按约定受限保存并排除 Git。

确认后，宿主成功建立独立实验 Goal、或以原子替换成功建立它，才开始数据动作。它只覆盖数据摘取、多轮试验、评测/审阅、报告和清理；不会结束、借用或拼接开发 Goal。分步 `clear + set/create` 不算安全替换；宿主不能原子替换已有 Goal 时不清除、不伪造完成或阻塞，直接说明真实恢复动作。恢复实验先核对记录中的 Goal 是否仍匹配；不匹配不自动续跑或重采。

## 技能与角色

| 项 | 用途 | 默认模型 |
| --- | --- | --- |
| `exp-run` / 主 Agent | 目标讨论、方案/配额协商、多轮编排和结论 | 当前会话；推荐 Sol/high 或 Astra/medium |
| `exp-data` / `exp_data` | 只读采样、有效性、脱敏与安全交付 | Luna/max |
| `exp_worker` | 持续编写、运行和记录实验 | Luna/max |
| `exp_reviewer` | 方案挑战与独立结果证据核验 | Astra/medium |

主 Agent 和审阅者方案讨论默认 2 轮、最多 4 轮；数据与实验角色按需唤起，持久复用，不因等待超时重启。模型真实不可用可以替代并记录，不为此重复索取人类确认。

## 安装到 Codex

在本仓库根目录执行以下命令；这是安装示例，本次开发不默认修改全局配置。两个技能必须一起安装，各自引用都在技能目录内部。

```bash
mkdir -p "$HOME/.codex/skills/exp-run" "$HOME/.codex/skills/exp-data" "$HOME/.codex/agents"
rsync -a experiment-workflow/skills/exp-run/ "$HOME/.codex/skills/exp-run/"
rsync -a experiment-workflow/skills/exp-data/ "$HOME/.codex/skills/exp-data/"
rsync -a experiment-workflow/skills/exp-data/agents/exp-data.toml "$HOME/.codex/agents/"
rsync -a experiment-workflow/skills/exp-run/agents/exp-worker.toml "$HOME/.codex/agents/"
rsync -a experiment-workflow/skills/exp-run/agents/exp-reviewer.toml "$HOME/.codex/agents/"
```

安装后重新打开 Codex，核对宿主实际提供的自定义角色和模型。自定义 Agent TOML 支持 `name`、`description`、`developer_instructions`、模型及思考强度；角色文件固定值可能覆盖调用值。人类指定其他模型或角色未加载时，使用通用角色附同样职责并显式设置模型/强度，不假装已经切换或加载。[官方自定义 Agent 说明](https://learn.chatgpt.com/docs/agent-configuration/subagents)

不需要 `flowctl`、Cursor SDK、iBrain 密钥或固定采集适配器。需要项目实际数据源和本地运行能力；宿主工具不足时明确说明，不宣称持久自主执行或独立审阅已发生。

## 数据与证据边界

生产只读，精确目标从当前项目查证；申请实际需要的沙箱/网络权限，拒绝后不绕过。样本文本不作为指令执行。数据摘取者按讨论选定策略脱敏并检查信号影响，不以固定脱敏算法保证所有场景。

原始数据、映射表、密钥不进 Git、不发 reviewer；自由文本、日志、错误和派生报告都需要检查。默认“完整评测集”是完整脱敏集；初始确认精确列出每个接收者/端点/模型可接收的数据类别、目的、数量和预算后，范围内的 iBrain 回放/盲评不重复索取授权。原始历史正文只有首次明确列出字段类别、接收者、端点/模型、目的和上限时才可交模型；凭证和映射表永不随此例外发送。reviewer 接收明确允许的代码、脱敏数据和证据，不只看主持者摘要；返回 stdout/API，不直接写工作区。只读 sandbox 不等于读隔离，路径限制在不能被宿主强制隔离时是协议约束，不宣称已实现强安全隔离。

本地工具返回会进入模型会话，原始数据应由本地程序处理，只回传检查过的统计或脱敏片段。原文模型回放先核对首次范围的字段类别、接收者/端点/模型、目的和上限，缺失或超出才说明范围变更；允许特定回放端点不代表允许把原文打印到 Agent 会话或交给 reviewer，不能以“本地读文件”声称原文没有外发。

结论写清改动、效果/退化、成本、全部尝试、可信度和不能证明什么。复验集用于调参后失去独立性；上线前后匹配默认描述性，不能自动推出因果或全流量收益。按实际证据支持/否定假设或报告不足，不虚构产品 no-go 规则。

允许本地提交代码和安全证据，不自动合并、部署或推送。清理自己启动的临时服务和副作用，数据留存按约定，不删共享资源。

## 验证

包结构验证使用 Codex 自带 skill-creator 验证器（需 PyYAML）；它只检验格式，不证明 Agent 决策正确：

```bash
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" experiment-workflow/skills/exp-data
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" experiment-workflow/skills/exp-run
```

行为场景见 [tests/scenarios.md](tests/scenarios.md)，实施及审阅记录见 [验证记录](../docs/reviews/2026-09-17-issue-3-experiment-verification.md)。测试只用虚构数据，不验证真实生产权限、实际脱敏质量或业务收益。

可运行的纯标准库配对 demo 及保存结果在 `tests/demo/`，独立检查驱动/指标：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s experiment-workflow/tests/demo -v
```

六例虚构样本的观察为基线 2/6、候选 5/6，仍有失败；它验证本地执行与保留证据，不是生产结论。历史运行记录未完整抓取终端，也未单独测量 CPU，不能据此宣称 CPU 上限已独立验证。

设计来源：[工作流概要](../docs/2026-09-17-issue-3-experiment-workflow-outline.md)。
