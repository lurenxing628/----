# 旧 UI 选项处置清单

- 状态：**建议待 review，未实施**。本文件不证明任何旧页面已经备份、下线，或任何新能力已经接通。
- 范围：汇总排产评估第 8 节、operations 评估第 12 节，并按本轮明确要求修正报表处置；不新增全站研究、架构或 DAG，不修改原评估、inventory 或源码。
- 工作区：`/Users/lurenxing/GitHub/----`，按已有脏工作区读取，保留他人暂存、未暂存和未跟踪内容。下文源码路径均相对此根目录。
- 输入：`.codestable/roadmap/workbench-prototype-migration/drafts/scheduling-backend-assessment.md:279`、`.codestable/roadmap/workbench-prototype-migration/drafts/operations-backend-assessment.md:370`；当前能力登记参照 `.codestable/roadmap/workbench-prototype-migration/drafts/prototype-capability-inventory.md`。

## 1. 处置口径与编号

**结论：旧 UI 可按建议退役，但不能将当前样板已展示或文字承诺的能力一并删除。** 特别是 `REPORT-013..016`，本次必须接入现有报表目录；批次 `overwrite / append / replace` 三种导入模式必须保留。

| 建议值 | 准确定义 |
| --- | --- |
| UI入口退役 | 仅建议不搬旧控件、旧布局或独立旧页面；不删除服务、路由所承载的能力、数据、历史或已保存参数。不表示已经下线 |
| 新页已有继续保留 | 当前**已挂载样板**有对应控件或业务位置，应保留并接真实后端；样例、禁用占位、只选文件均不等于后端已实现 |
| 当前样板承诺需接入 | 虽无生成按钮，但已明确展示能力声明，或本轮明确要求兑现；在现有同风格目录最小补齐操作与结果状态，不能整体归为退役 |

- `LEG-xxx` 绑定一项可独立裁决的旧选项或紧耦合控件组，不绑定行号、页面排序或实现阶段。现有编号保持不变；以后新增只追加，合并 / 废止保留原编号并记录去向，不重编号、不复用。
- 本稿所有条目均为 `review_status=pending`、`implementation_status=not_started`。表内“建议”不是已批准实施动作；本轮明确的报表与导入保留约束不得被 review 摘要误写成删除授权。
- `有` / `部分` / `无` / `声明项` 描述的是当前挂载 UI 的等价程度，不是后端完成度。只有字段名相似、底层有服务或脚本被加载，不能判定“有等价入口”。

### 当前样板的有效入口

`index.html?view=process` 实际挂载 `ProcessNative`，`?view=basedata` 挂载 `MasterDataOverview`；`BaseDataScreen` 及其旧 `BaseProcess / BaseMaterial / BaseCalendar / BaseEquipment / BasePersonnel` 等虽被加载，却未被当前路由挂载，**不得拿其中的外协组、物料需求、技能矩阵或班组编辑器作为本次保留依据**。

证据：`前端设计/ui_kits/workbench/app.jsx:95`、`前端设计/ui_kits/workbench/app.jsx:96`、`前端设计/ui_kits/workbench/app.jsx:99`；`前端设计/ui_kits/workbench/index.html:371`；`.codestable/roadmap/workbench-prototype-migration/drafts/prototype-capability-inventory.md` 的第 20 节排除表。

## 2. 存量保存规则

以下是后续实施的保存 / 验收约束，不是本轮已验证的数据迁移结果。每行除引用规则外，还列出该项特有的保存要求。

| 规则 | 保存要求 |
| --- | --- |
| CFG | 保留 `ScheduleConfig` 原参数、预设内容、active preset 及来源信息；隐藏字段不自动归零、清空或恢复默认。新页只提交其负责字段；非法旧值明确报错或展示已定义的降级，不能静默“修好” |
| PLAN | 保留正式版本、候选摘要 / 明细 / 角色关系、草稿 / 场景、历史及日志；保存请求身份与有效身份的区别，保留 partial、缺明细、历史、预览标记。旧页面退役不等于删历史表或退掉查询服务 |
| DATA | 保留业务主键、未展示字段及原有状态；不得把名称、备注、单位、类别或关系字段因新表单缺项写空。删除 / 重建仍需独立明确操作与引用保护 |
| REL | 保留人员设备授权、技能等级、主操、班组、工种及外协组关系；不把人员工种多选等同于授权全部同工种设备，不把显示分组直接改写班组 |
| CAL | 保留全局 / 个人逐日覆盖、默认与显式配置的区别、班次起止及跨夜配置、效率和普通 / 急件规则；省略字段不代表清空，休息不代表删除原配置 |
| MAT | 分开保存库存数值、单位、批次需求与到料事实；不根据低库存徽标重写齐套，也不因隐藏需求编辑器删除 `BatchMaterials` |
| EXEC | 保留已有执行事件、暂停、异常、数量、资源及完整计划身份；未知不填 0，备注 / 报工间空档不推断暂停或停机。新逐次事实与旧事件不能直接一一改名替换 |
| REPORT | 保留真实查询、指标边界、导出能力及既有审计。列表 / 统计 / 下载同身份同范围，异常值与不可计算状态不得省掉；旧专属列不必全搬新主界面，但已有事实和正式导出不能被丢弃 |
| IMPORT | 保留各业务独立的解析、模式、预检基线、引用保护及事务 / 逐项结果；不能把一种业务的 append / replace 规则套给另一种。不得在迁移过程中自动触发任何清空或导入 |
| SYS | `SystemConfig` 与 `ScheduleConfig` 分开；备份文件、维护记录、插件状态、操作日志和运行文件日志不因 UI 切换被清理或重写。保存偏好不能覆盖业务维护配置 |
| UI | 搜索、筛选、排序、分页、折叠、配色与缩放只改变查看态；重置查看态不清业务数据、正式计划、历史或审计 |

## 3. 报表：能力保留，旧外壳单独裁决

