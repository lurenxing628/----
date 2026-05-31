---
doc_type: roadmap-start-plan
roadmap: aps-frontend-workbench
created: 2026-05-31
last_reviewed: 2026-06-01
status: current
source_docs:
  - aps-frontend-workbench-roadmap.md
  - aps-frontend-workbench-items.yaml
  - drafts/2026-05-31-aps-frontend-page-design-spec.md
  - ../../audits/2026-05-31-aps-frontend-workbench-design-gap/index.md
---

# APS 前端工作台开工总方案

## 0. 这份方案是干什么的

这份文档不是新的调研，也不是视觉稿。它是给后续真正开工用的总施工单。

大白话说：前面已经知道“成熟 APS 前端应该像计划员工作台”，也审过“当前项目和设计稿差在哪里”。这份方案要回答下一步怎么动手：

- 先做哪一块，后做哪一块。
- 每一块具体改哪些页面。
- 哪些只改排版。
- 哪些要新增后端数据或 ViewModel。
- 哪些测试要跟着补。
- 哪些短期明确不做，避免边做边发散。
- 做完怎么算完成。

## 1. 已经拍板的短期口径

这些口径后续 feature-design 必须遵守，除非用户重新拍板。

### 1.1 系统短期使用方式

- 当前系统主要还是计划员一个人操作。
- 现场人员把情况汇报给计划员，计划员再录入系统。
- 现在不按“多人车间终端”来设计。

### 1.2 短期明确不做

- 不做反馈人必填。
- 不做多人账号权限。
- 不做现场员工登录后自己填报。
- 不做 Excel 导入预览 / 二次确认。
- 不做完整 MES 异常闭环。
- 不做扫码、消息推送、审批流。
- 不开放甘特拖拽写库。
- 不改排程算法。
- 不引入外部前端框架、外链脚本、外链样式或外链字体。
- 不升级会破坏 Python 3.8、Win7 x64、Chrome 109 的依赖或语法。

### 1.3 短期仍然要做

- 计划员打开首页后，要知道今天先处理什么。
- 页面之间跳转不能丢版本、方案、日期、批次或资源。
- 看到风险后，要能继续跳到能处理问题的页面。
- 非正式方案不能让计划员误以为能写现场实际。
- 资源负荷、停机影响、延期解释要用保守说法，不能把“没数据”说成“没风险”。

## 2. 总体路线

第一版不要追求“大而全”。第一版目标是让计划员能顺着一条路线做事：

```text
计划工作台首页
  -> 今日待处理
    -> 排产分析：看推荐方案和风险
    -> 甘特图：看任务位置和详情
    -> 资源派工：看排班和录现场实际
    -> 报表中心：看超期、资源负荷、计划和现场实际
```

这里先把三个容易混的词拆开：

- **第一轮开工包**：马上可以开工的最小三件事，只做“上下文链接合同、顶层入口、首页值班台第一版”。
- **第一版工作台**：第一轮之后继续补分析页、甘特详情、资源派工分层、报表最小回跳和主流程测试，让工作台能端到端走通。
- **第二阶段增强**：延期解释接现场事实、甘特资源负荷摘要、停机任务级影响、牵连批次/订单影响面。这些有价值，但不挡第一轮开工。

第一轮开工状态：

- 本方案已经允许进入第一轮开工包，不再等待新的口径确认。
- 阶段 0 是本方案自己的文档前置，本轮已经按用户拍板完成；阶段 0 不进入 `items.yaml`。
- 第一轮只包含包 A、包 B、包 C：包 A 对应第 5 节，包 B 对应第 6 节，包 C 对应第 7 节。
- 第 8 节及之后属于第一版后续或第二阶段增强，不属于第一轮马上开工范围。
- 第一轮必须带一组小烟测：顶层能进首页，首页能跳分析、甘特、资源派工、报表，并且版本、方案、日期不丢。

第一版成功标准：

- 从顶层导航 1 次点击能进入计划工作台首页。
- 从首页 1 次点击能到排产分析、甘特、资源派工、报表中心。
- 从首页待处理点出去后，目标页保留同一个版本、方案和日期范围。
- 计划员看到每类风险时，都有一个默认动作和一个备用动作。
- 普通用户可见文案都是中文业务话，不显示内部字段。
- 页面改动不破坏 Win7 离线交付。

## 2.1 下一位执行 Agent 直接开工规则

结论：下一位执行 Agent 可以直接按这份方案开第一轮，不需要再问用户确认产品口径。

它的第一步不是改代码，而是按 CodeStable 进入 `cs-feat-design`，先给 `workbench-context-link-contract` 写 feature design。只有这条 design 被确认后，再进入实现；后续再依次做 `workbench-nav-entry` 和 `dashboard-workbench-risk-todos`。

下一位 Agent 开工前只需要读这几份文件：

