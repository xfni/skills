---
name: coding-hard-constraints
description: Use when writing, reviewing, or refactoring any code - enforces structural rules including Yoda conditions, defensive programming, early returns, strong typing, function complexity limits, security boundaries, and concurrency safety
---

# 编码硬约束

编写、审查、重构任何代码时必须遵守。

## 1. Yoda 条件判断（核心强制）

常量/null 必须在比较运算符左侧。

```
✅ if (nil == err)         (Go)
✅ if (None is value)      (Python)
✅ if (undefined === data) (JS/TS)
❌ if (err == nil)
❌ if (value is None)
```

**简化规则**：可无损简化为布尔取反时，优先简化。

```
✅ !isValid
❌ false == isValid
```

## 2. 防御式编程

**对象访问**：严禁深度链式调用。

```typescript
// ❌
const city = user.address.city;
// ✅
const city = user?.address?.city;
```

```python
# ❌
city = user.address.city
# ✅
city = user.address.city if user and user.address else None
```

**集合返回**：函数返回集合时，严禁返回 null/None/undefined，必须返回空集合。

## 3. 早返原则

通过卫语句减少嵌套，主逻辑始终在最左侧缩进。

```typescript
// ❌
function process(order) {
  if (order) {
    if (order.isPaid) { /* 主逻辑 */ }
  }
}
// ✅
function process(order) {
  if (!order) return;
  if (!order.isPaid) return;
  /* 主逻辑 */
}
```

## 4. 类型与数据结构

| 规则 | 说明 |
|------|------|
| 禁止动态对象传递 | 严禁 `Map<String,Object>`、裸 `dict`、`Record<string,any>` 传递核心业务数据 |
| Schema 驱动 | 必须定义强类型：Java Record、Python Pydantic/Dataclass、TS Interface、Go Struct |
| 配置管理 | 禁止硬编码配置，通过环境变量/配置文件读取，并提供默认值 |

## 5. 函数复杂度边界

| 指标 | 上限 | 超出处理 |
|------|------|----------|
| 单函数行数 | 40 行 | 拆分为更小函数 |
| 参数个数 | 4 个 | 超出用结构体/对象收拢 |
| 嵌套层级 | 3 层 | 超出用早返拆解 |

## 6. 安全边界

| 规则 | 说明 |
|------|------|
| 输入校验 | 外部输入（HTTP、MQ、文件）必须在系统边界处校验，内部代码信任自己的类型 |
| 注入防护 | 禁止拼接 SQL/命令，参数化是唯一选项 |
| 日志脱敏 | 密钥、token、PII 禁止落日志 |

## 7. 并发与异步安全

| 规则 | 说明 |
|------|------|
| 共享可变状态 | 必须显式保护（锁/通道/原子操作），禁止裸读写 |
| 异步错误传播 | 严禁静默吞掉 `Promise.reject` / goroutine 中的 panic |
| 锁顺序 | 多锁场景必须规定获取顺序，防止死锁 |

## 红色警报 — 立即停下

| 这个念头 | 实际含义 |
|----------|----------|
| "这里不可能为 null" | 加可选链/空检查，运行时什么都不保证 |
| "只是内部调用，不需要校验" | 今天是内部，明天就是公开 API |
| "这段代码不会被并发访问" | 加保护，未来使用者不知道你的假设 |
| "一行拼接问题不大" | 参数化只需多写 3 个字符 |
| "函数长了点但逻辑连贯" | 超过 40 行就该拆，连贯不是理由 |
