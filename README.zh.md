# AI-Native Coding Skills

一套同时适用于 Claude Code 与 Codex 的共享技能，用于保持高质量、一致性的开发工作流。

[English](./README.md) | 简体中文

## 技能列表

| 技能 | 说明 |
|------|------|
| [git-commit-convention](./skills/git-commit-convention/) | 强制执行结构化 commit 格式：第一行 `前缀(ISSUE): 摘要`，正文使用类型序号条目（`feat1:`、`fix1:` 等），并严格限制文件提交范围 |
| [coding-guidelines](./skills/coding-guidelines/) | 编码行为准则：简洁、外科手术式修改、证据驱动抽象、模块边界与按风险可靠性 |
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

安装完成后，全部八个技能即可在所有项目中直接调用；其中三个 AI-native 工作流仅在显式调用时启用。

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

### coding-guidelines

减少 LLM 常见编码失误的六条行为准则：

| 准则 | 针对问题 |
|------|----------|
| **编码前先思考** | 错误假设、隐藏困惑、缺失权衡 |
| **简洁优先** | 过度复杂、臃肿抽象、推测性功能 |
| **外科手术式修改** | 无关改动、触碰任务范围外的代码 |
| **目标驱动执行** | 可验证的成功标准、测试优先循环 |
| **证据驱动抽象** | 没有当前消费者或变体支撑的框架化分层 |
| **模块边界与迁移** | 协调层吞入子系统行为、跨模块契约松散、迁移半途而废 |
| **可靠性边界** | 不可信输入、可执行接口、资源、隐私与并发风险 |

## 环境要求

- [Claude Code](https://claude.ai/code)（需支持 plugin 功能）

## 开源协议

MIT
