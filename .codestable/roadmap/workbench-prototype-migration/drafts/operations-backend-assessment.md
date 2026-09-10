---
title: Workbench 运营与基础资料后端接入评估
status: draft
assessment_date: 2026-09-09
scope: readonly-assessment
implementation: not-started
---

# 运营与基础资料后端接入评估

## 1. 结论与优先缺口

**当前目标不是把旧页换皮即可完成。已有基础 CRUD、Excel 导入、现场事件、复盘及备份服务可复用，但当前可进入样板含有后端尚未承载的业务语义。尤其是逐次报工、工艺分步确认、校准采纳、值班台处置，不能标为“后端已有，接线即可”。**

本材料仅评估并列出实现所需合同，不执行移植，不授权改库。当前脏工作区是事实源，HEAD `de96cd3f681bf4f3b1ca9183f347c56f3de8e73a` 仅作定位锚点，不代表下列源码与 HEAD 一致。核查时本机日期为 `2026-09-09`，时区 `Asia/Shanghai`。

| 优先项 | 已证实的差异 | 接入判断 |
| --- | --- | --- |
| O1 逐次报工 | 样板有 `reports[]`、每次数量/有效工时/实际资源、补齐、更正、自动整道完工；后端是一次开工到完工的事件状态机，`completed` 后无后续合法事件 | 需要业务数据合同与持久化能力，不是把 `reports[]` 翻译为多次 `finish`。见第 6 节 |
| O2 工艺与资源语义 | 样板人工确认每道工序归属、未知工种待建、人员多工种技能、供应商多工种、人员班次；旧后端没有等价字段/动作 | 可复用基础记录，但新增语义必须单列，不能改成全局工种归属或批量授权设备来冒充。见第 3 节 |
| O3 批次编辑 | 样板单批保存数量/齐套/日期；现有单批详情是 GET，批量更新 POST 只接优先级/交期/备注；裸 `op_id` 保存端点刻意拒绝 | 补单批保存合同；工序必须使用后端签发的 `update-token`。见第 5 节 |
| O4 分析口径 | 样板按计划完工日选工序、计划或实际资源关联，统一 10 分钟容差；旧复盘按计划时段交集、计划资源筛选，输出主要是展示标签 | 复用事实读取与正式方案限制，不直接复用旧报表结果作为五类新专题。见第 7 节 |
| O5 工时校准 | 样板种子中位数与“采纳”本地标记；未找到后端样本筛选、建议计算、来源/采纳人/锁定写回合同 | 全链路缺口；模板工时普通写接口不等于校准接口。见第 8 节 |
| O6 值班台处置 | 样板责任人、期限、动作、证据、关闭、重开和外协回厂登记；真实值班台明确“不保存已处理状态” | 读取风险可部分复用，处置台账和外协事实需新增。见第 9 节 |
| O7 主机维护结果 | 备份/恢复真实服务已存在；样板统一记录集、状态筛选、失败详情不能只由文件列表得到 | 保留维护锁、恢复前副本、校验及回滚；补结构化读结果，不虚构“校验通过”。见第 11 节 |
| O8 导入与反馈 | 多数旧写入口是表单 POST + flash + 重定向；预检也可能写审计日志；不同导入事务策略不同 | 不以 HTTP 200/302 或样板 toast 判断成功；保持预检/确认/部分失败的真实含义。见第 4 节 |

证据：`前端设计/ui_kits/workbench/field-report-model.js:22`、`core/models/operation_execution_event.py:59`、`web/routes/domains/scheduler/scheduler_ops.py:37`、`web/viewmodels/dashboard_workbench.py:251`。各项的具体调用与字段证据在后文，不以原型测试通过作为接入证明。

## 2. 评估基准与通用边界

### 2.1 当前可进入页面

以下原型路径均相对于 `前端设计/ui_kits/workbench/`；其余证据路径均相对于仓库根 `/Users/lurenxing/GitHub/----`。`文件:行号` 指本轮工作区源码，不是历史评审文档。

| 入口 | 真正的 Screen 和模型 | 当前数据/动作性质 |
| --- | --- | --- |
| `process` 基础资料 | `app.jsx:96` -> `ProcessNative.jsx:6` -> `plana-logic.js:34` | 闭包样例、DOM 临时表格、部分仅提示；没有正式数据写入 |
| `batches` | `BaseBatches.jsx:148`、`batch-draft-model.js` | 会话列表、编辑草稿、批量预览；Excel 明示未接入 |
| `field` | `FieldRecordScreen.jsx:2` -> `field-reporting.js:3`、`field-report-model.js`、`field-report-editor.js` | 逐次报工内存模型；确实能生成浏览器下载文件，不代表写过 SQLite |
| `fieldgantt` | `FieldGanttScreen.jsx:85`、`FieldGanttRows.jsx:25`、`fg-screen-model.js` | 当前报工/复杂/密集三套样例，实际条、剩余安排与原计划分开；只读展示/导出 |
| `review` / `reports` | `ExecutionReviewScreen.jsx:129`、`ReportsScreen.jsx:107`、`execution-analysis-model.js:131` | 共享范围、只读汇总/下钻/CSV；`current` 仍指内存报工样例 |
| `calib` | `CalibScreen.jsx:7` | 固定种子、采纳仅组件状态、导出仅 toast |
| `dashboard` | `DashboardScreen.jsx:2` -> `dashboard-workbench.js:5`、`dashboard-model.js:5` | 独立值班台样例，不与现场记录共用事实 |
| `basedata` | `MasterDataOverview.jsx:25`、`master-data-overview.js:20` | 从原生基础资料会话快照构造八域实体/问题/关系，只读，不是数据库扫描 |
| `system` | `SystemManagementScreen.jsx:182`、`system-workbench-model.js:67` | 当前机器记录为未知；独立管理样例；真实备份/恢复/删除/配置保存按钮禁用 |

**不要误把已加载脚本当成当前入口。** `index.html:362` 附近仍加载 `BaseProcess/BaseMaterial/BaseCalendar/BaseOpTypes/BaseSuppliers/BaseEquipment/BasePersonnel/BaseDataScreen`，但 `app.jsx:96` 实际选择 `ProcessNative`。旧 React 基础资料中的外协分组编辑、批次物料需求、专门技能矩阵向导、设备组向导，不因此自动成为本次样板必迁能力。反过来，当前原生页虽然有部分空按钮，按钮已占据的业务位置仍须登记为待接入，不能漏掉。

### 2.2 接口复用口径

- 下文“现有 HTTP”是已声明路由和服务调用的静态证据，不是本轮向真实库发请求的测试结果。蓝图前缀由 `web/bootstrap/factory.py:246` 至 `256` 注册。
- 基础资料、批次、旧报表、系统维护多数 GET 返回 Jinja HTML，POST 接 `request.form` 并 flash/重定向。不存在可直接假定的 `/api/materials`、`/api/calibration` 等 JSON API。可复用的是已核查业务服务；要保持 Screen 不整页跳转，需要结构化读写适配或保持同风格服务端渲染，不能把旧 HTML 接口伪称现成 JSON。
- 失败页面重定向最终也可能 HTTP 200；必须从明确的业务结果判断已提交、未提交、部分提交、已回滚或回滚失败，不能只读 `response.ok`。错误原文、字段、影响对象、重试条件要留在对应表单附近。
- “业务只读”不等于“请求绝不写任何东西”：`web/bootstrap/factory.py:399` 起的请求维护检查可能触发备份/清理；`web/routes/system_utils.py:155` 调用 `get_snapshot()`，后者会补缺省 `SystemConfig`；主数据 Excel 预检会写 `OperationLogs`。需要严格只读读取配置时已有 `SystemConfigService.get_snapshot_readonly()`，见 `core/services/system/system_config_service.py:198`。
- 表单未展示的旧字段应保留。尤其日历 `upsert` 是整行构造，省略 `shift_start/shift_end` 不等于不改；不要在换皮保存时覆盖原来夜班/跨夜配置。见 `core/services/scheduler/calendar_admin.py:92`、`118`、`282`。
- 将 UI 偏好/草稿与业务保存分开：搜索、排序、页码、折叠、缩放、明暗主题不写业务表；取消草稿不撤销已提交事实；返回列表、刷新、重新打开应用后仍存在的记录才可称持久化完成。

### 2.3 不能压平的数据粒度

| 对象 | 正式身份/存储 | 接入必须保留的差别 |
| --- | --- | --- |
| 零件模板 | `Parts.part_no`；`PartOperations` 按 `part_no + seq`；`ExternalGroups.group_id` | 模板工时不是某批次临时工时；重新解析可重建外协组 |
| 批次 | `Batches.batch_id`、`part_no`、`quantity` | 批次完工不能由任一道工序完工推定；物料齐套不是库存总数 |
| 批次工序 | `BatchOperations.id/op_code/batch_id/seq/piece_id` | 原型常用 `batch_id + seq`，正式数据另有 `piece_id`；不得合并同序号的不同工序实例 |
| 计划中的工序 | `schedule_version + schedule_id + op_id + batch_id + source_table + effective_plan_role + scenario_id` | 正式事件按完整身份读写；不能只按 `op_id` 汇总不同版本，不能把跨源同批次号当同一任务 |
| 执行事件 | `OperationExecutionEvents.id/event_type/event_time/previous_state_revision` | 是状态转换，不是一条拥有开始、结束、数量、有效工时的逐次报工单 |
| 样板逐次报工 | `task.id + report.id/reportNo + revision` | 正式承载缺失；不能把 event_id 当 reportNo，把 start/finish 两事件当两次生产 |

证据：`data/repositories/schedule_detail_query.py:5`、`core/models/operation_execution_event.py:251`、`data/repositories/operation_execution_event_repo.py:84`、`356`。该仓库明确拒绝只按 `op_id` 的旧读取入口。

## 3. 基础资料：字段与动作映射

### 3.1 零件工艺、工种