1. `.codestable/attention.md`
2. `.codestable/reference/system-overview.md`
3. `.codestable/roadmap/aps-frontend-workbench/2026-05-31-aps-frontend-workbench-start-plan.md`
4. `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md`
5. `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml`
6. `.codestable/roadmap/aps-frontend-workbench/drafts/2026-05-31-aps-frontend-page-design-spec.md`

开工时按这个顺序推进：

1. 先开 `workbench-context-link-contract` 的 feature design。
2. design 必须使用第 5.2 节的 9 个固定 `target_page`，不能自己另起名字。
3. design 必须把 `WorkbenchPlanContext`、`WorkbenchLink`、参数翻译表、关键跳转清单、非正式方案写入护栏写进验收。
4. design 不新增页面、不改算法、不做 Excel 预览、不做现场员工账号。
5. 设计确认后实现包 A，并跑 `tests/regression_scheduler_workbench_links_contract.py`。
6. 包 A 验收后再做包 B；包 B 验收后再做包 C。

如果下一位 Agent 发现文档和代码不一致，处理规则是：

- 代码里已有路由或字段名和文档名字不同：优先在 feature design 里写清翻译关系，不直接改业务路由。
- 文档内部再出现合同冲突：先回到本 roadmap 做 update，不在 feature 里悄悄绕开。
- 缺数据时：用中文说明“当前数据不足”，不能编影响面。
- 非正式方案下：不能输出写入按钮、表单 action、API URL、Excel 导入 URL、模板下载 URL 或 `data-*` 写入地址。

下一位 Agent 做完第一轮后，至少要能证明：

- 顶层有“计划工作台”或等价入口。
- 首页有今日待处理。
- 首页能跳分析、甘特、资源派工、报表。
- 跳转不丢版本、方案、日期。
- 页面正文不显示 `plan_role`、`scenario_id`、`op_id`、`schedule_id`、`source_table` 这类内部字段。

## 3. 开工顺序总览

建议按“阶段 0 + 11 个实施阶段”推进。阶段 0 是本文档前置，已经在本轮文档修正中完成，不进入 `items.yaml`。表里的“第一轮”才是马上开工范围，“第一版”是后续第一批可上线范围，“第二阶段”是增强项。

| 阶段 | 名称 | 目标 | 技术依赖 | 范围 |
|---|---|---|---|---|
| 0 | 口径收敛 | 修正文档中和当前拍板冲突的口径 | 无 | 开工前置 |
| 1 | 工作台上下文和链接 | 先保证跳页不丢上下文 | 无 | 第一轮 |
| 2 | 顶层计划工作台入口 | 让计划员知道从哪里进 | 阶段 1 | 第一轮 |
| 3 | 首页值班台和今日待处理 | 让计划员知道今天先处理什么 | 阶段 1、2 | 第一轮 |
| 4 | 排产分析行动层 | 先看推荐、风险和下一步，再看技术过程 | 阶段 1 | 第一版 |
| 5 | 甘特任务详情区 | 点任务后能稳定看到上下文和下一步 | 阶段 1 | 第一版 |
| 6 | 资源派工执行分层 | 把看排班和录现场事实分清 | 阶段 1 | 第一版 |
| 7 | 报表中心和明细回跳 | 报表看完能继续处理问题 | 阶段 1 | 第一版 |
| 8 | 工作台主流程测试 | 把第一版工作路线锁进测试和门禁 | 阶段 1-7 | 第一版 |
| 9 | 工作台用户指南 | 把真实页面路线写给计划员 | 阶段 8 | 第一版 |
| 10 | 延期解释接现场事实 | 延期解释不再忽略已经录入的现场事实 | 阶段 1、6 | 第二阶段 |
| 11 | 甘特资源负荷摘要 | 在甘特附近显示轻量资源压力 | 阶段 1、5 | 第二阶段 |

## 4. 阶段 0：口径收敛

### 4.1 要改什么

- 更新 roadmap/items 里关于 Excel 预览的旧说法。
- 更新资源派工相关条目，明确反馈人可空。
- 把“现场记录短期按计划员单人录入”写进方案和验收。
- 同步调整 roadmap/items 的开工顺序：上下文链接先行，顶层入口和首页依赖它。
- 如果总方案有阶段，items.yaml 必须有对应 feature 条目；没有条目的阶段不能放进第一版总验收。

阶段 0 本轮已完成，后续 feature-design 不需要再为这些口径停下来问人。

### 4.2 不改什么

- 不改代码。
- 不改测试。
- 不改数据库。

### 4.3 完成标准

- 计划文档里没有把反馈人必填写成短期必须做。
- 计划文档里没有把 Excel 预览、预览回执、二次确认写成短期必须做。
- `aps-frontend-workbench-roadmap.md`、`aps-frontend-workbench-items.yaml` 和本方案的开工顺序一致。
- 后续每条 feature-design 都能引用这个短期口径。

## 5. 阶段 1：工作台上下文和链接

### 5.1 为什么先做它

