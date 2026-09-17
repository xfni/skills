# 审查占用统一恢复：实现与 Astra 复审

## 设计

采用同一当前绑定谓词和锁内核对函数，供恢复、工件绑定变化及成功记录代码快照复用。确定旧绑定的 STARTED 添加 recovery_disposition，仅解除当前占用；不改原始 status、classification、绑定、finding、收据或计数，不宣称进程已停止。

BODY digest 定义工件绑定，代码另绑定已记录的快照。APPROVAL 或 revision 单独变化不归档；缺失或无法核验的信息不自动变成陈旧。现有快照写前及漂移校验不变。安全暂停允许有限事实整理，但不清理 signal、原因、阶段或 pending action。

迟到旧绑定结果不能批准当前产物；digest A→B→A 不使已解除尝试复活。执行存活及可能冲突由 Agent 查询现有任务句柄，未知不能冒充终止或清理完成。没有新增进程管理平台或历史结果导入接口。

## 独立复审

配置：independent-review，implementation+concurrency，subagent，gpt-6-astra/medium。范围仅为统一占用恢复增量，不覆盖此前其他工作区修改。

第一轮发现两项阻塞，均已先回归复现再修复：

- REC-1：begin_review 的重复 digest/snapshot 精确过滤漏掉未知绑定，可能启动重叠审查。改为目标 key/backend 与统一活动谓词；缺 digest、缺代码尝试 snapshot 均有回归。
- REC-2：同阶段其他里程碑的 STARTED 跨目标阻断路由。统一谓词排除已知不同 milestone 的尝试，保留未知归属的保守处理，不改旧尝试历史。

同一 Astra 线程修改后限定复核：两项均 RESOLVED，HIGH 证据强度，无新增阻塞；独立执行生命周期 36 项全部通过。

## 验证

本地全量：`PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.10 -m unittest discover -s workflow-v2/tests`。

最终 289 项：288 通过、1 跳过，28.680 秒。flow-run quick_validate 与 git diff --check 通过。

回归覆盖产物替换、旧状态恢复幂等、当前 STARTED 保留、同 BODY 审批变化、安全暂停保留、A→B→A 迟到结果、未知 digest/代码 snapshot 的重叠启动、不同里程碑占用。测试使用临时仓库，不证明任何历史进程实际已结束。

本次未修改真实项目状态，未同步 Codex，未 Git 提交或推送。
