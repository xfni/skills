---
name: init-claude
description: Use when initializing Claude configuration for a new project or setting up Claude globally for the first time
---

# init-claude：初始化 Claude 配置

## 概述

调用此技能后，按以下步骤为当前项目或全局环境配置 Claude。执行完毕后输出操作摘要。

---

## 步骤 0：确认作用域

向用户提问：

> 「请选择配置作用域：
> 1. **项目级**（写入当前目录 `.claude/settings.json` 和 `CLAUDE.md`）
> 2. **全局**（写入 `~/.claude/settings.json` 和 `~/.claude/CLAUDE.md`）」

根据回答确定路径变量：

| 变量 | 项目级 | 全局 |
|------|--------|------|
| `SETTINGS_PATH` | `<cwd>/.claude/settings.json` | `~/.claude/settings.json` |
| `CLAUDE_PATH` | `<cwd>/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `SKILLS_PATH` | `<cwd>/.claude/skills/` | `~/.claude/skills/` |

---

## 步骤 1：生成 CLAUDE.md

读取 `CLAUDE_PATH`。

### 若文件不存在

新建文件，写入以下完整内容：

~~~markdown
# 全局规范

## 1. Git Commit 规范

**永远不要擅自执行 `git commit`，除非用户主动提出 commit 要求。**

- 工作完成后，必须提醒用户手动执行 commit，不得代替用户提交。
- 每次执行 `git commit` 前，必须先调用 `git-commit-convention` skill，按照其规范构造提交信息。

## 2. 文档规范

在项目根目录的 `.ai` 文件夹内创建文档，文档按照子文件夹归类：

| 子目录 | 用途 |
|--------|------|
| `.ai/specs/` | 设计文档、规格说明 |
| `.ai/plans/` | 实施计划文档 |
| `.ai/reports/` | 分析报告、评估结果 |

- 所有 AI 辅助生成的项目文档默认放入 `.ai/` 对应子目录。
- 其他 `docs/` 目录用于面向用户的文档（README、用户说明等）。
~~~

### 若文件已存在

逐项检查，缺失则在文件**末尾追加**对应节（不修改已有内容）：

**检查项 A**：文件是否包含 `## 1. Git Commit 规范`？
- 不含 → 追加以下内容：

~~~markdown

## 1. Git Commit 规范

**永远不要擅自执行 `git commit`，除非用户主动提出 commit 要求。**

- 工作完成后，必须提醒用户手动执行 commit，不得代替用户提交。
- 每次执行 `git commit` 前，必须先调用 `git-commit-convention` skill，按照其规范构造提交信息。
~~~

**检查项 B**：文件是否包含 `## 2. 文档规范`？
- 不含 → 追加以下内容：

~~~markdown

## 2. 文档规范

在项目根目录的 `.ai` 文件夹内创建文档，文档按照子文件夹归类：

| 子目录 | 用途 |
|--------|------|
| `.ai/specs/` | 设计文档、规格说明 |
| `.ai/plans/` | 实施计划文档 |
| `.ai/reports/` | 分析报告、评估结果 |

- 所有 AI 辅助生成的项目文档默认放入 `.ai/` 对应子目录。
- 其他 `docs/` 目录用于面向用户的文档（README、用户说明等）。
~~~

---

## 步骤 2：合并 settings.json 放行列表

### 低风险命令列表（内嵌）

```json
[
  "Read",
  "Glob",
  "Bash(find *)",
  "Bash(mkdir *)",
  "Bash(xargs grep *)",
  "Bash(grep *)",
  "Bash(ls *)",
  "Bash(cat *)",
  "Bash(head *)",
  "Bash(tail *)",
  "Bash(wc *)",
  "Bash(diff *)",
  "Bash(tree *)",
  "Bash(stat *)",
  "Bash(awk *)",
  "Bash(sort *)",
  "Bash(uniq *)",
  "Bash(cut *)",
  "Bash(jq *)",
  "Bash(echo *)",
  "Bash(which *)",
  "Bash(env)",
  "Bash(printenv *)",
  "Bash(uname *)",
  "Bash(ps *)",
  "Bash(du *)",
  "Bash(cd *)",
  "Bash(git status)",
  "Bash(git log *)",
  "Bash(git diff *)",
  "Bash(git branch *)",
  "Bash(git show *)",
  "Bash(git stash list)"
]
```

### 合并步骤

1. 若目标目录不存在，先创建目录（`mkdir -p <cwd>/.claude/`）
2. 读取 `SETTINGS_PATH`（不存在则使用 `{}`）
3. 取出 `permissions.allow` 数组（字段不存在则视为 `[]`）
4. 将上方列表中所有条目与现有数组合并（**union，去重，保留原有条目**）
5. 将合并结果写回 `permissions.allow`，其他字段**保持不变**

**工具选择**：
- 优先使用 `jq` 命令行完成合并操作：
  ```bash
  jq '.permissions.allow = ((.permissions.allow // []) + $new | unique)' \
    --argjson new '<放行列表JSON>' \
    <SETTINGS_PATH> > /tmp/settings_tmp.json && mv /tmp/settings_tmp.json <SETTINGS_PATH>
  ```
- 若 `jq` 不可用（`which jq` 无输出），改用 Read 工具读取文件内容后，用 Write 工具写回合并后的 JSON。

---

## 步骤 3（仅项目级）：安装 git-commit-convention 技能

> 全局技能由用户自行管理，本步骤仅在项目级模式下执行；全局模式下直接跳至步骤 4。

将 `git-commit-convention` 技能复制到项目本地：

1. 查找源文件路径（按优先级）：
   - `~/.claude/skills/git-commit-convention/SKILL.md`
   - `~/.claude/plugins/` 下的任意同名技能

若两个路径均找不到源文件：
- 在摘要中输出：「⚠️ git-commit-convention 技能未找到，请手动安装」
- 跳过本步骤，不中断执行

2. 目标路径：`<cwd>/.claude/skills/git-commit-convention/SKILL.md`

3. 若目标目录不存在，先创建：
   ```bash
   mkdir -p <cwd>/.claude/skills/git-commit-convention
   ```

4. 复制文件（使用 Write 工具写入源文件内容）

---

## 步骤 4：输出摘要

执行完成后，输出以下摘要：

```
✅ init-claude 配置完成

作用域：[项目级 / 全局]

1. CLAUDE.md
   路径：<CLAUDE_PATH>
   操作：[新建 / 追加了 X 节]

2. settings.json
   路径：<SETTINGS_PATH>
   新增放行条目：X 条（原有 Y 条，合并后 Z 条）

3. git-commit-convention 技能
   [已安装到 <cwd>/.claude/skills/ / 跳过（全局模式）]
```