这是地基。没有统一链接，后面首页、分析、甘特、资源派工、报表都可能各拼各的 URL。最后用户点来点去，版本、方案、日期、资源就会丢。

### 5.2 具体要做

新增或整理一个统一的链接模块。这里的 ViewModel 大白话就是：新建一个专门负责生成跨页链接的小模块，别让每个页面自己拼 URL。

- 建议文件：`web/viewmodels/scheduler_workbench_links.py`
- 输出对象：`WorkbenchPlanContext`
- 输出对象：`WorkbenchLink`
- 负责把当前页面上下文翻译成目标页面能识别的 URL。

`WorkbenchPlanContext` 至少包含这些字段：

| 字段 | 含义 | 用户可见吗 |
|---|---|---|
| `version` | 排产版本号 | 可显示成“第 N 版” |
| `version_label` | 中文版本名 | 可见 |
| `plan_role` | adopted / baseline_best / critical_best 等内部方案身份 | 不直接显示 |
| `plan_role_label` | 中文方案身份 | 可见 |
| `scenario_id` | 模拟/候选方案内部编号 | 不直接显示 |
| `scenario_display_label` | 模拟/候选方案中文名 | 可见 |
| `date_from` / `date_to` | 工作台统一日期范围 | 不直接裸显示，转成中文范围 |
| `query_date` | 资源派工查询日期 | 可转中文 |
| `period_preset` | week / month / custom | 可转中文 |
| `batch_id` | 批次定位 | 可显示批次号 |
| `resource_type` | operator / machine / team | 可转人员/设备/班组 |
| `resource_id` | 资源内部 id | 不直接显示 |
| `resource_label` | 资源中文名 | 可见 |
| `is_preview` | 当前上下文是否只是预览或候选方案 | 不直接显示布尔值 |
| `can_write_feedback` | 当前上下文能否写现场实际 | 不直接显示布尔值 |
| `guardrail_text` | 不可写中文原因 | 可见 |
| `guardrail_reason_type` | plan_not_writable / task_state_blocked / action_unavailable / data_gap | 不直接显示，转成中文原因 |
| `capacity_source_label` | 容量来源，比如工作日历、班次、停机扣除情况 | 可见 |
| `capacity_gap_text` | 容量算不出来时缺什么数据 | 可见 |

`WorkbenchLink` 至少包含这些字段：

| 字段 | 含义 |
|---|---|
| `label` | 按钮或链接文案，比如“查看甘特图” |
| `url` | 目标地址；禁用时可以为空字符串 |
| `target_page` | dashboard / analysis / gantt / resource_dispatch / overdue_report / delay_diagnosis / utilization_report / execution_review / reports_index |
| `context_summary` | 中文说明，比如“第 12 版，正式采用方案，本周” |
| `disabled` | 是否禁用 |
| `disabled_reason` | 禁用中文原因 |
| `required_params` | 这条链接必须保留的参数名清单，用于测试 |

目标页字典第一版固定如下，后续实现不能自己另起名字：

| `target_page` | 页面 | URL 口径 | 必带参数 | 说明 |
|---|---|---|---|---|
| `dashboard` | 计划工作台首页 | `/` | 能拿到就带 `version`、`plan_role`、日期范围 | 顶层入口默认落点 |
| `analysis` | 排产分析 | `/scheduler/analysis` | `version`；候选方案带 `plan_role`、`scenario_id` | 看方案推荐和风险 |
| `gantt` | 甘特图 | `/scheduler/gantt` | `version`、`view`；能定位时带 `batch_id`、`resource_type/resource_id` | 看任务位置和详情 |
| `resource_dispatch` | 资源派工 | `/scheduler/resource-dispatch` | `version`、日期范围；能定位时带资源或批次 | 看排班，正式方案下由计划员代录现场事实 |
| `overdue_report` | 超期清单 | `/reports/overdue` | `version`；候选方案带 `plan_role`、`scenario_id` | 看哪些批次晚了 |
| `delay_diagnosis` | 延期解释 | `/reports/overdue` | `version`、`batch_id` 如果有 | 第一版复用超期清单里的延期解释列，不新增独立页面 |
| `utilization_report` | 资源负荷报表 | `/reports/utilization` | `version`、日期范围；能定位时带资源 | 看资源利用率和容量说明 |
| `execution_review` | 计划和现场实际 | `/reports/execution-review` | 正式采用 `version`、日期范围；能定位时带批次/资源 | 只看正式采用方案 |
| `reports_index` | 报表中心 | `/reports/` | 能拿到就带 `version`、日期范围 | 报表总入口 |

要统一处理这些参数：

| 业务意思 | 当前容易混的名字 | 方案口径 |
|---|---|---|
| 版本 | `version` | 继续用 `version` |
| 方案身份 | `plan_role`、`scenario_id` | URL 可带，页面显示中文 |
| 日期范围 | `date_from/date_to`、`start_date/end_date` | ViewModel 统一接收，再按目标页翻译 |
| 甘特定位 | `batch_id/resource_id/view`、`gantt_batch/gantt_resource/gantt_overdue` | ViewModel 负责翻译 |
| 资源派工视角 | `resource_type/resource_id`、`scope_type/scope_id/operator_id/machine_id/team_id` | ViewModel 负责翻译 |

