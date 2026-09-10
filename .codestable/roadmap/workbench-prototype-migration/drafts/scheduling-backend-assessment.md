# Workbench 样板迁移：排产后端能力评估

- 日期：2026-09-09，按本机 Asia/Shanghai 时间核验。
- 状态：评估草稿，供主方案引用；不构成运行时代码实施授权。
- 现场：`/Users/lurenxing/GitHub/----` 当前脏工作区，不以 HEAD 或旧文档替代现场源码。
- 范围：执行排产、候选对比、方案试调、计划甘特、交付风险、排产分析及对应旧页。仅追到这些能力所需的服务、模型和查询；不评估全站 shell、启动、打包、基础数据管理、报工或系统维护。
- 本轮唯一写入：本文件。未启动真实数据 app，未连接生产数据库，未修改运行时代码、原型、索引或既有修改。

## 1. 结论先行

**不能把当前样板理解为“已有后端能力换皮后就能完全一致运行”。** 排产引擎、正式版本持久化、代表候选保存、计划查询、延期报表、调整草稿与正式采用均有真实实现；但当前 HTTP 合同与样板交互之间存在实质缺口。

| 样板能力 | 真实后端结论 | 接入等级 |
| --- | --- | --- |
| 排产前检查、开始排产 | 有同步排产入口；没有样板就绪统计的完整只读接口；正式运行直接生成正式版本 | 服务可复用，请求和结果需适配；若要求先生成待采用候选，需要新增生命周期 |
| 候选对比、选择、采用 | 同一次运行可保存三个角色的代表结果；不是任意数量独立可采用方案；没有手动采用任意引擎候选的入口 | 对比读取可复用；任意候选采用缺失 |
| 试调设备、开工、冲突、保存、采用 | 有草稿、校验、模拟方案、正式采用服务；现有公开接口不能串成完整前端闭环 | 有服务基础，但身份、预览、事务与校验合同需补齐 |
| 设备 / 人员 / 批次计划甘特 | 有 JSON 数据接口，设备和人员两种服务视图；批次分组可以按返回的批次字段重组 | 只读可适配；固定日班、基线对照、编辑身份不能照搬 |
| 交付风险 | 有超期分桶和保守延期解释；不是样板“本方案全部批次健康表” | 超期服务可复用；完整范围、未排完识别、跨方案差值需补 |
| 排产分析 | 旧页有版本指标、尝试过程、趋势、诊断；当前样板 `AnalysisScreen` 实际是方案对比 | 有现成服务和 Web viewmodel，没有对应公开 JSON；未展示内容列入延期清单 |
| 异步运行 / 轮询 | 本范围未找到任务提交、状态查询、取消或进度事件接口；现有运行是同步持锁调用 | 缺失，不可用假进度冒充 |

最先需要主方案明确的阻塞：正式运行是否仍自动采用、是否允许手动采用引擎候选、样板“已完成工序可重排”如何处理、如何补齐试调的公开身份和校验。不能通过偷偷改 `plan_role`、忽略开关、先改全局配置再改回来或解析 HTML 冒充 JSON 来解决。

## 2. 取证与样板边界

已读根 `AGENTS.md`、`.codestable/attention.md`、`.codestable/reference/system-overview.md` 和项目版 `cs-explore`。本轮按“定向只读评估，授权保存一个指定草稿”执行，不扩建流程材料。

当前入口以 `前端设计/ui_kits/workbench/app.jsx:88` 的 `run / analysis / gantt / delay` 分派，以及 `前端设计/ui_kits/workbench/AppShell.jsx:31` 指向的 `trial-sample.html` 为准，未把各个备选设计 HTML 当现行样板。

| 当前样板来源 | 当前实际行为 |
| --- | --- |
| `前端设计/ui_kits/workbench/GanttScreen.jsx:1` | `RUN_SETTINGS` 存内存；计划起止日期、批次选择、`readyCheck / autoFill / lockStarted`；按钮只设置 `ran=true`，没有发排产请求 |
| `前端设计/ui_kits/workbench/preflight-model.js:7` | 对批次样例就地计算就绪、缺项、跳过；齐套开关会跳过未齐套批次，不进行真实日历产能排程 |
| `前端设计/ui_kits/workbench/PlanShared.jsx:2`、`前端设计/ui_kits/workbench/plan-workbench.js:7` | 方案共享 `localStorage['aps_trial_sample_v1']`；初始正式版本固定为 15；版本加一和“已采用”由本地对象比较决定 |
| `前端设计/ui_kits/workbench/AnalysisScreen.jsx:1` | 晚交批次、总拖期、调整工序、换设备、换型次数、候选选择、采用、导出；无后端请求 |
| `前端设计/ui_kits/workbench/GanttBoard.jsx:1`、`前端设计/ui_kits/workbench/trial-sample-views.js:66` | 设备 / 人员 / 批次分组、初始基线、仅变更、搜索、展开、详情和工艺顺序；时间轴固定两日日班 |
| `前端设计/ui_kits/workbench/DelayScreen.jsx:1` | 列出样例所有批次，并用最后工序完工判断交付；没有等待、停机、缺料根因事实 |
| `前端设计/ui_kits/workbench/trial-sample-views.js:105`、`前端设计/ui_kits/workbench/trial-sample.js:182` | 只编辑设备和开工，固定时长、不联动移动前后序；冲突草稿仍可本地保存，但不能采用；有放弃试调、重置样板、采用记录、CSV |

样板排产检查使用 5 月批次库，方案对比 / 试调用 9 月四批八工序样例，两者明确不是一批数据。真实接入必须由本次排产结果提供后续页面身份，不能保留两套独立的示例来源。参见 `前端设计/ui_kits/workbench/GanttScreen.jsx:15`、`前端设计/ui_kits/workbench/PlanShared.jsx:20`。

## 3. 真实路由清单

以下均为当前源码真实 route，不是建议新建 API。前缀 `/scheduler` 和 `/reports` 来自 `web/bootstrap/factory.py:253` 附近的蓝图注册；本轮仅核实前缀，不展开启动架构。`web/routes/domains/scheduler/scheduler_route_registrar.py:5` 注册排产子模块。

### 3.1 排产、分析与计划读取

| Method / Path | Request 要点 | Response / 行为 | 来源 |
| --- | --- | --- | --- |
| `GET /scheduler/` | `status / only_ready / page / per_page` | HTML 排产调度页，批次表、全局常用配置、运行表单；不是 `/scheduler/batches` 管理页 | `web/routes/domains/scheduler/scheduler_batches.py:67`；`templates/scheduler/batches.html:1` |
| `POST /scheduler/run` | 表单重复字段 `batch_ids`；可选 `start_dt / end_date / run_time_budget_seconds`；`enforce_ready / strict_mode` | 同步调用 `ScheduleService.run_schedule`。成功或 partial 后 `302` 到该版甘特；其他结果及 `AppError` flash 后重定向排产页。不是 JSON，HTTP 成功重定向不等于排产完整成功 | `web/routes/domains/scheduler/scheduler_run.py:38` |
| `POST /scheduler/simulate` | 与 run 同组表单参数，服务另传 `simulate=True` | 当前正常服务返回无新版本，flash 后 `302` 回排产页；不是持久候选 / 甘特草稿 | `web/routes/domains/scheduler/scheduler_week_plan.py:433`；`core/services/scheduler/schedule_service.py:348` |
| `GET /scheduler/gantt` | `version / plan_role / plan_context_token`，也兼容 `scenario_id`；`view / week_start / offset / start_date / end_date / gantt_zoom`；`gantt_batch / gantt_resource` 为页面筛选态 | HTML。解析版本、方案、范围及公开预览 token；显式不存在版本报错，不把它改成 latest | `web/routes/domains/scheduler/scheduler_gantt.py:158` |
| `GET /scheduler/gantt/data` | `view=machine\|operator`；上述版本 / 预览 / 日期参数；`include_history` 布尔 | JSON `{success:true,data:{...}}`，合同版本 3；任务、日历、资源日负荷、关键链、方案身份公开字段、空态和降级信息。不会消费 `gantt_batch / gantt_resource` 预过滤 | `web/routes/domains/scheduler/scheduler_gantt.py:315`；`core/services/scheduler/gantt_service.py:53` |
| `GET /scheduler/analysis` | `version` 决定历史指标主体；`plan_role / plan_context_token\|scenario_id / date_from\|start_date / date_to\|end_date / batch_id / resource_type / resource_id / query_date / period_preset` 等用于导航和候选链接上下文 | HTML `selected_summary / selected_metrics / candidate_comparison_display / diagnostic_sections / attempts / trace_chart / trend_rows`。携带 scenario 参数不会将历史指标主体重算成模拟方案指标 | `web/routes/domains/scheduler/scheduler_analysis.py:71`；`web/viewmodels/scheduler_analysis_vm.py:102` |
| `GET /scheduler/week-plan` | `version / plan_role / plan_context_token\|scenario_id / week_start / offset / batch_id / resource_type / resource_id` | HTML 周计划预览；服务有完整行，页面预览与导出不可混当全量 | `web/routes/domains/scheduler/scheduler_week_plan.py:258` |
| `GET /scheduler/week-plan/export` | 同周计划查询字段 | XLSX，错误可 flash 后重定向；生成并记录导出操作，不改变排程 | `web/routes/domains/scheduler/scheduler_week_plan.py:370` |
| `GET /scheduler/week-plan/print` | `week_start / version / plan_role / plan_context_token\|scenario_id / batch_id / resource_type / resource_id`；`group_by=machine\|operator`；可选 `day` 必须在本周 | HTML 打印页，全量行重新分组。历史正式 / 非正式方案有“不得下发执行”警示；该入口不是 JSON 和候选采用接口 | `web/routes/domains/scheduler/scheduler_week_plan_print.py:36`、`web/routes/domains/scheduler/scheduler_week_plan_print.py:106` |