当前原生样板的能力包括：零件搜索/阶段筛选/选择/批量删除，新增零件，整条或逐行路线输入与预览，每道工序自制/外协确认，未知工种待归类，工时填报及重开步骤，路线/工时导入，筛选/全部 Excel 或 CSV 导出。证据：`plana-logic.js:458`、`665`、`750`、`805`、`1132`、`1329`、`1582`、`1766`。

| 样板字段/动作 | 现有 method/path 或可复用服务 | 持久化与缺口 |
| --- | --- | --- |
| 图号 `code`、名称 `name`、路线 `route`；列表/详情 | `GET /process/`；`GET /process/parts/<part_no>`；`PartService.list/get_template_detail` | 映射 `part_no/part_name/route_raw/route_parsed`，返回 HTML。样板阶段筛选并非 `route_parsed=yes/no` 可完整表达 |
| 新增零件并带路线/工序/工时 | `POST /process/parts/create`，表单 `part_no,part_name,route_raw,remark,strict_mode` | `PartService.create()` 可事务保存并解析，但不能接样板每行 `src/setup/unit` 作为完整新建载荷。连续调用“建零件+逐行写工时”不是一个原子动作 |
| 基础信息编辑 | `POST /process/parts/<part_no>/update`，`part_name,route_raw,remark` | 仅更新零件基础信息，不等于重新生成工序；不能保存文字后就显示工序已同步 |
| 整条路线解析/重新生成 | `POST /process/parts/<part_no>/reparse`，`route_raw,strict_mode`；`PartService.parse/reparse_and_save` | `reparse_and_save` 写 `Parts`，删除重建 `PartOperations/ExternalGroups`，保留同 seq 自制工时，新外协组默认 `separate`；失败解析在替换之前拦截。服务 `parse` 可复用做预检，未找到独立手工路线 JSON 预检路由 |
| 逐行路线及每道工序人工归属 | 无等价写路由；现有路线解析器按工种/路线解释得到 `source` | 样板 `seq,op,src`、`PART_STAGE.attr`、未知工种待建与确认人/时点没有正式字段。不能用 `POST /process/op-types/<op_type_id>/update` 改全局 `category` 代替一条路线的归属确认；否则影响其他模板 |
| 自制换型 `setup`、单件 `unit` 保存 | `POST /process/parts/<part_no>/ops/<int:seq>/hours`，`setup_hours,unit_hours`；`PartService.update_internal_hours` | 写模板 `PartOperations`，非批次 `BatchOperations`。当前 HTTP 一道工序一次；样板整页保存多道工序需明确全成/部分成策略及逐行错误 |
| 删除零件/批量删除 | `POST /process/parts/<part_no>/delete`；`POST /process/parts/bulk/delete`，重复字段 `part_nos` | `PartService.delete()` 有批次引用保护。批量逐项执行，失败可与成功并存；不能沿用原型删除 DOM 即成功 |
| 自制/外协工种 `code,name,note` | `GET /process/op-types`；`GET /process/op-types/<op_type_id>`；`POST /process/op-types/create`；`POST /process/op-types/<op_type_id>/update`；`POST /process/op-types/<op_type_id>/delete` | 表单 `op_type_id,name,category,remark`，归属 `internal/external`。样板 `note -> remark`，`int/ext -> internal/external`；列表 HTML 的工种数之外，设备/技能人员关联数需真实聚合 |
| 外协工种默认周期策略 `policy`、待归类工种列表和转建 | 仅工种 CRUD 部分可用；无 `policy` 或待归类工作流端点 | `merge_mode` 是具体外协组字段，不是 `OpTypes` 默认策略。待建名称不能伪造真实 `op_type_id`。转建还需处理待建项引用与路线重新校验 |
| 工种列表批量删除 | 没有工种批量删除路由；有单条 delete 服务 | 可以新增批量业务包装，或明确逐项结果；不能宣称原型批量动作已有对应 HTTP |

正式证据：`web/routes/process_parts.py:95`、`174`、`228`、`251`；`core/services/process/part_service.py:138`、`193`、`215`、`269`、`379`；`web/routes/process_op_types.py:17`；样板字段实际定义 `plana-logic.js:1478`。

**工时缺失/零值和流程阶段需单独定合同。** 正式模板模型工时默认 `0.0`，重新生成时也是 0 或保留同序号旧值，不能仅凭 0 还原“未录入”；原生样板把单件 0 标为复核项，而主数据总览允许非负有限 0。保存负数/NaN/Infinity、0 合法与“待复核”不能混为一事。样板“缺项保持待补”的承诺也不等于旧宽松解析：后者可把缺外协周期暂按 1 天并返回警告。证据：`core/models/part_operation.py:29`、`core/services/process/part_route_validation.py:27`、`142`，`plana-logic.js:654`、`720`，`master-data-overview.js:133`。不能为保持样式而把上述警告删掉。

### 3.2 设备、人员、供应商、物料

当前原生资源页都有搜索、选择、批量删除、导入/导出、新增，行内“查看/编辑/删除”位置。`plana-logic.js:264` 的通用行按钮、`265` 的分页并不构成完整 CRUD；`1717` 新增只是临时 DOM 插行，`1226` 批删只是移除行。下表记录的是这些位置要兑现的后端能力。

| 样板字段/动作 | 现有 method/path、字段 | 真正数据边界/缺口 |
| --- | --- | --- |
| 设备 `code,name,op,group,status`，详情 | `GET /equipment/`、`GET /equipment/<machine_id>`；`POST /equipment/create`、`POST /equipment/<machine_id>/update` | 对应 `machine_id,name,op_type_id,team_id,status`；另有旧字段 `category,remark`。`op` 必须用工种 ID，不能用显示名称；“设备组”不能未经确认等同于人机共用 `ResourceTeams` 班组 |
| 设备可用/检修、单删/批删 | `POST /equipment/<machine_id>/status`；`POST /equipment/<machine_id>/delete`；`POST /equipment/bulk/delete`，`machine_ids` | 状态 `active/maintain/inactive`；检修状态不自动产生有起止时间的 `MachineDowntime`。删除有正式引用约束；样板未提供单独停机编辑 |
| 人员 `code,name,skills[],shift,status` | `GET /personnel/`、`GET /personnel/<operator_id>`；`POST /personnel/create`、`POST /personnel/<operator_id>/update` | 可保存 `operator_id,name,status,team_id,remark`；`Operators` 没有 `skills[]` 和“白班/两班倒/夜班”字段。按日期的 `OperatorCalendar` 不是一个固定班次枚举 |
| 人员在岗/请假，单删/批删 | `POST /personnel/<operator_id>/status`；`POST /personnel/<operator_id>/delete`；`POST /personnel/bulk/delete`，`operator_ids` | 正式 `active/inactive`，旧页把 inactive 标“停用/休假”。样板请假可使人不可用，但保存 inactive 后无法无损区分请假与停用；不能假装后端有 `leave` |
| 人员工种多选与工种页技能人数 | 无等价 `OperatorOpType` 路由；可复用 `OperatorMachineService` 和查询服务读已有设备授权 | 真实关系是 `OperatorMachine(operator_id,machine_id,skill_level,is_primary)`，不是人员-工种多对多。由可操作设备聚合出工种仅是读投影，勾选工种不得自动授权该工种全部设备 |
| 供应商 `code,name,ops[],lead,status` | `GET /process/suppliers`、`GET /process/suppliers/<supplier_id>`；`POST /process/suppliers/create`、`POST /process/suppliers/<supplier_id>/update`、`POST /process/suppliers/<supplier_id>/delete` | 可写 `supplier_id,name,op_type_id,default_days,status,remark`；真实单个可空 `op_type_id`，样板 `ops[]` 是多个；真实周期是大于 0 的数字天数，不能发送“3 天”文本；`待复核` 不在 `active/inactive` 状态内 |
| 供应商批删 | 无批删路由，单删服务可复用 | 引用保护和逐项结果需包装。不能复制供应商编号以模拟多工种，或把待复核静默转启用 |
| 物料 `code,name,spec,stock,status` | `GET /material/materials`；`POST /material/materials/create`、`POST /material/materials/<material_id>/update`、`POST /material/materials/<material_id>/delete` | 对应 `material_id,name,spec,stock_qty,unit,status,remark`。样板库存如 `1,240 kg` 是合并显示，正式库存数值与单位分开；`低库存` 不是正式状态，后端只有 `active/inactive`，也未见低库存阈值字段 |
| 物料批删、物料文件导入/导出 | 没有对应批删或 Excel/CSV 业务路由 | 单条服务不是文件导入实现。低库存徽标不能从批次未齐套直接替代，库存保存也不会自动变更每批到料记录 |

正式证据：`web/routes/equipment_pages.py:171`、`245`、`328`；`web/routes/personnel_pages.py:122`、`152`、`227`、`263`；`web/routes/process_suppliers.py:54`、`95`；`web/routes/material.py:38`、`60`；`core/models/enums.py:11`、`core/models/machine.py:11`、`core/models/operator.py:11`、`core/models/supplier.py:11`、`core/models/material.py:11`。样板表单证据：`plana-logic.js:1481` 至 `1515`。

### 3.3 工作日历

| 样板动作 | 复用点 | 字段、影响与缺口 |
| --- | --- | --- |
| 月历、上一月/下一月/今天、按日查看、月统计 | `GET /scheduler/calendar`；`CalendarService` 管理读委托 `CalendarAdmin.list_all/list_range` | 旧 GET 是全部显式配置的 HTML，不是月视图 JSON；默认日期要与显式配置区分，不能把每个日历格都当已存记录。样板 `calState.cfg` 的月为 0 基，正式日期为 `YYYY-MM-DD` |
| 单日工作/休息、工时、效率%、普通/急件独立开关、备注 | `POST /scheduler/calendar/upsert`，`date,day_type,shift_hours,shift_start,shift_end,efficiency,allow_normal,allow_urgent,remark` | `work/rest` 需映射 `workday/holiday`，休息应明确零工时和不可排；`100% -> 1.0`。正式效率必须 >0，即使休息也不能直接传 0；班次结束填了会重新计算可用小时。样板未露出班次起止，要制定保留原值的保存合同 |
| 清除某日配置回默认 | 服务 `CalendarAdmin.delete(date_value)` 已有，无对应删除 HTTP | 清除不是写一条 0 小时日历，否则工作日无法恢复默认。需要可审计的删除适配 |
| 日期范围统一设置：每天/仅工作日/仅周末 | 单日 `upsert`、`upsert_no_tx` 可复用；没有此范围编辑 HTTP | 需有限日期范围、实际命中日期预览、原子批量写或明确逐日结果，不能循环调用后假称整体原子。旧 Excel 日历接口是另一种载荷，不是范围编辑 API |

