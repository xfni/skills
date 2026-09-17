# Flow 最小独立审查链：实现与复审

## 初衷及边界

标准为一条独立 GPT 审查链和一条外部审查链。真实不可用或人类明确限制路线时，至少一条有效独立审查链可有条件交接。不要求凑失败次数，不强制第三条 Astra consistency。一次指包含必要修复复核的审查链，不是一次调用。

控制器继续验证当前审查对象和有效收据；不能用作者自审、测试通过或模型不可用替代独立审查。历史阻塞发现跨版本及路线保留；原审查者通常复核，不可用时由独立接管审查者携带原发现、修复和证据明确关闭。

## 实现

- `review degrade --lane gpt|external --basis human|unavailable --reason ...` 登记真实路线限制或 Agent 观测原因。登记为 CALLER_ATTESTED，不冒充运行失败或 PASS。人类限制沿当前运行复用；不可用记录绑定当前工件及代码快照。
- `review_completion` 使用最小保证决定交接；缺失标准路线记录 `EXTERNAL_REVIEW_GAP` 的 lane、原因及实际失败尝试，结果为有条件通过。
- 独立报告可以用 `resolved_reviews` 引用同工件的历史阻塞尝试并说明复核证据；另一路普通 PASS 不自动清除发现。原报告及绑定不修改。
- 保留旧 consistency 收据和接口用于兼容，但不再强制执行第三审。
- Flow Spec、Plan、Code、Run 和共享合同，以及独立 Cursor/iBrain 技能已同步本次规则。未修改外部 runner、模型默认值或凭证。

## Astra 独立复审

配置：`independent-review / implementation / subagent / gpt-6-astra / medium`。

第一轮发现 `ibrain-fallback-requires-cursor-failure`：登记 Cursor 工具不可用后，iBrain 仍要求一次 Cursor 失败。已先用回归测试复现，再允许有效的当前 external/unavailable 记录支持备用路线；不伪造 human selection 或 Cursor attempt。

同一 Astra 线程修改后限定复核结论：F-1 已解决，最终审查通过。独立运行生命周期测试 28 项全部通过。

前向场景经临时 fixture 验证：纯 GPT 有效保证可有条件交接；旧权限绕过发现不能被新版普通 PASS 清除；零收据即使两路都降级也不能通过；GPT 不可用时可用有效 iBrain 报告继续。

## 本地验证

命令：`PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.10 -m unittest discover -s workflow-v2/tests`。

最终结果：281 项，280 通过、1 跳过，28.876 秒。修改的六个技能 quick_validate 全部通过；`git diff --check` 通过。

验证使用临时测试仓库及受控 transport，不证明真实供应商当前可用。独立 GPT 执行、自然语言降级原因和修复证据判断仍由 Agent 负责，不声称控制器能够证明模型身份或内容正确性。本次未发送项目内容给外部供应商，未修改真实项目控制器，未同步 Codex、未 Git 提交或推送。
