# init-claude 技能设计文档

**日期**: 2026-05-26  
**状态**: 已批准  
**位置**: `/Users/nixiaofeng/工作/code/skills/init-claude/SKILL.md`

---

## 背景

在新项目接入 Claude 时，每次都需要手动配置：
- `.claude/settings.json` 放行低风险命令
- `CLAUDE.md` 写入 commit 规范 + 文档规范
- 安装 `git-commit-convention` 技能

目标：一个 `init-claude` 技能，一次调用完成以上所有配置。

---

## 功能范围

### 包含
1. **交互式选择作用域**：项目级或全局
2. **生成/更新 CLAUDE.md**：内嵌全局规范模板，追加而非覆盖
3. **合并 settings.json**：低风险命令列表 union 合并，不删除现有条目
4. **安装 git-commit-convention 技能**（仅项目级）

### 不包含
- 项目类型专属命令（Java/Python/Node 额外放行）
- 自动 commit 生成的配置文件

---

## 执行流程

```
调用 init-claude
  │
  ├─ 询问：「配置项目级还是全局？」
  │    ├── 项目级 → <cwd>/.claude/ + <cwd>/CLAUDE.md
  │    └── 全局   → ~/.claude/ + ~/.claude/CLAUDE.md
  │
  ├─ 步骤 1：生成 CLAUDE.md
  │    - 如文件不存在 → 新建并写入完整模板
  │    - 如文件已存在 → 检查是否已含各规范节，缺失部分追加
  │
  ├─ 步骤 2：合并 settings.json 放行列表
  │    - 读取目标 settings.json（不存在则用 {}）
  │    - 将技能内嵌的低风险命令列表与 permissions.allow 做 union 合并
  │    - 写回文件
  │
  └─ 步骤 3（仅项目级）：安装 git-commit-convention 技能
       - 将 git-commit-convention/SKILL.md 复制到
         <cwd>/.claude/skills/git-commit-convention/SKILL.md
```

---

## CLAUDE.md 模板内容

```markdown
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
```

---

## 低风险命令放行列表

以下命令在合并时加入 `permissions.allow`（与现有条目 union，不覆盖）：

```json
[
  "Read", "Glob",
  "Bash(find *)", "Bash(mkdir *)", "Bash(xargs grep *)",
  "Bash(grep *)", "Bash(ls *)", "Bash(cat *)",
  "Bash(head *)", "Bash(tail *)", "Bash(wc *)",
  "Bash(diff *)", "Bash(tree *)", "Bash(stat *)",
  "Bash(awk *)", "Bash(sort *)", "Bash(uniq *)",
  "Bash(cut *)", "Bash(jq *)", "Bash(echo *)",
  "Bash(which *)", "Bash(env)", "Bash(printenv *)",
  "Bash(uname *)", "Bash(ps *)", "Bash(du *)",
  "Bash(cd *)",
  "Bash(git status)", "Bash(git log *)", "Bash(git diff *)",
  "Bash(git branch *)", "Bash(git show *)", "Bash(git stash list)"
]
```

---

## 技能文件结构

```
init-claude/
  SKILL.md       ← 技能主文件，包含流程说明 + 内嵌模板 + 放行列表
```

无需脚本，无需额外资源文件。

---

## 合并逻辑说明

**settings.json 合并规则**：
- 读取目标路径 `settings.json`
- 取 `permissions.allow` 数组（不存在则为 `[]`）
- 与技能内嵌列表合并，结果去重排序
- 写回 `permissions.allow`，其他字段保持不变

**CLAUDE.md 追加规则**：
- 若文件不存在：新建并写入完整模板
- 若文件已存在且不含 `## 1. Git Commit 规范`：在文件末尾追加 Commit 规范节
- 若文件已存在且不含 `## 2. 文档规范`：在文件末尾追加文档规范节
- 已存在的节：不修改，不重复写入