关键跳转清单必须写进测试：

| 来源 | 目标 | 必带参数 | 禁用规则 |
|---|---|---|---|
| 首页超期待办 | 超期清单 / 延期解释 | `version`、日期范围、`batch_id` 如果有 | 无版本时禁用 |
| 首页方案待确认 | 排产分析 | `version`、`plan_role`、`scenario_id` 如果有 | 无候选方案时不生成 |
| 首页资源高负荷 | 资源派工，备用资源负荷报表 | `version`、日期范围、资源类型/资源对象 | 资源对象缺失时跳总览 |
| 首页现场情况待确认 | 资源派工现场事实区 | 正式采用 `version`、日期范围、批次/资源 | 非正式方案不生成写入入口 |
| 分析推荐卡 | 甘特 / 超期清单 / 资源派工 | `version`、`plan_role`、`scenario_id`、日期范围 | 无目标对象时降级到页面总览 |
| 甘特任务详情 | 资源派工 / 计划和现场实际 | `version`、任务定位、资源定位 | 非正式方案下计划和实际入口禁用 |
| 报表明细 | 甘特 / 资源派工 | `version`、日期范围、批次/资源 | 目标字段不足时显示原因 |

### 5.3 不能做错的点

- 页面上不能直接显示 `scenario_id`、`plan_role`、`op_id` 这类内部字段。
- 非正式方案不能生成现场记录写入入口，也不能下发写入 API URL、Excel 导入 URL、模板下载 URL、表单 action 或任何 `data-*` 写入地址。
- 去计划和现场实际时，要说明它只看正式采用方案。
- 链接禁用时必须显示中文原因。

### 5.4 要补的测试

- 新增：`tests/regression_scheduler_workbench_links_contract.py`
- 覆盖首页到分析、甘特、资源派工、报表。
- 覆盖分析推荐卡到甘特和超期清单。
- 覆盖甘特任务详情到资源派工。
- 覆盖报表明细回甘特或资源派工。
- 覆盖非正式方案禁用现场写入和现场复盘入口。

### 5.5 完成标准

- 后续页面不再各自手拼关键工作台跳转。
- 上表列出的关键跳转都带版本、方案、日期。
- 不可用入口有中文原因。
- 测试能证明跳转不丢上下文。

## 6. 阶段 2：顶层计划工作台入口

### 6.1 要做什么

把顶层“首页”升级成“计划工作台”，让计划员能从第一层导航进入核心作业。

主要文件：

- `templates/base.html`
- `templates/components/ui_macros.html`
- `static/css/ui_contract.css`

验收：

- 顶层出现“计划工作台”或等价入口。
- 入口指向 `/` 的工作台首页。
- 能一跳到首页值班台、排产分析、甘特、资源派工、计划和现场实际。
- 只改顶层入口文案和轻量入口，不重做全站导航结构，不引入新菜单体系，不改业务路由。
- 不用外部菜单库。
- 文案全是中文业务名。

## 7. 阶段 3：首页值班台和今日待处理

### 7.1 要做什么

首页从“统计卡 + 常用入口”改成“今天先看什么”。

建议新增：

- `web/viewmodels/dashboard_workbench.py`

首页首屏建议结构：

```text
计划工作台
  上下文条：最新版本 / 方案 / 日期范围 / 数据更新时间
  风险卡：待排 / 超期 / 资源高负荷 / 现场情况待确认
  今日待处理：最多 6 条
  最近排产结果摘要：采用方案 / 推荐理由 / 代价 / 下一步
```

今日待处理第一版按下面规则生成，不能在模板里临时猜：

| 待处理类型 | 数据来源 | 生成条件 | 默认动作 | 备用动作 | 严重度 |
|---|---|---|---|---|---|
| 超期批次 | 最新正式采用方案的超期清单 | 有超期批次 | 查看超期解释 | 定位甘特 | danger |
| 方案需要确认 | 候选方案 / 推荐卡摘要 | 存在至少 1 个可比较候选方案或推荐卡，并且它不是最新正式采用方案的重复展示；第一版不保存“已读/已确认”状态 | 打开排产分析 | 查看甘特 | warning |
| 资源负荷偏高 | 资源负荷报表服务 | 利用率可算且达到固定阈值：warning >= 75%，danger >= 90% | 查看资源派工 | 查看资源负荷报表 | warning / danger |
| 现场情况待确认 | 正式采用方案的任务现场状态 | 只统计当前日期范围内已经到计划开始时间、但 `actual_start_time`、`actual_end_time`、`current_status` 都还不能说明现场进展的任务；不统计未来任务 | 打开资源派工现场事实区 | 查看计划和现场实际 | notice / warning |
| 基础数据缺口 | 日历、容量、停机、资源等服务返回的数据缺口 | 数据不足导致风险无法判断 | 查看对应维护入口或说明页 | 打开相关报表 | notice |

