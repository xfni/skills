# Flow 评审生命周期修复 Implementation Plan

> 按 TDD 在现有 ISSUE-2 worktree 逐项执行；用户明确要求完成后 Astra/medium 只读复查，不提交或部署。

**Goal:** 消除已复现的评审登记循环与错误路由，并结束可捕获异常中的 attempt。

**Architecture:** 复用现有 state/reviews/resume 模块；局部 next_review_action 供三个现有消费者使用，不引入状态机框架。

**Tech Stack:** Python 3.10、unittest、现有 Flow 文档契约。

**Spec:** `docs/superpowers/specs/2026-09-16-flow-review-lifecycle.md`

## Global Constraints

保留真实回执/内容身份/快照/权限/清理和有界重试；未知结果不通过；只改本 worktree；不联网调用外部模型；Astra 通过后交付。

## Tasks

- [ ] tests/test_review_lifecycle.py 先复现：三个阶段 DRAFT 登记与评审；未批准交接拒绝；envelope 更新保留 receipts。
- [ ] artifacts.py/state.py 实现 reviewable 草案与同内容批准刷新，继续在 handoff 检查批准。
- [ ] 先复现外部修复、iBrain/一致性恢复、任意入口全通过恢复，再在 reviews.py 抽取下一步计算并迁移 state/resume 调用。
- [ ] 先复现 INCOMPLETE 阻塞/非阻塞两种路径，修正补证/修复动作及同内容重试规则。
- [ ] 先故障注入 begin 后审查包异常，确保异常留下终结记录、不会 PASS/fallback，并处理最新 state_revision。
- [ ] 更新 flowctl/artifact/阶段契约，明确草案→评审→envelope 批准→登记刷新→交接及新的 approve 动作。
- [ ] 完整 Flow/root 回归、技能验证和 diff check；Astra/medium 复审具体修复边界并处理有证据的 findings。

测试命令统一为 `PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m unittest discover -s workflow-v2/tests -q`；定向 RED/GREEN 使用 `-p test_review_lifecycle.py`。仓库回归将 tests 作为发现目录。

## Execution outcome

上述任务均已执行。17 项专项测试通过；Flow 全量 248 项通过（跳过 1 项）；仓库 42 项通过（跳过 12 项）；四个修改技能 quick_validate 通过；git diff --check 通过。

Astra/medium 独立只读复查通过，独立重跑 17 项专项测试。发现并已验证修复两个 Blocker：iBrain 修复后的失败耗尽路径在 consistency/handoff 判定不一致；旧阶段 APPROVAL 元数据更新覆盖当前 pending_action。真实外部评审服务未在测试中调用。未提交、推送或同步 Codex。