### 3.2 草稿与模拟方案接口

以下全部 `POST`，请求体必须是 JSON 对象。正常响应都是 `{success:true,data:...}`；校验不通过可以仍返回 `success:true`，须检查 `data.status / can_apply`。`AppError` 使用统一 JSON 错误，普通校验通常 HTTP 400 / code `1001`，执行冲突通常 HTTP 409 / code `6003`，未预期异常由 route 返回 500。`error.details.field` 可能被改为中文标签，内部 reason / ID 不保证公开，不能按中文消息反解析状态。来源：`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:167`、`web/error_boundary.py:256`、`core/errors.py:155`。

| Method / Path | Request 字段 | 实际公开 data | 服务与边界 |
| --- | --- | --- | --- |
| `POST /scheduler/gantt/adjustments/create-draft` | `base_version` 正整数；`base_plan_role` 必填；可选 `reason / expires_at` | `draft_id / status / change_count / message` | `GanttAdjustmentDraftService.create_draft`。服务端操作者；基础历史、角色、真实明细必须存在；仅写草稿 |
| `POST /scheduler/gantt/adjustments/record-time-change` | `draft_id / op_id`；可选 `schedule_id / change_type`，默认 `move_time`，另支持 `resize_time`；`from_start / from_end / to_start / to_end` | `draft_id / change_type / validation_status / message` | 仅向 editing 草稿追加变更；记录成功不表示完成业务校验，`to_end` 不会自动随 `to_start` 平移 |
| `POST /scheduler/gantt/adjustments/record-resource-change` | `draft_id / op_id`；可选 `schedule_id / from_machine_id / to_machine_id / from_operator_id / to_operator_id` | 同上 | 设备与人员分别记录；换设备不会自动选择对应人员。与时间变更是两次独立请求 / 写入 |
| `POST /scheduler/gantt/adjustments/discard-draft` | `draft_id`，可选 `reason` | `draft_id / status / change_count / message` | 将存在草稿标为 `discarded`，不删除正式计划；不是“撤销一次编辑”，也不是删除所有历史 |
| `POST /scheduler/gantt/adjustments/validate-simulate` | `draft_id`；可选 `base_version / base_plan_role` 作预期基础校验 | `status=valid\|warning\|blocked / can_apply / message / issue_count / issues[{severity,code,message}]` | 内存投影和校验，不生成新正式版本；不返回调整后 tasks；公开 issues 删掉了 `op_id / related_op_id` |
| `POST /scheduler/gantt/adjustments/save-scenario` | `draft_id`；可选 `scenario_name / base_version / base_plan_role` | **仅 `scenario_name / created_by / message`** | 重新校验；非 blocked 可保存；落场景头、全部投影行、执行快照，草稿转 `saved_scenario`；**不返回 scenario ID、token 或 preview URL** |
| `POST /scheduler/gantt/adjustments/publish-scenario` | `scenario_id / confirm_text='正式采用' / reason`；可选 `base_version / base_plan_role` | `new_version / published_by / reason / view_url / message` | 必须是 active 场景、基础角色 adopted、基础版本仍最新；重新校验并核执行快照，原子发布新正式版本 |

