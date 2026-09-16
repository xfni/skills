# AI-Native Coding Skills

一组小而明确、跨运行时复用的技能：将有边界的需求推进到可验证代码，同时避免 Agent 把简单改动写成框架。支持 Claude Code、Codex，以及可选的 Cursor 只读审阅。

[English](./README.md) | 简体中文

## 从这里开始

仅在你明确需要完整的决策、审阅与证据链时，显式调用 AI-native 工作流：

```mermaid
flowchart LR
    D["直接讨论"] --> I["$requirement-to-intent"]
    RC["$requirement-council<br/>可选，仅 Codex"] --> I
    Q["$requirement-clarification<br/>可选 grilling"] --> I
    RC --> Q
    I -. 人工确认的 intent.md .-> R["$intent-to-roadmap"]
    R --> S["$roadmap-to-spec-plan"] --> C["$spec-plan-to-code"]
    S -. 选择评审 profile .-> I["$independent-review"]
    C -. 选择评审 profile .-> I
    C --> CG["coding-guidelines"]
    S -. 可选只读终审 .-> CU["Cursor"]
    C -. 可选只读终审 .-> CU
```

`requirement-to-intent` 是 roadmap 前的统一门。人工可选 Council、需求澄清、两者或直接讨论。Council 写入候选 `requirement.md`；需求澄清在可用时包装 `grilling`，并将人工决策记入该产物；只有 Intent Gate 可以写入人工确认的 `intent.md`。

提供 issue key 后，Intent Gate 会读取一次 PMS，并把该不可变快照共享给选定路径。如果沙箱网络访问失败，它会为一次只读的提权重试申请权限；拒绝或再次失败会记为 `PMS_UNAVAILABLE`，且不暴露凭据。

所有工作流技能均为仅显式调用。可选需求方法只在人工选择时由 Intent Gate 编排；后续阶段不会自动启动。

## 技能与依赖

| 技能 | 解决什么问题 | 依赖与交接 |
|---|---|---|
| [git-commit-convention](./skills/git-commit-convention/) | 让本地提交保持需求范围清晰、关联文档完整，并遵循中文提交信息格式。 | 独立使用。需要 Git 仓库；提交时需要 issue 编号。 |
| [coding-guidelines](./skills/coding-guidelines/) | 编码与审阅时避免推测性抽象、范围蔓延、不安全边界和半迁移。 | 实现与审阅的基线。`spec-plan-to-code` **必须依赖**。 |
| [independent-review](./skills/independent-review/) | 统一设计、实现和并发 profile 的证据、范围、发现与复审标准。 | 调用方选择 profile、`subagent` 或 `cursor`、模型与思考强度；本技能不做路由决定。 |
| [cursor-review](./skills/cursor-review/) | 检查 Cursor 是否能在禁用本地工具和隐式索引的前提下执行一次有边界的纯字节审阅。 | 必须显式选择并使用控制器绑定请求。当前适配器因 Cursor bridge 无法证明两项安全能力而 fail closed。 |
| [requirement-council](./skills/requirement-council/) | 执行带对话上下文的 Agent 间需求讨论，并给出有证据支持的方案、风险和待补事实。 | **可选，仅 Codex** 阶段，由主 Agent 和两个子角色组成。它写入候选 `requirement.md`；由 `$requirement-to-intent` 负责交接。 |
| [requirement-clarification](./skills/requirement-clarification/) | 通过 `grilling` 或内置回退流程，与人工对齐已有 `requirement.md`。 | Intent 前的可选阶段；它更新需求 revision，但不创建 Intent 或 roadmap。 |
| [requirement-to-intent](./skills/requirement-to-intent/) | 选择需求路径，并产出权威的、人工确认的 `intent.md`。 | Roadmap 前的必经门；可编排 Council、需求澄清、两者或直接讨论。 |
| [intent-to-roadmap](./skills/intent-to-roadmap/) | 将已确认 Intent 转为包含 `REQ-*`、`DEC-*`、`AC-*` 与 Phase ID 的 roadmap。 | 要求 `intent.md` 且 `status: CONFIRMED`；不得重新解释 Intent 的范围、非目标或不变条件。 |
| [roadmap-to-spec-plan](./skills/roadmap-to-spec-plan/) | 将一个已确认 roadmap 阶段转为决策包、Spec、可执行 Plan、验收矩阵和审阅台账。 | **必须依赖**确认后的 roadmap / Phase ID。调用 `independent-review` 的 `design` 或 `concurrency` profile，并显式选择 Astra 或 Cursor。已批准产物交给 `spec-plan-to-code`。 |
| [spec-plan-to-code](./skills/spec-plan-to-code/) | 依据已批准决策包、Spec 和 Plan 实现代码，并保留按变更类型选择的测试、独立审阅、探针、运行时验证与证据。 | **必须依赖** `roadmap-to-spec-plan` 的批准产物和 `coding-guidelines`。调用 `independent-review` 的实现/并发 profile，并显式选择 reviewer backend、模型与思考强度。 |

