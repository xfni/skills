---
name: spec-review-gate
description: "Use when about to create any .ai/plans/ document, or when user says 'start implementation', 'write a plan', or 'begin coding'. Also use proactively when a spec involves concurrency, locking, asyncio cross-thread boundaries, shared mutable state, or startup/shutdown lifecycle."
---

# Spec 评审门禁

## 概述

Spec 进入 Plan 前的强制检查点。高风险设计缺陷在 Plan 阶段修复代价远低于实现后修复。

## 风险识别

扫描当前 Spec，识别触发词：

| 风险类型 | 触发词 / 特征 | 级别 |
|----------|--------------|------|
| **并发 / 锁** | asyncio、threading、Lock、Condition、TOCTOU、race condition、to_thread | 🔴 强制评审 |
| **生命周期** | lifespan、startup、shutdown、try/finally 跨组件、计时上下文 | 🔴 强制评审 |
| **共享可变状态** | 全局变量、进程级单例、module-level 可变对象、计数器 | 🔴 强制评审 |
| **外部 Schema** | 数据库表结构变更、对外 API 接口、消息格式 | 🟡 建议评审 |
| **纯业务逻辑** | Prompt、流程调整（不含上述） | ⚪ 可跳过 |

命中任一 🔴 → 必须走完门禁流程才能创建 Plan。

## 门禁流程

```
识别风险等级
    ↓ 🔴 强制
调用 concurrent-design-review（双视角评审协议）
    ↓
展示对应评审清单（见下方）
    ↓
问用户：「以下问题是否已完成评审？」
    ↓ 已评审              ↓ 跳过
追加评审状态标记       Plan 头部写警告标注
    ↓
创建 Plan 文件
```

**REQUIRED SUB-SKILL**：并发/生命周期类 Spec 评审时，必须使用 `concurrent-design-review` 执行双视角审查（代码实现派 + 系统健壮派）。

**职责边界**：当前主 agent 或 Spec 作者不得评审自己的 Spec，也不得以自检结果写入“已通过”。Gate 不得预先派发 reviewer；`concurrent-design-review` owns coverage、独立 reviewer 派发、模型/推理强度选择与复审条件。Gate 只提供 Spec、相关代码路径和风险范围，并依据该专项评审报告写入门禁状态。

## 评审清单（按类型）

**并发 / 锁**
- [ ] 是否存在 TOCTOU（check → act 之间有竞态）？
- [ ] `Condition.wait()` 是否均在非事件循环线程执行？
- [ ] 写者等待是否有防饥饿机制（`_writer_waiting` 类标志）？
- [ ] 超时策略：超时时退化行为是否比强制继续更安全？
- [ ] 所有计数器是否有下溢保护 + ERROR 日志？

**生命周期**
- [ ] 所有早退路径（return/raise）是否执行了 cleanup？
- [ ] 计时/追踪上下文是否在所有路径（含异常早退）中正确 detach？
- [ ] enter/exit 是否严格配对（未 enter 不得 exit）？

**共享可变状态**
- [ ] 模块级可变变量读写是否均在锁内？
- [ ] 多进程/多 worker 场景是否明确标注适用范围？

## 评审状态标记

评审通过后，在 Spec 文件末尾追加（Hook 会检查此标记）：

```
---
**评审状态**：已通过 | 评审轮次：N | 评审人数：1 | 评审者：独立专项 reviewer（详见 concurrent-design-review 报告） | 日期：YYYY-MM-DD
```

Plan 文件第一行须包含：

```markdown
> **关联 Spec**：`.ai/specs/YYYY-MM-DD-xxx.md`（已评审）
```

跳过评审时，Plan 文件第一行须包含：

```markdown
> ⚠️ 本计划跳过了 Spec 评审，风险自担。
```

## 禁止行为

- 高风险 Spec 无评审标记，不得静默创建 Plan
- 主 agent 或 Spec 作者不得评审自己的 Spec；不得以主 agent 自检替代独立子 agent 报告
- 未按 `concurrent-design-review` 的覆盖与独立性规则完成评审，不得标记为“已通过”
- 用户说"跳过"，必须写警告标注，不得不留痕迹地放行