路由逐项来源：`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:14`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:33`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:55`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:76`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:92`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:109`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:134`；公开投影见同文件 `web/routes/domains/scheduler/scheduler_gantt_adjustments.py:174`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:196`、`web/routes/domains/scheduler/scheduler_gantt_adjustments.py:205`。

**现有 Web 闭环断点**：甘特 data 不提供 `op_id / schedule_id`，写接口却需要 `op_id`；save-scenario 不给预览和发布需要的场景引用；没有草稿读取、场景列表、按草稿恢复预览的 route。虽然 repository 有 `list_drafts_by_base` 和 `get_scenario_by_draft`，不能把它们写成已可调用的 HTTP 能力。不得解析业务编号猜数据库 ID，也不得删除现有公开字段裁剪来接通。

### 3.3 风险与全局排产参数

| Method / Path | Request / Response 要点 | 状态边界 / 来源 |
| --- | --- | --- |
| `GET /reports/overdue` | `version / plan_role / plan_context_token\|scenario_id / batch_id / resource_type / resource_id`；HTML 超期分桶、异常数据、延期解释 | 按整版范围判断，不用页面日期参数筛风险；`web/routes/reports.py:24`、`web/routes/reports_page_support.py:218` |
| `GET /reports/overdue/export` | 同方案 / 批次 / 资源参数，返回 XLSX | 无日期过滤；有导出留痕；`web/routes/reports_export_routes.py:28` |
| `GET /reports/utilization`；`GET /reports/utilization/export` | 上述身份 / 资源参数，加 `start_date / end_date / batch_id`；分别 HTML / XLSX | 可用作计划负荷参考，不是样板固定两日日班占用率；`web/routes/reports.py:29`、`web/routes/reports_export_routes.py:56` |
| `GET /scheduler/config` | 无 JSON 读取合同；HTML 全局设置、预设、状态 | `web/routes/domains/scheduler/scheduler_config.py:315` |
| `POST /scheduler/config` | 表单白名单见第 8 节；仅收已提交字段，toggle 用 yes/no 规范化 | `save_page_config` 合并当前快照、严格验证、事务保存全局参数；可影响 active preset 和修复提示；返回 `302`+flash，**不是单次 run override**。`web/routes/domains/scheduler/scheduler_config.py:424`、`web/routes/domains/scheduler/scheduler_config.py:470`；`core/services/scheduler/config/config_page_save_service.py:279` |
| `POST /scheduler/config/preset/apply` | `preset_name`，兼容 `name`；可选 `next` | 应用全局参数；`custom` 只标记手工设置；不是选择某个已算出的排程。`web/routes/domains/scheduler/scheduler_config.py:361` |
| `POST /scheduler/config/preset/save`；`POST /scheduler/config/preset/delete` | `preset_name`，兼容 `name` | 保存当前配置为预设 / 删除自定义预设，不是保存 / 删除排程结果；内置预设受保护。`web/routes/domains/scheduler/scheduler_config.py:385`、`web/routes/domains/scheduler/scheduler_config.py:412` |
| `POST /scheduler/config/default` | 无业务表单字段 | 恢复全局默认配置，不是重置某个试调样板。`web/routes/domains/scheduler/scheduler_config.py:480` |

排产工序原始资料写入另有 `POST /scheduler/ops/update-token/<token>`，表单自制字段为 `machine_id / operator_id / setup_hours / unit_hours`，外协为 `supplier_id / ext_days`；它直接更新 `BatchOperations`，**不能充当试调保存接口**。裸 `POST /scheduler/ops/<int:op_id>/update` 当前只提示入口失效并重定向，并不执行更新。仅为划清试调边界列出，不展开资料管理评估。来源：`web/routes/domains/scheduler/scheduler_ops.py:37`、`web/routes/domains/scheduler/scheduler_ops.py:44`、`web/routes/domains/scheduler/scheduler_ops.py:55`。

## 4. 正式 / 候选 / 草稿身份合同

### 4.1 不能混用的对象

| 对象 | 持久化与身份 | 读取 / 采用约束 |
| --- | --- | --- |
| 配置预设 | `preset_name` 对应全局排产参数 | 与某次排产 version、候选、场景无直接同一性 |
| 正式结果 | `Schedule.version` + `ScheduleHistory.version`；角色 `adopted`；来源 `schedule` | 历史正式和当前正式必须区分；`partial` 不可冒充可执行成功版本 |
| 引擎代表候选 | `ScheduleCandidate` 摘要 + `ScheduleCandidateSelection` 角色关系 + 必要的 `ScheduleCandidateRows` | 合法角色仅 `adopted / baseline_best / critical_best`；只保存非 adopted 代表候选的明细，并非每个尝试都有明细 |
| 调整草稿 | `ScheduleAdjustmentDraft` + 追加式 `ScheduleAdjustmentChange` | 基础 `base_version / base_plan_role`；没有作为新版本的 version；editing 阶段可反复记录和校验 |
| 已保存模拟方案 | `ScheduleAdjustmentScenario` + `ScheduleAdjustmentScenarioRow`，持久化执行快照 | `scenario_id` + 基础版本 / 角色，来源 `adjustment_scenario_rows`；仅 active 可预览；published 后应转新正式 version 阅读 |
| 不落库插单模拟 | `run_schedule(simulate=True)` 的一次结果 | `version=None / result_persisted=false / can_open_result_version=false`，没有可恢复场景身份 |

角色、来源、完整成功状态事实源：`core/models/schedule_plan_role.py:5`。候选明细选择：`core/services/scheduler/run/schedule_candidate_summary.py:99`、`core/services/scheduler/run/schedule_candidate_persistence.py:159`、`core/services/scheduler/run/schedule_candidate_persistence.py:199`。草稿 / 场景状态转换：`core/services/scheduler/gantt_adjustment_draft_service.py:84`、`core/services/scheduler/gantt_adjustment_scenario_service.py:54`、`core/services/scheduler/gantt_adjustment_publish_service.py:71`。

一个候选若同时是 `baseline_best` 和 adopted，代表角色可能从 `schedule` 读同一组排程。**数据相同不等于身份相同**：requested role 仍是对比参考，不能靠样板 `same(tasks)` 将它提权为正式。`baseline_best` 是“本次运行的原算法代表结果”，**不是样板初始正式基线 v15，也不是上一个版本**。

### 4.2 页面必须共同携带的字段

| 字段 | 使用合同 |
| --- | --- |
| `version` | 已生成版本的整数；新建 / 检查中的对象不可预先猜 `latest+1`。以返回的 `new_version` 为准 |
| `requested_plan_role / effective_plan_role` | 保留用户所选和实际展示两者；不能只存一个 selected 名称 |
| `plan_role_status / plan_role_message` | 至少正确处理 `resolved_adopted / resolved_comparison / fallback_to_adopted / scenario_preview`。服务 `resolve_plan` 允许缺合法对比角色时显式退回 adopted；不能隐藏其提示 |
| `is_scenario_preview / scenario_display_name` | 场景预览不是“另一正式版”；候选和草稿不能获得正式页的身份标签 |
| `schedule_result_status` | `success / partial / failed` 等结果状态与请求是否成功分开；可执行完整成功集合当前只有 `success` |
| `detail_saved` | 代表是否存在可查看明细；候选摘要存在不代表甘特可开 |
| `is_current_executable_official_version / is_superseded_by_newer_version` | 服务端判断当前正式和被替代状态；不能用本地 version 或单一 adopted 标签推断 |
| `can_dispatch / can_write_feedback` | 跨页时保留并由后端决定，本评估不实现派工 / 报工；对比请求退回 adopted 仍不能取得写资格 |
| `plan_context_token` | 仅是场景 URL 引用，进程内存、默认 12 小时过期，重启 / 过期可能失效；不是持久场景主键。token 错误不得悄悄展示正式计划 |

内部还有 `source_table / source_row_id / candidate_id / candidate_key / scenario_id`，供服务解析和持久化，不应将它们原样扩散进公开任务数据。当前 `public_gantt_data_payload` 递归剔除这些字段以及 `op_id / schedule_id`。新编辑目标应提供受服务解析的公开引用，而非移除裁剪。

证据：`core/services/scheduler/schedule_plan_query_service.py:98`、`core/services/scheduler/schedule_plan_query_service.py:139`、`core/services/scheduler/schedule_plan_query_service.py:461`；`core/services/scheduler/schedule_plan_identity_builder.py:71`、`core/services/scheduler/schedule_plan_identity_builder.py:159`；`core/models/schedule_plan_role.py:134`；`web/viewmodels/scheduler_gantt_public_payload.py:9`；`web/routes/domains/scheduler/scheduler_plan_context_token.py:21`；`web/public_token_registry.py:32`、`web/public_token_registry.py:96`。

注意 latest 当前来自历史最大版本，不是“向后寻找最近一个 success”。若最新版本是 partial，不能擅自回退旧 success 再称当前正式。`data/repositories/schedule_history_repo.py:46`、`core/services/scheduler/schedule_plan_identity_builder.py:31`、`core/services/scheduler/schedule_plan_identity_builder.py:137`。

## 5. 排产执行：参数、状态和不兼容点

### 5.1 单次运行的真实合同

`ScheduleService.run_schedule(batch_ids, start_dt=None, end_date=None, created_by=None, simulate=False, enforce_ready=None, strict_mode=False, run_time_budget_seconds=None)` 是现有服务入口，见 `core/services/scheduler/schedule_service.py:198`。

| 字段 / 样板项 | 当前真实规则 | 对样板的影响 |
| --- | --- | --- |
| `batch_ids: list[str]` | 非空、清空白和去重、逐个确认存在；选中 completed / cancelled 批次直接拒绝；无可重排工序直接拒绝 | 样板全部待排 / 仅齐套 / 手工选择可以生成这组字段，但必须让后端重新校验 |
| `start_dt` | 支持本地日期 / 日期时间，空值默认次日 08:00；样板仅有日期 | 提交需明确当天开工时间语义，不能丢弃现有 08:00 默认语义或写死所有日班 |
| `end_date` | 不能早于开始日；是排产完成期限，不是甘特裁剪窗口 | 与 GET 甘特 `end_date` 同名但不同用途，不能在跨页时机械共享 |
| `run_time_budget_seconds` | 可选、有限正数；不保存全局配置；当前仅多候选分支消费该单次总预算，普通分支仍用 cfg.time_budget_seconds | 样板未展示，暂不搬入口；不能承诺对所有模式都覆盖，更不是异步任务硬超时或完成百分比 |
| `readyCheck` → `enforce_ready` | 未传用 `cfg.enforce_ready_default`；传 true 时任何选中批次非 yes 会拒绝整个运行 | 样板是“跳过未齐套后继续”。要保留原交互，必须明确得到 included / excluded 批次并在服务端按该范围校验，不能只原样转开关 |
| `ready_date` | 通过齐套 gate 后，算法在 readiness_gate_enabled=true 时以齐套日 00:00 设置批次开工下界；实际落槽再校验资源日历 | 样板就绪检查未计算这条时间下界；不能只检查 yes 后忽略未来齐套日期；关闭 gate 时本路径不初始化这条下界 |
| 样板 `autoFill` | 现有 run 入口无此单次字段，取全局 `auto_assign_enabled` | `POST /run` 附 `autoFill` 或 `auto_assign_enabled` 都不会成为覆盖参数；不能偷偷保存全局配置。关闭自动分配时缺资源记排产错误，不等价于干净跳过一道工序 |
| 样板 `lockStarted`（UI 实际为已完成工序） | completed / skipped 工序固定排除；真实已完成事实也排除重排；processing / paused 事实固定为种子 | 样板“可重排已完成工序”无等价参数；不得把此开关接 `strict_mode` 或冻结窗口。需修改业务合同 / 获得样板行为调整决策 |
| `strict_mode` | 控制配置和算法输入异常是停止还是按既有兼容规则降级并提醒 | 样板没有对应控件；后续需明确固定政策并保留降级输出，不能默认为“无坏数据” |
| `freeze_window_enabled / freeze_window_days` | 全局配置；以上一版本、运行起始到起始加 N 天的排程，按批次工序前缀建立冻结 seed | 不等价于样板每道工序 `locked`，也不是已完成锁定开关；run 没有单次冻结 ID 列表 |
| 工序顺序 | 服务采集实际工序，调度层建立顺序和资源约束；当前请求无手工 seq 重排字段 | 样板按前置关系显示可以保留，编辑时间不能修改 seq 或自动假定后序一起移动 |

参数和初筛证据：`core/services/scheduler/run/schedule_input_collector.py:83`、`core/services/scheduler/run/schedule_input_collector.py:101`、`core/services/scheduler/run/schedule_input_collector.py:125`、`core/services/scheduler/run/schedule_input_collector.py:153`、`core/services/scheduler/run/schedule_input_collector.py:173`、`core/services/scheduler/run/schedule_input_collector.py:208`、`core/services/scheduler/run/schedule_input_collector.py:266`；状态证据：`core/services/scheduler/schedule_service.py:34`、`core/services/scheduler/schedule_service.py:82`；缺资源错误：`core/algorithms/greedy/internal_operation.py:114`。冻结真实流程：`core/services/scheduler/run/freeze_window.py:274`、`core/services/scheduler/run/freeze_window.py:364`、`core/services/scheduler/run/freeze_window.py:433`；真实事实固定与冻结 seed 合并：`core/services/scheduler/run/schedule_input_runtime_support.py:136`。

冻结输出需保留 `freeze_state / freeze_applied / freeze_application_status / freeze_disabled_reason / freeze_degradation_reason / freeze_degradation_codes`，例如 disabled、active、degraded 和 partially_applied 不能都画成“已固定”。全部冻结时本次运行明确失败，不生成“新候选”。

齐套时间下界证据：`core/algorithms/greedy/scheduler.py:379`、`core/algorithms/greedy/scheduler.py:399`。单次预算分支证据：`core/services/scheduler/run/schedule_orchestrator.py:233`、`core/services/scheduler/run/optimizer_config.py:186`。多候选循环只在发起下一个候选前检查总 deadline，已开始候选不会据此被中断，也未把剩余总预算传入候选优化调用；所以总用时可能超过填写值。见 `core/services/scheduler/run/schedule_candidate_runner.py:181`、`core/services/scheduler/run/schedule_candidate_runner.py:324`。

### 5.2 正式运行状态

1. 进程级 `_RUN_SCHEDULE_LOCK.acquire(blocking=False)` 防止并行排产；忙时直接报错，不排队。
2. 采集配置、工序、资源和执行快照，运行优化；`graph_analysis_mode=on` 才启动引擎多候选对比，`off / report` 不等价于生成多方案。
3. 校验实际结果的工序范围、时间、资源及执行状态变化，分配 version；在编排事务内写正式 `Schedule`、批次 / 工序状态、历史和候选记录。自动补资源是否写回工序，另取 `auto_assign_persist`。
4. 正式选择由引擎的 selection policy 自动完成。成功响应不是“候选等待确认”；旧候选页只是已算结果的对照。
5. 服务返回 `is_simulation / version / result_persisted / can_open_result_version / strategy / strategy_params / result_status / summary / overdue_batches / time_cost_ms`。`summary` 含 counts、errors、warnings、降级、指标等，不可只抽 success 和 version。

证据：`core/services/scheduler/schedule_service.py:210`、`core/services/scheduler/schedule_service.py:264`、`core/services/scheduler/schedule_service.py:290`、`core/services/scheduler/schedule_service.py:348`；`core/services/scheduler/run/schedule_orchestrator.py:123`、`core/services/scheduler/run/schedule_orchestrator.py:233`、`core/services/scheduler/run/schedule_orchestrator.py:398`；`core/services/scheduler/run/schedule_persistence.py:33`、`core/services/scheduler/run/schedule_persistence.py:61`、`core/services/scheduler/run/schedule_persistence.py:301`；`core/services/scheduler/run/schedule_candidate_persistence_helpers.py:29`；`core/services/scheduler/run/schedule_summary_contract.py:142`。

`simulate=True` 当前不分配新版本、不持久化正式结果，也不保存场景；虽然计算会经过优化器，返回却没有可恢复的任务明细身份。旧页 `templates/scheduler/_run_panel.html:46` 的“生成新版本”确认文字以及 `web/routes/domains/scheduler/scheduler_week_plan.py:436` 的旧注释与当前真实服务行为不一致，**不得据此规划“调用 simulate 得到候选甘特”**。

### 5.3 异步 / 轮询现状

在当前排产 route、服务入口、优化编排和 `static/js/scheduler_run.js` 中检索了任务提交 / 查询 / 取消、线程池、`job_id / run_id`、poll / progress。未找到本范围可用的异步运行或轮询合同；优化器局部名为 progress 的变量是搜索算法参数，不是服务进度。

- `POST /run`、`POST /simulate`、`validate-simulate`、`save-scenario` 和 `publish-scenario` 都同步返回。
- 前端可以做“正在处理”的不定进度等待，但不能展示伪造阶段 / 百分比；重复 GET 甘特不是运行状态查询。
- 请求断开 / 浏览器超时不能证明后端未写版本。没有 request ID 去查本次结果前，不应自动重提运行或发布。
- 若主方案要求可刷新恢复的后台运行，必须补任务状态和本次结果定位；不是只把 `fetch` 改成轮询。具体最小字段见第 9 节，不在本轮实施。

## 6. 方案试调：可复用边界与缺口

```mermaid
flowchart LR
    A[严格解析已有版本与角色] --> B[editing 草稿]
    B --> C[追加时间或资源变更]
    C --> D[内存投影与校验]
    D -->|blocked| B
    D -->|valid 或 warning| E[保存 active 场景及执行快照]
    E --> F[场景预览]
    E -->|adopted 基础且仍最新| G[重新校验与核对现场快照]
    G --> H[新正式版本及发布日志]