样板 `前端设计/ui_kits/workbench/ReportsScreen.jsx:218` 已挂载“其他报表 · 数据接入状态”，四项都显示“后台支持 · 当前不可生成”；`前端设计/ui_kits/workbench/report-workbench-model.js:10` 至 `前端设计/ui_kits/workbench/report-workbench-model.js:13` 为四项声明。inventory 的完整编号是 `WBP-REPORT-013..016`，本文件保留其映射，不另改 inventory。

本节对四项能力的处置采用**本轮最新要求**：两份评估中“暂不搬旧专题 / 旧 Excel”的说法，不能再作为删除这四项能力的依据。不得只接值班台风险摘要就声称报表已完成，也不得跳回旧专属页面就声称已完成新目录接入。

| 稳定 ID | 原选项 / 字段及真实旧页路径 | 当前样板等价入口 | 建议 | 存量保存与接入边界 |
| --- | --- | --- | --- | --- |
| LEG-001 | 超期批次 / XLSX；`version,plan_role,batch_id,resource_type,resource_id`；`GET /reports/overdue`、`GET /reports/overdue/export`。旧模板 `templates/reports/overdue.html:39` | **声明项**：`?view=reports` 目录；`WBP-REPORT-013`，模型 `前端设计/ui_kits/workbench/report-workbench-model.js:10` | 当前样板承诺需接入 | REPORT+PLAN：本次在现有目录最小补全查看 / 生成 / Excel 操作、加载 / 空 / 失败 / 不可评估状态；保留整批交期、全部工序与未排完边界，不能以单道工序完工代替交付 |
| LEG-002 | 资源负荷 / 利用率及 XLSX；上述身份与 `start_date,end_date`；`GET /reports/utilization`、`GET /reports/utilization/export`。旧模板 `templates/reports/utilization.html` | **声明项**：同目录；`WBP-REPORT-014`，`前端设计/ui_kits/workbench/report-workbench-model.js:11` | 当前样板承诺需接入 | REPORT+CAL：本次接真实计划占用、日历容量及导出；容量为零或缺失时不可计算，不拿“实际工时 / 固定 8 小时”替代 |
| LEG-003 | 停机影响及 XLSX；计划身份、日期、设备 / 批次范围；`GET /reports/downtime`、`GET /reports/downtime/export`。旧模板 `templates/reports/downtime.html` | **声明项**：同目录；`WBP-REPORT-015`，`前端设计/ui_kits/workbench/report-workbench-model.js:12` | 当前样板承诺需接入 | REPORT+EXEC：本次接有效停机台账与计划时段交集及导出；不把报工空档当停机，不把交集小时直接称最终延期 |
| LEG-004 | 正式执行复盘 / Excel；`version,date_from,date_to,batch_id,resource_type,resource_id`；`GET /reports/execution-review`、`GET /reports/execution-review/export`。旧模板 `templates/reports/execution_review.html:18` | **声明项**：同目录；`WBP-REPORT-016`，`前端设计/ui_kits/workbench/report-workbench-model.js:13` | 当前样板承诺需接入 | REPORT+EXEC+PLAN：本次接正式采用身份、真实执行事件及 Excel；保留身份拒绝与事实缺口。不用现有五专题 CSV 或计划试调 CSV 冒充正式 Excel |
| LEG-005 | 旧报表中心及四个独立旧页面的外壳 / 布局；`GET /reports/` 和上述四页；`templates/reports/index.html:51` | **部分**：现有 `?view=reports` 已有同域目录，但四项尚不可生成 | UI入口退役 | REPORT：仅旧独立页面外壳 / 导航建议退役；LEG-001..004 接通并验收前不能以该项为理由移除能力。HTML 页面入口裁决不等于删除导出 / 数据路由 |
| LEG-006 | 旧各报表独立筛选表单与版本加载器；`version,plan_role,start_date,end_date,date_from,date_to,batch_id,resource_type,resource_id`；对应旧报告页 | **部分**：`ReportsScreen` / `AnalysisShared` 有共享范围，但来源、日期和实际资源语义不完全一致 | UI入口退役 | UI+REPORT+PLAN：可不搬四套旧表单；必要身份、日期和资源参数仍由新共享上下文明确提供。后台不支持的范围必须报错 / 禁用，不能查另一范围 |
| LEG-007 | 旧超期独立列：已排 / 未排 / 时间异常 / 交期异常、截至、延期天数；旧“为什么晚了”展开；`/reports/overdue`；`templates/reports/overdue.html:86`、`templates/reports/overdue.html:140` | **部分**：`?view=delay` 有交付依据；目录 `REPORT-013` 承诺完整批次风险，未展示原列组 | UI入口退役 | REPORT：原列布局 / 独立展开器可退役；分桶、不可评估、证据等级、缺口和真实原因不能丢或改成确定根因，按新页必要状态 / 详情及真实 Excel 承载 |
| LEG-008 | 旧复盘专属分析列：暂停时长、异常原因 / 严重程度 / 预计影响 / 受影响设备人员 / 处理状态 / 建议重排；`/reports/execution-review`；`templates/reports/execution_review.html:108` | **无同组主表列**；`REPORT-016` 有正式复盘 / Excel 承诺 | UI入口退役 | REPORT+EXEC：仅旧专属主表列组可不搬；LEG-004 的正式查询 / Excel 能力保留，已存在执行事实不可删，不从备注补造这些值 |
| LEG-009 | 周计划表 XLSX 旧专属入口；`week_start,offset,version,plan_role,batch_id,resource_type,resource_id`；`GET /scheduler/week-plan`、`GET /scheduler/week-plan/export`；`templates/scheduler/week_plan.html:12` | **无等价周计划格式**：样板计划对比 CSV 和 `REPORT-016` 正式执行 Excel 都不是周计划 XLSX | UI入口退役 | REPORT+PLAN：仅暂不搬该旧专属入口，保留周计划查询 / 导出服务和历史；不据此取消 LEG-001..004 的本次接入 |
| LEG-010 | 周派工单打印 / 设备人员切换；`group_by=machine/operator`；`GET /scheduler/week-plan/print`；`templates/scheduler/week_plan_print.html:32` | **无**同款打印入口 | UI入口退役 | REPORT+PLAN：保留打印能力和非正式 / 历史方案“不得下发执行”警示。route 支持 `day` 不代表旧页有单日筛选控件，不虚增遗漏项 |