排序规则：

1. `danger` 在前，`warning` 其次，`notice` 最后。
2. 同级时按超期批次、方案确认、资源负荷、现场情况待确认、基础数据缺口排序。
3. 同一类型只显示最重要一条；明细数量写在影响说明里。
4. 同一类型多条时这样挑：超期按最晚交期风险和超期时长优先；方案按推荐卡优先；资源负荷按利用率最高优先；现场情况按计划开始时间最早优先；基础数据缺口按会影响排程判断的范围最大优先。
5. 最多 6 条，超过时显示“还有 N 条同类问题，请进入对应页面查看”。
6. 没有最新正式采用方案时，不生成现场情况待确认，只显示“暂无正式采用方案，不能判断现场情况”。
7. 反馈人为空不算红色风险，不阻断保存，不阻断报表；最多作为记录信息不完整的普通提示。
8. 首页文案用“现场情况待确认”或“暂未收到/录入现场情况”，不要写成“必须补录”。

第一轮首页完成时，还要补一个小烟测，不等阶段 8：

- 从顶层进入 `/`。
- 从首页进入排产分析、甘特、资源派工、报表中心。
- 首页待处理用 `WorkbenchLink` 生成动作。
- 跳出去后 `version`、`plan_role`、日期范围不丢。

### 7.2 不要做成什么样

- 不要做成营销首页。
- 不要做大横幅和装饰图。
- 不要让首页承载所有明细。
- 不要在模板里临时写复杂业务判断。
- 不要把所有没录现场实际的未来任务都算成缺口，避免把现场记录变相做成必填。

### 7.3 要补的测试

- `tests/regression_workbench_nav_entry_contract.py`
- `tests/regression_dashboard_workbench_contract.py`
- `tests/regression_aps_workbench_first_round_flow_contract.py`
- `tests/regression_frontend_ui_language_polish.py`

### 7.4 完成标准

- 计划员打开首页能看到按上表生成的待处理项或明确空状态。
- 每个待处理项都有中文标题、影响说明、证据、动作按钮。
- 没有待处理时显示清楚空状态。
- 页面不显示内部字段。

## 8. 阶段 4：排产分析行动层

### 8.1 目标

排产分析页不要先让用户看技术过程，而是先告诉用户：

- 当前排产结果怎么样。
- 推荐哪个方案。
- 这个方案有什么代价。
- 哪些地方可能会晚。
- 下一步应该看甘特、超期清单还是资源派工。

### 8.2 页面顺序

建议调整为：

1. 当前版本和方案身份。
2. 风险/空状态。
3. 推荐方案卡。
4. 三方案摘要。
5. 延期/诊断行动卡。
6. 指标卡。
7. 优化过程和趋势图。

### 8.3 需要新增的数据

推荐卡第一版要补影响面，但要拆清楚已有和新增：

- 已有可复用：超期批次、拖期、工期、换型次数、三方案差值文案。
- 需要补强但必须保守：受影响批次数、最晚超期时长、资源压力、数据缺口。能安全算出来就显示，算不出来就写“当前数据不足”，不能硬编。
- 需要补水：历史 summary 被裁剪后，要能从候选方案记录补回展示所需摘要。

如果某项算不出来，不能空着，也不能硬编，要显示“当前数据不足”。

### 8.4 主要文件

- `templates/scheduler/analysis.html`
- `templates/scheduler/analysis_parts/_candidate_comparison.html`
- `templates/scheduler/analysis_parts/_diagnostic_sections.html`
- `web/viewmodels/scheduler_analysis_candidates.py`
- `web/viewmodels/scheduler_analysis_candidate_helpers.py`

### 8.5 要补的测试

- `tests/regression_scheduler_analysis_workbench_layout.py`
- 继续跑现有候选方案中文测试，避免内部字段露出。

### 8.6 完成标准

- 用户先看到推荐、风险和下一步。
- 技术过程仍在，但不抢第一屏。
- 没有候选方案时，有清楚空状态。
- 推荐卡不显示内部字段名。
- 跳甘特、资源派工、超期清单时不丢上下文。

## 9. 阶段 5：甘特任务详情区

### 9.1 目标

甘特图继续只读，但点一条任务后，旁边或下方要稳定显示任务详情。不要只靠鼠标弹窗。

### 9.2 详情区显示什么

第一版显示：

- 批次。
- 图号或物料信息，能拿到就显示，拿不到就不假装。
- 工序。
- 设备或人员。
- 计划开始/结束。
- 实际开始/结束，若无则显示“暂未记录现场实际”。
- 是否超期。
- 下一步：查看超期解释、查看资源派工、查看计划和现场实际。

### 9.3 主要文件