证据：`plana-logic.js:848`、`914`、`997`；`web/routes/domains/scheduler/scheduler_calendar_pages.py:12`、`42`；`core/services/scheduler/calendar_admin.py:92`、`118`、`282`、`320`。

### 3.4 批次物料需求的范围边界

旧系统有完整的 `GET /material/batches?batch_id=<id>`，以及 `POST /material/batches/<batch_id>/requirements/add`、`POST /material/requirements/<int:bm_id>/update`、`POST /material/requirements/<int:bm_id>/delete`。新增字段 `material_id,required_qty,available_qty`；更新为数量字段及页面返回用 `batch_id`。服务以真实 `bm_id` 找所属批次，不应把返回参数当记录所有权。

该旧编辑区没有进入当前 `ProcessNative`；原生物料页仅说“去批次管理引用”，`BaseBatches` 当前也没有物料需求编辑区。因此**需求增删改暂不移植**，但值班台/批次齐套的真实读取必须尊重其存在。`BaseMaterial.jsx` 有旧样板不等于当前可达。

持久化口径：`BatchMaterialService` 写 `BatchMaterials` 并在同一事务同步 `Batches.ready_status/ready_date`，不扣减 `Materials.stock_qty`；新增到料留空默认等于需求量；单行仅够/不够，批次的 partial 是“部分需求行已齐”，不是“每行都到了一部分”；无需求行回默认齐套并清空齐套日期，全部齐套保留人工齐套日期，不足则清空。证据：`web/routes/material.py:101`、`145`；`core/services/material/batch_material_service.py:64`、`160`。不要将样板低库存/库存总数换算为该齐套状态。

## 4. 导入、预检、确认和导出

### 4.1 真正存在的端点

表中同一基路径 `B` 的端点均为：`GET B` 旧向导页、`GET B/template` 下载模板、`POST B/preview` 上传预检、`POST B/confirm` 确认写入、`GET B/export` 导出当前库数据。这是明确的拼接规则，不是拟议 API；例如路线预检的完整地址是 `POST /process/excel/routes/preview`。

| B 基路径 | 当前样板对应 | 关键模式/边界 | 路由证据 |
| --- | --- | --- | --- |
| `/process/excel/routes` | 工艺路线导入/模板/导出 | `overwrite/append/replace`、`strict_mode`；有批次时 replace 禁止 | `web/routes/process_excel_routes.py:152`、`167`、`224`、`300`、`346` |
| `/process/excel/part-operation-hours` | 工时定额导入/导出 | `overwrite` 更新、`append` 只补空工时；**不接受 `fill`**，也不接受 replace | `web/routes/process_excel_part_operation_hours.py:233`、`246`、`303`、`387`、`433` |
| `/process/excel/op-types` | 自制/外协工种导入/导出 | 工种统一表，带 `category`；样板按链筛选导出需增加真实筛选投影 | `web/routes/process_excel_op_types.py:143`、`157`、`208`、`284`、`330` |
| `/process/excel/suppliers` | 供应商导入/导出 | 单工种和默认周期合同，不能读多工种 chips 后直接提交 | `web/routes/process_excel_suppliers.py:122`、`136`、`225`、`333`、`379` |
| `/equipment/excel/machines` | 设备导入/导出 | 设备编号、名称、工种、状态及班组；引用基线包括工种/班组 | `web/routes/equipment_excel_machines.py:182`、`196`、`292`、`393`、`438` |
| `/personnel/excel/operators` | 人员导入/导出 | 工号、姓名、状态、备注、班组；不支持人员工种技能/固定班次 | `web/routes/personnel_excel_operators.py:105`、`120`、`197`、`291`、`338` |
| `/scheduler/excel/batches` | 批次 Excel 导入/模板/导出 | `overwrite/append/replace`、`auto_generate_ops`、`strict_mode`；replace 会清全部批次，并非筛选结果 | `web/routes/domains/scheduler/scheduler_excel_batches.py:139`、`155`、`238`、`347`、`392` |
| `/scheduler/excel/calendar` | 服务可借用，但样板是日期范围表单，非 Excel 控件 | 日期、类型、班次开始/结束、工时、效率、普通/急件、说明；替换不是单月替换 | `web/routes/domains/scheduler/scheduler_excel_calendar.py:138`、`159`、`220`、`343`、`388` |

另有 `GET /process/excel/part-operations` 和 `GET /process/excel/part-operations/export`，仅导出工序清单，无导入对应，见 `web/routes/process_excel_part_operations.py:20`、`31`。人员设备关系的 `/personnel/excel/links`、`/equipment/excel/links` 以及个人日历 `/personnel/excel/operator_calendar` 也存在上述五端点，但属于旧页暂不迁选项，不能拿它们代替样板的人员-工种技能表。

### 4.2 载荷与事务

1. **主数据预检**：`multipart/form-data` 上传 `file`，另带 `mode` 和所属业务开关；标准单表 `.xlsx` 解析保留源行信息。返回旧模板上下文 `preview_rows,raw_rows_json,preview_baseline,mode_value,filename`，不是直接 JSON。
2. **主数据确认**：表单回传 `raw_rows_json,preview_baseline,mode,filename` 及原开关。服务端重新读取当前记录/引用、比对基线、重新逐行校验，不能只发送客户端“已通过”的状态。基线绑定行内容、模式、现有数据、业务 extra_state，见 `web/routes/helpers/excel_utils.py:41`、`168`，不是单纯文件名。
3. **预检的写边界**：不提交主数据，但 `log_excel_import()` 能写预检审计；标准上传解析会创建并清理临时 `.xlsx`，不是完全无文件副作用，见 `web/routes/helpers/excel_utils.py:338`、`core/services/common/excel_audit.py:39`。本次没有调用这些路由。
4. **整批是否原子要分业务**：批次/设备/人员使用 `execute_preview_rows_transactional`，正常配置下运行期 AppError 会抛出并回滚事务；路线和模板工时在外层事务内捕获逐行 AppError 并计数继续，可能部分成功。不得给所有向导统一写“任一失败整批零写入”。证据：`core/services/common/excel_import_executor.py:121`；`core/services/scheduler/batch_excel_import.py:12`；`web/routes/process_excel_route_apply.py:117`、`143`；`core/services/process/part_operation_hours_excel_import_service.py:60`、`90`。
5. **预检不是最后一次校验**：引用变化、模板变化、模式变化应返回“重新预检”，不要自动沿用过期确认。批次自动生成工序开关参与基线；生成失败不能留下只有批次没有工序的半成品。已有静态测试线索 `tests/excel_data_io/test_batch_excel_import_strict_mode_hardfail_atomic.py`，本轮未运行。
6. **样板额外承诺尚未成立**：`plana-logic.js:1766` 声称 `.xlsx/.csv`、2000 行、按编号增量、引用关键字段二次确认，实际仅模拟点击结果；现有标准路线是 `.xlsx`，没有证明上述 CSV 解析/导出和统一二次确认存在。不可把旧 `replace` 选项自动搬到原生基础资料通用导入。批次样板明确保留 replace，必须明确清空范围和保护结果。
7. **导出范围**：旧主数据导出多读全量，批次 `GET /scheduler/excel/batches/export` 调 `batch_svc.list()` 并 `filters={}`，不接勾选 ID；样板“所选”“当前筛选/全部”与 CSV 都需适配，不可静默扩大导出范围。浏览器成功创建 Blob 也不证明用户已经保存文件。证据：`web/routes/domains/scheduler/scheduler_excel_batches.py:392`、`plana-logic.js:1780`、`BaseBatches.jsx:520`。

**推荐接入判定**：保留样板弹窗/表格样式，但业务预检结果必须来自后端，确认后读回写入对象。是否把单步弹窗扩成预检/确认阶段是实现设计，不是新增旧功能；不能以“样式一致”为由省掉破坏性写入前的结果检查。

## 5. 批次管理

