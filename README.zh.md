# Claude Code Skills

一套用于保持高质量、一致性开发工作流的 Claude Code 技能集合。

[English](./README.md) | 简体中文

## 技能列表

| 技能 | 说明 |
|------|------|
| [git-commit-convention](./git-commit-convention/) | 强制执行结构化 commit 格式：第一行 `前缀(ISSUE): 摘要`，正文使用类型序号条目（`feat1:`、`fix1:` 等），并严格限制文件提交范围 |
| [init-claude](./init-claude/) | 为新项目初始化 Claude 配置——生成 `CLAUDE.md`、合并低风险命令放行列表到 `settings.json`、并将 `git-commit-convention` 安装到项目本地 |
| [coding-hard-constraints](./coding-hard-constraints/) | 编码硬约束：Yoda 条件判断、防御式访问、早返原则、强类型、函数复杂度限制、安全边界、并发安全 |
| [coding-observability-errors](./coding-observability-errors/) | 日志与异常治理：入口/出口埋点、标准化错误码、资源释放、超时要求、错误传播策略 |
| [karpathy-guidelines](./karpathy-guidelines/) | 源自 [Andrej Karpathy 观察](https://x.com/karpathy/status/2015883857489522876) 的编码行为准则：编码前先思考、简洁优先、外科手术式修改、目标驱动执行 |

## 安装

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

安装完成后，全部五个技能即可在所有项目中直接调用。

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

### coding-hard-constraints

编写、审查或重构任何代码时强制遵守的结构性规则：

- **Yoda 条件** — 常量在左：`nil == err`、`None is value`
- **防御式访问** — 禁止深链式调用，使用可选链或空值守卫
- **早返原则** — 卫语句优先，主逻辑保持在最左侧缩进
- **强类型** — 禁止用裸 `dict`、`Map<String,Object>`、`Record<string,any>` 传递业务数据
- **复杂度限制** — 单函数最多 40 行、4 个参数、3 层嵌套
- **安全边界** — 仅使用参数化查询，系统边界处校验输入，禁止日志中出现密钥
- **并发安全** — 所有共享可变状态必须显式保护

### coding-observability-errors

Service 层与外部集成的日志和异常规范：

- **埋点** — 入口（INFO）、关键节点（INFO）、出口（INFO）、排查细节（DEBUG）、预期内错误（WARN）、系统崩溃（ERROR）
- **注释** — 解释*为什么*，而非*是什么*；公共函数必须有标准头注释
- **异常治理** — 禁止空 catch 块；异常必须映射为标准 `Code + Message`；资源必须使用 `try-with-resources` / `with` / `defer`
- **错误传播** — 可恢复错误返回结果码，不可恢复错误向上抛出
- **超时** — 每个跨服务调用必须显式设置超时（不低于 P99 基线）

### karpathy-guidelines

减少 LLM 常见编码失误的四条行为准则：

| 准则 | 针对问题 |
|------|----------|
| **编码前先思考** | 错误假设、隐藏困惑、缺失权衡 |
| **简洁优先** | 过度复杂、臃肿抽象、推测性功能 |
| **外科手术式修改** | 无关改动、触碰任务范围外的代码 |
| **目标驱动执行** | 可验证的成功标准、测试优先循环 |

## 环境要求

- [Claude Code](https://claude.ai/code)（需支持 plugin 功能）

## 开源协议

MIT
