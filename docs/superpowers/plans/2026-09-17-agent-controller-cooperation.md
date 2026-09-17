# Agent–Controller Cooperation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline task-by-task execution. Steps use checkbox syntax. The human has authorized implementing the reviewed design in the current working area; preserve all pre-existing edits. This is a controller refactor, not standalone feature admission.

**Goal:** Agent 主导流程，控制器只核对当前动作确定事实并记账。

**Architecture:** 沿用现有模块和事务。收敛收据事实查询、用一个可选处置引用承载 Agent 的语义适用性判断，登记与位置解耦，恢复优先已有记录，不增加工作流框架。

**Tech Stack:** Python 3.10 标准库、unittest、JSON CLI、Markdown skills。

**Spec:** ../specs/2026-09-17-agent-controller-cooperation-design.md

## Global Constraints

- 原收据摘要、来源、终态不改写；明确撤销、已知 blocker、宿主禁令不能被处置豁免。
- 当前收据与历史保证适用性分开；CALLER_ATTESTED 不升级为 CONTROLLER_EXECUTED。
- 保留 CLI 必需参数、状态格式、四状态三结果；仅增加可选入口及处置引用。
- 不改业务 state/events，不提交、推送或部署，除非人类另行要求。
- 每个 TASK 先观察真实行为失败，再实现并验证；既有变更保留。

## TASK-1：入口、登记和位置（AC-2/8/12）

**Files:** state.py、cli.py；tests/test_agent_cooperation.py。
**Interfaces:** initialize_state(..., stage='flow-requirement', milestone=None)；register_artifact(..., disposition_path=None)。已有参数顺序不变。

- [x] 创建真实 Git 临时仓库；init 到 flow-code/M1，再登记 Code，断言不制造 Spec/Plan 完成。
- [x] 登记 Requirement 补说明，断言已有 Plan/Code 和当前 Code 位置保留；complete 补材料仍 complete。
- [x] Run `python3 -m unittest discover -s workflow-v2/tests -p test_agent_cooperation.py`，观察入口或保留位置断言失败。
- [x] 增加 init 的 --stage/--milestone，只新 controller 生效；登记仅更新对象和建议，不推断业务失效、不改 upstream 原绑定。

```python
state = initialize_state(path, 'BCS-710', root, 'feature-BCS-710-test',
                         stage='flow-code', milestone='M1')
assert state['current_stage'] == 'flow-code'
assert not state['artifacts']
```

- [x] 验证 TASK-1 测试通过，记录原行为测试中需要按已批准设计调整的断言。

## TASK-2：历史保证和可复用处置（AC-3/4/5/6）

**Files:** reviews.py、state.py、snapshot.py、handoff.py，必要时单一 dispositions.py；test_agent_cooperation.py。
**Interfaces:** `--disposition <json>`；最小 reason/evidence、source_attempts 或 route_event；代码计算新对象摘要和实际快照。

- [x] 写旧真实 PASS 在补说明后不可直接移植、处置后可支撑对应交接的命令序列。
- [x] 写 missing receipt、FAILED、revoked、再次变化拒绝复用的反例。
- [x] 观察失败后，实现纯收据事实查询及处置绑定；共享于 register/resume/handoff/snapshot。

```python
material = {'reason': 'Explanation only; scope and implementation unchanged',
            'evidence': [str(report)], 'source_attempts': original_attempts}
```

- [x] 保留原 report/role/source；只登记 Agent 适用性，恢复索引不复活明确撤销。
- [x] 验证新 Code 和当前 review role 计数独立；保持有界实际运行重试。

## TASK-3：恢复、撤销和 pause（AC-1/3/4/8/10/11）

**Files:** resume.py、signals.py、signal.schema.json；test_agent_cooperation.py 和 existing recovery tests。
**Interfaces:** resume 原位置不重规划；signal 的可选 pause_revision，未提供时从当前 pause 自动定位。

- [x] 写重复恢复位置不变、无关历史候选不影响登记、explicit route-back 原证据仍可定位的反例。
- [x] 写错误 pause revision 不清 gate、existing init 不清 gate。
- [x] 观察失败，再把已有 controller 的恢复收敛为事实刷新；首次入口由 init 明确，不扫描重选已有阶段。
- [x] 显式 route-back 撤销当前保证时保存被引用的旧 snapshot/artifact/gap；RESUMED 关联原 gate，而不是自然语言真假校验。
- [x] 验证事务冲突不会重复外部执行，原原子写入协议不变。

## TASK-4：失败可记录、工具故障交 Agent（AC-7/9/11）

**Files:** integration_results.py、artifacts.py、signals.py、handoff.py、errors.py/cli.py；test_agent_cooperation.py。
**Interfaces:** 不新增 stage/result；原 ok/code/details 可加 missing/warnings/suggested_actions。

- [x] 写 legacy Plan 无场景表可记录 BLOCKED、完成缺证不能 PASS、补充结果不能掩盖别的失败。
- [x] 观察失败后，取消 normal 场景全集匹配门禁，保留结果终态、当前对象及原结果引用。
- [x] 不把 helper 故障/UNCLASSIFIED/预算耗尽自动转换成全球人工或业务阻塞；返回补证/repair 提示，原状态保留。
- [x] 验证不可解析终审不提升为 PASS、不凭模型猜 vendor wording 获得 fallback。

## TASK-5：契约与技能同步（AC-12）

**Files:** flowctl-contract.md、orchestration-contract.md、review-contract.md、artifact-contract.md、flow-contract.md、README.md、Flow skills。

- [x] baseline agent 演练“已在 Integration、旧字段缺失/工具 unknown、用户要求继续”，保存其实际选择。
- [x] 精简控制器总调度措辞，说明 pending_action 是建议，Agent 提出受控动作；不绕过真实审批与权限。
- [x] 给最小入口及处置例子，说明历史外审范围而非新快照 PASS。
- [x] 新指导下重跑相同演练，核对自主安全修复而非无依据人类解锁。
- [x] quick_validate 所有 9 个 Flow skill；检查旧矛盾措辞及不必要新门禁。

## TASK-6：完整验证与 Astra 审阅

- [x] Run `PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m unittest discover -s workflow-v2/tests`；核对终态、跳过与错误输出。
- [x] 在临时复制的 BCS-690/716 状态中演练恢复；只读原工作区，校验原 state/events 摘要不变。
- [x] Run `git diff --check`，核对本轮及既有工作区差异。
- [x] Astra/medium 按 implementation+concurrency profile 审阅实际代码、设计、测试及证据边界；修复已确认 blocker，限定复审。
- [ ] 交付测试、审阅结论、未部署/未提交事实；不自动 push。