```

### 6.1 已实现的校验

- 创建基础：`base_version` 拒绝 bool / float / 非正数；role 必须在三个合法角色中；编辑用 `resolve_existing_plan`，缺明细拒绝，不走查看端的显式 fallback。
- 记录变更：草稿须 editing、`op_id` 正整数、change_type 合法；变更 append，按记录 ID 顺序投影。单纯保存变更不验证资源可用性、时间合法性或工序归属。
- 校验投影：op 必须在基础明细中，end 必须晚于 start；检查同资源时段冲突、同 `(batch_id,piece_id)` 的 seq 前后序、日历班次 / 优先级、设备停机；交期与齐套是 warning。`warning` 的 `can_apply=true`，可以保存并进入发布检查。
- 保存场景：再次 evaluate，落全部投影行和 `execution_snapshot_revision / execution_snapshot_op_ids / execution_snapshot_op_count`；草稿转 saved_scenario，此后不能继续 append。
- 发布场景：只接基础 role adopted；重新 evaluate saved_scenario 草稿，校验保存行与重算结果一致；`BEGIN IMMEDIATE` 内确认 base_version 仍为历史最新，核执行快照、已开工 / 暂停 / 完成事实和异常；claim 场景、分配版本、写正式 / 历史 / 草稿状态；发布日志失败回滚。

证据：`core/services/scheduler/gantt_adjustment_draft_service.py:27`、`core/services/scheduler/gantt_adjustment_draft_service.py:108`、`core/services/scheduler/gantt_adjustment_draft_service.py:176`；`core/services/scheduler/gantt_adjustment_projection.py:48`、`core/services/scheduler/gantt_adjustment_projection.py:61`、`core/services/scheduler/gantt_adjustment_projection.py:81`；`core/services/scheduler/gantt_adjustment_validation_service.py:75`、`core/services/scheduler/gantt_adjustment_validation_service.py:113`；`core/services/scheduler/gantt_adjustment_scenario_service.py:66`、`core/services/scheduler/gantt_adjustment_scenario_service.py:101`；`core/services/scheduler/gantt_adjustment_publish_service.py:89`、`core/services/scheduler/gantt_adjustment_publish_service.py:107`、`core/services/scheduler/gantt_adjustment_publish_service.py:154`、`core/services/scheduler/gantt_adjustment_publish_service.py:353`。引用均按当前工作区源码定位。

### 6.2 不能宣称已经覆盖的合同

| 不兼容点 | 证据和具体影响 | 需要进入主方案的要求 |
| --- | --- | --- |
| 公开 task ID 不是写入 ID | `core/services/scheduler/gantt_tasks.py:192` 取 op_code / 合成公共 ID；公开 payload 删 op_id；write 要正整数 op_id | 由服务端给编辑引用并解析到所选计划的 op，禁解析 ID 字符串猜主键 |
| 保存不能自动打开场景 | save-scenario 的公开 data 没有 scenario 引用；仓库有按 draft 找场景的方法但无 route | 返回可用 preview URL / 公开场景引用，并提供重新打开途径 |
| 校验不返回预览 tasks | `evaluate_draft` 内有 adjusted_rows，`validate_draft` 仅给状态；route 又删 issue 的工序关联 | 补可展示的完整投影和 `task_ref / related_task_ref`；不让浏览器自己“验过”后声称引擎验过 |
| 警告不等于阻塞 | 样板采用按钮以 `vm.issues.length > 0` 禁用；后端齐套 / 交期 warning 的 can_apply=true | 分开 blocker 与 warning；采用按钮需使用真实能力及阻塞原因，不能把 HTTP success 或 issues 数量当采用判据。见 `前端设计/ui_kits/workbench/PlanShared.jsx:50`、`core/services/scheduler/gantt_adjustment_validation_service.py:34` |
| 换设备与移时间非原子动作 | 两个 record route 分别写；样板一个“保存试调”同时包含 resource 和 start | 增加一个业务动作的原子保存合同，部分请求失败不能提示整体已保存 |
| 移动默认不保时长 | `_apply_change` 只取 to_start / to_end；单传 to_start 保留旧 end | 样板固定时长必须在服务端按完整起止计算 to_end；窗口裁剪时间不可用作输入 |
| 设备与人员不是一一对应 | 样板 `前端设计/ui_kits/workbench/trial-sample-model.js:204` 直接把 person 换成 resource.person；后端两个字段独立 | 必须确认合法设备 / 人员组合；没有唯一人员时不能默选第一个或保留不兼容人员 |
| 锁定 / 工艺适配不等价 | projection 只保留 lock_status，不以其拒绝移动；`_collect_issues` 未调用设备工种、人员技能匹配，也没有 frozen-row 比较；内存探针已确认投影接受 locked 行移动和未知设备字符串 | 在试调与发布的承重服务补相关校验。不能因资源无重叠就画“工艺 / 固定工序检查通过”。本轮未做发布穿透测试，不宣称所有非法资源都能落正式表 |
| `from_*` 不是乐观并发检查 | 变更记录会存 from_*、schedule_id，但投影只用 op_id 和 to_*；同上内存探针 | 补基线内容 / 草稿修订号检查。只匹配 base_version / role 不足以判定页面未过期 |
| 草稿记录数不是调整工序数 | repo 用 `COUNT(ScheduleAdjustmentChange)` 更新 change_count；同一工序改时间又改设备可计两条；投影即使同值也标 is_changed | UI“调整工序”须按明确 baseline 比较不同 task 的实际变化；不能填 change_count |
| 草稿可编辑生命周期不同 | 场景保存即将草稿变 saved_scenario；无回 editing、按场景继续改或读取草稿的公开入口；expires_at 在本路径只存储，没有到期校验 | 若界面仍允许继续试调，必须定义重开 / 分支行为和过期政策，不伪称现有 API 支持 |
| 候选采用不是场景采用 | 候选角色能建草稿、保存预览，但 publish 明确拒绝非 adopted 基础 | 采用 baseline_best / critical_best 必须新增独立核验和采用服务；不能改传 adopted 来绕过身份 |
| 采用确认合同不同 | 样板输入 person 和 reason；后端操作者来自 g / web，另要求 confirm_text='正式采用' | person 不能映射为可信 published_by；须明确确认按钮与现有二次确认合同的产品决策，不能声称字段直接兼容 |
| 发布后指标不是自动完整重算 | `core/services/scheduler/gantt_adjustment_publish_service.py:417` 的手工发布 summary 记录来源 / 变更 / 校验 / 原因 / 快照，没有引擎完整指标块和换型重算 | 对手工方案的 KPI 重新按真实安排评估；缺值显示不可评估，不能继承原版 KPI 或换型预置值 |

以上资源、锁定和前后序问题属于“现有试调校验覆盖不等于样板宣称覆盖”，不是要求迁移旧页所有高级选项。工序先后检查不等于自动重排后续，更不等于允许改工艺顺序。

## 7. 甘特、候选指标和交付风险字段级映射

### 7.1 计划甘特

数据来源 `core/services/scheduler/gantt_tasks.py:227`、`core/services/scheduler/gantt_contract.py:91`、`core/services/scheduler/gantt_service.py:254`。只读画图可基于既有 `GET /scheduler/gantt/data`，不必重写排程服务。

| 样板字段 / 用途 | 当前数据来源 | 必须处理的差异 |
| --- | --- | --- |
| `task.id` | `tasks[].id` | 显示 / 选择标识可用；非数据库 ID，跨方案对照仍要保证同工序同一性 |
| `batch / op` | `meta.batch_id / meta.operation_label / meta.op_type_name / meta.seq` | 不能从 name 切字符串还原批次工序；同批多 piece 分链 |
| `resource / person` | `meta.machine_id / operator_id`，展示用 `machine / operator` | 样板 person 分组映射服务 `view=operator`；外协 / 未分配不能显示为真实设备 |
| `start / end` 画条 | `tasks[].start / end` | 已裁剪到请求窗口；详情 / 差值 / 试调用 `meta.plan_start_time / plan_end_time` |
| `predecessor` | `dependencies` 为 task ID 字符串，`edge_type=process` | 当前只在返回窗口内连线，不能以缺 predecessor 推断整条工艺无前序；全链详情需全范围查询 |
| `locked` | `lock_status='locked'` | 仅展示有基础；该状态不能替代试调服务的禁止修改校验 |
| `part / qty / due` | meta 有 part_no、part_name、due_date；当前 task meta **没有 quantity** | 样板详情的数量需要同一计划上下文补齐批次数据，不可继续写死 4 批 / 8 工序 |
| 批次视图 | `meta.batch_id / piece_id / seq` 前端重组 | 不是请求 `view=batch`，该枚举目前会被拒绝 |
| 时间轴与容量 | `calendar_days[]`；`resource_load[{date,resource_id,resource_label,hours,capacity_hours,ratio}]` | 不可固定 08:00-18:00 或每资源 20 小时；ratio 可以 null；不可把画条跨度直接当真实工时 |
| 初始基线 / 仅变更 | 无现成双方案差值 DTO，可分别解析目标和 baseline 全量明细 | 必须显式保存 baseline 身份；不是 baseline_best 别名，也不能用窗口内缺行当删除 |
| 关键链 | `critical_chain.available / ids / edges / scope / critical_chain_partial` | 与工艺顺序不同；当前样板没有旧页的关键链控制，暂不搬入口 |
| 降级 / 空态 | `degraded / degradation_events / degradation_counters / empty_reason / overdue_markers_*`，以及 `status / has_history / version_time_span / range_source` | no_history、查无任务、坏时间被剔除、关键链不可用不可统一显示零任务 / 无风险 |

显式起止查询受 62 天限制；默认可按版本跨度，不能无条件截为两天。`core/services/scheduler/gantt_plan_query.py:22`。资源日负荷目前按内部工序、请求窗口和日历容量计算，外协不占内部容量；全量任务和负荷条带不得被某个前端搜索悄悄改变统计口径，见 `core/services/scheduler/gantt_resource_load.py:67`、`web/routes/domains/scheduler/scheduler_gantt.py:68`。

### 7.2 候选对比与分析

- 当前 `candidate_comparison` 有 `enabled / planned_candidate_count / completed_candidate_count / failed_candidate_count / skipped_candidate_count / time_budget_reached / run_time_budget_seconds / selection_policy / selection_reason_code / candidates[]`。
- 单候选公开摘要有 `label / kind / status / roles / detail_saved / metrics / health / elapsed_ms`；核心 metrics 有 `failed_ops / overdue_count / total_tardiness_hours / weighted_tardiness_hours / makespan_hours / changeover_count`。失败、跳过、无明细必须保留状态；不能强制填满三个成功候选行。
- 同次运行代表候选对比可用 `build_analysis_read_context` + `build_candidate_comparison_display`；当前没有对应 JSON route，建议包装已有公开投影，不直接公开原始 result_summary。
- 当前样板“调整工序、换设备、相对初始基线提前小时”没有现成候选摘要字段，必须对两个已解析身份的完整任务集做差。缺明细不可填 0。
- 历史趋势比较的是历史版本指标；scenario 导航上下文不改变历史 selected_summary。新界面若显示当前模拟方案指标，必须另算该场景，而非把旧 analysis HTML 的指标换个标题。
- 摘要可能被 size guard 截断，`summary_truncated / summary_count_parse_failed`、指标解析失败、缺历史都要显式保留，不能从残缺 attempts 重算“全量最优”。

来源：`core/services/scheduler/run/schedule_candidate_summary.py:39`、`core/services/scheduler/run/schedule_candidate_summary.py:117`、`core/services/scheduler/run/schedule_candidate_summary.py:141`；`web/routes/domains/scheduler/scheduler_analysis_read.py:49`、`web/routes/domains/scheduler/scheduler_analysis_read.py:320`；`web/viewmodels/scheduler_analysis_vm.py:206`；`templates/scheduler/analysis_parts/_optimization_process.html:1`。

### 7.3 交付风险

`ReportEngine.overdue_batches` 返回 `version` 和方案 metadata、`count / scheduled_count / unscheduled_count / invalid_time_count / invalid_due_count / as_of_time / items / scheduled_items / invalid_time_items / unscheduled_items` 及 `report_degraded` 一组字段。

单行包含 `bucket / bucket_label / is_scheduled / batch_id / part_no / part_name / quantity / due_date / finish_time / as_of_time / delay_hours / delay_days`，异常行可有 `data_issue_message`。`count` 包括异常数据桶，不能直接填样板“预计晚交批数”。完整来源：`core/services/report/report_engine.py:170`、`core/services/common/overdue_calculations.py:87`。

| 样板交付字段 | 可取证能力 | 差异 / 新合同要求 |
| --- | --- | --- |
| 全部方案批次列表 | 甘特计划明细、批次信息、已有超期分桶 | overdue 只返回超期 / 异常，不含所有按期行，不能当完整健康表 |
| 交付截至 | 后端 date 的次日 00:00 排他边界 | 样板 due 是具体 datetime；需服务给 `due_exclusive` 和明确风险枚举；`finish >= due_exclusive` 即超期 |
| 晚交小时 | scheduled 桶已有 delay_hours | 恰好次日 00:00 时也属超期但 delay_hours=0；样板 `lateHours ? 晚交 : 按期` 会错判，内存探针已确认 |
| 最后工序完工 | 全版有效明细可求末工序 | 只有部分工序排上时，MAX(end) 只是部分完工；不可据此标可按期 |
| 评估范围 | 必须绑定目标 plan + 本次批次范围 | 当前 repo 超期查询从全部有交期的 Batches 左联所选 plan，可能包含该版未排到的其他批次；不是原型四批限定范围 |
| 相对初始基线 | 比较两个完整身份的同批完工 | 缺基线、缺行、部分排产时应 unavailable，不能填 0 或将缺行解释为提前 |
| 交付依据与原因 | 延期诊断有 last_operation、confirmed_facts、candidate_clues、confidence、data_gaps、suggested_actions | 可取保守事实，不能把“建议复核线索”改为已证实唯一根因 |

当前运行摘要已经新增 `incomplete_batches={count,items[:50]}`，明细有 `batch_id / reason_code / scheduled_op_count / failed_op_count / due_date / partial_finish_time`，未排完批次不应计为健康 / 临期 / 已完成。**但 ReportEngine 的超期 SQL 仍基于 MAX(valid end)，未消费这份运行完整性桶**，且摘要列表只保留前 50 条；仅拼接摘要样本不足以还原全量健康列表。主方案需将完整性判断纳入新的交付风险投影，不复制样板前端求 max 的简化算法。

证据：`core/services/scheduler/summary/due_risk_items.py:111`、`core/services/scheduler/summary/due_risk_items.py:149`；`data/repositories/schedule_plan_query_repo.py:379`、`data/repositories/schedule_plan_query_repo.py:413`；`core/services/scheduler/schedule_delay_diagnosis_service.py:42`、`core/services/scheduler/schedule_delay_diagnosis_service.py:149`。

还有历史口径限制：计划行保存了时段 / 资源，但详情查询实时联当前 `BatchOperations / Batches / Machines / Operators / Suppliers`，并非当时全部业务元数据快照。因此历史版本风险可能反映当前交期 / 工艺元数据，不能宣称“完全还原当次所有原始输入”。证据：`data/repositories/schedule_detail_query.py:62`、`data/repositories/schedule_plan_query_repo.py:419`。

## 8. 旧页有、当前计划样板未展示：暂不迁移清单

本表依据实际模板和它们消费的现行字段 metadata，不依赖旧使用手册。暂不迁移的是入口 / 展示，不意味着清空相关已保存配置或删除后端能力。样板已有设备、人员、批次分组、搜索、初始基线、仅变更、方案选择和采用确认，不列作“旧页遗漏”。

### 8.1 排产页与高级设置

| 旧页具体选项 / 操作 | 字段 / 值或行为 | 实际来源 |
| --- | --- | --- |
| 常用方案切换、手工设置、管理方案入口 | `preset_name / custom`，切换立即改变全局配置，不是结果候选选择 | `templates/scheduler/batches.html:10`、`templates/scheduler/batches.html:19`、`templates/scheduler/batches.html:32` |
| 运行列表按状态筛选 | 全部 / pending / scheduled / processing / completed / cancelled | `templates/scheduler/batches.html:65` |
| 齐套显示细分 | 全部 / yes / partial / no；样板只有“仅已齐套”快捷选择，不同于完整筛选器 | `templates/scheduler/batches.html:76` |
| 本次开始时分 | `start_dt` 为 datetime-local；样板只有日期 | `templates/scheduler/_run_panel.html:11` |
| 本次计算时限 | `run_time_budget_seconds` | `templates/scheduler/_run_panel.html:21` |
| 参数问题立即停止开关 | `strict_mode`，与齐套开关分开 | `web/viewmodels/scheduler_run_options.py:28`；`templates/scheduler/_run_panel.html:28` |
| 独立“模拟排产（插单模拟）”操作 | `/scheduler/simulate`；旧确认文字已与服务不一致，迁移不能带错语义 | `templates/scheduler/_run_panel.html:46` |
| 预设另存 / 删除 / 恢复默认 | `preset_name`，内置预设不能删除；恢复默认影响全局参数 | `templates/scheduler/config.html:81`、`templates/scheduler/config.html:97`、`templates/scheduler/config.html:303` |
| 排产排序策略 | `sort_strategy=priority_first\|due_date_first\|weighted\|fifo` | `templates/scheduler/config.html:127`；`core/services/scheduler/config/config_field_spec.py:91` |
| 计算模式与目标 | `algo_mode=greedy\|improve`；`objective=min_overdue\|min_tardiness\|min_weighted_tardiness\|min_changeover` | `templates/scheduler/config.html:137`、`templates/scheduler/config.html:147`；`core/models/objective.py:48` |
| 优先级 / 交期权重 | `priority_weight / due_weight` | `templates/scheduler/config.html:157`、`templates/scheduler/config.html:164` |
| 派工方式 / 智能派工策略 | `dispatch_mode=batch_order\|sgs`；`dispatch_rule=slack\|cr\|atc` | `templates/scheduler/config.html:171`、`templates/scheduler/config.html:181`；`core/services/scheduler/config/config_field_spec.py:166`、`core/services/scheduler/config/config_field_spec.py:188` |
| 全局优化时间 / 假期效率 | `time_budget_seconds / holiday_default_efficiency` | `templates/scheduler/config.html:192`、`templates/scheduler/config.html:200` |
| 全局近期冻结开关和天数 | `freeze_window_enabled / freeze_window_days` | `templates/scheduler/_config_switches.html:2` |
| 优先主操 / 高技能 | `prefer_primary_skill` | `templates/scheduler/_config_switches.html:13` |
| 全局齐套默认值 | `enforce_ready_default`；样板当前只展示本次检查 | `templates/scheduler/_config_switches.html:18` |
| 全局缺资源自动分配 | `auto_assign_enabled`；样板本次 autoFill 与此不同作用域 | `templates/scheduler/_config_switches.html:23` |
| 深度优化及时间 | `ortools_enabled / ortools_time_limit_seconds` | `templates/scheduler/_config_switches.html:28` |
| 工序图分析模式 | `graph_analysis_mode=off\|report\|on` | `templates/scheduler/config.html:226`；`core/services/scheduler/config/config_field_spec.py:332` |
| 工序图前序循环停止、调试导出 | `graph_block_on_cycle / graph_debug_export` | `templates/scheduler/_config_switches.html:38`、`templates/scheduler/_config_switches.html:43` |
| 工序图权重 | `graph_critical_weight / graph_impact_weight` | `templates/scheduler/config.html:237`、`templates/scheduler/config.html:244` |
| 候选档数 | `graph_candidate_weight_count=3\|5\|7` | `templates/scheduler/config.html:251`；`core/services/scheduler/config/config_field_spec.py:386` |
| 正式自动选择规则 | `graph_selection_policy=balanced\|score_only` | `templates/scheduler/config.html:262`；`core/services/scheduler/config/config_field_spec.py:387` |
| 综合选择容忍度 | `graph_overdue_tolerance_count=0\|1\|2`；`graph_tardiness_tolerance_ratio=0.05\|0.1\|0.2` | `templates/scheduler/config.html:273`、`templates/scheduler/config.html:284`；`core/services/scheduler/config/config_field_spec.py:388` |

配置枚举与当前模板逐项对应。后端 `ready_weight` 和 `auto_assign_persist` **不计入“旧页可选输入遗漏”**：旧页并未给它们独立输入控件，后者是状态展示 / 隐藏修复字段，见 `core/services/scheduler/config/config_constants.py:110`、`web/viewmodels/scheduler_config_panel.py:189`。其真实运行影响仍必须保留，不能因为不搬控件就重置。

### 8.2 甘特、分析和风险旧页

| 旧页具体选项 / 展示 | 当前处理 | 实际来源 |
| --- | --- | --- |
| 甘特任意起止日期、上周 / 本周 / 下周、独立版本加载 | 样板固定日期和方案列表，未展示相同的周导航 / 日期表单；暂不增加旧控件，但真数据范围不能写死 | `templates/scheduler/gantt.html:88`、`templates/scheduler/gantt.html:108` |
| 甘特粒度 | 月 / 周 / 日 / 12小时 / 6小时 / 小时 / 15分钟 / 5分钟 / 1分钟，以及放粗 / 放细 | `templates/scheduler/gantt.html:170` |
| 甘特配色 | 按批次 / 优先级 / 归属（自制外协）/ 工序状态 | `templates/scheduler/gantt.html:186` |
| 甘特批次 / 资源下拉细筛 | 样板搜索和批次分组不是原筛选器；旧下拉暂不移植 | `templates/scheduler/gantt.html:195`、`templates/scheduler/gantt.html:201` |
| 仅超期 / 仅外协 / 高亮关键工序 | 原型计划甘特没有同组开关 | `templates/scheduler/gantt.html:208` |
| 工序关系线模式 | 只关键 / 全部工艺 / 不显示 | `templates/scheduler/gantt.html:227` |
| 清除聚焦 / 重置查看态 | 与样板“重置样板草稿和历史”不同，后者不可接清全局正式数据 | `templates/scheduler/gantt.html:233`；`前端设计/ui_kits/workbench/trial-sample-views.js:127` |
| 候选失败工序数、总工期及每个候选的多种明细跳转 | 样板表只展示其现有指标和页面流，暂不增加旧列；失败 / 缺明细状态仍不能隐藏 | `templates/scheduler/analysis_parts/_candidate_comparison.html:59` |
| 版本总体指标、冻结 / 配置状态、诊断依据 | 当前样板方案对比未展示旧版完整分析区，暂不搬展示 | `templates/scheduler/analysis.html:27`；`templates/scheduler/analysis_parts/_diagnostic_sections.html:1` |
| 优化过程曲线和尝试方案排名 | 含方案来源、策略、派工、失败工序、目标值、参考条形 | `templates/scheduler/analysis_parts/_optimization_process.html:12`、`templates/scheduler/analysis_parts/_optimization_process.html:30` |
| 历史版本趋势 | 超期、拖期、加权拖期、总工期、内制工期、换型、设备 / 人员平均利用率 | `templates/scheduler/analysis_parts/_trend_charts.html:1` |
| 超期清单 Excel、已排 / 未排 / 时间异常 / 交期异常分桶、截至时间 | 样板交付风险无旧导出和分桶控件；暂不搬原 UI，但异常状态要在新合同中保留 | `templates/reports/overdue.html:36`、`templates/reports/overdue.html:86` |
| 延期解释展开：建议先复核、证据等级、证据缺口、下一步 | 样板当前只展示交付依据与无根因声明，不能新增假根因；完整解释入口延期 | `templates/reports/overdue.html:140` |
| 周计划 XLSX / 打印及设备、人员视图切换 | 计划样板的“导出对比 CSV”并非这些导出，暂不迁移旧入口；另有报表领域时由主方案去重。route 虽支持 day，但本轮未找到单日筛选控件，不把它列作旧页遗漏 | `templates/scheduler/week_plan.html:12`；`templates/scheduler/week_plan_print.html:32` |

特别剔除误判：旧 `gantt.html` 当前明确 `data-gantt-mode="view"`，没有加载草稿编辑脚本；测试也锁住旧页未接调整接口。因此“拖动 / 改资源 / 校验 / 保存场景 / 发布”是**后端能力已存在但旧页未启用**，不能列作“旧页原有选项需保留”。来源：`templates/scheduler/gantt.html:263`、`tests/gantt/test_gantt_adjustment_validate_simulate.py:389`。

## 9. 可直接纳入主方案的最小新增 / 适配合同

本节是未来实现需求，**不是当前已存在 route**。为避免主方案误标已有能力，先给动作 / DTO 合同，不抢占最终新接口命名。保持样板布局不等于继续固定样例的批次数、日期、设备对应人员或本地版本。

| 动作 | 最小字段合同 | 复用点 / 必须补的部分 |
| --- | --- | --- |
| 查询方案工作区 | 入：`version? / requested_plan_role? / scenario_ref? / baseline_ref?`；出：服务端公开 `plan_ref / baseline_ref / plan_identity / available_plans[] / version_time_span / warnings`，每个可选方案带明细可用状态和动作能力 | 复用 PlanQuery + 历史查询；补公开列表 / 可恢复引用。plan_ref 不用标签 / 数组位置；不以短期 token 作持久主键 |
| 获取计划内容 | 入：`plan_ref / start_date / end_date`；出：`tasks[{task_ref,id,batch_id,piece_id,seq,source,machine_id,operator_id,plan_start_time,plan_end_time,display_start,display_end,lock_status,predecessor_refs,editable,edit_block_reason}]`；`batches[{batch_id,part_no,part_name,quantity,due_date,due_exclusive,completion_state}]`；`calendar_days / resource_load / completeness / degradation` | 只读字段尽量复用 gantt DTO；补编辑引用、完整性、数量、范围外前序信息，勿让 raw op_id 出公开 payload |
| 排产前检查 | 入：明确 `batch_ids / start_dt / end_date / enforce_ready / missing_resource_policy / completed_operation_policy`；出：`included_batch_ids / excluded_batches[{id,reason}] / eligible_operations / auto_assign_required / skipped_operations / blockers / warnings / effective_config / input_revision` | 无现成完整 HTTP / service preflight。可重用已有纯校验和采集边界，但不能调用正式 run 伪装只读检查；资源日历可行性未算时标 `not_evaluated` |
| 单次资源与完成规则 | `missing_resource_policy=auto_assign\|exclude`；完成项固定策略需明确；输入变更不能保存全局 config | 引擎目前无这组单次覆盖和排除合同；exclude 仍要尊重前后序，不可任意移除一个前置工序后排其后序。完成工序可重排是未决业务缺口 |
| 执行排产 | 入：经确认范围、参数、`input_revision / request_id`；出：真实 `result_status / result_persisted / version / can_open_result_version / summary / plan_ref / candidate_options` | 复用 run 核心。必须先确定“运行自动采用”还是“候选等待采用”；后者需要新持久生命周期，不能沿现有正式 run 偷换语义 |
| 异步提交与状态（如主方案要求） | 提交回 `job_id / status_url / state`；查询 `state=queued\|running\|succeeded\|partial\|failed\|interrupted`、`result_persisted / result_version / error / started_at / finished_at`；无真实进度则 `progress=null`；终态稳定、request_id 可查重 | 当前全部缺失。任务运行结果必须绑定本次 request_id，重启恢复要能区分“未落库”与“结果待确认”；是否支持取消单独定契约，当前不可承诺 |
| 保存一次试调 | 入：`draft_ref / expected_revision / task_ref / target_machine_id / target_operator_id / target_start`；服务按固定时长计算 end；出：新 revision、投影任务、`validation{status,can_apply,issues[{severity,code,message,task_ref,related_task_ref}]}` 和差值 | 复用投影 / 草稿记录；补单动作原子性、目标组合校验、固定工序 / 工艺校验、并发保护。业务冲突可保存草稿但不得发布 |
| 保存模拟并打开 | 入：`draft_ref / expected_revision / scenario_name`；出：`scenario_ref / preview_url / plan_identity / validation / can_publish / publish_block_reason` | 复用 SaveScenario；补公开引用。明确保存后继续编辑是新分支还是新草稿，不直接写 saved_scenario 草稿 |
| 正式采用 | 入：明确来源 `scenario_ref` 或新定义的 candidate_ref、基础身份和 revision、显式确认、`reason`；操作者服务端；出：`new_version / plan_ref / view_url / audit_record` | 现有发布只支持 adopted 基础场景；引擎候选采用是新增承重能力。必须保留最新版本 / 执行快照 / 重复发布 / 日志原子性限制 |
| 风险投影 | 入：`plan_ref / baseline_ref? / assessment_batch_ids / as_of_time`；出：每批 `completion_state / due_exclusive / finish_time? / risk=on_time\|overdue\|incomplete\|unscheduled\|invalid_data\|unavailable / delay_hours? / baseline_delta_hours? / last_task_ref? / evidence / data_gaps`，并返回统一统计范围 | 复用合法超期计算和保守诊断；补全批健康行、未排完和基线差值。数值 null 与 0 分开，风险分类不以 delay_hours truthy 判断 |
| 对比 / 导出 | 比较绑定两边 plan_ref 和相同范围；`changed_operation_count / moved_operation_count / total_tardiness_hours / changeover_count? / metric_availability`；导出带身份、范围、不可评估原因 | 已有候选 metrics 可复用。样板 CSV 不等于旧周计划 XLSX，需单独确定表格字段；不得从残缺摘要反推全量计划 |

### 建议落地顺序与前置决策

1. 先固定公开计划身份、完整读取、基线定义、指标不可用状态。排产 / 对比 / 甘特 / 风险共享同一身份，不先接生产写按钮。
2. 核定样板三个开关与正式运行生命周期。`autoFill` 单次作用域、未齐套自动排除、完成工序可重排均不能直接等价映射；未决前不得标“完全一致接入完成”。
3. 补试调公开引用、草稿恢复、原子记录、投影预览与服务校验；再开放场景保存 / adopted 基础正式采用。引擎候选采用单独实现，不能混用旧 route。
4. 确有后台运行要求时补提交 / 查询 / 结果绑定，再接真实轮询；无此授权只可保留同步不定进度，不增加伪 API。
5. 旧页源码备份、入口切换和下线由主方案统一安排。本评估不执行备份 / 下线，也不因旧页暂不迁移选项而删除其配置、历史表或服务。

## 10. 验收用例与本轮验证边界

### 10.1 主方案应安排的定点验收

- 身份：三个角色、角色指同一数据、缺候选明细显式回退、损坏候选关系拒绝、历史正式、partial、无历史、场景过期 / 发布后旧引用；跨对比 / 甘特 / 风险不掉身份。
- 运行：空选、重复批次、已完成 / 取消批次、全无可重排、未齐套混选、齐套日期下限、缺设备 / 人员两种政策、严格 / 非严格异常、全部冻结、部分冻结降级；检查阶段不生成正式版本。
- 试调：设备 / 人员重叠、工艺不匹配、固定工序移动、已开工 / 暂停 / 完成保护、跨班 / 停机、前后序、过期基线、并发改同草稿、时间资源联合保存失败；blocked 草稿保留但不可采用。
- 采用：非 adopted 基础场景拒绝；候选采用走独立合同；现场快照改变、异常工序、重复发布、日志失败全部按合同拒绝且不写半个正式版本。
- 甘特：机器 / 人员值转换、批次分组、外协 / 空资源、多 piece 工艺、跨窗任务完整起止、>62 天显式范围、无容量 ratio=null、坏时间与关键链降级，不沿用两日固定日班。
- 风险：次日 00:00 超期零小时、部分排完不能标按期、坏交期 / 坏时间、无计划、非本次批次混入、摘要截断 50 条之外、两边基线范围不齐、手工发布无指标不可沿用旧指标。
- 异步若新增：刷新恢复、超时后查本次结果、同 request_id 重试不重复运行 / 发布、应用重启前后状态、失败不伪装成功；没有真实进度源不产生百分比。

可复用测试证据入口：`tests/gantt/test_gantt_adjustment_validate_simulate.py`、`tests/gantt/test_gantt_draft_save_and_preview.py`、`tests/gantt/test_gantt_scenario_publish.py`、`tests/gantt/test_gantt_adjustment_publish_execution_revision.py`、`tests/web_pages/test_plan_role_adopted_single_source_contract.py`、`tests/schedule/summary/test_schedule_summary_incomplete_batches_risk.py`。这里只核读适用测试与入口，**没有把这些测试写成已在本轮运行通过**。

### 10.2 本轮实际完成的验证

1. `git status --short` 确认大量既有暂存 / 未暂存 / 未跟踪修改，本轮按现场源码读取，未回退任何内容。
2. 使用真实 `tools.symbol_locator` 的 `whereis / callers / callees` 查询了 `run_schedule`、`_run_schedule_impl`、`resolve_plan`、`publish_scenario`、`get_gantt_tasks`、`evaluate_draft`。通过 `python3 -B` 调 CLI，禁用 rebuild 写盘；返回快照为 `2026-09-08 16:23`，查询时未提示过期，未重建索引。静态图中存在 ambiguous 边和未含 tests 的盲区，已逐条用当前 route 调用和服务源码补证，不能把“0 confident caller”解读为未使用。
3. 定义 / 影响面核实：`ScheduleService.run_schedule` 由真实 run / simulate route 调用，经 collector、orchestrator 到持久化；PlanQuery 被甘特 / 风险 / 草稿解析共用；evaluate_draft 被 validate、save、publish 三条链共用；publish 由正式采用 route 调用并进入执行快照保护。
4. 在 `.venv/bin/python -B` 中执行四个纯内存探针，无数据库连接、无 Flask app 实例、无落盘测试文件，均通过断言：齐套 gate 对未齐套批次拒绝；投影本身允许 locked 行移动且不核 from_* / schedule_id / 目标设备存在性；交期次日 00:00 已属超期但小时数为 0；公开甘特裁剪剔除调整需要的内部 ID。
5. 探针只证明具体函数行为，不证明完整发布事务、真实数据可行性、页面视觉等价或全仓质量。未运行真实 app、生产排产、pytest 数据库测试或质量门禁；本轮只授权一个文档写入，未让测试生成数据库 / 缓存等额外文件。本报告不提供 clean-worktree proof。
6. 最终静态核对：文档中的 28 组唯一 Method / Path 均与当前路由 AST 对上，未导入或启动 app；225 处文件行号引用均存在且落在非空源码行，14 张 Markdown 表列数一致。已逐项回看关键合同及旧页控件来源；这些检查不等于 HTTP 集成测试。文档仍为未提交的新文件，未扩大到 Win7 浏览器验证或移植实施。
