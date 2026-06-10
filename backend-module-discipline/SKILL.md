---
name: backend-module-discipline
description: Use before writing any code — as a pre-coding checklist to prevent boundary leakage, loose contracts, parallel boolean groups, symmetric copies, half-migrations, and size creep in backend services.
---

# 后端模块纪律

## 概述

复杂后端服务的架构腐化不是「某几个函数偶然写长了」，而是六类根因反复叠加的结果：

| 根因 | 典型表现 |
|------|----------|
| **边界泄漏** | 协调层承担子系统内部状态机、修复循环等细节 |
| **契约散装** | 跨层用裸 `dict` + 魔法字符串传递业务结果 |
| **平行表达** | 同一语义同时用枚举、布尔、字符串三套表达 |
| **对称副本** | 两处镜像流程各写一份，极易漂移 |
| **半迁移** | 引入新对象后留「逐步迁移」代理，永远未删 |
| **体量失控** | 单文件 2000+ 行，核心方法 500 行 / 7 出口 |

以下规则用于**新功能开发与评审**；存量超标按重构计划渐进消化。

---

## 一、模块边界

### 1.1 协调层只做协调

协调层（orchestrator / coordinator / engine / runner）只负责：**阶段调度、调用子系统、把结果写回上下文/响应流**。

禁止在协调层实现：
- 子系统的 shadow/enforce 模式分支
- 多轮修复 / 重试状态机
- 子系统专属的输出格式组装
- 子系统内部的归一化、审计拼装

**红线信号**：协调层中某子系统专用方法 ≥ 3 个，或单个子系统相关逻辑累计超过 ~80 行 → 应回迁到子模块门面。

### 1.2 子系统对外单一入口

每个子系统对协调层暴露**一个门面方法**；协调层不得直接调用内部实现方法。

构造也走工厂，禁止在 2+ 处手搓相同构造块：

```python
# ✅ 协调层只调门面
result = await guard_service.review(ctx)

# ❌ 协调层直接调内部
result = await guard_service._run_state_machine(ctx, mode="enforce")
await guard_service._emit_sse_events(result)
```

### 1.3 跨层传结果对象，不传实现细节

模块边界的主契约必须是 **dataclass / Enum / TypedDict**，禁止用裸 `dict` + 字符串 key 作为业务代码的主接口。

```python
# ✅ 类型边界
@dataclass
class GuardResult:
    decision: GuardDecision  # Enum
    reason: str

# ❌ 裸 dict 契约
{"status": "blocked", "reason": "...", "applied": True}
```

内部审计 / debug 可 `.to_dict()`，但**读写业务状态只用属性**。

---

## 二、数据与类型

### 2.1 枚举优先，禁止平行布尔组

用 `Enum` 表达互斥状态；不维护一组 `stopped_by_*` / `applied_*` 布尔再在出口翻译。

```python
# ✅
class StopReason(Enum):
    TOKEN_LIMIT = "token_limit"
    GUARD_BLOCK = "guard_block"
    TOOL_FINISH = "tool_finish"

# ❌
stopped_by_token: bool = False
stopped_by_guard: bool = False
stopped_by_tool: bool = False
```

状态字面量统一进枚举；**禁止**新增裸 `"status": "..."` 字符串（含大小写混用）。

### 2.2 参数过多 → 收拢 Context

| 信号 | 动作 |
|------|------|
| 函数参数 ≥ 8 | 收拢为 `XxxContext` / `XxxBinding` |
| 同类参数在 ≥ 3 个调用点重复传递 | 从 `ctx` 读取，调用点只保留差异参数 |
| 闭包捕获 ≥ 5 个变量并层层下传 | 提取上下文对象，闭包改方法 |

### 2.3 同构逻辑只写一次

- 结构相同的 handler → 工厂函数 + 模块级函数
- **对称代码**（两处流程镜像）→ 必须抽公共函数；禁止「先复制一份改改」
- 归一化、trace 构造、配置解析 → 单模块单函数；禁止复制到多文件

### 2.4 依赖用 Protocol，不用 `Any` + `getattr`

注入的 evaluator、provider、checker 等定义 `Protocol`，构造参数类型标注；测试 Fake 实现同一 Protocol。

---

## 三、体量红线

超限须在**本 PR 或紧邻下一 PR** 拆分，禁止无计划增厚热点文件。

| 对象 | 软上限 | 超限处理 |
|------|--------|----------|
| 单文件 | ~800 行（核心协调层可暂放宽至 ~1200，须有拆分计划） | 按职责拆文件 |
| 单方法 | ~80 行 | 按阶段/分支拆私有方法 |
| `__init__` 参数 | ~6 个 | 收拢为 Binding 对象 |
| 单方法 return 出口 | ≤ 3 个 | 用 Result 类型统一 |

**热点文件新增逻辑前先问**：这段代码放哪个子模块更合适？

---

## 四、迁移纪律

### 4.1 迁移要么做完，要么不做

禁止长期「向后兼容属性代理」「TODO 下一 PR 删」。

- 引入新对象时：**同一里程碑内**完成调用方迁移 + 删代理 + 改测试
- 兼容层最多存活 **1 个 PR**；PR 标题标注 `[迁移]` / `[收尾]`

### 4.2 结构重构的节奏

1. **契约先行**：跨边界先对象化 + contract test，再拆方法/文件
2. **字节等价**：纯搬迁不改行为；旧输出 vs 新输出字段级对比
3. **分步可回退**：每步独立 commit，全量相关测试通过再下一步

推荐顺序：边界对象化 → 删半迁移代理 → 拆 God method → 抽对称副本 → 文件物理拆分。

---

## 五、可测试性

- 可独立验证的校验逻辑、预算检查、结果构造 → **模块级函数**，不要包在 async 巨闭包里
- 判断标准：若必须 mock 整棵协调器才能测一段校验，说明层级放错了
- 跨边界改动须补 **contract test** 或集成测试

---

## 六、PR 评审清单

改动协调层或子系统边界时逐项过：

1. **边界**：协调层是否新增子系统内部分支/状态机/输出格式组装？
2. **契约**：是否新增裸 dict key、魔法 status 字符串、metadata 乒乓？
3. **重复**：是否与现有代码对称或三胞胎？能否抽公共？
4. **体量**：文件/方法是否越过软上限？本 PR 增厚还是瘦身？
5. **迁移**：是否留下属性代理、未删旧路径、open TODO？
6. **类型**：是否该收成 Context / Enum / dataclass？
7. **测试**：边界变更是否有 contract / 集成测试？

---

## 一句话原则

> **协调层只调度；子系统自闭环；边界用类型，不用 dict 传话；对称代码立刻抽；半迁移不过夜；超限先拆再写功能。**
