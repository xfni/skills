# EXP-DEMO-001 实验记录

## 范围与起始状态

- issue：`issues/3`
- 实验代号：`EXP-DEMO-001`
- 类型：本地固定样本配对预开发实验；不涉及生产数据、生产源、部署或外部模型调用。
- 起始代码版本：`fac03481737f98dd6e7854a7201901d618ae4b62`
- 起始工作树：目标目录 `experiment-workflow/tests/demo/` 运行前无文件；其他未跟踪改动属于并行 Agent，未读取或修改。
- 数据：6 条无敏感信息的固定内联虚构查询，数据版本 `fixed-inline-v1`。
- 起始规则：

  ```text
  baseline(query)  = query
  candidate(query) = query.lower().strip()
  ```

baseline 和 candidate 使用独立预测函数；成功率由实际逐样本布尔结果计算，未让两种策略调用同一预测逻辑形成 tautology。

## 参数、配额与执行

- 配对：每条固定输入同时运行 baseline 和 candidate。
- 分母：全部 6 条样本；未过滤失败样本。
- 正式比较配额：1 个数据集、1 轮；已用 1 轮，剩余 0 轮。
- 驱动/指标单测：一次 unittest 检查；不计入正式比较轮次。
- 资源边界：本地标准库、CPU 上限 30 秒；无网络、无外部模型调用。
- CPU 时间：未单独测量；执行未使用计时器，不能报告实际 CPU 秒数。
- 原始机器可读结果：`experiment_result.json`。
- 执行证据：`red_test_output.txt`、`green_test_output.txt`、`formal_command_output.txt`。

实际命令与退出码：

```text
python -m unittest discover -s experiment-workflow/tests/demo -p 'test_*.py'
退出码：1（RED，实现在测试后才添加）

python -m unittest discover -s experiment-workflow/tests/demo -p 'test_*.py'
退出码：0（GREEN，3 个测试）

python experiment-workflow/tests/demo/demo_experiment.py --output experiment-workflow/tests/demo/experiment_result.json
退出码：0（正式比较）
```

## 指标与全部样本结果

| 策略 | 正确 | 总数 | 成功率 |
| --- | ---: | ---: | ---: |
| baseline | 2 | 6 | 0.3333333333333333 |
| candidate | 5 | 6 | 0.8333333333333334 |

| 样本 | query | label | baseline prediction / 成功 | candidate prediction / 成功 |
| --- | --- | --- | --- | --- |
| case-01 | `"  HELLO "` | `hello` | `"  HELLO "` / 否 | `hello` / 是 |
| case-02 | `bye` | `bye` | `bye` / 是 | `bye` / 是 |
| case-03 | `HELLO` | `hello` | `HELLO` / 否 | `hello` / 是 |
| case-04 | `bye!` | `bye` | `bye!` / 否 | `bye!` / 否 |
| case-05 | `hello` | `hello` | `hello` / 是 | `hello` / 是 |
| case-06 | `"  bye"` | `bye` | `"  bye"` / 否 | `bye` / 是 |

## 结论、失败与限制

- 在这 6 条固定本地样本上，candidate 比 baseline 多正确 3 条：2/6 → 5/6；这是样本内描述性观察，不是线上收益或因果结论。
- `bye!` 仍然失败，candidate 未处理标点；失败样本已保留在 JSON 和上表中。
- 样本是小规模、固定、虚构且未独立复验；调参/复验没有执行，因此不能外推到真实流量、整体业务或生产质量。
- 未进行 independent review；本记录仅提供 worker 的可重建代码、数据、命令和实际结果。
- 未修改生产业务实现或默认配置；无生产副作用需要清理。