### 四项报表的最小补全约束

- 继续使用现有 `ReportsScreen` 目录 / 主题风格与控件体系，不扩建第二个旧式报表首页，不引入另一套独立筛选外壳。
- 四项必须可定位、查看 / 生成，并使用各自真实 Excel 导出；操作使用当前真实计划身份与明确范围。必要的最小确认 / 条件补全在该目录内解决，不将旧专属控件整套搬回。
- 未就绪保留“当前不可生成”及具体缺口；开始加载、生成失败、范围无数据、部分数据不可评估、下载已交浏览器等状态分别呈现。声明项变成真可用前不能只改徽标。
- `REPORT-001..012` 的现有五专题、下钻、图表和 CSV 继续保留，它们不替代四项新增接入；本文件不重新拆其架构或生成 DAG。

## 4. 排产执行与全局排产设置

下表所说“无”只针对当前 `?view=run` 或其他实际挂载入口，不以未挂载 React 基础资料推定存在。`/scheduler/config` 在 operations 第 12 节的重复项统一归本节，不另编重复 ID。

| 稳定 ID | 原选项 / 字段及真实旧页路径 | 当前样板等价入口 | 建议 | 存量数据 / 配置保存规则 |
| --- | --- | --- | --- | --- |
| LEG-011 | 常用方案切换 / 手工设置 / 高级设置链接；`preset_name,custom`；`GET /scheduler/`、`GET /scheduler/config`；`templates/scheduler/batches.html:19` | **无**配置预设选择；`?view=analysis` 选择的是结果方案 | UI入口退役 | CFG：保留预设及 active preset；不得把结果方案选择映射成全局预设应用 |
| LEG-012 | 排产列表状态筛选：全部 / pending / scheduled / processing / completed / cancelled；`status`；`/scheduler/`；`templates/scheduler/batches.html:65` | **部分**：run 有批次范围选择，无同款完整状态下拉 | UI入口退役 | DATA+UI：保留真实状态及已完成 / 取消禁排边界；退出筛选不改批次状态 |
| LEG-013 | 齐套显示筛选：全部 / yes / partial / no；`only_ready`；`/scheduler/`；`templates/scheduler/batches.html:76` | **部分**：run 有“仅已齐套”，不是原四态筛选 | UI入口退役 | DATA+MAT：保留 partial/no 与 ready_date；显示筛选不替代 enforce_ready 运行校验 |
| LEG-014 | 单次开始时分；`start_dt` datetime-local；`/scheduler/`；`templates/scheduler/_run_panel.html:11` | **部分**：`GanttScreen` 仅起止日期 | UI入口退役 | CFG+PLAN：不丢真实开始时分；日期如何转换开工时间需固定合同，不能把旧值统一清成午夜 |
| LEG-015 | 单次计算时限；`run_time_budget_seconds`；`/scheduler/`；`templates/scheduler/_run_panel.html:21` | **无** | UI入口退役 | CFG：不写回全局 time_budget_seconds；保留当前模式适用边界，不冒充异步任务硬超时 |
| LEG-016 | 本次严格参数检查；`strict_mode`；`/scheduler/`；`web/viewmodels/scheduler_run_options.py:28` | **无**；齐套 / 缺资源 / 已完成开关不等价 | UI入口退役 | CFG：固定处理策略须 review；不能默认宽松并隐藏异常警告，也不能偷接成完成工序重排开关 |
| LEG-017 | 插单模拟按钮；`POST /scheduler/simulate`；旧页 `/scheduler/`；`templates/scheduler/_run_panel.html:46` | **无等价动作**：当前方案试调是另一生命周期 | UI入口退役 | PLAN：保留模拟服务；不沿用旧“会生成新版本”的错误提示，不将不落库模拟当候选场景 |
| LEG-018 | 预设另存 / 删除 / 恢复默认；`preset_name`，`POST /scheduler/config/preset/save`、`POST /scheduler/config/preset/delete`、`POST /scheduler/config/default`；旧页 `/scheduler/config`；`templates/scheduler/config.html:81`、`templates/scheduler/config.html:303` | **无**；“重置样板”不等价 | UI入口退役 | CFG：保留自定义与内置预设及保护；迁移或重置查看态不能调用恢复默认 / 删除预设 |
| LEG-019 | 排产排序；`sort_strategy=priority_first/due_date_first/weighted/fifo`；`/scheduler/config`；`templates/scheduler/config.html:127` | **无** | UI入口退役 | CFG：继续按存量策略运行；不能统一改成样板“均衡”方案名 |
| LEG-020 | 计算模式、优化目标；`algo_mode=greedy/improve`，`objective=min_overdue/min_tardiness/min_weighted_tardiness/min_changeover`；`/scheduler/config`；`templates/scheduler/config.html:137`、`templates/scheduler/config.html:147` | **无** | UI入口退役 | CFG：保留原值与指标解释；“无控件”不能覆盖成默认优化目标 |
| LEG-021 | 优先级 / 交期权重；`priority_weight,due_weight`；`/scheduler/config`；`templates/scheduler/config.html:157` | **无** | UI入口退役 | CFG：保留完整权重及 ready_weight 联动规则，不能仅保留新页可见两个值而破坏原快照 |
| LEG-022 | 派工方式 / 智能派工规则；`dispatch_mode=batch_order/sgs`，`dispatch_rule=slack/cr/atc`；`/scheduler/config`；`templates/scheduler/config.html:171`、`templates/scheduler/config.html:181` | **无** | UI入口退役 | CFG：保留原方式 / 规则，不因甘特显示顺序改变调度顺序 |
| LEG-023 | 全局优化时限 / 假期效率；`time_budget_seconds,holiday_default_efficiency`；`/scheduler/config`；`templates/scheduler/config.html:192`、`templates/scheduler/config.html:200` | **无**同款全局输入 | UI入口退役 | CFG+CAL：两字段原值继续存在，容量 / 日历读取不能固定成样例日班 |
| LEG-024 | 近期冻结开关 / 天数；`freeze_window_enabled,freeze_window_days`；`/scheduler/config`；`templates/scheduler/_config_switches.html:2` | **无**等价配置；task.locked 与“已完成工序锁定”不等价 | UI入口退役 | CFG+PLAN：保留冻结规则、seed 及降级 / 未生效原因，不能重置为不冻结 |
| LEG-025 | 优先主操 / 高技能；`prefer_primary_skill`；`/scheduler/config`；`templates/scheduler/_config_switches.html:13` | **无** | UI入口退役 | CFG+REL：保留偏好及其依赖的真实技能 / 主操数据 |
| LEG-026 | 全局齐套默认；`enforce_ready_default`；`/scheduler/config`；`templates/scheduler/_config_switches.html:18` | **部分**：run 的 readyCheck 是本次检查 | UI入口退役 | CFG+MAT：不把本次开关保存成全局默认；保留服务拒绝与样板跳过语义的差异 |
| LEG-027 | 全局缺资源自动分配；`auto_assign_enabled`；`/scheduler/config`；`templates/scheduler/_config_switches.html:23` | **部分**：run 的 autoFill 是本次规则 | UI入口退役 | CFG+REL：不以临时切全局值再恢复来接 autoFill；保留 auto_assign_persist 的原值和实际写回边界 |
| LEG-028 | 深度优化及时间；`ortools_enabled,ortools_time_limit_seconds`；`/scheduler/config`；`templates/scheduler/_config_switches.html:28` | **无** | UI入口退役 | CFG：保留原配置，不因未迁控件擅自启停插件或承诺运行环境一定可用 |
| LEG-029 | 工序图分析模式；`graph_analysis_mode=off/report/on`；`/scheduler/config`；`templates/scheduler/config.html:226` | **无** | UI入口退役 | CFG：保留仅分析 / 参与排产差别；候选页需要数据不构成擅自把 off 改 on 的理由 |
| LEG-030 | 工序循环停止、调试导出；`graph_block_on_cycle,graph_debug_export`；`/scheduler/config`；`templates/scheduler/_config_switches.html:38`、`templates/scheduler/_config_switches.html:43` | **无** | UI入口退役 | CFG：原校验与诊断配置不变，不通过移除 UI 吞掉循环失败或擅自删除已有诊断文件 |
| LEG-031 | 工序图权重；`graph_critical_weight,graph_impact_weight`；`/scheduler/config`；`templates/scheduler/config.html:237`、`templates/scheduler/config.html:244` | **无** | UI入口退役 | CFG：保留原权重及运行摘要，不从条形图或推荐文案倒推参数 |
| LEG-032 | 候选档数；`graph_candidate_weight_count=3/5/7`；`/scheduler/config`；`templates/scheduler/config.html:251` | **无**；样板固定三种方案不等价 | UI入口退役 | CFG+PLAN：保留真实候选数量 / 未保存明细状态，不能裁成三条“成功” |
| LEG-033 | 自动正式方案选择规则；`graph_selection_policy=balanced/score_only`；`/scheduler/config`；`templates/scheduler/config.html:262` | **无**；手工“采用此方案”不是该配置 | UI入口退役 | CFG+PLAN：保留自动选择规则与实际 selection 记录，不把手工采用写为全局配置修改 |
| LEG-034 | 候选选择容忍度；`graph_overdue_tolerance_count=0/1/2`，`graph_tardiness_tolerance_ratio=0.05/0.1/0.2`；`/scheduler/config`；`templates/scheduler/config.html:273`、`templates/scheduler/config.html:284` | **无** | UI入口退役 | CFG：两项原值及校验继续生效，不随新 UI 的风险徽标改变 |