- `templates/scheduler/gantt.html`
- `static/js/gantt_render.js`
- `static/js/gantt_popup.js`
- `static/css/aps_gantt.css`
- 可能新增：`web/viewmodels/scheduler_gantt_workbench.py`

### 9.4 不做什么

- 不做拖拽写库。
- 不做保存视图。
- 不做左侧任务简表。
- 不做模拟沙盒。

### 9.5 要补的测试

- `tests/regression_gantt_task_detail_panel_contract.py`
- 后续加入浏览器几何路径。

### 9.6 完成标准

- 未选任务时显示“点击甘特条查看任务详情”。
- 点击任务后详情区更新。
- 详情区不遮挡甘特。
- 移动或窄屏下不重叠。
- 不显示内部字段。

## 10. 阶段 6：资源派工执行分层

### 10.1 目标

资源派工页保留现有能力，但把“计划员看排班”和“计划员录现场事实”分清。

### 10.2 页面结构

建议分成两个车道：

```text
计划员查看
  - 任务明细
  - 日历矩阵
  - 甘特图
  - 导出资源派工

现场事实
  - 现场记录任务卡
  - 今日任务 / 待开工 / 待完工 / 现场情况待确认
  - 手动填写实际情况
  - Excel 直接导入
  - 查看计划和现场实际
```

### 10.3 已拍板的边界

- 反馈人保持可空。
- Excel 继续直接导入；短期只保留现有直接导入和导入后的结果/错误提示。
- 不做 Excel 导入前表格预览。
- 不做 Excel 二次确认弹窗。
- 不做多人权限。
- 不做现场员工账号。

### 10.4 仍要处理的风险

- 非正式方案下，不要让计划员误以为可以写现场实际。
- 暂停、继续、报异常、撤销、审批、扫码、消息推送全部后移；已有暂停/异常字段只作为计划员代录的事实或备注展示，不新增闭环。
- “查看计划和现场实际”是复盘入口，不是写入入口。
- 前端 JS 不能自己拼写入 URL；没有后端给的可用动作和 URL，就不能写。

### 10.5 主要文件

- `templates/scheduler/resource_dispatch.html`
- `static/js/resource_dispatch_core.js`
- `static/js/resource_execution.js`
- `web/viewmodels/scheduler_resource_dispatch.py`
- `web/viewmodels/scheduler_resource_dispatch_execution.py`

### 10.6 要补的测试

- `tests/regression_resource_dispatch_workbench_lane_contract.py`
- 继续跑 `tests/regression_resource_dispatch_site_records_frontend_contract.py`

### 10.7 完成标准

- 页面能看出两个区域：计划员查看、现场事实。
- 现场记录入口不再被 Excel 控件抢首屏。
- 非正式方案写入入口禁用或清楚说明原因，并且不输出写入按钮、表单 action、API URL、Excel 导入 URL、模板下载 URL、任何 `data-*` 写入地址。
- 反馈人可空的口径继续成立。
- Excel 预览不出现。

## 11. 阶段 7：报表中心和明细回跳

报表中心不再只是四张入口卡，而是风险入口。

要补：

- 每张报表卡说明“能回答什么”。
- 每张报表卡说明“不能证明什么”。
- 资源负荷行能跳甘特或资源派工。
- 计划和现场实际行能跳回对应任务。
- 超期清单能跳延期解释或甘特定位。
- 停机影响没有数据时，不说“没有影响”，只说“没有停机记录或尚未维护停机数据”。

还要明确哪些是新增数据能力：

- 报表中心风险摘要需要新增页面级汇总。
- 计划和现场实际明细需要把安全的任务/资源定位字段交给模板。
- 停机影响任务级明细是第二阶段增强；第一版只做设备级说明和回跳，不假装能列出所有受影响任务。

### 11.1 主要文件

- `templates/reports/index.html`
- `templates/reports/overdue.html`
- `templates/reports/utilization.html`
- `templates/reports/execution_review.html`
- `templates/reports/downtime.html`
- `core/services/report/utilization.py`
- `core/services/report/downtime_impact.py`
- 建议新增或复用：`web/viewmodels/scheduler_reports_workbench.py`

### 11.2 要补的测试

- `tests/regression_reports_workbench_backlink_contract.py`

### 11.3 完成标准

- 报表不是死胡同。
- 没数据时不误导用户。
- 不引入外部图表库。

## 12. 阶段 8：主流程测试

### 12.1 要做什么

要补的不是只检查网页里有没有某个样式名的测试，而是用户路线测试。

第一轮 A/B/C 的小烟测已经随第 7 节完成；本阶段做的是第一版完整主流程测试，依赖阶段 1-7，不依赖第二阶段的延期解释接现场事实，也不依赖甘特资源负荷摘要。

建议新增：

- `tests/regression_aps_workbench_flow_contract.py`
- 扩展 `tests/ui_geometry_contract_data.py`
- 扩展 `tools/test_registry.py`。
- 扩展质量门禁注册表，建议新增 `aps_frontend_workbench` 分组。

必须覆盖：