| 样板能力 | 可复用 method/path / 服务 | 字段及不能遗漏的边界 |
| --- | --- | --- |
| 列表、搜索、状态/齐套/列筛选、排序、选择、展开工序 | `GET /scheduler/batches`；`BatchService.list_page/list_operations`；`GET /scheduler/batches/<batch_id>` | GET 支持 `status,only_ready,page,per_page`，不传 status 默认 pending，`status=` 才是全部；服务另可按 priority/part_no 查询。样板 search/列排序/每批进度/缺资源数不全在现有列表响应内；不能仅对一个后端分页做过滤却显示为全库筛选 |
| 新增批次 | `POST /scheduler/batches/create` | `batch_id,part_no,quantity,due_date,priority,ready_status,ready_date,remark,strict_mode,next`；默认从模板生成工序，缺模板尝试解析路线。样板新增为 `ops:[]`，必须明确接入后采用哪一行为，不能同一按钮两套成功语义 |
| 单批基础信息保存 | **无等价完整 HTTP**；可复用 `BatchService.update()` | 样板需写 `quantity,due_date,priority,ready_status,ready_date,remark`。现有 `/batches/bulk/update` 只接受后三者中的交期/优先级/备注，不能补齐数量与齐套，也不能用空白清空交期。不得虚构 `/batches/<id>/update` 已存在 |
| 批量修改/预览/确认 | `POST /scheduler/batches/bulk/update` | `batch_ids` 重复字段、`bulk_priority,bulk_due_date,bulk_remark,next`；留空不改。逐批事务，允许部分失败；没有批量动作专用的后端预览 token，样板 revision 预览保护仍需正式对接 |
| 复制所选 | `POST /scheduler/batches/bulk/copy` | `batch_ids,next`，末尾数字 +1，冲突继续找可用号；新批次及工序状态 pending，复制工序补充信息；不复制实际事件、排程结果或 BatchMaterials。每条复制事务独立，返回旧 flash 中的映射/失败样本 |
| 单删/多删 | `POST /scheduler/batches/<batch_id>/delete`；`POST /scheduler/batches/bulk/delete` | 按实际批次 ID；涉及工序、排程及外键引用，不是只删列表。已有事件通过外键保护被引用的排程/工序，不可为了使删除成功而清除历史执行事件 |
| 按最新模板刷新 | `POST /scheduler/batches/<batch_id>/generate-ops` | `strict_mode,next`；`create_batch_from_template(...rebuild_ops=True)` 在事务内删除旧批次工序、重建并回待排。需保存失败与旧工序仍保留的证据。原型清空完工/草稿的行为不能越过正式执行事件保护 |
| 批次自制工序编辑 | **`POST /scheduler/ops/update-token/<token>`** | 保存地址由详情上下文 `operation_update_actions[form_key]` 提供，服务解析 token 回 op_id；表单 `machine_id,operator_id,setup_hours,unit_hours,next`，写 `BatchOperations`。`POST /scheduler/ops/<int:op_id>/update` 只 flash 入口失效，不保存，不能推荐复用 |
| 批次外协工序编辑 | 同一个 `POST /scheduler/ops/update-token/<token>` | `supplier_id,ext_days,next`；`ScheduleService.update_external_operation` 检查供应商可用和外协组。样板说 merged 可单填周期，真实服务 **禁止 merged 逐道设置 ext_days**，只能保留整组口径；这是合同冲突，不是参数改名 |
| 工序进度/完工徽标 | `BatchService.list_operations` 的状态 + 完整身份的执行事实 | 样板从前序 `done` 推断“进行中”只是演示。正式“前序已完”不证明本序实际开工；计划状态、执行状态及无报工要分别展示 |

证据：`BaseBatches.jsx:378`、`464`、`634`、`760`；`web/routes/domains/scheduler/scheduler_batches.py:132`、`189`、`250`、`334`、`368`、`401`；`web/routes/domains/scheduler/scheduler_batch_detail.py:382`；`web/routes/domains/scheduler/scheduler_ops.py:17`、`37`、`44`；`core/services/scheduler/batch_copy.py:10`；`core/services/scheduler/operation_edit_service.py:136`、`156`；执行外键见 `core/infrastructure/migrations/v15.py:38`，v19 经 v18 继承该约束。

模板/批次还存在两套样板数据：`ProcessNative` 的 `APSPlanAData` 与 `BaseBatches` 的 `BD.usePartsStore()` 不同源。不能认为原型工艺新增已真实联动批次图号选项；正式接入必须统一真实 `Parts/PartOperations`，但不能把两套 mock 简单合并入数据库。

## 6. 现场记录与实际甘特

### 6.1 当前能复用的现场 HTTP

统一前缀 `E=/scheduler/resource-dispatch/execution`，表内路径为完整地址。读取、模板与导入也需要完整查询上下文，不能仅带任务号。

| method/path | 请求/响应关键字段 | 当前能力与限制 |
| --- | --- | --- |
| `GET /scheduler/resource-dispatch` | HTML，携带各数据/实际写入 URL 及计划上下文 | 旧资源派工页面，不是样板实际甘特 |
| `GET /scheduler/resource-dispatch/execution/data` | 查询 `version,plan_role,period_preset,scope_type,start_date,end_date`；非 custom 还需 `query_date`，可带 `batch_id,operator_id,machine_id,team_id,team_axis` | JSON `{success,data:{plan_identity,can_write_feedback,disabled_reason,degradation_events,tasks}}`；主卡是工序级聚合，不带完整 `reports[]` |
| `GET /scheduler/resource-dispatch/execution/tasks/<task_key>/events` | 同查询上下文 | JSON `task_card,events[]`，事件有 `event_id,action,event_time,record_time,created_by,remark`、异常字段及资源显示信息；不是逐次报工明细 |
| `GET /scheduler/resource-dispatch/execution/<int:op_id>/events` | 除查询上下文还需 `schedule_id,batch_id` | 老的内部身份读取可用，但新 Screen 优先使用公开 task_key 入口，不自行还原内部 ID |
| `POST /scheduler/resource-dispatch/execution/tasks/<task_key>/actual` | JSON `state_key,idempotency_key,created_by/feedback_person,actual_start_time,actual_finish_time,quantity_done,quantity_scrapped,remark`，还可带暂停/异常字段 | 组合写 start/pause/resume/exception/finish，返回 `event,current_status,idempotency_reused,task_card`；下一次必须用读回的 state_key |
| `POST /scheduler/resource-dispatch/execution/<int:op_id>/actual` | 上述载荷外，需 `schedule_id,batch_id,expected_state_revision` | 内部身份版本的组合写入口；不等于任意更新已报事实 |
| `POST /scheduler/resource-dispatch/execution/<int:op_id>/start` | 身份/修订字段 + `event_time,operator_id,machine_id,remark` | 写开始事件；资源与正式安排有校验，不可当任意换机换人接口 |
| `POST /scheduler/resource-dispatch/execution/<int:op_id>/finish` | 身份/修订字段 + `event_time,quantity_done,quantity_scrapped,remark` | 终结工序事件，不是“本次结束”；不能做多次部分报工 |
| `POST /scheduler/resource-dispatch/execution/<int:op_id>/pause`、`POST /scheduler/resource-dispatch/execution/<int:op_id>/resume` | `event_time`，pause 还需 `reason_code`，可带 `remark` | 旧事件能力，可保留旧数据读取；不把报工间空档推定为 pause |
| `POST /scheduler/resource-dispatch/execution/<int:op_id>/report-exception` | `event_time,reason_code,severity,impact_minutes,affected_machine_id,affected_operator_id,handling_status,suggest_reschedule,remark,reason_detail` | 异常事实，不是值班台通用认领/关闭台账 |

证据：`web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:48`、`95`、`128`、`144`、`176`、`217`；完整查询要求 `scheduler_resource_dispatch_query.py:50`、`95`；task_key/state_key 处理 `scheduler_resource_dispatch_execution_context.py:250`；返回投影 `web/viewmodels/scheduler_resource_dispatch_execution.py:259`、`356`、`398`。

可用的查询形状示例，仅作合同说明，本轮未发送：`?version=<真实版本>&plan_role=adopted&period_preset=custom&scope_type=operator&start_date=2026-09-01&end_date=2026-09-09`。不能使用样板固定 v15 当真实版本。

### 6.2 从样板逐字段看差额

| 样板字段/动作 | 后端现状 | 接入要求 |
| --- | --- | --- |
| 工序目标 `target`，累计 `qty`、剩余 `remaining` | 现有任务卡投影没有应做数量和累计完成数量；`Schedule` 明细投影含 piece_id，不含批次数量 | 明确整批工序/单件工序的目标量来源，不能把所有任务的 target 都填 `Batches.quantity`；补类型化读投影 |
| 每次 `reportNo,id,start,end,qty,hours,machine,person,remark,recorded,revision` | 事件表有单个 event_time；数量在 finish 事件，schema 无逐次 `effective_hours/report_no`；公开 event_payload 也未输出 quantity_done | 需要真正的逐次记录身份、版本及数值字段；不能抓展示标签反向解析。补录有效工时必须是实际字段，不从计划或时段跨度推算 |
| 新增部分报工、补齐同条记录 | 状态机只允许开工一次、完工一次，中间可暂停/恢复/异常 | `end` 是本次结束而非整道结束；数量报齐且所有段完整后才整道完成。现有 finish 不具备这个规则 |
| 更正完整记录/已完工后的更正 | 事件仓库仅追加，无更正路由/类型 | 原型要求原因并保存 before/after，revision 不符拒绝；正式应可追溯、可重算，不得直接 UPDATE 历史事件或删除重写，更正减量可能使工序重新未完成 |
| 换设备/人员 | 组合 actual 入口使用计划设备/人员写 start；样板各次可改资源 | 不能丢掉实际资源再声称复盘能看资源变更。需合法资源候选、实际资源记录与允许偏离的合同 |
| 报齐剩余、一键最大数量 | 样板只是填写该次上限，仍校验时间/工时后保存 | 正式要在事务里检查最新累计量，不能把客户端 max 当唯一防超报保护 |
| 时间轴、展开、详情、筛选、草稿 | 纯前端可复用 | 正式使用本机生产时间合同；原型 `Date.parse(s+'Z')` 是样例时钟约定，不能把 SQLite 本地时间直接当 UTC，避免八小时时差 |

证据：`field-report-model.js:22`、`25`、`32`；`field-report-editor.js:66`、`95`、`112`；`core/models/operation_execution_event.py:59`；`core/services/scheduler/resource_dispatch_actual_record_service.py:285`、`343`；`data/repositories/operation_execution_event_repo.py:17`、`195`；`data/repositories/operation_execution_state_builder.py:237`。后端 `actual_duration_minutes` 是整段开始到结束跨度，不是样板逐次“有效加工小时”。

### 6.3 写保护、重复提交与失败留痕

- 可写只限最新可执行正式 adopted 方案、`source_table=schedule`、无 scenario；历史/候选/模拟必须保留只读状态及理由，不因样板 `source='current'` 放开。`ResourceDispatchExecutionService` 返回的 guard 与事务内 `OperationExecutionFeedbackService._load_current_official_schedule` 均需保留。
- `record_event()` 在 `BEGIN IMMEDIATE` 内校验完整身份、修订号、事件序列、资源，写事件并读回状态；同幂等 key、同内容为重放，冲突不得另写。`state_key` 过期必须先刷新核对，不能无提示换新 key 重试。证据：`core/services/scheduler/operation_execution_feedback_service.py:94`、`368`。
- 已成功事件本身是落库事实，不代表另有一份完善的操作日志。当前路由 `except AppError` 只返回可见 JSON 错误；未知异常才明确 `logger.exception` 带 task_key/op_id/action。**未找到每个校验拒绝都写 OperationLogs 的保证**，不能在新页显示“所有失败均已审计”。若目标要求逐次报工及更正失败可查，应补失败记录合同，并区分业务写入失败、审计写入失败。证据：`scheduler_resource_dispatch_execution_routes.py:144`、`160`、`scheduler_resource_dispatch_execution_context.py:101`、`tests/operation_execution/test_operation_execution_error_log_context.py:1`。

