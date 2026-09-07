---
name: coding-observability-errors
description: Use when writing service layer code, utility functions, external integrations, or exception handling - enforces logging conventions, comment standards, exception handling, and error propagation rules
---

# 可观测性与异常治理

编写 Service 层、工具类、外部调用、异常处理代码时必须遵守。

## 1. 日志埋点（Tracing）

所有核心逻辑必须具备以下日志足迹：

| 节点 | 内容 | 等级 |
|------|------|------|
| 入口(Entry) | 方法名 + 关键输入参数（脱敏） | INFO |
| 关键节点(Milestone) | 分支切换、循环开始、异步调用时的当前状态 | INFO |
| 出口(Exit) | 处理结果或耗时 | INFO |
| 排查逻辑 | 中间变量、条件判断细节 | DEBUG |
| 预期内异常 | 业务预期中的错误（如余额不足） | WARN |
| 系统崩溃 | 不可恢复错误 | ERROR |

```python
def transfer(from_id, to_id, amount):
    log.info("transfer entry: from=%s, to=%s, amount=%s", from_id, to_id, amount)
    if not sufficient_balance(from_id, amount):
        log.warn("insufficient balance: from=%s, amount=%s", from_id, amount)
        return Result.fail("INSUFFICIENT_BALANCE")
    log.info("transfer exit: from=%s, to=%s, success", from_id, to_id)
```

## 2. 注释规范

**Docstring/Javadoc**：每个公共函数必须包含标准头注释，说明功能、参数边界和可能的副作用。

**"为什么"而非"是什么"**：注释解释复杂业务背景或历史特殊处理，不解释语法。

```python
# ❌ 将用户列表按年龄排序
users.sort(key=lambda u: u.age)

# ✅ 按年龄排序确保年长用户优先分配有限资源（政策 2024-03 生效）
users.sort(key=lambda u: u.age)
```

## 3. 异常治理

| 规则 | 说明 |
|------|------|
| 异常不留空 | 严禁 `catch {}`、`except: pass`、空 catch 块 |
| 错误码封装 | 分布式系统中，异常必须映射为标准化错误码（Code）和用户友好信息（Message） |
| 资源释放 | 必须使用 `try-with-resources`(Java)、`with`(Python)、`defer`(Go) 确保可靠关闭 |

```java
// ❌
try { ... } catch (Exception e) { }

// ✅
try { ... } catch (Exception e) {
    log.error("failed to process order: orderId={}", orderId, e);
    throw new BizException(ErrorCode.ORDER_PROCESS_FAILED, e);
}
```

## 4. 错误传播策略

| 错误类型 | 处理方式 | 示例 |
|----------|----------|------|
| 可恢复错误 | 返回 error/code，由调用方决定处理 | `return Result.fail("INVALID_INPUT")` |
| 不可恢复错误 | 抛异常/panic，向上传播 | `throw new SystemException("DB_CONNECTION_LOST")` |

**跨服务调用必须有超时**，默认值不低于 P99。

```go
// ❌
resp, err := http.Get(url)

// ✅
ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
defer cancel()
req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
resp, err := client.Do(req)
```

## 红色警报 — 立即停下

| 这个念头 | 实际含义 |
|----------|----------|
| "先 catch 住，以后再填日志" | 以后不会填。现在就写日志或重新抛出 |
| "这个异常不影响主流程，忽略就好" | 不影响主流程也要记日志，否则排查时是盲区 |
| "超时用默认的就行" | 默认超时可能无限等待，必须显式设置 |
| "错误码以后再统一" | 以后不会统一。现在就用标准 Code+Message |