- 首页到超期解释。
- 首页到方案对比。
- 首页到甘特。
- 首页到资源派工。
- 甘特任务到资源派工。
- 资源负荷到报表和资源派工。
- 报表明细回甘特或资源派工。
- 非正式方案下现场写入禁用。
- 普通页面不显示内部字段。

浏览器几何必须明确覆盖这些 URL：

- `/`
- `/scheduler/analysis`
- `/scheduler/gantt?view=machine`
- `/scheduler/gantt?view=operator`
- `/scheduler/resource-dispatch`
- `/reports/`
- `/reports/overdue`
- `/reports/utilization`
- `/reports/execution-review`

几何检查至少覆盖 1280、1024、768 三档宽度，检查主内容不重叠、按钮不被遮挡、文字不挤出、关键操作入口可见。

浏览器兼容口径：

- 最终兼容证明必须面向 Chrome 109。
- 如果本机只跑了更新版本 Chrome，只能算布局烟测，不能当成 Chrome 109 兼容证明。
- 新增测试登记到 `tools/test_registry.py`；只有现有门禁入口不能自动识别新分组时，才改 `scripts/run_quality_gate.py`。

## 13. 阶段 9：工作台用户指南

### 13.1 要做什么

更新用户指南，用大白话告诉计划员：

- 早上打开先看首页。
- 超期先看哪里。
- 方案怎么比。
- 甘特图怎么看任务详情。
- 资源太满怎么查。
- 现场实际在哪里录。
- 哪些页面只是查看，哪些页面会写入现场事实。

主要文件：

- `static/docs/aps_three_gap_user_guide.md`
- `web/viewmodels/page_manuals_scheduler_outputs.py`
- `docs/dev/aps-browser-scheduler-qa-replay.md`

## 14. 阶段 10（第二阶段）：延期解释和现场事实接线

这一节只属于第二阶段，不属于第一轮，也不属于第一版验收。第一版可以继续在超期清单里看已有延期解释，但不要求延期解释接入现场事实。

### 14.1 目标

如果计划员已经录了现场实际，第二阶段的延期解释就不能还说“没有现场事实”。延期解释要尽量利用已有现场事实。

### 14.2 要做什么

- 延期诊断按批次和工序关联现场执行事件。
- 如果有实际开始/结束，用它解释偏差。
- 如果没有，才显示“暂未记录现场实际”。
- 牵连批次/订单第一版不做精确影响面；如果不能算，就明确说“当前不能判断牵连批次/订单”。
- 展示层接收的是中文事实、线索和数据缺口，不直接暴露事件 id。

### 14.3 主要文件

- `core/services/scheduler/schedule_delay_diagnosis_service.py`
- `core/services/scheduler/operation_execution_feedback_service.py`
- `core/services/report/delay_diagnosis_presentation.py`
- `templates/reports/overdue.html`

这阶段已在 items.yaml 里新增 roadmap item：`delay-diagnosis-site-facts-bridge`。它依赖 `workbench-context-link-contract` 和 `resource-dispatch-execution-lane`。

### 14.4 完成标准

- 不再固定说“没有现场执行反馈”。
- 有现场事实时能显示。
- 没有现场事实时用保守说明。
- 不暴露内部字段。

## 15. 阶段 11（第二阶段）：甘特资源负荷摘要

这一节只属于第二阶段，不属于第一轮，也不属于第一版验收。第一版甘特只要求任务详情和下一步链接，不要求 Top 5 资源负荷摘要。

### 15.1 甘特附近资源负荷

在甘特附近显示最忙设备和人员，不让计划员必须先跳报表才知道哪里满。

第二阶段显示：

- 最忙设备 Top 5。
- 最忙人员 Top 5。
- 负荷小时。
- 利用率。
- 任务数。
- 容量来源说明。
- 去资源派工或资源负荷报表的入口。

容量说明要保守：

- 如果只是按工作日历估算，就写清楚。
- 如果没有扣除停机，就写清楚。
- 如果当前只是用全局日历工时估算、没有按单台设备或单个人细分，也要写清楚。
- 如果算不了利用率，就写“数据不足，暂时算不了”。

主要接线层建议放在 `web/viewmodels/scheduler_gantt_workbench.py`。它负责把资源负荷报表服务整理成甘特页能直接展示的 Top5 摘要，模板不直接拼报表 service 原始字段。

## 16. 每个 feature 开工前都要检查

每个子 feature 进入 `cs-feat-design` 前，都要回答这些问题：

- 这次改的是哪个页面或哪条链路。
- 用户看到什么变化。
- 是否需要新增 ViewModel。
- 是否需要改 service。
- 是否会影响旧测试。
- 是否会显示内部字段。
- 是否会破坏 Win7 / Chrome 109。
- 是否仍兼容 Python 3.8。
- 是否引入了外链脚本、外链样式、外链字体或离线不可用资源。
- 是否涉及写入现场事实。
- 如果涉及写入，是否只对正式采用方案开放。
- 如果没有数据，页面怎么说。