`ready_weight` 和 `auto_assign_persist` 不是旧页独立可选控件，不另编“遗漏”编号；仍分别受 LEG-021 / LEG-027 保存规则约束。`SystemManagementScreen` 的自动维护 / 偏好不能覆盖这些排产配置。

## 5. 计划甘特、候选对比与分析旧控件

| 稳定 ID | 原选项 / 字段及真实旧页路径 | 当前样板等价入口 | 建议 | 存量数据 / 配置保存规则 |
| --- | --- | --- | --- | --- |
| LEG-035 | 任意日期范围、上周 / 本周 / 下周、独立版本加载；`start_date,end_date,week_start,offset,version`；`/scheduler/gantt`；`templates/scheduler/gantt.html:88`、`templates/scheduler/gantt.html:108` | **部分**：`?view=gantt` 有方案切换，日期为样例，无原表单 | UI入口退役 | UI+PLAN：可退旧导航器，不可把真实范围固定成两天；数据 / 页眉 / 导出身份及范围一致 |
| LEG-036 | 时间粒度及步进；`gantt_zoom`：月、周、日、12小时、6小时、小时、15分钟、5分钟、1分钟；`/scheduler/gantt`；`templates/scheduler/gantt.html:170` | **无**同组控件 | UI入口退役 | UI：不改任务时段或历史，既有查看偏好不得被解释为业务排程参数 |
| LEG-037 | 甘特配色；`ganttColorMode=batch/priority/source/status`；`/scheduler/gantt`；`templates/scheduler/gantt.html:186` | **无**配色选择器 | UI入口退役 | UI+PLAN：允许新固定视觉编码，保留优先级 / 归属 / 状态事实；不据配色修改业务状态 |
| LEG-038 | 批次 / 设备或人员下拉细筛；`gantt_batch,gantt_resource`；`/scheduler/gantt`；`templates/scheduler/gantt.html:195`、`templates/scheduler/gantt.html:201` | **部分**：样板有搜索和分组，无同款下拉 | UI入口退役 | UI：不清掉真实批次 / 资源关系；局部筛选不能偷偷改变全量负荷或差值口径 |
| LEG-039 | 仅超期 / 仅外协 / 关键工序高亮；`ganttOnlyOverdue,ganttOnlyExternal,ganttHighlightCC`；`/scheduler/gantt`；`templates/scheduler/gantt.html:208` | **无**同组开关 | UI入口退役 | UI+PLAN：保留风险、外协与关键链数据及不可用标记；退控件不等于删判断 |
| LEG-040 | 关系线模式；`ganttDepsMode=critical/process/none`；`/scheduler/gantt`；`templates/scheduler/gantt.html:227` | **部分**：新页有工艺顺序，但不是关键链模式切换 | UI入口退役 | UI+PLAN：不删除依赖关系，不把工艺前后序当关键路径 |
| LEG-041 | 清除聚焦 / 重置查看态；`ganttClearFocus,ganttResetView`；`/scheduler/gantt`；`templates/scheduler/gantt.html:233` | **部分**：新页有搜索、选择，trial 有“重置样板”，语义不等价 | UI入口退役 | UI：不得映射成清除正式排程、采用历史或所有草稿 |
| LEG-042 | 候选额外列和多明细跳转；`failed_ops,makespan_hours` 等；`/scheduler/analysis`；`templates/scheduler/analysis_parts/_candidate_comparison.html:59` | **部分**：`?view=analysis` 已有对比、甘特、风险，未有旧额外列组 | UI入口退役 | PLAN+REPORT：只退旧额外列 / 链接组，保留新对比入口及其真实数据；失败、无明细不能被省成成功 |
| LEG-043 | 版本总体指标、冻结 / 配置状态、诊断依据旧区域；`selected_metrics,freeze_display,diagnostic_sections`；`/scheduler/analysis`；`templates/scheduler/analysis.html:27` | **部分**：样板显示方案 KPI，不是历史诊断全区 | UI入口退役 | PLAN+CFG：保留历史摘要、截断 / 解析失败 / 降级信息；新指标不具证据时不可沿用旧版本值 |
| LEG-044 | 优化曲线、尝试排名 / 来源 / 排序策略 / 派工 / 失败数 / 目标值；`trace_chart,attempts`；`/scheduler/analysis`；`templates/scheduler/analysis_parts/_optimization_process.html:12` | **无** | UI入口退役 | PLAN：不清运行摘要或尝试记录；不把尝试条数冒充候选明细数 |
| LEG-045 | 历史趋势：超期、拖期、加权拖期、总 / 内制工期、换型、设备 / 人员平均利用率；`trend_rows,trend_charts`；`/scheduler/analysis`；`templates/scheduler/analysis_parts/_trend_charts.html:1` | **无等价历史版本趋势**；样板执行趋势是另一口径 | UI入口退役 | PLAN+REPORT：保留版本历史及计算依据，不因旧趋势图不搬而清数据 |

