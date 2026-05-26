# init-claude 技能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 `init-claude` 技能，调用后交互式地为项目或全局生成 CLAUDE.md、合并 settings.json 放行列表、安装 git-commit-convention 技能。

**Architecture:** 纯静态 Markdown 技能文件（SKILL.md），Claude 读取后按内嵌流程操作文件系统；无需脚本。技能内嵌 CLAUDE.md 模板和完整放行列表，合并逻辑以清单形式写出，让 Claude 直接执行。

**Tech Stack:** Markdown（技能文件）、JSON（settings.json 合并）、文件系统操作（Bash/Write 工具）

---

## 文件结构

| 操作 | 路径 | 说明 |
|------|------|------|
| 创建 | `init-claude/SKILL.md` | 技能主文件，含流程 + 模板 + 放行列表 |
| 创建 | `.ai/plans/2026-05-26-init-claude-skill.md` | 本计划文件（已创建） |

---

## Task 1：创建 init-claude/SKILL.md

**Files:**
- Create: `init-claude/SKILL.md`

- [ ] **Step 1：创建技能目录**

```bash
mkdir -p /Users/nixiaofeng/工作/code/skills/init-claude
```

Expected: 目录创建成功，无输出。

- [ ] **Step 2：写入 SKILL.md**

写入以下完整内容到 `init-claude/SKILL.md`：

```markdown
---
name: init-claude
description: Use when setting up Claude for a new project or configuring globally - asks project vs global scope, then generates CLAUDE.md with commit and documentation conventions, merges low-risk command allowlist into settings.json, and installs git-commit-convention skill
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

1. 读取 `SETTINGS_PATH`（不存在则使用 `{}`）
2. 取出 `permissions.allow` 数组（字段不存在则视为 `[]`）
3. 将上方列表中所有条目与现有数组合并（**union，去重，保留原有条目**）
4. 将合并结果写回 `permissions.allow`，其他字段**保持不变**
5. 若目标目录不存在，先创建目录（`mkdir -p`）

---

## 步骤 3（仅项目级）：安装 git-commit-convention 技能

将 `git-commit-convention` 技能复制到项目本地：

1. 查找源文件路径（按优先级）：
   - `~/.claude/skills/git-commit-convention/SKILL.md`
   - `~/.claude/plugins/` 下的任意同名技能

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
```

- [ ] **Step 3：验证文件写入正确**

```bash
head -5 /Users/nixiaofeng/工作/code/skills/init-claude/SKILL.md
```

Expected：
```
---
name: init-claude
description: Use when setting up Claude for a new project...
---
```

- [ ] **Step 4：检查文件行数合理**

```bash
wc -l /Users/nixiaofeng/工作/code/skills/init-claude/SKILL.md
```

Expected：行数在 100–200 行之间。

---

## Task 2：冒烟测试——在测试目录中调用技能

**Files:**
- Create (临时): `/tmp/test-init-claude/` — 测试用空项目目录

- [ ] **Step 1：创建测试目录**

```bash
mkdir -p /tmp/test-init-claude
```

- [ ] **Step 2：在对话中模拟调用技能，选择「项目级」**

在 `/tmp/test-init-claude` 目录下调用 `init-claude` 技能，选择项目级配置。

验证以下文件被生成：

```bash
ls /tmp/test-init-claude/CLAUDE.md
ls /tmp/test-init-claude/.claude/settings.json
ls /tmp/test-init-claude/.claude/skills/git-commit-convention/SKILL.md
```

Expected：三个文件均存在，无报错。

- [ ] **Step 3：验证 CLAUDE.md 内容**

```bash
grep "Git Commit 规范" /tmp/test-init-claude/CLAUDE.md
grep "文档规范" /tmp/test-init-claude/CLAUDE.md
```

Expected：两行均有输出。

- [ ] **Step 4：验证 settings.json 包含放行列表**

```bash
cat /tmp/test-init-claude/.claude/settings.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
allows = data.get('permissions', {}).get('allow', [])
print(f'放行条目数：{len(allows)}')
assert 'Bash(git status)' in allows, 'git status 未放行'
assert 'Read' in allows, 'Read 未放行'
print('✅ 验证通过')
"
```

Expected：
```
放行条目数：33
✅ 验证通过
```

- [ ] **Step 5：验证 git-commit-convention 技能已安装**

```bash
grep "name: git-commit-convention" /tmp/test-init-claude/.claude/skills/git-commit-convention/SKILL.md
```

Expected：
```
name: git-commit-convention
```

- [ ] **Step 6：清理测试目录**

```bash
rm -rf /tmp/test-init-claude
```

---

## Task 3：验证技能在已有配置文件时的追加行为

**Files:**
- Create (临时): `/tmp/test-init-claude-existing/` — 含已有 CLAUDE.md 和 settings.json 的测试目录

- [ ] **Step 1：创建带已有配置的测试目录**

```bash
mkdir -p /tmp/test-init-claude-existing/.claude
```

写入已有 CLAUDE.md（**不含**规范节）：

```bash
cat > /tmp/test-init-claude-existing/CLAUDE.md << 'EOF'
# 项目说明

这是一个已有配置的项目。
EOF
```

写入已有 settings.json（含已有放行条目）：

```bash
cat > /tmp/test-init-claude-existing/.claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": ["Bash(npm run *)", "Bash(node *)"]
  }
}
EOF
```

- [ ] **Step 2：调用 init-claude 技能，选择项目级**

在 `/tmp/test-init-claude-existing` 目录下调用技能。

- [ ] **Step 3：验证 CLAUDE.md 追加而非覆盖**

```bash
grep "项目说明" /tmp/test-init-claude-existing/CLAUDE.md
grep "Git Commit 规范" /tmp/test-init-claude-existing/CLAUDE.md
```

Expected：两行均有输出（原有内容保留，规范节已追加）。

- [ ] **Step 4：验证 settings.json 合并保留原有条目**

```bash
cat /tmp/test-init-claude-existing/.claude/settings.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
allows = data.get('permissions', {}).get('allow', [])
print(f'放行条目数：{len(allows)}')
assert 'Bash(npm run *)' in allows, '原有条目丢失'
assert 'Bash(git status)' in allows, '新增条目缺失'
assert 'Read' in allows, 'Read 缺失'
print('✅ 合并验证通过')
"
```

Expected：
```
放行条目数：35
✅ 合并验证通过
```

- [ ] **Step 5：清理测试目录**

```bash
rm -rf /tmp/test-init-claude-existing
```

---

## Self-Review 结果

**Spec 覆盖检查：**
- ✅ 交互式选择作用域 → Task 1 步骤 0
- ✅ 生成 CLAUDE.md（新建 + 追加两种情况）→ Task 1 步骤 1
- ✅ 合并 settings.json 放行列表（union 去重）→ Task 1 步骤 2
- ✅ 安装 git-commit-convention 技能（仅项目级）→ Task 1 步骤 3
- ✅ 输出摘要 → Task 1 步骤 4
- ✅ 已有配置时追加而非覆盖 → Task 3

**占位符扫描：** 无 TBD / TODO / "类似于 Task N" 表述。

**类型一致性：** 无跨任务函数/变量名不一致问题（纯 Markdown + Bash 操作）。
