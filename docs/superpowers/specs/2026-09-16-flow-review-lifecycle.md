# Flow 评审生命周期修复

修复已确认的五类问题：草案登记要求先批准、恢复生成不可执行下一步、外部修复重开 GPT、INCOMPLETE findings 重试矛盾、外部审查异常遗留 STARTED。

- Spec/Plan/Code 的 DRAFT 可登记及受控评审，不代表批准。批准只更新 envelope；BODY 不因评审完成改写。批准更新不使相同内容的评审失效，未批准仍不可交接。
- 登记、评审结束和恢复复用同一局部下一步选择，覆盖 GPT、Cursor、iBrain、最终一致性、批准及交接。外部修复保留有真实回执的 GPT lane，恢复亦保留明确的 carry-forward 依据；一致性失败仍重开必要 lanes。
- INCOMPLETE 有阻塞 finding 返回所属模型修复；没有阻塞 finding 可同内容补证重试，保留有限轮数。未知结论不能变成通过。
- begin 后的可捕获外部审查异常必须留下非通过的终结记录，保留安全错误分类，不允许活跃 attempt 被猜测取消。进程被强杀的宿主恢复不在本次自动推断范围。
- 保留当前 digest、真实报告回执、代码快照、单次外发绑定、权限和回放清理约束。不得增加新授权门或全历史验证。

现有重复选择分别位于 state.register_artifact、reviews.submit_review/record_process_result、resume.reconcile_resume，三处对同一评审依赖产生不同动作；抽取局部函数而非通用控制器框架有直接必要性。