依赖术语：

- **必须依赖**：没有前置产物或技能时不得开始。
- **按条件调用**：仅在触发条件成立时使用。
- **可选**：能提高讨论或覆盖质量，但技能已提供明确降级路径。

## 运行环境与外部能力

| 运行时或能力 | 用于 |
|---|---|
| [Claude Code](https://claude.ai/code)（支持 plugin） | 将本仓库安装为 Claude Code 插件。 |
| [Codex](https://openai.com/codex/) | 将选定技能安装或链接到 `~/.codex/skills/`。仓库提供仅显式调用的工作流元数据。 |
| 经控制器批准的外部审阅后端 | `$cursor-review` 是可选能力；在 Cursor 能证明本地工具与隐式索引均已禁用前保持不可用，Flow 可使用已授权的运行时后备。 |
| `grilling` 技能 | `requirement-clarification` 的可选引擎；缺失时该技能使用内置回退流程。 |
| `brainstorming` 指引 | 可用于扩展替代方案；Requirement Council 已内置必要的比较核心，不依赖该技能。 |
| `pms-issue-reader` 技能与 PMS 访问 | `requirement-to-intent` 在 issue 校验后使用一次；沙箱环境可能弹出只读网络权限申请。 |
| 已配置的审阅模型 | 工作流引用 Astra 等独立审阅模型；宿主运行时需要提供等价且已授权的审阅能力。 |
| Requirement Council（仅 Codex） | 需要将两个自定义 Agent TOML 全局安装到 Codex。每次运行由 moderator 选择模型/思考强度档位，并在创建子 Agent 时传入；未获宿主证明时，只读行为属于协议约束。 |

Requirement Council 默认仅在开始和结束时比较仓库快照；用户明确要求时才启用审计模式。宿主无法证明只读隔离时，结果标为协议约束而非直接失败；发现仓库变化即终止运行。

## 安装

### Claude Code

```text
/plugins add-marketplace github:xfni/skills
/plugins install nixiaofeng-skills@nixiaofeng-skills
```

### Codex

仓库通过 `.codex-plugin/plugin.json` 暴露共享的 `skills/` 目录。市场条目发布前，可 clone 本仓库，将所需技能复制或链接到 `~/.codex/skills/`：

```bash
ln -s "$(pwd)/skills/intent-to-roadmap" ~/.codex/skills/intent-to-roadmap
```

对其他所需技能重复操作。工作流技能保持仅显式调用，例如 `$intent-to-roadmap`。

#### Requirement Council（个人 Codex 安装）

Requirement Council 使用个人 Codex Agent，而不是项目级 Agent。必须完成以下两个安装步骤：

1. 将 `skills/requirement-council` 复制或链接到 `~/.codex/skills/requirement-council`。
2. 将 `skills/requirement-council/agents/` 中两个独立 Agent TOML 复制到 `~/.codex/agents/`：
   - `requirement-council-value-boundary-explorer.toml`
   - `requirement-council-risk-counterexample-critic.toml`

例如，在仓库根目录执行：

```bash
mkdir -p ~/.codex/skills ~/.codex/agents
ln -s "$(pwd)/skills/requirement-council" ~/.codex/skills/requirement-council
cp skills/requirement-council/agents/requirement-council-value-boundary-explorer.toml ~/.codex/agents/requirement-council-value-boundary-explorer.toml
cp skills/requirement-council/agents/requirement-council-risk-counterexample-critic.toml ~/.codex/agents/requirement-council-risk-counterexample-critic.toml
```

安装或更新 Agent TOML 后，请启动一个全新的 Codex 会话，让个人 Agent 发现机制重新加载这些文件。

请使用功能主题显式调用。主 Agent 会使用相关历史对话作为需求上下文，因此调用文本无需重复完整需求：

```text
$requirement-council
客服人员需要保存常用筛选条件，并在之后快速重新打开。
初步设想是个人筛选列表；是否支持团队共享尚未确定。
现有权限必须继续控制用户能够看到哪些记录。
```

此 Skill 有意不包含在 Claude Code plugin 中。它的两个子 Agent 不会通过 `.codex-plugin/plugin.json` 全局安装；请按以上两个个人 Codex 步骤安装。Council 只写入候选 `requirement.md`；请用 `$requirement-to-intent` 显式交接到后续工作流。

### Cursor 审阅配置（可选）

`$cursor-review` 只接受控制器在私有目录中物化的请求文件，以及 `--no-tools` 与 `--expected-request-digest`。在读取任何请求字节或凭据前，控制器会用隔离 Python 执行已固定并捕获的适配器字节，并要求能力检查同时证明本地工具和隐式索引均已禁用。当前 Cursor bridge 无法证明该合同，因此 `scripts/cursor_review.py --check-capabilities` 会返回带 framing 的 `BACKEND_UNAVAILABLE`，Flow 随后执行已授权的运行时后备策略。不得用专用 runtime、API key 文件或仓库 workspace 代替这项证明。

## 开源协议

MIT