## 17. 风险清单

### 17.1 最大风险：上下文没先统一

如果不先做统一链接，后面每个页面都会自己拼 URL，最后会变成到处补洞。

处理方式：阶段 1 必须靠前。

### 17.2 页面越做越重

首页、甘特、资源派工都有可能被塞太多信息。

处理方式：每页只回答自己的核心问题。首页负责“先干什么”，甘特负责“任务在哪里”，资源派工负责“排班和现场事实”，报表负责“看证据和回跳”。

### 17.3 误导用户

典型误导：

- 没有停机记录，被说成没有停机影响。
- 利用率算不了，被显示成 0%。
- 非正式方案显示可写按钮。
- 延期诊断忽略已经录入的现场实际。

处理方式：所有数据不足都用中文说明，不强行给结论。

### 17.4 旧测试拦新设计

旧测试锁住了旧首页结构、候选方案链接数量、资源派工页面口径。

处理方式：每个 feature design 都要写“哪些旧测试要保留，哪些旧断言要改口径”。

## 18. 第一轮建议开工包

如果要马上开工，我建议第一轮只做三个小包：

### 包 A：工作台上下文和链接

目标：先把跳转不丢上下文解决。

输入：

- 当前页面能拿到的 `version`、`plan_role`、`scenario_id`、日期范围、批次、资源。
- 第 5.2 节字段表、目标页字典、关键跳转清单。
- 现有首页、排产分析、甘特、资源派工、报表路由。

产出：

- `web/viewmodels/scheduler_workbench_links.py`
- `WorkbenchPlanContext`
- `WorkbenchLink`
- `tests/regression_scheduler_workbench_links_contract.py`

验收：

- 首页、分析、甘特、资源派工、报表之间跳转不丢 `version`、方案、日期范围。
- `target_page` 只使用第 5.2 节目标页字典里的名字。
- 非正式方案不输出任何现场写入按钮、表单 action、API URL、Excel 导入 URL、模板下载 URL 或 `data-*` 写入地址。
- 禁用链接都有中文原因。

### 包 B：顶层计划工作台入口

目标：让用户从顶层知道去哪。

输入：

- 现有 `templates/base.html` 顶层导航。
- 包 A 产出的链接模块。
- 当前本地样式和宏组件。

产出：

- 顶层出现“计划工作台”入口。
- 入口指向 `/` 的工作台首页。
- 下拉或入口组至少包含：排产分析、甘特图、资源派工、报表中心、计划和现场实际。
- `tests/regression_workbench_nav_entry_contract.py`

验收：

- 从顶层 1 次点击能进入工作台首页。
- 从顶层入口组 1 次点击能进入上述核心页面。
- 不重做全站导航结构，不引入新菜单体系，不改业务路由。
- 不引入外部菜单库。
- 页面文案全是中文业务名。

### 包 C：首页值班台第一版

目标：首页能回答“今天先处理什么”。

输入：

- 包 A 产出的链接模块。
- 最新正式采用方案。
- 超期清单。
- 候选方案或推荐卡摘要。
- 资源负荷报表。
- 现场任务实际记录状态。
- 基础数据缺口信息。

产出：

- `web/viewmodels/dashboard_workbench.py`
- 首页待处理区域。
- `tests/regression_dashboard_workbench_contract.py`
- `tests/regression_aps_workbench_first_round_flow_contract.py`

验收：

- 首页最多显示 6 条待处理。
- 每条都有中文标题、影响说明、证据、默认动作、备用动作。
- 资源负荷阈值固定为：warning >= 75%，danger >= 90%。
- 没有正式采用方案时，不生成现场情况待确认，只显示中文说明。
- 反馈人为空不算红色风险，不阻断保存，不阻断报表。
- 页面不显示内部字段。
- 第一轮小烟测证明：顶层进首页、首页跳分析/甘特/资源派工/报表、跳转不丢上下文。

这三个包完成后，用户就能看到最小闭环：从顶层进入计划工作台，首页看到待处理，再点到具体页面，而且上下文不丢。

## 19. 验收总标准

整条工作台第一版完成时，应该满足：

- 顶层能进入计划工作台。
- 首页能列出今日待处理。
- 页面跳转不丢版本、方案、日期。
- 分析页先给推荐和风险。
- 甘特点任务有稳定详情。
- 资源派工能分清看排班和录现场事实。
- 报表能回到处理页面。
- 第一版不要求延期解释接现场事实；这是第二阶段增强。做完第二阶段后，延期解释才必须不忽略已经录入的现场事实。
- 第一版不要求甘特资源负荷摘要；这是第二阶段增强。做完第二阶段后，甘特附近才必须能看到 Top 5 资源压力和容量说明。
- 非正式方案不能写现场实际。
- 普通用户看不到内部字段。
- 关键页面有回归测试和浏览器几何覆盖。
- 用户指南和真实页面一致。