## 6. 基础资料、批次与导入旧选项

本节沿用 operations 已完成评估中的旧模板证据，未重启业务调用链研究。当前原生基础资料均以 `?view=process -> ProcessNative` 为比较对象。

| 稳定 ID | 原选项 / 字段及真实旧页路径 | 当前样板等价入口 | 建议 | 存量数据 / 配置保存规则 |
| --- | --- | --- | --- | --- |
| LEG-046 | 零件备注；`remark`；`GET /process/parts/<part_no>`；`templates/process/detail.html:23` | **无**同款零件备注输入 | UI入口退役 | DATA：保留原备注，保存名称或路线时不清空 |
| LEG-047 | 路线文字单独保存 / 按路线重生成的旧分区；`route_raw`；`/process/parts/<part_no>`；`templates/process/detail.html:46` | **部分**：原生三步工艺流有路线编辑，不是旧五区布局 | UI入口退役 | DATA+REL：仅旧分区退役；新路线编辑继续兑现。重解析对工序 / 外协组的影响必须明确，不能用保存文字冒充完成重生成 |
| LEG-048 | 零件新增 / 重解析 / 路线导入严格宽松切换；`strict_mode`；`/process/`、`/process/parts/<part_no>`、`/process/excel/routes`；`templates/process/list.html:44`、`templates/process/excel_import_routes.html:11` | **无**同组开关 | UI入口退役 | DATA+IMPORT：固定策略待 review；保留宽松降级提醒及失败边界，禁止默默采用宽松并吞警告 |
| LEG-049 | 具体连续外协组：separate/merged、整组 / 逐序天数、严格开关、合法首尾组删除；`merge_mode,total_days,ext_days_<seq>,strict_mode`；`/process/parts/<part_no>`；`templates/process/detail.html:145`、`templates/process/detail.html:167`、`templates/process/detail.html:209` | **无**等价组编辑器；默认外协策略、批次 ext_days 输入均不等价 | UI入口退役 | REL+DATA：保留既有 ExternalGroups 及成员 / 周期规则；不得将 merged 展平或清空，不能凭未挂载 BaseDataScreen 判已有 |
| LEG-050 | 工种全局归属修改；`category=internal/external`；`GET /process/op-types/<op_type_id>`；`templates/process/op_type_detail.html:27` | **无**等价全局修改；逐工序确认 / 待建转类不是该动作 | UI入口退役 | DATA+REL：保留原工种分类；不得用全局 category 修改冒充一条工艺的人工确认 |
| LEG-051 | 设备类别 / 备注 / 班组 ID 及过滤、批量状态 / 单条停用；`category,remark,team_id,machine_ids,status=active/maintain/inactive`；`/equipment/`、`/equipment/<machine_id>`；`templates/equipment/list.html:48`、`templates/equipment/detail.html:36` | **部分**：原生有设备状态 / 显示组，但无全套旧班组与批量状态控件 | UI入口退役 | DATA+REL：保留 category、remark、team_id、inactive；设备组不可未经确认写成班组，检修不自动新建停机事实 |
| LEG-052 | 人员设备双向授权及双方 Excel 向导；`machine_id,operator_id,skill_level,is_primary`；`/personnel/<operator_id>`、`/equipment/<machine_id>`、`/personnel/excel/links`、`/equipment/excel/links`；`templates/personnel/detail.html:59`、`templates/equipment/detail.html:68` | **无**等价授权编辑器；样板工种技能多选不等价 | UI入口退役 | REL+IMPORT：保留全部既有授权 / 主操 / 技能等级，继续供排产合法性读取；新多选不能自动扩大设备授权 |
| LEG-053 | 人员备注、班组归属 / 过滤、批量在岗 / 停用及旧停用休假标签；`remark,team_id,operator_ids,status`；`/personnel/`、`/personnel/<operator_id>`；`templates/personnel/list.html:48`、`templates/personnel/detail.html:39` | **部分**：原生有在岗 / 请假，无完整旧控制组 | UI入口退役 | DATA+REL：旧 inactive 不可全部改名成请假或恢复 active；保留备注 / 班组及不等价状态 |
| LEG-054 | 班组独立增删改 / 人机数量 / 启停备注；`team_id,name,status,remark`；`GET /personnel/teams`；`templates/personnel/teams.html:12`、`templates/personnel/teams.html:54` | **无**当前独立班组编辑页 | UI入口退役 | REL：不删 ResourceTeams 或人机归属；新页统计仍可读取真实关系 |
| LEG-055 | 停机台账新增 / 取消、单设备 / 类别 / 全设备批量停机；`start_time,end_time,reason_code,reason_detail,scope_type,scope_value`；`/equipment/<machine_id>`、`GET /equipment/downtimes/batch`；`templates/equipment/detail.html:155`、`templates/equipment/downtime_batch.html:16` | **无**维护表单；值班台冲突和 REPORT-015 是读取能力 | UI入口退役 | EXEC+DATA：保留有效 / 取消停机台账；LEG-003 仍必须接入读取 / 统计 / 导出，不以退维护表单取消报告 |
| LEG-056 | 个人日历完整页及 Excel 导入导出；`date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,remark`；`/personnel/<operator_id>/calendar`、`/personnel/excel/operator_calendar`；`templates/personnel/calendar.html:30`、`templates/personnel/calendar.html:113` | **无**等价个人逐日覆盖；固定“夜班”选项不等价 | UI入口退役 | CAL+IMPORT：保留所有个人日期覆盖，不批量改成默认班次 |
| LEG-057 | 全局日历显式班次起止；`shift_start,shift_end`；`GET /scheduler/calendar`；`web/routes/domains/scheduler/scheduler_calendar_pages.py:47` | **部分**：原生有日历 / 工时 / 范围维护，未露出同字段 | UI入口退役 | CAL：仅起止控件暂不搬；保留跨夜与既有起止，不能由只填小时的表单重写整行时丢字段 |
| LEG-058 | 全局日历 Excel 向导 / 模板 / 导出；`mode` 与日期 / 班次字段；`GET /scheduler/excel/calendar`；`templates/scheduler/excel_import_calendar.html` | **无**同款 Excel 入口；原生日期范围编辑不是 Excel | UI入口退役 | CAL+IMPORT：保留服务 / 数据；不把 replace 理解为只替换当前月，范围维护能力仍须兑现 |
| LEG-059 | 物料单位、备注独立编辑；`unit,remark`；`GET /material/materials`；`templates/material/materials.html` | **部分**：库存显示可带单位，无同组独立输入 | UI入口退役 | MAT+DATA：保存库存数值时保留单位 / 备注，不从拼接显示文字覆盖业务字段 |
| LEG-060 | 批次物料需求增删改、到料留空即齐套；`required_qty,available_qty,material_id`；`GET /material/batches`；`templates/material/batch_materials.html` | **无**当前需求编辑区；未挂载 BaseMaterial 不算入口 | UI入口退役 | MAT：保留 BatchMaterials 与齐套同步规则；库存不是到料，不删需求、不因新页无输入改成全部齐套 |
| LEG-061 | 供应商不绑定工种、单工种选择和备注；`op_type_id` 可空、`remark`；`GET /process/suppliers/<supplier_id>`；`templates/process/supplier_detail.html:27`、`templates/process/supplier_detail.html:48` | **部分**：原生多工种 chips 不等价于旧可空单关系 | UI入口退役 | DATA+REL：保留空值 / 单工种关系和备注；不得复制供应商编号或静默丢关系模拟多选 |
| LEG-062 | 主数据通用向导旧只新增 / 清空本类重导模式；`mode=append/replace`；`/process/excel/routes`、`/process/excel/op-types`、`/process/excel/suppliers`、`/equipment/excel/machines`、`/personnel/excel/operators` | **无**同款全模式选择，原生通用导入只声明增量 | UI入口退役 | IMPORT+DATA：只不搬这些主数据额外模式，保留服务原保护；**不适用于批次 LEG-076..078**。路线 replace 有批次引用限制，不能绕过 |
| LEG-063 | 工时导入“只补空工时”；`mode=append`；`GET /process/excel/part-operation-hours`；`templates/process/excel_import_part_operation_hours.html` | **无**该旧模式选择器 | UI入口退役 | IMPORT：保留原“只补空”的特殊语义；不能命名成后端不接受的 fill，也不引入工时 replace；原已知工时不隐式覆盖 |
| LEG-064 | 批次手工新增严格开关；`strict_mode`；`GET /scheduler/batches`；`templates/scheduler/batches_manage.html:80` | **无**同款新建开关；详情模板刷新有独立严格项 | UI入口退役 | DATA：仅该开关暂不搬；新建固定行为待 review，不能删除 LEG-079 的模板刷新严格项 |
| LEG-065 | 批次导入自动生成工序开关；`auto_generate_ops`；`GET /scheduler/excel/batches`；`templates/scheduler/excel_import_batches.html:28` | **无**同款导入开关 | UI入口退役 | IMPORT+PLAN：固定行为必须明确并绑定预检；原工序资源 / 工时 / 外协周期可能被重建，不能在选择文件或普通更新时隐式执行 |
| LEG-066 | 批次导入严格开关；`strict_mode`；`GET /scheduler/excel/batches`；`templates/scheduler/excel_import_batches.html:108` | **无**同款导入开关，但三模式当前已显示 | UI入口退役 | IMPORT：保留后端校验与拒绝 / 降级输出；开关是否固定不影响三模式保留承诺 |
| LEG-067 | 批次详情“最新方案排程去向”旧区；最新正式 / 方案明细；`GET /scheduler/batches/<batch_id>`；`templates/scheduler/batch_detail.html:31` | **无**同款旧去向区；样板计划甘特 / 对比另有入口 | UI入口退役 | PLAN：保留历史关联和真实计划身份读取；不能删除排程或改成总跳 latest |
| LEG-068 | 资源派工班组维度、人机双表、跨组 / 周月查询；`scope_type=team,team_axis,team_id` 及日期范围；`GET /scheduler/resource-dispatch`；`templates/scheduler/resource_dispatch.html:71`、`templates/scheduler/resource_dispatch.html:111` | **无**整页等价；现场记录 / 实际甘特是其他界面 | UI入口退役 | REL+PLAN+EXEC：保留派工读取所需关系 / 上下文；不迁整页不等于允许历史 / 候选写现场事实 |
| LEG-069 | 旧资源任务列表导出；`GET /scheduler/resource-dispatch/export`，同派工查询范围；`templates/scheduler/resource_dispatch.html:398` | **无**同款旧任务表；现有报工 / 甘特导出格式不同 | UI入口退役 | REPORT+EXEC：保留服务和数据，明确格式差别；不能用此项取消正式 REPORT-016 Excel |
| LEG-070 | 旧实际填写额外输入：`quantity_scrapped,pause_start_time,pause_end_time,pause_duration_minutes,pause_reason,pause_remark,exception_time,exception_reason,exception_severity,exception_remark`；旧页 `/scheduler/resource-dispatch`；`static/js/resource_execution_actual.js:83`、`static/js/resource_execution_actual.js:92` | **无**这些额外输入；逐次报工已有的本次完成数量、时间、有效工时不在退役范围 | UI入口退役 | EXEC：保留旧报废 / 暂停 / 异常事实并供正式复盘读取；未知不得填零，不能用更正报工去删除旧事件；暂停 / 异常反馈人元数据也不得被新会话覆盖 |

