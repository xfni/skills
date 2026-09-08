# AI-Native Coding Skills

一套同时适用于 Claude Code 与 Codex 的共享技能，用于保持高质量、一致性的开发工作流。

[English](./README.md) | 简体中文

## 技能列表

| 技能 | 说明 |
|------|------|
| [git-commit-convention](./skills/git-commit-convention/) | 强制执行结构化 commit 格式：第一行 `前缀(ISSUE): 摘要`，正文使用类型序号条目（`feat1:`、`fix1:` 等），并严格限制文件提交范围 |
| [init-claude](./skills/init-claude/) | 为新项目初始化 Claude 配置——生成 `CLAUDE.md`、合并低风险命令放行列表到 `settings.json`、并将 `git-commit-convention` 安装到项目本地 |
| [coding-guidelines](./skills/coding-guidelines/) | 编码行为准则：简洁、外科手术式修改、证据驱动抽象与按风险的可靠性边界 |
| [privacy-coding-rule](./skills/privacy-coding-rule/) | 组织内部的隐私和数据处理规则，以权威内部制度为准执行 |
| [backend-module-discipline](./skills/backend-module-discipline/) | 后端模块纪律：协调层只调度、子系统单入口、类型对象跨边界、枚举优先、对称代码立刻抽、半迁移不过夜、体量红线 |
| [concurrent-design-review](./skills/concurrent-design-review/) | 并发、生命周期与共享状态设计的独立双视角评审：同时核查真实代码路径与系统失败模式 |
| [requirements-to-roadmap](./skills/requirements-to-roadmap/) | 显式调用的需求设计工作流：定位、讨论、质询并冻结有边界的需求路线图 |
| [roadmap-to-spec-plan](./skills/roadmap-to-spec-plan/) | 显式调用的设计工作流：将确认的 roadmap 转为经审阅的决策包、Spec 和可执行 Plan |
| [spec-review-gate](./skills/spec-review-gate/) | 写 Plan 前的风险门禁：识别并发与生命周期设计，并调用专项评审工作流 |
| [spec-plan-to-code](./skills/spec-plan-to-code/) | 显式调用的开发工作流：按变更类型验证，实现已批准的 Spec 和 Plan 并保留证据 |

## 在 Claude Code 中安装

**第一步 — 添加 marketplace：**

```
/plugins add-marketplace github:xfni/skills
```

**第二步 — 安装插件：**

```
/plugins install nixiaofeng-skills@nixiaofeng-skills
```

**第三步 — 初始化项目：**

```
/init-claude
```

安装完成后，全部十一个技能即可在所有项目中直接调用；其中三个 AI-native 工作流仅在显式调用时启用。

## 在 Codex 中使用

同一份源文件已通过 `.codex-plugin/plugin.json` 打包。当前仓库尚未发布 Codex marketplace 条目时，可先 clone 本仓库，再将 `skills/` 下所需目录复制或链接至 `~/.codex/skills/`。三个 AI-native 工作流仍通过 `agents/openai.yaml` 保持仅显式调用。

## 技能详解

### git-commit-convention

在每次 `git commit` 前强制执行规范化的提交格式：

```
feat(BCS-448): 将 ask-user 重构为三通道架构

feat1: 将原单通道 ask-user 拆分为 CLI、HTTP、SDK 三通道入口
fix1: 修复 HTTP 通道在空 body 时返回 500 的问题
```

强制规则：
- 第一行标题必须包含 issue 编号
- 正文至少一条类型序号条目（`feat1:`、`fix1:`、`refactor1:` 等）
- `.ai/` 和 `docs/` 下的关联文档必须与代码同批提交
- 禁止在开发过程中自行提交，必须先询问用户

### init-claude

一条命令完成新项目的 Claude 配置初始化：

1. 询问：项目级还是全局作用域？
2. 写入（或追加）`CLAUDE.md`，包含 commit 规范与文档规范
3. 将精选低风险命令放行列表合并到 `.claude/settings.json`
4. 将 `git-commit-convention` 复制到项目的 `.claude/skills/`

### privacy-coding-rule

组织内部隐私与数据处理要求的统一入口：

- **制度优先** — 以权威内部规则为准，不得自行发明或放宽隐私规则
- **全链路评估** — 覆盖采集、转换、遥测、消息队列、存储、导出、测试数据与外部调用
- **获批目的地** — 仅使用获批的存储、遥测字段、脱敏方式和外部集成
- **证据与升级** — 保留制度引用和要求的证据；规则缺失或冲突时升级给制度责任人

### coding-guidelines

减少 LLM 常见编码失误的五条行为准则：

| 准则 | 针对问题 |
|------|----------|
| **编码前先思考** | 错误假设、隐藏困惑、缺失权衡 |
| **简洁优先** | 过度复杂、臃肿抽象、推测性功能 |
| **外科手术式修改** | 无关改动、触碰任务范围外的代码 |
| **目标驱动执行** | 可验证的成功标准、测试优先循环 |
| **证据驱动抽象** | 没有当前消费者或变体支撑的框架化分层 |
| **可靠性边界** | 不可信输入、可执行接口、资源、隐私与并发风险 |

### backend-module-discipline

复杂后端服务防止架构腐化的六项纪律，来源于两次大规模重构的复盘：

| 纪律 | 防止什么 |
|------|----------|
| **协调层只调度** | 编排器承担子系统状态机和细节 |
| **子系统单入口** | 协调层直调内部方法，绕过门面 |
| **类型对象跨边界** | 裸 dict + 魔法字符串契约 |
| **枚举优先** | 平行布尔组 + 大小写混用字符串 |
| **对称代码立刻抽** | 两处镜像流程漂移 |
| **半迁移不过夜** | 兼容代理长期存活演变成永久债务 |

附体量红线（文件 ~800 行、方法 ~80 行、出口 ≤ 3）和七项 PR 评审清单。

## 环境要求

- [Claude Code](https://claude.ai/code)（需支持 plugin 功能）

## 开源协议

MIT