### 6.4 现场 Excel

真实已有：`GET /scheduler/resource-dispatch/execution/actual-template`；`POST /scheduler/resource-dispatch/execution/import/preview`；`POST /scheduler/resource-dispatch/execution/import/confirm`；以及直接导入 `POST /scheduler/resource-dispatch/execution/import`。

- 模板为两业务表：“任务反馈”及“暂停明细”。前者列 `任务识别码,批次,工序,计划设备,计划人员,实际开工时间,实际完工时间,完成数量,报废数量,异常时间,异常原因,异常严重程度,异常说明,反馈人,备注`；后者列 `任务识别码,暂停开始时间,暂停结束时间,暂停时长分钟,暂停原因,暂停说明,反馈人`。证据：`core/services/scheduler/resource_dispatch_actual_records.py:16`。
- preview 上传 `file`，JSON 回 `preview_token,raw_rows,rows,summary`；confirm JSON 回传 `raw_rows` 或 `rows` 以及 `preview_token`，查询上下文不能变化。确认重新预检；最终事件在同一写事务完成。直接 import 也先预检再写，不是绕过验证。证据：`resource_dispatch_actual_record_service.py:76`、`97`、`107`。
- **样板文件不是该模板**：样板“报工记录”十列，核心为 `报工编号,批次号,工序,本次完成数量,实际开工,本次实际完工,有效加工工时(h),实际设备,实际人员,备注`，最多 5000 行；重复导入不累计，允许补齐未知字段，已知事实冲突拒绝，完整记录更正走明确流程。全部错误归零提交；支持下载问题清单。证据：`field-report-import.js:4`、`278`，`field-reporting.js:58`、`73`。
- 所以，已有四个端点可复用流程部件，**不能直接支持样板逐次模板**；需要新模板合同和真实逐次记录存储。数据错配应失败，禁止把有效工时塞进 remark，把每次 end 发成整道 finish。
- 样板“导出报工”实际生成 XLSX 的报工明细/工序汇总；旧 actual-template 是填写模板，旧执行复盘 export 是工序级对照，两者均不能替代报工导出。见 `field-reporting.js:35`。

### 6.5 实际甘特

范围仅是现场实际甘特，不重复评估计划甘特/排产计算。样板已有设备/人员/批次分组、折叠、搜索、仅看选中、超期类别筛选、明细/链显示、缩放、适应范围、定位、来源返回、CSV；这些交互可在统一工作台样式内保留，数据需按以下边界接入：

- 原计划基线：真实计划开始/结束与计划资源；实际条：同一工序的逐次记录开始/本次结束/数量/有效工时/实际资源；剩余条：正式提供的 `remainingPlan.start/end/machine/person`。三者不能合并成一个大条，不能让实际工序换机后仍画在原计划设备上。
- 只有开始未结束的报工画开工点，不强行延长至“现在”；剩余计划缺失画“待续排”，不把原计划尾段当新剩余安排。实际缺数展示“已知数量/待补”，不是零产量。证据：`FieldGanttRows.jsx:45`、`92`。
- 当前 execution/data + events 可提供基线及事件事实的一部分，但缺逐次记录、目标/累计量、完整剩余安排投影。交给排产代理的边界只是请求其提供权威剩余计划与工序身份，不在本材料新增排产算法。不能在前端按已知工时比例推算新的可执行资源时间。
- “已完晚”“到期未确认完成”“剩余安排预计晚”是不同集合；`fg-screen-model.js:25` 使用各自真实时间与 10 分钟边界。`FieldGanttScreen.jsx:54` 导出需同一来源/同一筛选下的基线和逐次记录，不只是可见分页或像素截图。
- 样板复杂/密集源保留为演示检查选项时必须始终只读、独立，不允许调用真实写入；跨源定位失败要明示，不能仅凭相同批次号命中生产记录。

## 7. 执行复盘与报表中心

### 7.1 已有真实入口

| method/path | 真实用途及复用部分 | 不能冒充 |
| --- | --- | --- |
| `GET /reports/` | 报表首页 HTML | 样板五专题已经接入 |
| `GET /reports/execution-review` | `ReportEngine.execution_review`；`version,date_from,date_to,batch_id`，资源过滤为 `resource_type=machine/operator,resource_id`；正式采用方案的工序计划/实际对照 | 逐次报工台账、有效工时与全部指标原始数值接口 |
| `GET /reports/execution-review/export` | 同正式方案与过滤，下载 XLSX；空结果拒绝导出 | 样板 CSV 或仅当前页导出 |
| `GET /reports/overdue`、`GET /reports/overdue/export` | 批次交期/完整计划的超期报表及 XLSX | 样板“工序完成情况”；批次交付专题暂不移植 |
| `GET /reports/utilization`、`GET /reports/utilization/export` | 计划占用/真实可用日历产能，`version,plan_role,start_date,end_date` 等 | 样板设备/人员“已报工时” |
| `GET /reports/downtime`、`GET /reports/downtime/export` | 有效停机台账与计划交集 | 报工间空档、异常归责或样板正式停机专题 |

证据：`web/routes/reports.py:19`；`web/routes/reports_export_routes.py:28`、`56`、`98`、`129`；`web/routes/reports_execution_review_page.py:123`；`core/services/report/execution_review.py:215`、`261`、`319`。执行复盘路由拒绝非 adopted 和 scenario，见 `web/routes/reports_request_support.py:64`；不应随着新界面增加候选源而放开真实执行事实读取。

### 7.2 样板五类专题与分析合同

| Screen/专题 | 样板字段和动作 | 后端缺口/接法 |
| --- | --- | --- |
| 执行复盘总览 | 到期完成/按时率，计划/实际累计曲线，开完工偏差分布，未闭合账龄，设备/人员已报小时，重点事实点击进入报表；汇总 CSV | 保留 `ExecutionReviewScreen.jsx:75` 的分析首屏；需要数值型工序与逐次事实，不读旧 `*_label` 做数学；统计与明细使用同一 cohort |
| 工序完成情况 `delivery` | `target,qty,remaining,status,planStart,planEnd,actualStart,actualEnd,startDelta,endDelta`；详情/实际甘特定位、排序/分页/CSV | 旧复盘提供计划实际标签，但不含完整数量/逐次原始值；不能把 current_status=completed 与样板“全量报齐且各段完整”直接等价 |
| 报工记录 `records` | 一次一行，`reportNo,start,end,qty,hours,machine,person,recorded`，工序内记录分页 | 当前事件列表缺逐次记录实体；补同一事实投影，不能把每个事件都计一次报工 |
| 设备工时 `machines` / 人员工时 `people` | 按实际资源聚合 `hours`、未知工时条数、报工数和工序数；点击资源形成关联工序范围 | 复用资源 ID/名称，不能改为按计划设备分组；未知不能填 0，空资源要作为未分配事实暴露；不是利用率 |
| 数据完整性 `quality` | 未报工/字段待补/计划缺项，缺开始、结束、数量、工时、设备、人员；返回现场补录、CSV | 后端校验失败与历史字段缺失要区分；“无报工”不等于“没生产”；不允许缺失字段被 DTO 默认 0 或计划值填满 |

共同 scope 是 `source,dateFrom,dateTo,batch,resourceType,resource,search,focus`，共同派生视图包含来源版本与截至时点。`review <-> reports <-> fieldgantt` 跳转要带完整 scope、稳定 task ID 及返回上下文；排序、页码、选中工序、工序内记录分页是 UI 状态。见 `ReportsScreen.jsx:50`、`107`，`ExecutionReviewScreen.jsx:147`，`AnalysisShared.jsx`。

### 7.3 必须修正的口径差异

- **日期**：样板 `low <= planEnd < endDate+1日` 选工序，其全部报工随入；旧 `execution_review` 经 `list_detail_rows_between` 按计划区间相交取行，并纳入坏时间行供上层处理。例：9 月 1 日开工、9 月 10 日计划完工的工序，查 9 月 1 日至 9 月 9 日，旧口径会出现，样板口径应不出现。证据：`execution-analysis-model.js:131`，`core/services/report/execution_review.py:171`，`data/repositories/schedule_plan_query_repo.py:313`，`data/repositories/schedule_time_sql.py:73`。
- **资源**：样板按“计划或实际资源关联”选工序，并包含这些工序全部报工；旧 SQL 只过滤 `s.machine_id/s.operator_id`。不能在调用旧资源过滤后再补前端筛选，否则实际换入资源的工序早已漏读。样板 `person` 还需映射正式 `operator`，`all` 在旧报表不是合法资源枚举；全部资源应省略成对过滤字段。证据：`execution-analysis-model.js:44`，`data/repositories/schedule_resource_sql_filters.py:22`，`core/models/schedule_resource_filter.py:8`。
- **分母**：到期分母为 `planEnd <= asOf` 的工序数；完成率为已确认完成/到期，按时率为到期且完工偏差 <=10 分钟/到期。不能只对已完工工序求按时率并冠同名；零分母显示未知。已完工偏差另用 median、最近秩 P90，不能混入未完工预计时间。证据：`execution-analysis-model.js:32`、`57`。
- **工时**：只合计已知有效报工小时，附未知条数；未知与实际 0 不同。计划/实际起止跨度、扣暂停后的时间、有效加工小时和定额单件小时是四个量。报表不可从“暂无现场反馈”文字推导数字。
- **图表与导出**：报表导出必须覆盖整个已筛选集合而非一页，带来源/版本/截至/日期/资源/焦点；实际累计曲线是用当前事实回算，不是当时已保存的历史状态，未来时点实际数为未知。见 `execution-analysis-model.js:90`、`158`、`163`。