LEG-062 的精确导入基路径与模式来自 `.codestable/roadmap/workbench-prototype-migration/drafts/operations-backend-assessment.md` 第 4 节；并非所有主数据都有 replace，工时例外单列 LEG-063，物料没有据此推定一个不存在的 Excel 路由。

## 7. 系统与历史旧入口

| 稳定 ID | 原选项 / 字段及真实旧页路径 | 当前样板等价入口 | 建议 | 存量数据 / 配置保存规则 |
| --- | --- | --- | --- | --- |
| LEG-071 | 手工清理过期备份 / 批量删除；`POST /system/backup/cleanup`、`POST /system/backup/delete-batch`；旧页 `/system/backup`；`templates/system/backup.html:46`、`templates/system/backup.html:51` | **无**同组操作；样板单个删除另列 LEG-080 | UI入口退役 | SYS：不得在页面迁移时运行清理或批删；保留备份文件、自动维护规则与记录。单删不具自动清理同等保底保证 |
| LEG-072 | 操作日志单条 / 批量删除；`POST /system/logs/delete`、`POST /system/logs/delete-batch`；旧页 `/system/logs`；`templates/system/logs.html:120`、`templates/system/logs.html:229` | **无**删除审计入口 | UI入口退役 | SYS+EXEC：不得因 UI 切换删除 OperationLogs；运行文件日志始终只读，不扩大为可删除 |
| LEG-073 | 旧操作日志独立高级筛选；`module,action,limit` 最近 N 条；`GET /system/logs`；`templates/system/logs.html:75` | **部分**：新 system 有统一来源 / 日期 / 类型 / 状态 / 文本筛选，但无同款高级表单 | UI入口退役 | UI+SYS：仅旧表单暂不搬；保留 module/action 和查询上限语义，不将尾部 N 条包装成全历史。新筛选另见 LEG-081 |
| LEG-074 | 插件状态 / 详情 / 启停；`plugin_id,enabled`，`POST /system/plugins/toggle`；旧展示页 `/system/backup`；`templates/system/backup.html:196`、`templates/system/backup.html:273` | **无**当前插件页 | UI入口退役 | SYS+CFG：保留已有插件配置 / 状态，不能因不显示而重置启停或卸载 |
| LEG-075 | 系统排产历史独立详情；`version,limit,page,per_page`；`GET /system/history`；`templates/system/history.html:23`、`templates/system/history.html:57` | **部分**：样板计划选择 / 采用记录不是该旧独立详情页 | UI入口退役 | PLAN+SYS：保留 ScheduleHistory / 采用记录 / 诊断事实及身份解析，不把本地样例 history 作为正式替代 |

