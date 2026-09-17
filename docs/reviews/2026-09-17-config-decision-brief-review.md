# 配置必要性与需求决策概要：修改及验证记录

## 边界

基线为 master `de5ec0ac6c8c3670b6aaba4b7bc2f4afe109c2f4` 加已有未提交的需求蜂群优化。人类批准本轮设计并要求完成后交 Astra 复审。本轮仅改技能、角色提示和共享文档；不改 flowctl、schema、全局 AGENTS.md 或 coding-guidelines，不提交、推送或部署。

新增可选行为按实际作用判断，不默认增加开关。必要性在既有设计理由中说明，按风险取舍验证及维护成本；保留安全和测试隔离。决定经 Spec、Plan、TASK 传给 coder，新发现交主 Agent 局部处理，不新增控制器字段、配置表单或人工门禁。

每次实质需求探索结束给完整 Decision Brief，覆盖推荐、人类已选与待决、目标、范围/非目标、取舍、重要风险、证据限制和下一步。摘要不单独确认，不靠措辞更新撤销旧授权；重要风险不因篇幅或场景数量截断。

## 行为演练

使用隔离上下文的只读 subagent，按实际技能处理假设任务，不启动 Flow、PMS、业务服务或人工交互，不写业务文件。不是五次重复的统计实验，也不是全流程实施证明。

修改前：

- `config_brief_baseline` 读取旧共享契约、Requirement、Code 和 coder。三个场景为不必要默认关闭开关/API 模式、轮次耗尽且产品选择未决、安全停用与恢复措辞修正。
- `coder_variability_baseline` 仅读旧 coder 角色，在工期紧、root 忙、资深同事建议的压力下纸面处理 TASK。
- 配置场景已经正确拒绝推测性开关；不能声称本轮修复了已观察到的配置失误。coder 原话：『不添加 `ENABLE_NEW_MATCHER`，不新增 `mode=legacy|new`。它们会引入未批准的环境差异和调用分支』。
- 轮次耗尽输出有推荐、选项、成本未知和未跑服务限制，但没有完整交付边界及显式非目标，体现“待选菜单”与完整概要的差异。原话：『目前有两个可行方向，但过滤应该覆盖哪些调用方，还需要你选择』，后续进入两条方向及待选问题。本轮补输出结构，配置部分主要补最短跨阶段传播和必要控制边界。

修改后：

- `config_brief_forward` 新上下文读取更新后的共享契约、Requirement/协议、Spec、Plan、Code 和 coder，复测同三场景。
- 普通过滤输入不误判为运营配置，拒绝推测性开关；任务包明确『不新增开关、环境变量或兼容模式』，不增加人工确认。
- 轮次耗尽概要明确用户/目标、推荐与条件备选、最小服务器范围、非目标、成本未知、源码推断不等于实测、下一步及最终授权未发生。原话：『最小范围是现有列表接口的过滤能力及其验证，不扩建通用过滤框架』；『也不把新 UI、通用平台或两套并存逻辑列入承诺』。
- 保留真实安全开关，不假定热更新，不把关闭/回退当撤回已发送消息；措辞恢复不重新授权。实际停用时限仍待实施验证。
- 同一测试线程追加边界：无待决项仍输出目标、范围/非目标、成本和未验证说明再使用既有最终授权；无可行备选的阻塞仅报已知成果及缺口，不造方案；直接 Code 不追补 Requirement/配置收据，使用既有测试 Mongo 连接配置不变成新增产品开关，但目标/隔离和宿主权限仍须核验；单用户安全需求可成立，不自行增加 hot reload，临时开关明确撤除归属。以上追加测试共享前次上下文，不是独立重复样本。

以上为单样本纸面演练，未独立执行安装后的自定义 coder，没有验证真实代码/TDD效果或长轮次稳定性。

## 机械验证

- `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s workflow-v2/tests -v`：运行 276 项，275 项通过、1 项跳过，22.521 秒。跳过项需要已安装 Cursor SDK；不联网。既有测试通过不证明模型必然遵守新增提示。
- skill-creator `quick_validate.py` 分别校验 flow-requirement、flow-spec、flow-plan、flow-code：全部成功。
- 当前 `python` 为 3.10，首次使用 `tomllib` 不可用；改用已安装 `tomli.loads` 校验 coder、value、risk 三份 TOML：全部成功。不是未修复的角色配置错误。
- `git diff --check`：成功；flowctl.py、flowctl_lib 和 schemas 没有 diff。

## Astra 复审

`astra_config_and_decision_brief_design`，`implementation / subagent / gpt-6-astra / medium`，只读复审原文件、相关完整 diff 和新 swarm 参考文档，独立运行 diff 空白检查。

结论：符合已收敛设计，无实质阻断或需重新人类决策的歧义。原四项发现均 resolved：

- CFG-01 / `config-semantic-boundary`：按作用识别 API 模式，正常业务输入和常量不会自动成为运营配置。
- CFG-02 / `config-lifecycle-cost`：必要安全/隔离、停用/回滚/恢复、风险加权验证及临时撤除范围。
- BRIEF-01 / `decision-brief-exit-coverage`：所有实质退出完整概要，不造选项、不硬截风险、不新增确认门。
- CFG-03 / `config-task-propagation`：决定进入 coder TASK，直接入口不追索历史配置收据。

文档证据强度 high；这不是部署、真实业务效果或统计有效性证明。Astra 未独立复跑主 Agent 的行为样本和 276 项测试，未作该部分通过声明。
