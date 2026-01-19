---
name: auto-unit-test
description: Automatically generates and executes unit tests for public methods. Detects language (Java/TypeScript/Python), identifies test frameworks (JUnit/Jest/PyTest), generates tests following project conventions, validates syntax, runs tests, and marks uncovered branches. Use when adding or modifying public methods, or when user requests "生成单元测试".
---

# 自动完成单元测试编写与执行

## 触发条件

在以下情况下自动应用此技能：
- 用户新增 public 方法
- 用户修改 public 方法
- 用户明确请求"生成单元测试"或类似表述

## 执行流程

### 1. 识别语言和测试框架

检测当前文件语言：
- **Java**: 查找 `*.java` 文件，检查是否使用 JUnit 4/5、TestNG
- **TypeScript/JavaScript**: 查找 `*.ts`/`*.js` 文件，检查是否使用 Jest、Mocha、Vitest
- **Python**: 查找 `*.py` 文件，检查是否使用 pytest、unittest

检测方法：
- 检查 `pom.xml`、`build.gradle`（Java）
- 检查 `package.json`、`jest.config.js`（TypeScript/JavaScript）
- 检查 `requirements.txt`、`pytest.ini`、`setup.py`（Python）
- 查看现有测试文件的导入语句和装饰器

### 2. 检查现有测试

查找对应的测试文件：
- **Java**: `src/test/java/` 下相同包结构的 `*Test.java` 或 `*Tests.java`
- **TypeScript**: `__tests__/` 或 `*.test.ts`、`*.spec.ts`
- **Python**: `test_*.py` 或 `*_test.py`，通常在 `tests/` 或 `test/` 目录

如果测试已存在：
- 读取现有测试文件，分析代码风格和模式
- 检查是否已覆盖目标方法
- 如果已覆盖，询问是否更新现有测试或创建新测试用例

### 3. 生成单元测试

遵循项目现有测试代码风格：
- 复制现有测试的导入模式、命名约定、断言风格
- 使用相同的测试类/函数结构
- 保持一致的 mock 和 fixture 使用方式

生成测试内容：
- 为每个 public 方法创建测试方法/函数
- 覆盖正常流程、边界条件、异常情况
- 使用有意义的测试名称，描述测试场景
- 添加必要的 setup/teardown 逻辑

### 4. 语法校验

在生成测试后立即验证：
- **Java**: 检查编译错误（如可能，使用 `javac` 或 IDE 检查）
- **TypeScript**: 检查类型错误（如可能，使用 `tsc --noEmit`）
- **Python**: 检查语法错误（使用 `python -m py_compile` 或 `ast.parse`）

如果发现语法错误，修复后重新验证。

### 5. 执行单元测试

运行生成的测试：
- **Java (JUnit)**: `mvn test` 或 `./gradlew test`，或直接运行测试类
- **TypeScript (Jest)**: `npm test` 或 `jest <test-file>`
- **Python (pytest)**: `pytest <test-file>` 或 `python -m pytest <test-file>`

捕获测试结果：
- 记录通过的测试数量
- 记录失败的测试及其错误信息
- 如果测试失败，分析原因并修复

### 6. 标记未覆盖分支

分析代码覆盖率（如工具可用）：
- 识别未执行的代码分支
- 在测试文件中添加 `TODO` 注释，标注未覆盖的逻辑

示例标记格式：
```python
# TODO: 未覆盖分支 - 当 input 为 None 时的异常处理
# TODO: 未覆盖分支 - 边界条件：空列表输入
```

## 输出格式

**只输出单元测试代码及运行结果摘要，不输出解释文字。**

### 测试代码输出格式

```python
# 直接输出完整的测试代码，无需额外说明
```

### 运行结果摘要格式

```
测试执行结果：
- 通过: 5/5
- 失败: 0
- 覆盖率: 80% (4/5 分支)

未覆盖分支：
- [TODO] 异常处理分支：当参数为 None 时
```

## 语言特定指南

### Python (pytest)

测试文件命名：`test_<module_name>.py`
测试类命名：`Test<ClassName>`
测试方法命名：`test_<method_name>_<scenario>`

```python
import pytest
from module import ClassName

class TestClassName:
    def test_method_name_normal_case(self):
        # 正常流程测试
        pass
    
    def test_method_name_edge_case(self):
        # 边界条件测试
        pass
    
    def test_method_name_exception(self):
        # 异常情况测试
        pass
```

### Java (JUnit 5)

测试类命名：`<ClassName>Test`
测试方法命名：`test<MethodName><Scenario>`

```java
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ClassNameTest {
    @Test
    void testMethodNameNormalCase() {
        // 正常流程测试
    }
    
    @Test
    void testMethodNameEdgeCase() {
        // 边界条件测试
    }
}
```

### TypeScript (Jest)

测试文件命名：`<module>.test.ts` 或 `<module>.spec.ts`

```typescript
import { ClassName } from './module';

describe('ClassName', () => {
    test('methodName normal case', () => {
        // 正常流程测试
    });
    
    test('methodName edge case', () => {
        // 边界条件测试
    });
});
```

## 注意事项

1. **保持简洁**: 生成的测试代码应该清晰、简洁，避免过度复杂的 setup
2. **遵循约定**: 严格遵循项目现有的测试代码风格和约定
3. **实际可运行**: 确保生成的测试可以在项目环境中实际运行
4. **有意义断言**: 每个测试都应该有明确的断言，验证预期行为
5. **独立性**: 测试之间应该相互独立，不依赖执行顺序