当前没有找到可一次返回样板五专题所需原始数值和逐次事实的正式 JSON 入口。可以复用查询服务、正式身份护栏和导出工具，仍需统一分析读模型/投影与共享范围合同，不能新增五份各算各的口径。

## 8. 工时定额校准

样板实际字段为图号/工序、工种、定额单件、实际中位数、样本数、偏差、建议/样本不足状态、采纳；有搜索、绝对偏差 >20% 筛选、详情、导出。`CalibScreen.jsx:12` 是固定 SEED，`67` 只是 `setAdopted`；`107` 才是未来意图“近 N 次，剔除暂停/异常，写回、来源、采纳人、日期、锁定，导入不覆盖锁定”。**没有实算中位数或真实采纳证据。**

只读检索 `web/routes,core/services,data,templates` 的 `calibr/校准/median/中位数/quota` 等未找到等价校准业务实现。普通可复用写入只有 `POST /process/parts/<part_no>/ops/<int:seq>/hours` 和模板工时 Excel 导入，不含建议身份、采纳人、样本集、定额锁定。`PartOperation` 模型也没有校准字段。已有 `lock_status` 属于排程锁定，不能借用。

要兑现当前样板能力，至少需明确以下合同后才可开发：

1. 校准目标是模板 `part_no + seq`，还是某批次工序实例；样板意图倾向模板定额，不应只改一个 `BatchOperations.unit_hours` 却声称已采纳。
2. 样本粒度是逐次报工还是整道工序完工，每个样本的有效小时/数量如何得到；一次 start/finish 跨度不能当“实际单件”。换型小时是否已经包含于有效工时、是否扣除、返工/报废如何计量，都未见已实现合同。
3. `N`、最少样本数、时间范围、异常/暂停剔除依据、0 数量及未知工时过滤、不同设备/工种/模板修订混用规则；剔除记录要可解释，不能凭备注里有“暂停”就删除样本。
4. 建议需有旧值、建议值、样本 ID/修订集、算法口径版本、生成时点；采纳前核对旧定额/样本未变化，过期建议不得直接覆盖。
5. 采纳事务写定额和采纳审计，带采纳人/时间/原因/来源；锁定后普通工时 Excel 导入是跳过、拒绝还是显式解除，必须统一。普通 `update_internal_hours` 没有这一保护，不能直接挂采纳按钮。
6. 新定额默认只影响后续模板复制/后续安排，不能隐式重建已有批次、改写已采用计划、影响历史复盘基线。需实际读回证明，并向工艺页回显真实校准来源。

以上属于待补能力/待定口径，不是本轮设计决策或移植实施。旧系统未找到校准页面，因此没有“旧校准选项暂不移植”可列，不能虚构。

## 9. 值班台

真实入口 `GET /`，`web/routes/dashboard.py:341` 组装 `build_dashboard_workbench_summary`，读取待排批次、当前合法历史/摘要、当日计划和完整身份执行事实、备份健康提示；返回 HTML。没有值班台通用更新 POST。

| 样板能力 | 可复用事实/服务 | 缺口 |
| --- | --- | --- |
| 交期风险/关联批次 | 已有 overdue 结果、批次详情、真实导航 context | 样板具体卡片/明细需投影；本材料不重复计划算法/候选方案评估 |
| 执行偏差、待回填 | 旧摘要的现场缺口读取、执行事实与复盘服务 | 样板 `actualRows.hours/quota` 及 20% 超耗不能从缺报工 count 得到；值班台手工回填必须写统一正式报工事实，而非再建独立数组 |
| 外协发出/计划回厂/实际回厂/确认状态 | `Suppliers/ExternalGroups/BatchOperations` 可提供供应商和计划周期信息 | 未找到完整外协回厂登记的正式实体或路由。周期不是回厂事实，不能更新 `default_days/ext_days` 冒充实际回厂 |
| 停机冲突、关联原计划工序 | `MachineDowntimeQueryService`、`ReportEngine.downtime_impact` 的真实停机与交集 | 交集小时不是最终后移量；该 Screen 样板不含旧停机新建/取消全套表单，暂不追加 |
| 齐套缺口 | `BatchService.list`、`BatchMaterialService.list_for_batches` | 使用真实 ready_status/ready_date；未齐套或待补不允许写为“已确认到料” |
| 条目认领/跟进/待验证/关闭/重开 | 无等价更新 HTTP；`OperationLogs` 是审计，不是处置状态表 | 样板 `owner,deadline,action,remark,completedAt,completionEvidence,evidenceRef`、状态历史必须有稳定条目身份和正式持久化；关闭处置不改风险计算事实 |
| 处置历史、按状态/搜索、跨页定位 | 现有导航 link builder 可承载已验证 context | 样板 `recordLog[]` 是内存 before/after。正式记录需含来源版本/对象 ID；跨源无映射就只开概览，不假高亮 |

直接证据：`dashboard-model.js:42`、`85`、`104`、`116`；`dashboard-workbench.js:34`、`89`；`web/viewmodels/dashboard_workbench.py:251` 明确“待处理项根据当前数据实时生成，暂不保存已处理状态”；`dashboard_workbench_todos.py:137` 起把现场缺口定义为情况待确认，非断言未生产。

如果要保持当前样板全部能力，值班台处置及外协回厂是新增后端能力，不是旧选项迁移。应与逐次报工采用同一真实事实源，处置只是附加说明/责任状态；不能“关闭”后抹掉晚交、停机或报工证据。无历史处置台账时显示没有处置记录，不能伪造全已处理。

## 10. 主数据总览

`MasterDataOverview.jsx` 期望八域：零件、工艺路线、工种、设备、人员、物料、供应商、日历；提供实体/待维护项两个清单，域/状态/搜索/排序/分页，详情字段完整率、关系、问题、维护定位及筛选全量 CSV。

- 现有正式各域 list/get 服务、`PartService.get_template_detail`、`OperatorMachineQueryService`、`ResourceTeamService`、日历查询、物料批次查询可复用；**未找到统一主数据总览 HTTP/服务**。不能把 `GET /equipment/` 当主数据总览。
- 当前 `master-data-overview.js:17` 用 `DOMParser` 解析原生样例单元格，`loaded` 必须 `schemaVersion=1,source='native-session'`；这只能用于样例，正式读模型应由原始记录/ID/引用直接构造，不应抓旧 HTML 或 DOM chips 来判关系。
- 最小正式结果需八域加载状态、实体稳定 ID/名称/状态/字段检查结果、问题 `rule/code/evidence/entity_id`、关系两端 ID、维护目标及可定位状态；“检查过”不是持久业务状态，刷新读最新事实即可，不因为浏览器看过一次便写主表。
- 工种人数当前只按样板技能名称关联，正式必须区分“有相关设备操作关系”与“技能已登记”；模板外协组供应商以 group_id/supplier_id 关系为准，不从“热处理 3 天”字符串推断；不存在的记录与未加载域分别计数。
- 不能把原型抬头的 86 条、14 台、23 人当已加载实体。样板总览已刻意只计算实际会话记录；正式接口分页时需服务端全量计数与一致筛选，不能把一个域第一页当全集计算就绪度。
- 维护跳转必须能到具体图号/工种/设备/人员/日期，保存后重新读取涉及的问题/关系；无真实目标映射要保持不可定位理由，不因名称相同自动匹配另一条记录。

证据：`master-data-overview.js:3`、`20`、`46`、`90`、`187`、`218`、`244`；`MasterDataOverview.jsx:65`、`89`、`107`、`131`；`plana-logic.js:1831`、`1853`。

## 11. 系统备份恢复、日志、配置

### 11.1 页面与数据源

样板“概况/备份恢复/运行日志/配置”已具备统一布局、过滤/分页/详情、导出样例日志 CSV、当前原型诊断 JSON、即时页面偏好。`current` 数据集 `backups:null,logs:null` 表示未知，不能显示 0；`sample` 的 verified/failed/pending/blocked 等是情境样本，不是真实任务队列或文件。立即备份/恢复/删除/正式诊断包/正式配置保存当前是禁用占位，纳入待接入能力，但本轮不解禁或调用。

| 现有 method/path | 关键字段/结果 | 可复用范围与边界 |
| --- | --- | --- |
| `GET /system/health` | JSON `app,status,contract_version,ui_mode,timestamp` | 进程响应/契约健康，不检查 SQLite 完整性、备份有效性、磁盘空间；不能据 status=ok 画“数据库健康” |
| `GET /system/backup` | HTML `backups,settings,job_state`、unsafe/error counts 和 samples | 备份文件清单来自目录，配置/最近自动任务来自正式服务；没有统一所有历史恢复事件列表，不能把每个文件标 verified |
| `POST /system/backup/create` | 无业务表单字段；生成 manual 文件 | 调 `BackupManager.backup`，成功后操作日志；耗时磁盘动作，不允许加载概况时隐式触发 |
| `POST /system/backup/restore` | 表单 `filename`，仅正式备份目录目标 | 调 `run_backup_restore` 完整流程；最终 flash/302，不是 JSON 成功布尔值 |
| `POST /system/backup/delete` | `filename` | 删除真实文件；不可逆，且手工删除不是按保留天数清理的保底策略，不能宣传始终留 3 份 |
| `POST /system/backup/settings` | `auto_backup_enabled,auto_backup_interval_minutes,auto_backup_cleanup_enabled,auto_backup_keep_days,auto_backup_cleanup_interval_minutes` | 写 `SystemConfig`，与排产 `ScheduleConfig` 分开 |
| `GET /system/runtime-logs` | `file,level,q`；HTML `entries,read_error,file_exists,total_before_filter,max_entries` | 文件日志只读。默认尾部最多 200 条，再做筛选，不能冒充全历史分页；无样板任意日期/类型/status 全库查询 |
| `GET /system/logs` | `start_time,end_time,module,action,log_level,limit,page,per_page` | `OperationLogs` 业务审计，`limit<=500` 为最近 N 条查询上限，再分页；WARN 与文件 WARNING 要归一显示但保留来源 |
| `GET /system/runtime-logs/diagnostic-package` | 下载 ZIP | 白名单日志 + 最近 200 条操作日志 + 环境信息；会创建临时 ZIP、结束后清理并记录导出；不是备份库下载 |
| `POST /system/logs/settings` | `auto_log_cleanup_enabled,auto_log_cleanup_keep_days,auto_log_cleanup_interval_minutes` | 写 `SystemConfig` 三字段，清理对象仅 `OperationLogs`，不是运行文件日志 |