## 8. 已有等价控件：明确保留而非遗漏

| 稳定 ID | 原选项 / 字段及真实旧页路径 | 当前样板等价入口 | 建议 | 存量数据 / 配置保存规则 |
| --- | --- | --- | --- | --- |
| LEG-076 | 批次导入更新已有 / 新增缺少；`mode=overwrite`；`GET /scheduler/excel/batches`；`templates/scheduler/excel_import_batches.html:100` | **有（UI）**：`?view=batches` 批量维护弹窗，`前端设计/ui_kits/workbench/BaseBatches.jsx:201`；`WBP-BATCH-010` | 新页已有继续保留 | IMPORT+DATA：接真实预检 / 确认、更新与新增结果；未提交不写库。未展示字段不因 UI 载荷缺项清空；文件名不等于已导入 |
| LEG-077 | 批次导入只新增 / 已有跳过；`mode=append`；`/scheduler/excel/batches`；`templates/scheduler/excel_import_batches.html:101` | **有（UI）**：同弹窗，`前端设计/ui_kits/workbench/BaseBatches.jsx:202` | 新页已有继续保留 | IMPORT：已有批次和工序保持不变，真实报告跳过 / 新增 / 失败；不能改成覆盖，也不是模板工时“只补空” |
| LEG-078 | 批次先清空全部后重导；`mode=replace`；`/scheduler/excel/batches`；`templates/scheduler/excel_import_batches.html:102` | **有（UI）**：同弹窗，`前端设计/ui_kits/workbench/BaseBatches.jsx:203` | 新页已有继续保留 | IMPORT+PLAN：不能移除该模式；明确目标是**全部批次，不是筛选 / 勾选集合**。仅单次显式确认且通过真实预检基线、引用和事务保护后允许执行；取消 / 失败不伪称清空成功；迁移本身不触发 replace |
| LEG-079 | 按模板重生成工序的严格开关；`strict_mode`，`POST /scheduler/batches/<batch_id>/generate-ops`；旧批次详情页 | **有（UI）**：“资料不完整时停止刷新”；`前端设计/ui_kits/workbench/BaseBatches.jsx:729`，确认刷新 `前端设计/ui_kits/workbench/BaseBatches.jsx:734` | 新页已有继续保留 | DATA+PLAN：保留严格检查与确认；不能因 LEG-064 / 066 暂不搬开关把此项一并删掉。重建范围、已补资源 / 工时影响及取消后不改需真实回读证明 |
| LEG-080 | 单个删除备份；`filename`，`POST /system/backup/delete`；旧页 `/system/backup` | **有业务位置，禁用占位**：system 备份恢复；`前端设计/ui_kits/workbench/SystemManagementScreen.jsx:128`；`WBP-SYS-010` | 新页已有继续保留 | SYS：后续接真实目标文件、明确确认及结果；不得升级成一键清理 / 批删，也不能假称永远保底留三份。本轮未删除任何文件 |
| LEG-081 | 日志日期 / 级别 / 文本读取及备份详情；日志 `start_time,end_time,log_level,file,level,q`，备份 `filename`；旧页 `/system/logs`、`/system/runtime-logs`、`/system/backup` | **有（UI）**：system 统一来源 / 日期 / 类型 / 状态 / 搜索 / 分页 / 详情；`前端设计/ui_kits/workbench/SystemManagementScreen.jsx:66`；`WBP-SYS-006/012` | 新页已有继续保留 | UI+SYS：真实来源、未知 / 未读取、尾部读取上限和完整详情必须区分；接口不足列待适配，不删除已有控件或让其悄悄无效 |