证据：`SystemManagementScreen.jsx:105`、`139`、`182`；`system-workbench-model.js:16`、`67`、`123`；`web/routes/system_backup.py:79`、`111`、`163`、`188`、`331`；`web/routes/system_runtime_logs.py:39`、`89`；`web/routes/system_logs.py:30`、`90`；`web/routes/system_health.py:15`。

### 11.2 真实维护的危险边界与结果

1. **备份**：SQLite Backup API -> 临时副本 -> `integrity_check` -> 原子升为正式文件，维护窗口按数据库路径互斥。不能改成复制一个可能未包含 WAL 内容的文件。只有本次实际校验成功可称校验通过；历史文件只 list/stat 不补造校验结果。见 `core/infrastructure/backup.py:120`、`368`。
2. **恢复**：明确选择目录内 filename；关闭当前请求 DB；完整 `run_backup_restore` 外层维护窗口内先备份 before_restore，检查源库，复制后状态 `copied_pending_verify`，继续 `ensure_schema` 成功才是 `verified`。只调用 `BackupManager.restore().ok` 会把“待校验”当最终成功。见 `web/routes/system_backup.py:331`，`web/routes/system_backup_actions.py:16`、`54`。
3. **失败分类**：`busy` 未执行；`before_restore_backup_failed` 原库未改；`backup_integrity_failed` 源无效；`restore_failed_rolled_back` 与 `restore_failed_rollback_failed`；`verify_failed_rolled_back` 与 `verify_failed_rollback_failed`。不得把“已自动回滚”显示恢复成功，更不能显示所有失败都未修改过原库。现有网页只给 message/category，样板统一详情若要显示代码/保护副本/审计结果需结构化投影。见 `core/infrastructure/backup.py:206`、`238`，`web/routes/system_backup_actions.py:88`。
4. **文件删除与清理**：手工单删/批删按选择删除，不受自动清理保底的同等承诺；`POST /system/backup/cleanup` 才按保留期且保留最新最低份数。自动清理还有每轮数量上限。本次样板有删除备份，未包含一键手工清理/批量删除全套操作，后两项暂不迁。证据：`web/routes/system_backup.py:188`、`219`、`299`，`core/services/system/maintenance/cleanup_task.py:104`。
5. **自动维护**：请求触发检查，不是每分钟常驻定时线程；自动备份失败跳过本轮备份清理；正常退出备份共用开关。配置间隔 `1..1440` 分钟，保留期 `1..365` 天。不能因为界面有“待执行”就造服务端任务队列。见 `core/services/system/system_maintenance_service.py:81`、`123`，`core/services/system/system_config_service.py:94`。
6. **业务结果和留痕结果分开**：自动任务返回 `oplog_persisted/job_state_persisted`，文件已成功时记日志失败不应反称文件操作失败；但 UI 必须提示留痕不完整。恢复成功使用新连接写操作日志，失败流程主要进文件日志，未保证每次失败都在统一恢复台账中。见 `core/services/system/maintenance/backup_task.py:21`、`75`；`web/routes/system_backup.py:41`。`OperationLogger.info()` 可返回 False，不能只因调用过就写“已审计”。
7. **日志读取**：区分文件不存在、没有匹配项、读取失败、只读尾部、单条长日志被截断。文件日志可解析 head/body/level；不能按字符串里的“成功”强推业务 status。正式样板综合日志需定义运行文件记录与 OperationLogs 的来源、稳定行键、时间区间、排序/分页边界，现有两个 HTML 页不能直接拼成全库无损日志。
8. **导出**：正式诊断包读取失败有 `operation_logs_READ_FAILED.txt` 等明确说明，构包失败要显示错误；样板当前诊断 JSON只检测页面依赖，不能替代正式 ZIP，二者应保留不同名称/范围。样板 CSV 全筛选日志导出目前没有等价服务器入口，可复用读取后生成，但要标清 200/500 条窗口及是否截断。见 `web/routes/system_runtime_logs.py:142`，`core/services/system/runtime_log_reader.py:27`、`183`、`219`。

### 11.3 配置保存缺口

- 样板八个自动维护字段与 `SystemConfigService` 基本同构，可复用 `update_backup_settings/update_logs_settings`。但当前是两个 POST、两个事务，不能一次点击两个请求后显示“八项全部原子保存”；应分组明确结果，或另建统一服务事务合同。
- 配置快照 `dirty_fields/dirty_reasons/dirty_reason_items` 必须在真实页显示；不能拿被读侧归一后的数值称数据库原值合法。未加载、加载失败、旧值已临时归一、草稿校验通过、正式保存成功应不同状态。
- 原型校验草稿是只读，可以保留本地即时校验，但正式保存必须服务重验；若要保存前做真实后端预检，目前没有独立 SystemConfig validate HTTP。
- 主题走工作台已有机制，每页条数/紧凑行距只是页面会话；不写入 `SystemConfig`，更不能误调用 `/scheduler/config`。全局 shell/部署不在本材料范围。
- 保存设置现有路由主要 flash，`SystemConfigService` 没有在该写流程内提供完整 before/after 采纳审计。若目标要求每次配置变更都可追溯，要补相关结果，不能由自动任务的日志反推是谁改了参数。

## 12. 旧页有、当前样板没有：暂不移植清单

本表指具体旧 UI 选项暂不进入新 Screen，**不是删服务、删数据或绕过隐藏字段校验**。因样板现有能力所必需的真实关系读取仍应保留。基础资料旧 React 样板未被当前路由采用，不据其扩大范围。

| 旧页具体选项 | 旧入口/字段 | 证据与暂缓边界 |
| --- | --- | --- |
| 零件备注；基础信息单独保存路线文字与“按路线重新生成”的旧分区 | `/process/parts/<part_no>/update` 的 `remark`；旧独立表单 | `templates/process/detail.html:23`、`46`。新增 Screen 内保留所需路线编辑，不整套搬旧五区布局 |
| 零件创建/重解析/路线导入的显式严格/宽松切换 | `strict_mode` | `templates/process/list.html:44`、`templates/process/detail.html:54`、`templates/process/excel_import_routes.html:11`。当前原生三步流没有同控件；不能默默采用宽松默认并隐藏警告，必须另定内部固定策略 |
| 每个具体连续外协组的 separate/merged、整组总天数、逐工序天数、严格开关及删除首尾组 | `POST /process/parts/<part_no>/groups/<group_id>/mode`：`merge_mode,total_days,ext_days_<seq>,strict_mode`；`POST .../delete` | `templates/process/detail.html:145`、`167`、`209`。样板“外协工种默认策略”不是这一组级编辑器；已有组仍影响批次，读取/限制不能删 |
| 工种详情直接改全局自制/外协 category | `POST /process/op-types/<op_type_id>/update` 的 `category` | `templates/process/op_type_detail.html:27`。样板逐工序确认/待建转分类不是全局修改 |
| 设备类别、备注、显式班组过滤/班组 ID、批量可用/维修/停用、单条停用选项 | `category,remark,team_id`；`POST /equipment/bulk/status` 的 `machine_ids,status` | `templates/equipment/list.html:48`、`86`、`184`，`templates/equipment/detail.html:36`。当前样板设备组概念待厘清，不顺带移植整个班组管理 |
| 人员/设备双向操作关系的添加/移除、技能等级、主操勾选及双方 Excel 向导 | `/personnel/<id>/link/{add,update,remove}`，`machine_id,skill_level,is_primary`；设备侧对称；双方 `/excel/links` | `templates/personnel/detail.html:59`、`103`、`146`；`templates/equipment/detail.html:68`、`134`。样板工种技能多选不等价，旧关系数据继续保留供资源合法性判断 |
| 人员备注、班组归属/班组过滤、批量在岗/停用、独立停用与休假旧标签 | `team_id,remark`，`POST /personnel/bulk/status` | `templates/personnel/list.html:48`、`69`、`162`；`templates/personnel/detail.html:39`。样板请假语义冲突仍是待解决项，不借此丢弃旧 inactive |
| 班组独立增删改、人数/设备数统计、启停/备注 | `GET /personnel/teams`；`POST /personnel/teams/create`、`POST /personnel/teams/<team_id>/update`、`POST /personnel/teams/<team_id>/delete` | `templates/personnel/teams.html:12`、`54`；`web/routes/personnel_teams.py:18` |
| 设备停机台账：开始/结束、原因代码/说明、取消；按单设备/类别/全部设备批量停机 | `/equipment/<machine_id>/downtimes/create`、`.../<int:downtime_id>/cancel`；`GET /equipment/downtimes/batch`、`POST /equipment/downtimes/batch/create` | `templates/equipment/detail.html:155`、`205`；`templates/equipment/downtime_batch.html:16`。值班台读取停机冲突不代表已包含停机维护表单 |
| 个人日历完整页面、个人 Excel 导入导出 | `/personnel/<operator_id>/calendar`、`POST .../calendar/upsert`；`/personnel/excel/operator_calendar` | `templates/personnel/calendar.html:30`、`113`。不能把样板单选“夜班”当个人日期覆盖已实现 |
| 全局日历班次开始/结束显式输入、Excel 导入/导出向导 | `shift_start,shift_end`；`/scheduler/excel/calendar` | `templates/scheduler/calendar.html`，`web/routes/domains/scheduler/scheduler_calendar_pages.py:47`。当前样板范围批量维护应兑现，但无需自动追加旧 Excel 页面；保存不展示的字段不得破坏跨夜数据 |
| 物料独立单位和备注编辑；批次物料需求完整增删改、到料留空即齐套 | `unit,remark`；`/material/batches` 和 requirements 三写端点 | `templates/material/materials.html`、`templates/material/batch_materials.html`；`web/routes/material.py:43`、`145`。保留存量单位并拆库存读投影，不顺带增加旧需求编辑区 |
| 供应商“不绑定工种”、备注与旧单工种选择器 | `op_type_id` 可空、`remark` | `templates/process/supplier_detail.html:27`、`48`。样板多选也不能借机清掉存量关系；是否支持新多工种另立合同 |
| 主数据通用向导的只新增/清空本类后重导；工时“只补空工时” | `mode=append/replace`；工时 append 特殊含义 | 旧各 `excel_import_*.html` 与第 4 节路由。当前原生通用导入只声明增量，不默认搬破坏性 replace；**批次样板已含这三种模式，不在暂缓之列** |
| 批次手工新增严格开关；Excel 自动生成工序/严格开关；详情“最新方案排程去向”旧区 | `strict_mode,auto_generate_ops`；最新方案去向表 | `templates/scheduler/batches_manage.html:80`、`templates/scheduler/excel_import_batches.html`、`templates/scheduler/batch_detail.html:31`。模板刷新严格开关样板已有，应保留；新增/导入开关不整套补回，但其固定行为必须说明 |
| 资源派工的班组维度、班组人员/设备双表、跨班组列表、周/月查询和旧任务列表导出 | `scope_type=team,team_axis,team_id`；`GET /scheduler/resource-dispatch/export` | `templates/scheduler/resource_dispatch.html:71`、`111`、`339`、`398`。只评估现场读取必要上下文，不迁整页资源派工 |
| 现场旧填写中的报废数量、暂停起止/时长/原因、异常时点/严重程度/原因/反馈人 | actual 表单及旧任务反馈/暂停明细模板 | `static/js/resource_execution_actual.js`，`core/services/scheduler/resource_dispatch_actual_records.py:16`。当前逐次报工样板没有这些输入；旧事实仍要可读且不能从报工空档臆造。独立 start/pause 等低层路由存在不代表旧页都显示独立按钮 |
| 旧复盘暂停时长、异常原因/严重程度/预计影响/受影响资源/处理状态/建议重排诸列，旧 XLSX 对照报表 | `GET /reports/execution-review` 旧字段投影及 export | `core/services/report/execution_review.py:319`；`templates/reports/execution_review.html:86`。样板报表五专题和 CSV 保持，旧专属分析列不整套搬入 |
| 超期批次报表、日历利用率报表、停机影响报表及各 XLSX | `/reports/overdue`、`/reports/utilization`、`/reports/downtime` | `templates/reports/index.html:51` 及对应模板。报表样板只列后台能力说明，未形成相应可用专题；值班台必要风险数据复用不等于迁移旧专题 |
| 手工清理过期备份、批量删除备份 | `POST /system/backup/cleanup`、`POST /system/backup/delete-batch` | `templates/system/backup.html:46`、`51`。样板单个“删除备份”仍需接；不要自动追加旧批删/一键清理 |
| 操作日志单条/批量删除、模块/动作/最近 N 条独立高级过滤 | `POST /system/logs/delete`、`POST /system/logs/delete-batch`；`module,action,limit` | `templates/system/logs.html:75`、`120`、`229`。样板已有统一来源/日期/类型/状态/文本筛选应兑现，但不因此新增删除证据功能；运行文件日志始终只读 |
| 插件状态/详情及启停 | `POST /system/plugins/toggle`，`plugin_id,enabled` | `templates/system/backup.html:196`、`273`。样板配置只有自动维护和偏好，无插件页 |
| 系统排产历史独立详情页 | `GET /system/history`，`version,limit,page,per_page` | `templates/system/history.html:23`、`57`、`204`。仅列旧入口；历史计划身份读取仍需保留，排产方案细节归另一代理 |
| 排产配置/预设/恢复默认的整套旧页面 | `/scheduler/config` 及 preset/default 操作 | 不属于本材料系统配置范围；样板自动维护配置不得代替或覆盖 ScheduleConfig，细节交排产代理 |

## 13. 复用顺序与验收条件

### 13.1 可供后续路线图直接拆分的边界

| 包 | 先决条件 | 交付边界 |
| --- | --- | --- |
| A 基础读取/标准 CRUD 适配 | 核定现有 ID、枚举、原型可达入口及不展示字段保留规则 | 基础页原样式，真实列表/新建/编辑/删除反馈；不包含技能、多工种、归属确认等假映射 |
| B 业务合同缺口 | 每工序归属与未填工时、人员技能/班次、供应商多工种、设备组、低库存口径确认 | 新增必要模型/接口与审计；不能由前端显示字段冒充后端关系 |
| C 批次与文件 | 模板事实统一、单批编辑/批量预览合同、token 工序保存 | 新增/编辑/复制/同步/删除、范围准确导出和真实预检确认；现存事件保护不弱化 |
| D 逐次实际事实 | 工序/分件目标量、报工唯一 ID、修订/幂等、实际资源与有效工时合同 | 分次新增/补齐/更正/自动完工/导入导出；不改排产算法，输出消费用事实投影 |
| E 实际甘特/复盘/报表 | D；正式计划身份/剩余安排由对应后端负责人提供 | 共用数值事实及同 cohort，所有筛选/下钻/CSV一致；图表不造实际和剩余时段 |
| F 校准与值班台 | D；采样/定额锁定/处置身份/外协回厂合同 | 校准建议采纳、风险处置闭环与来源历史；普通工时保存/OperationLogs 不冒充完整链路 |
| G 主数据总览/系统管理 | A/B 真实读投影；已有维护服务结构化结果 | 八域健康/关系、真实备份/日志/配置；主机危险动作仍走完整保护与可查失败 |

这些是评估依赖，不是授权实施或工期承诺。旧选项清单不能当必须补回清单。

### 13.2 样式一致与真实合同的联合验收

- 以当前实际 Screen 为视觉基线，保留 `plana`、`batch-workbench`、`r-*`、`fg-*`、`er-*`、`rw-*`、`md-*`、`sm-*` 页面作用域及 `APSWorkbenchUI` 控件/表格/指标/导入导出按钮；不以跳去旧页、嵌 iframe、整块旧模板作为“样式一致的全部接回”。样式入口清单见 `index.html:18` 至 `36`，公共控件 `workbench-ui.js`。
- 后续必须在真实类型数据的空态、加载失败、长中文/长路径、大量行、部分失败、只读版本、过期 token、深浅色及窄窗口下做截图/交互验收；原型 DOM/CSS 测试只能证明样板状态，不能代替正式响应和持久化验证。本轮未做视觉验收。
- 所有新增/更正/采纳/配置写操作：成功响应后重新查询，重开应用仍一致；取消/失败主记录不变；未知异常留下足够定位信息；审计失败与主操作成功分开报告。
- 导入：错误 Excel 不改主表；预检后引用/内容/模式变化拒绝确认；重复导入不重复数量；部分成功业务给出确切成败行；文件导出核对行数、所有分页、字段和来源，不只核对下载按钮点击。
- 数值/时间：0 与未知、批次与工序与逐次、分件目标、跨夜、计划完工日边界、10 分钟边界、实际资源变更、多版本事件隔离，以及校准异常样本有定点测试。
- 维护：临时库/临时目录才可演练备份恢复；至少覆盖目标损坏、保护副本失败、busy、恢复后校验失败、回滚成功/失败、磁盘/权限失败、留痕失败、清理保底、文件日志读取失败。严禁拿生产库做 UI 验收。

### 13.3 本轮验证与证据限制

- 协调方在本轮追加消息中提供：已用 Chromium 109 检查 15 个入口、60 个主题/尺寸状态，无脚本报错、无外网请求，关键工作流 247 check 通过。本评估接受这项原型验证输入，不重复扩展兼容性研究；未由本评估独立复跑，也未据此认定真实后端持久化已接入、Win7 真机整包已经验收。后端差额仍以本材料的正式源码证据为准。
- 已读 `AGENTS.md`、`.codestable/attention.md`、`.codestable/reference/system-overview.md`、项目版 `cs-explore`；已核对当前脏工作区、实际入口、路由 method/path、字段获取、服务/仓库/旧模板。
- 已使用 `PYTHONDONTWRITEBYTECODE=1 python3 -m tools.symbol_locator` 定位 `reparse_and_save`、`create_batch_from_template`、`record_actual_situation`、`execution_review`、`_build_work_calendar`、`run_backup_restore`，并查 `record_actual_situation` 调用方和 `run_backup_restore` 下游。使用现有 `2026-09-08 16:23` 快照，执行前检查 `is_stale=False`，未重建索引。工具明确提示 ambiguous 边、不含 tests，已按当前源码逐调用核对，未冒充全量调用链证明。
- 本轮只写本文件。没有启动 Flask/产品服务，没有请求真实接口、连接真实 SQLite、触发导入/备份/恢复/清理，也没有运行会生成其他产物的全量质量门禁。
- 文档静态校核：用 AST 解析 107 个路由源码文件、提取本范围蓝图前缀下 199 个 method/path 声明形状，核对文内明确列出的地址；另核对证据文件存在、引用行号范围、非空行及文档空白格式。这些检查不导入产品模块、不注册应用、不连接数据库，不等于接口实测。
- 相关测试仅作为后续定点回归入口：`tests/excel_data_io/test_excel_preview_confirm_baseline_guard.py`、`tests/excel_data_io/test_batch_excel_import_strict_mode_hardfail_atomic.py`、`tests/operation_execution/test_operation_execution_scope_read_contract.py`、`tests/operation_execution/test_execution_review_identity_guard.py`、`tests/migration_db/test_restore_integrity_check_contract.py`、`tests/calendar_maintenance/test_maintenance_telemetry_isolation.py`。**本轮未运行这些测试，未获得真实数据库行为或 clean-worktree proof。**
- “未找到接口/字段”指在本轮当前正式 `web/routes + core/services + data + models` 检索及相关调用中没有证据；不把原型 JS、未来文档或未调用的功能说明算生产实现。不检查实际用户数据量、备份是否可恢复或现有生产数据是否完整。