批次三模式当前仍仅选择文件并显示未接入，代码 `前端设计/ui_kits/workbench/BaseBatches.jsx:191`、`前端设计/ui_kits/workbench/BaseBatches.jsx:263` 明示不会写入。本节“保留”指必须兑现 UI 承诺，**不是本轮确认解析、导入或保护已验收**。

## 9. 不编造成旧页遗漏的项目

以下不是“旧页面原有选项”，不分配 LEG 编号，不用于缩减主方案待接能力：

- **逐次报工 / 更正**：inventory 已有 `WBP-FIELD-012` 等，operations 评估第 6 节确认缺少相应正式逐次记录与修订合同。属于当前样板承诺的后端缺口，不是旧更正按钮待搬；不得用旧 finish 事件、直接 UPDATE / 删除历史替代。
- **手动采用引擎候选**：排产评估第 6 节已区分候选只读与 adopted 基础场景发布；缺少任意候选手动采用服务。不能将其登记成“旧候选采用选项退役”，也不能把 `plan_role` 改成 adopted 绕过。
- **草稿试调 / 保存场景 / 发布**：旧甘特实际为 `data-gantt-mode="view"`，服务 route 存在不代表旧页已启用。当前试调样板有控件，应继续作为待接合同，不从“旧页未展示”推导不做。
- **工时定额校准**：operations 评估第 8 节未找到旧校准页，当前样板有采纳承诺；不编造“旧校准选项暂缓”。
- **未挂载基础资料 React 编辑器**：只加载 `BaseDataScreen` 不构成当前入口；其中的组、技能、物料需求或个人日历编辑器不增加当前样板承诺。以实际 `ProcessNative` 和 inventory 挂载表为准。
- **其他当前可见占位**：立即备份 / 恢复 / 正式诊断包 / 保存正式维护配置、原生资料增删改 / 导入导出等，即使禁用或仅提示，仍归 inventory 的待接事项。本清单不以“没有后端”为由删除它们，也不再展开其架构。

## 10. Review 与后续执行边界

- 本稿先供主方案按稳定编号引用；LEG-005..075 中具体旧 UI 退役建议仍需 review，不能直接作为删除脚本的输入。LEG-001..004 与 LEG-076..078 的本次保留要求已由用户明确，不能归为“可整体放弃”。
- 旧页后续下线应在新入口合同验收、存量值 / 关系 / 历史保存核验、旧页面源码与必要资产可追溯备份后，另行按授权执行；本轮**未备份、未下线、未移植、未清理数据**。
- 未展示字段采取“保留原值且仍受业务校验”的原则；现有服务若整行覆盖、重解析重建或状态域不兼容，应回到对应评估的问题合同解决，不能以隐藏控件规避。
- 后续实际导入、删除、恢复等高影响操作仍需该次操作的明确目标和确认；本文件不是批次 replace、备份删除或数据库修改授权。
- 本轮验证限于文档完整性、编号唯一性、来源引用和上述有界入口核对；不启动真实 app，不跑导入 / 报工 / 备份 / 排产，也不以其他代理的 Win7 或浏览器结果替代真实后端验收。不提供 clean-worktree proof。
