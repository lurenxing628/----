# web与web_new_test三轮全面审查
- 日期: 2026-04-02
- 概述: 按三轮方式审查网页层、视图模型层与测试样板目录，重点检查引用链、输入归一化、页面装配与潜在影响使用的缺陷。
- 状态: 进行中
- 总体结论: 待定

## 评审范围

# web与web_new_test三轮全面审查

- 日期：2026-04-02
- 范围：`web/`、`web_new_test/`，并按需追踪到相关服务层、模板层、静态资源层与测试文件。
- 方法：分三轮推进；每完成一个有意义的模块级审查单元，立即记录里程碑；仅做只读分析，不修改业务代码。
- 重点：引用链追踪、关键函数与变量流、可用性风险、潜在 BUG、测试与脚本覆盖迹象。

## 初始结论

审查已启动，待完成三轮逐步更新。

## 评审摘要

- 当前状态: 进行中
- 已审模块: web/routes/reports.py, web/routes/scheduler_gantt.py, web/routes/scheduler_week_plan.py, web/routes/scheduler_analysis.py, web/routes/scheduler_resource_dispatch.py, core/services/report/report_engine.py, core/services/scheduler/gantt_service.py, core/services/scheduler/resource_dispatch_service.py, data/repositories/schedule_repo.py, web_new_test/templates/scheduler/batches.html, web_new_test/templates/scheduler/batches_manage.html, templates/scheduler/batches.html, templates/scheduler/batches_manage.html, web/routes/scheduler_run.py, web/routes/scheduler_batches.py, core/services/scheduler/batch_service.py, web/bootstrap/factory.py, core/services/common/safe_logging.py, core/services/scheduler/schedule_optimizer_steps.py, web/ui_mode.py, web_new_test/templates/base.html, core/services/scheduler/resource_pool_builder.py, core/services/scheduler/schedule_service.py, tests/regression_schedule_summary_algo_warnings_union.py, templates/process/list.html, web/routes/process_parts.py, core/services/process/part_service.py, templates/process/detail.html, core/services/process/route_parser.py, core/services/scheduler/gantt_tasks.py, templates/scheduler/gantt.html, static/js/gantt_render.js, static/css/aps_gantt.css, core/services/scheduler/resource_dispatch_support.py, core/services/scheduler/resource_dispatch_rows.py, templates/scheduler/resource_dispatch.html, static/js/resource_dispatch.js
- 当前进度: 已记录 5 个里程碑；最新：ms-silent-round3-overdue-markers
- 里程碑总数: 5
- 已完成里程碑: 5
- 问题总数: 6
- 问题严重级别分布: 高 0 / 中 5 / 低 1
- 最新结论: 坏 `result_summary` 目前会把甘特图与资源排班中心的超期信号静默抹平，属于能直接误导调度人员的真实风险。
- 下一步建议: 三轮静默回退复查已完成；下一步应回到运行验证与最终收口，优先复现实锤的 6 个问题，再决定最终结论。
- 总体结论: 待定

## 评审发现

### 版本参数归一化不一致

- ID: version-parameter-normalization
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: ms-round3-version-chain
- 说明:

  `reports` 导出链路已经把缺失、空值、非法值和 `version<=0` 统一回退到最新版本，且有回归脚本保护；但页面侧 `reports._page_version_or_latest()`、`scheduler_gantt.gantt_page/gantt_data`、`scheduler_week_plan.week_plan_page/week_plan_export`、`scheduler_analysis.analysis_page` 只校验“能否转成整数”，不会拦截 `<=0`。后续 `ReportEngine` 与 `GanttService` 会直接以 `0/-1` 查询排程表，因此页面会出现空结果、错误版本号，和导出接口的行为不一致。`week_plan_export` 还会在 `version=0` 时把结果文件名写成 `v1`，进一步放大误导。对复制链接、书签、手工改参和陈旧页面参数来说，这是直接可见的异常表现。
- 建议:

  抽出统一的版本解析辅助方法，至少在所有页面与导出入口上对 `version<=0` 执行同一策略（显式拒绝或回退最新版本二选一），并补充页面侧回归用例，覆盖 `0`、负数、空值、非整数四类输入。
- 证据:
  - `web/routes/reports.py:33-67#_export_version_or_latest/_page_version_or_latest`
  - `tests/regression_reports_export_version_default_latest.py:76-124#main`
  - `web/routes/scheduler_week_plan.py:99-145#week_plan_export`
  - `web/routes/scheduler_resource_dispatch.py:72-101#_sanitize_dispatch_args_from_error/resource_dispatch_page`
  - `core/services/scheduler/resource_dispatch_service.py:87-96#ResourceDispatchService._normalize_version`
  - `core/services/report/report_engine.py:86-148#ReportEngine.overdue_batches/utilization`
  - `core/services/scheduler/gantt_service.py:152-207#GanttService.get_gantt_tasks/get_week_plan_rows`
  - `data/repositories/schedule_repo.py:105-153#ScheduleRepository.list_overlapping_with_details`
  - `web/routes/reports.py`
  - `tests/regression_reports_export_version_default_latest.py`
  - `web/routes/scheduler_gantt.py`
  - `web/routes/scheduler_week_plan.py`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/scheduler_resource_dispatch.py`
  - `core/services/report/report_engine.py`
  - `core/services/scheduler/gantt_service.py`
  - `core/services/scheduler/resource_dispatch_service.py`
  - `data/repositories/schedule_repo.py`

### 新界面缺少严格模式入口

- ID: new-ui-missing-strict-mode-controls
- 严重级别: 中
- 分类: HTML
- 跟踪状态: 开放
- 相关里程碑: ms-round3-new-ui-and-logging
- 说明:

  旧界面 `templates/scheduler/batches.html` 和 `templates/scheduler/batches_manage.html` 都提供了 `strict_mode` 复选框，分别用于“严格调度参数校验”和“严格工艺解析”；但新界面覆盖模板 `web_new_test/templates/scheduler/batches.html`、`web_new_test/templates/scheduler/batches_manage.html` 把这些控件删掉了。后端路由 `scheduler_run.run_schedule()`、`scheduler_batches.create_batch()`、`scheduler_batches.generate_ops()` 仍然读取并下传 `strict_mode`，`BatchService.create_batch_from_template()` 也会基于该标记决定是否允许兼容性回退。结果是 `v2` 用户永久失去这组校验开关，和 `v1` 用户的业务行为不一致：同样的数据与配置问题，在旧界面可以被强制拒绝，在新界面却只能走兼容回退。
- 建议:

  把旧界面已有的 `strict_mode` 控件补回所有已覆盖的新界面批次页，并增加界面对齐回归，至少校验 `v1`/`v2` 两套页面都能提交该字段。
- 证据:
  - `web_new_test/templates/scheduler/batches.html:202-227#content`
  - `templates/scheduler/batches.html:217-248#content`
  - `web_new_test/templates/scheduler/batches_manage.html:15-65#content`
  - `templates/scheduler/batches_manage.html:15-73#content`
  - `web/routes/scheduler_run.py:33-47#run_schedule`
  - `web/routes/scheduler_batches.py:149-175#create_batch`
  - `web/routes/scheduler_batches.py:344-360#generate_ops`
  - `core/services/scheduler/batch_service.py:415-471#BatchService.create_batch_from_template`
  - `web_new_test/templates/scheduler/batches.html`
  - `templates/scheduler/batches.html`
  - `web_new_test/templates/scheduler/batches_manage.html`
  - `templates/scheduler/batches_manage.html`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/scheduler/batch_service.py`
  - `web/bootstrap/factory.py`
  - `web/routes/scheduler_gantt.py`
  - `core/services/common/safe_logging.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `web/ui_mode.py`
  - `web_new_test/templates/base.html`

### 请求级应用日志未绑定

- ID: request-scope-app-logger-missing
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: ms-round3-new-ui-and-logging
- 说明:

  `create_app_core()` 会创建 `app_logger` 并把处理器挂到 `app.logger`，但请求生命周期中的 `_open_db()` 只写入了 `g.db` 与 `g.op_logger`，没有把应用日志对象写入 `g.app_logger`。与此同时，网页层大量服务构造仍以 `logger=getattr(g, 'app_logger', None)` 传参，因此这些服务在请求内拿到的文件日志对象恒为 `None`。结合 `safe_logging.safe_log()` 对 `None` 直接返回、以及 `schedule_optimizer_steps.py` 等代码里的 `if logger:` 分支，许多“已忽略但需要排障”的告警会完全丢失，现场只剩数据库操作留痕或什么都没有。该问题不会立刻改坏业务结果，但会明显削弱 Windows 单机现场的故障定位能力。
- 建议:

  在 `_open_db()` 中显式绑定 `g.app_logger = current_app.logger`（或统一改为直接传 `current_app.logger`），并为至少一个会进入可选告警分支的页面链路补一条回归，防止再次出现静默失联。
- 证据:
  - `web/bootstrap/factory.py:216-224#create_app_core`
  - `web/bootstrap/factory.py:279-281#_open_db`
  - `web/routes/scheduler_gantt.py:55-63#gantt_page`
  - `core/services/common/safe_logging.py:6-22#safe_log`
  - `core/services/scheduler/schedule_optimizer_steps.py:193-201#_run_ortools_seed`
  - `web_new_test/templates/scheduler/batches.html`
  - `templates/scheduler/batches.html`
  - `web_new_test/templates/scheduler/batches_manage.html`
  - `templates/scheduler/batches_manage.html`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/scheduler/batch_service.py`
  - `web/bootstrap/factory.py`
  - `web/routes/scheduler_gantt.py`
  - `core/services/common/safe_logging.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `web/ui_mode.py`
  - `web_new_test/templates/base.html`

### 资源池降级告警未向页面用户显示

- ID: resource-pool-warning-hidden-from-web
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: ms-silent-round1-scheduler-warning-surface
- 说明:

  `build_resource_pool()` 失败时会把自动分配资源池直接降级为关闭，并生成“自动分配资源池构建失败，已降级为不自动分配” warning；`ScheduleService` 也会把这条 warning 合并进 `summary.warnings` 与历史摘要。但 `scheduler_run.run_schedule()` 只对 `【冻结窗口】`、`【停机】` 两类前缀做 flash，`templates/scheduler/batches.html` 也不显示 warning 列表，导致用户在主排产页面看到的仍然是普通成功提示，而不是“本次排产已关闭 auto-assign”的明确信号。对缺省资源较多的工单，这会直接改变排产结果，却没有同步暴露给主操作路径。
- 建议:

  不要用前缀白名单筛掉非冻结/非停机的降级 warning；至少把资源池降级、自动分配关闭这类 warning 也展示到排产完成后的页面反馈中，或在“最近一次排产”卡片中增加 warning 摘要。
- 证据:
  - `core/services/scheduler/resource_pool_builder.py:189-253#build_resource_pool`
  - `core/services/scheduler/schedule_service.py:389-405#ScheduleService._run_schedule_impl`
  - `core/services/scheduler/schedule_service.py:453-505#ScheduleService._run_schedule_impl`
  - `web/routes/scheduler_run.py:64-74#run_schedule`
  - `templates/scheduler/batches.html:80-109#content`
  - `tests/regression_schedule_summary_algo_warnings_union.py:74-104#main`
  - `core/services/scheduler/resource_pool_builder.py`
  - `core/services/scheduler/schedule_service.py`
  - `web/routes/scheduler_run.py`
  - `templates/scheduler/batches.html`
  - `tests/regression_schedule_summary_algo_warnings_union.py`

### 模板自动解析降级结果未向用户显式暴露

- ID: template-autoparse-degradation-hidden
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: ms-silent-round2-template-autoparse
- 说明:

  零件创建和批次懒生成模板两条链路都会触发工艺路线自动解析，但当前实现把解析失败与兼容回退都压成了“成功态”。`PartService.create()` 在非 strict_mode 下若自动解析失败，只写一条 `safe_warning()` 后继续返回创建成功；而 `create_part()` 没有传 logger，也没有 flash 失败细节，导致这条 warning 实际会静默丢失。详情页也仅显示“如果还未解析，请重新解析”的泛化提示，没有原始错误。与此同时，`BatchService._default_template_resolver()` 直接丢弃 `upsert_and_parse_no_tx()/reparse_and_save()` 返回的 `ParseResult`，使 `RouteParser` 在兼容模式下产生的 warning 无法继续传到 `create_batch()` / `generate_ops()` 的页面反馈。用户可能以为模板和工序都是正常生成的，实际上内部/外协归类、外协周期等关键语义已经被兼容逻辑改写。
- 建议:

  把自动解析的 warning/error 显式回传到网页层：零件创建至少在成功 flash 后补一条“解析失败/已兼容回退”的 warning；批次懒生成模板则不要丢弃 `ParseResult`，应把 warning 列表透传给 `create_batch()` / `generate_ops()` 页面反馈。
- 证据:
  - `templates/process/list.html:26-38#content`
  - `web/routes/process_parts.py:67-79#create_part`
  - `core/services/process/part_service.py:162-170#PartService.create`
  - `core/services/common/safe_logging.py:6-26#safe_log/safe_warning`
  - `templates/process/detail.html:59-64#content`
  - `core/services/scheduler/batch_service.py:121-125#BatchService._default_template_resolver`
  - `core/services/scheduler/batch_service.py:142-157#BatchService._load_template_ops_with_fallback`
  - `web/routes/scheduler_batches.py:149-177#create_batch`
  - `web/routes/scheduler_batches.py:344-363#generate_ops`
  - `core/services/process/route_parser.py:207-255#RouteParser.parse`
  - `templates/process/list.html`
  - `web/routes/process_parts.py`
  - `core/services/process/part_service.py`
  - `core/services/common/safe_logging.py`
  - `templates/process/detail.html`
  - `core/services/scheduler/batch_service.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/process/route_parser.py`

### 坏摘要会静默抹掉超期信号

- ID: malformed-summary-erases-overdue-signals
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: ms-silent-round3-overdue-markers
- 说明:

  甘特图与资源排班中心都把“超期”判定建立在 `schedule_history.result_summary` 的历史摘要上，但两条读取链在摘要损坏时都会直接回空集合而不发出任何信号。`GanttService._overdue_batch_ids_from_history()` 捕获 `json.loads()` 异常后返回 `[]`，`extract_overdue_batch_ids()` 也在解析失败时返回 `set()`；后续任务/行对象照常生成，只是所有 `is_overdue` 都变成 `False`。结果是甘特图上的红色边框、仅超期筛选、tooltip 的超期说明，以及资源排班中心里的超期统计卡、明细 badge、日历矩阵红字都会一起消失，而页面仍显示为成功加载。对调度员来说，这不是“功能小降级”，而是把真实存在的超期任务伪装成“无超期”的错误状态。
- 建议:

  不要把摘要解析失败直接等价为“无超期”。至少应记录 warning/logger，并把“历史摘要损坏，超期标记可能不完整”的信号带到页面；更稳妥的是在合同里显式返回 `summary_parse_error` 一类标记，让甘特图和资源排班中心显示降级提示，而不是静默清零。
- 证据:
  - `core/services/scheduler/gantt_service.py:52-69#GanttService._overdue_batch_ids_from_history`
  - `core/services/scheduler/gantt_service.py:152-159#GanttService.get_gantt_tasks`
  - `core/services/scheduler/gantt_tasks.py:170-209#_build_one_task`
  - `templates/scheduler/gantt.html:100-102#content`
  - `templates/scheduler/gantt.html:137-141#content`
  - `templates/scheduler/gantt.html:160-167#content`
  - `static/js/gantt_render.js:54-63#applyFilters`
  - `static/js/gantt_render.js:968-976#custom_popup_html`
  - `static/css/aps_gantt.css:78-82#css`
  - `core/services/scheduler/resource_dispatch_support.py:14-34#extract_overdue_batch_ids`
  - `core/services/scheduler/resource_dispatch_service.py:144-148#ResourceDispatchService._load_overdue_set`
  - `core/services/scheduler/resource_dispatch_service.py:256-293#ResourceDispatchService.get_dispatch_payload`
  - `core/services/scheduler/resource_dispatch_rows.py:113-151#normalize_dispatch_row`
  - `core/services/scheduler/resource_dispatch_support.py:46-84#build_dispatch_summary`
  - `templates/scheduler/resource_dispatch.html:152-175#content`
  - `static/js/resource_dispatch.js:61-66#renderFlags`
  - `static/js/resource_dispatch.js:128-135#renderSummary`
  - `static/js/resource_dispatch.js:220-224#renderCalendar`
  - `core/services/scheduler/gantt_service.py`
  - `core/services/scheduler/gantt_tasks.py`
  - `templates/scheduler/gantt.html`
  - `static/js/gantt_render.js`
  - `static/css/aps_gantt.css`
  - `core/services/scheduler/resource_dispatch_support.py`
  - `core/services/scheduler/resource_dispatch_service.py`
  - `core/services/scheduler/resource_dispatch_rows.py`
  - `templates/scheduler/resource_dispatch.html`
  - `static/js/resource_dispatch.js`

## 评审里程碑

### ms-round3-version-chain · 轮次三：报表与排程展示页的版本参数链路收尾

- 状态: 已完成
- 记录时间: 2026-04-02T17:20:49.379Z
- 已审模块: web/routes/reports.py, web/routes/scheduler_gantt.py, web/routes/scheduler_week_plan.py, web/routes/scheduler_analysis.py, web/routes/scheduler_resource_dispatch.py, core/services/report/report_engine.py, core/services/scheduler/gantt_service.py, core/services/scheduler/resource_dispatch_service.py, data/repositories/schedule_repo.py
- 摘要:

  继续沿 `reports -> report_engine -> schedule_repo`、`gantt/week_plan/analysis -> GanttService/HistoryQueryService`、`resource_dispatch -> ResourceDispatchService` 三条链路核对 `version` 参数口径。确认 `reports` 导出接口已通过 `_export_version_or_latest()` 把缺失、空值、非整数和 `<=0` 统一回退到最新版本，并已有 `tests/regression_reports_export_version_default_latest.py` 保护；但 `reports` 页面侧 `_page_version_or_latest()` 仅做整数转换，不拦截 `<=0`，`scheduler_gantt.py`、`scheduler_week_plan.py`、`scheduler_analysis.py` 也只做“能转整数”校验，随后把 `0/-1` 继续传入 `ReportEngine` / `GanttService` / 仓储层。结果是同一套页面与导出对非法版本的处理口径不一致：页面可能展示空数据、错误版本号，`week-plan/export` 在 `version=0` 时还会因为 `int(data.get('version') or 1)` 把文件名回写成 `v1`。相对地，`resource_dispatch` 已经通过 `_normalize_version()` + 无效参数清理回跳保持了稳定行为。
- 结论:

  报表页、甘特图、周计划、排产分析在 `version<=0` 场景下存在统一性缺口，属于已确认的用户可见 BUG。
- 证据:
  - `web/routes/reports.py:33-67#_export_version_or_latest/_page_version_or_latest`
  - `tests/regression_reports_export_version_default_latest.py:76-124#main`
  - `web/routes/scheduler_gantt.py:47-57#gantt_page`
  - `web/routes/scheduler_gantt.py:95-110#gantt_data`
  - `web/routes/scheduler_week_plan.py:52-69#week_plan_page`
  - `web/routes/scheduler_week_plan.py:99-145#week_plan_export`
  - `web/routes/scheduler_analysis.py:25-38#analysis_page`
  - `web/routes/scheduler_resource_dispatch.py:72-101#_sanitize_dispatch_args_from_error/resource_dispatch_page`
  - `core/services/scheduler/resource_dispatch_service.py:87-96#ResourceDispatchService._normalize_version`
  - `core/services/report/report_engine.py:86-148#ReportEngine.overdue_batches/utilization`
  - `core/services/report/report_engine.py:162-198#ReportEngine.downtime_impact/export_downtime_impact_xlsx`
  - `core/services/scheduler/gantt_service.py:152-179#GanttService.get_gantt_tasks`
  - `core/services/scheduler/gantt_service.py:194-207#GanttService.get_week_plan_rows`
  - `data/repositories/schedule_repo.py:105-153#ScheduleRepository.list_overlapping_with_details`
  - `web/routes/reports.py`
  - `tests/regression_reports_export_version_default_latest.py`
  - `web/routes/scheduler_gantt.py`
  - `web/routes/scheduler_week_plan.py`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/scheduler_resource_dispatch.py`
  - `core/services/report/report_engine.py`
  - `core/services/scheduler/gantt_service.py`
  - `core/services/scheduler/resource_dispatch_service.py`
  - `data/repositories/schedule_repo.py`
- 下一步建议:

  继续收口 web_new_test 覆盖页面与请求级日志链路，确认新界面与旧界面的功能对齐程度。
- 问题:
  - [中] 其他: 版本参数归一化不一致

### ms-round3-new-ui-and-logging · 轮次三：新界面批次页对齐与请求级日志链路收尾

- 状态: 已完成
- 记录时间: 2026-04-02T17:22:00.798Z
- 已审模块: web_new_test/templates/scheduler/batches.html, web_new_test/templates/scheduler/batches_manage.html, templates/scheduler/batches.html, templates/scheduler/batches_manage.html, web/routes/scheduler_run.py, web/routes/scheduler_batches.py, core/services/scheduler/batch_service.py, web/bootstrap/factory.py, web/routes/scheduler_gantt.py, core/services/common/safe_logging.py, core/services/scheduler/schedule_optimizer_steps.py, web/ui_mode.py, web_new_test/templates/base.html
- 摘要:

  继续对 `web_new_test` 覆盖页做旧界面/新界面对照，并回溯到对应路由、服务与应用启动链。核对结果表明：`web_new_test/templates/scheduler/batches.html` 和 `web_new_test/templates/scheduler/batches_manage.html` 在覆盖旧界面后，把旧模板已有的 `strict_mode` 开关整段删掉了，但后端 `scheduler_run.run_schedule()`、`scheduler_batches.create_batch()`、`scheduler_batches.generate_ops()` 仍会读取 `request.form['strict_mode']` 并把该标记下传到 `ScheduleService` / `BatchService.create_batch_from_template()`；因此新界面用户无法启用“严格调度参数校验”和“严格工艺解析”，同一功能在 `v1`/`v2` 两种界面下行为已经不再一致。与此同时，应用启动时虽然创建了 `app_logger`，但 `before_request` 只把 `g.db` 与 `g.op_logger` 写入请求上下文，没有写入 `g.app_logger`；而网页层多处却以 `logger=getattr(g, 'app_logger', None)` 构造服务。结合 `safe_logging.safe_log()` 与 `schedule_optimizer_steps.py` 中的 `if logger:` 分支，这意味着大量可选告警和降级提示会因为 `logger` 恒为 `None` 而直接静默丢失。对 `ui_mode` 的覆盖装配同时做了复核：`/static-v2` 与 `ui_v2_static.static` 链路本身可达，当前阻断点主要集中在功能对齐与日志可观测性，而不是静态资源注册。
- 结论:

  `web_new_test` 已确认存在界面功能缺口；请求级应用日志对象未绑定则属于低级别但真实存在的可观测性缺陷。
- 证据:
  - `web_new_test/templates/scheduler/batches.html:202-227#content`
  - `templates/scheduler/batches.html:217-248#content`
  - `web_new_test/templates/scheduler/batches_manage.html:15-65#content`
  - `templates/scheduler/batches_manage.html:15-73#content`
  - `web/routes/scheduler_run.py:33-47#run_schedule`
  - `web/routes/scheduler_batches.py:149-175#create_batch`
  - `web/routes/scheduler_batches.py:344-360#generate_ops`
  - `core/services/scheduler/batch_service.py:415-471#BatchService.create_batch_from_template`
  - `web/bootstrap/factory.py:216-224#create_app_core`
  - `web/bootstrap/factory.py:279-281#_open_db`
  - `web/routes/scheduler_gantt.py:55-63#gantt_page`
  - `core/services/common/safe_logging.py:6-22#safe_log`
  - `core/services/scheduler/schedule_optimizer_steps.py:193-201#_run_ortools_seed`
  - `web/ui_mode.py:118-179#init_ui_mode`
  - `web_new_test/templates/base.html:44-47#head`
  - `web_new_test/templates/scheduler/batches.html`
  - `templates/scheduler/batches.html`
  - `web_new_test/templates/scheduler/batches_manage.html`
  - `templates/scheduler/batches_manage.html`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/scheduler/batch_service.py`
  - `web/bootstrap/factory.py`
  - `web/routes/scheduler_gantt.py`
  - `core/services/common/safe_logging.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `web/ui_mode.py`
  - `web_new_test/templates/base.html`
- 下一步建议:

  整理最终结论并收口三轮审查结果，优先把版本参数统一化与新界面严格模式缺口列为修复项。
- 问题:
  - [中] HTML: 新界面缺少严格模式入口
  - [低] 可维护性: 请求级应用日志未绑定

### ms-silent-round1-scheduler-warning-surface · 轮次一：排产降级告警的页面暴露链复查

- 状态: 已完成
- 记录时间: 2026-04-02T17:56:37.261Z
- 已审模块: core/services/scheduler/resource_pool_builder.py, core/services/scheduler/schedule_service.py, web/routes/scheduler_run.py, templates/scheduler/batches.html, tests/regression_schedule_summary_algo_warnings_union.py
- 摘要:

  围绕“静默回退是否真的被用户看到”先复查排产主链。沿 `resource_pool_builder -> schedule_service -> scheduler_run -> scheduler/batches.html` 追踪后确认：资源池构建失败时，`build_resource_pool()` 会把自动分配直接降级为关闭，并写入 warning；`ScheduleService` 也会把该 warning 合并进 `summary.warnings` / `result_summary`，现有回归 `tests/regression_schedule_summary_algo_warnings_union.py` 还专门保证了这条 warning 不会在摘要构建阶段丢失。但网页入口 `scheduler_run.run_schedule()` 只会把前缀为 `【冻结窗口】` 或 `【停机】` 的 warning flash 给用户，资源池 warning 不在白名单内；而 `templates/scheduler/batches.html` 的“最近一次排产”卡片也只展示超期和算法指标，不展示 warning 列表。结果是：一旦自动分配资源池构建失败，页面仍会提示“排产完成”，但用户既看不到 auto-assign 已被关闭，也不知道这次排产已经走了降级路径，只能去系统历史里手看原始摘要 JSON。这个回退虽然不完全无痕，但对主操作路径来说已经接近静默。
- 结论:

  排产主链对资源池降级 warning 的页面暴露不完整，属于会隐藏调度语义变化的真实问题。
- 证据:
  - `core/services/scheduler/resource_pool_builder.py:189-253#build_resource_pool`
  - `core/services/scheduler/schedule_service.py:389-405#ScheduleService._run_schedule_impl`
  - `core/services/scheduler/schedule_service.py:453-505#ScheduleService._run_schedule_impl`
  - `web/routes/scheduler_run.py:64-74#run_schedule`
  - `templates/scheduler/batches.html:80-109#content`
  - `tests/regression_schedule_summary_algo_warnings_union.py:74-104#main`
  - `core/services/scheduler/resource_pool_builder.py`
  - `core/services/scheduler/schedule_service.py`
  - `web/routes/scheduler_run.py`
  - `templates/scheduler/batches.html`
  - `tests/regression_schedule_summary_algo_warnings_union.py`
- 下一步建议:

  继续检查工艺路线自动解析、批次懒生成模板以及零件创建路径里，兼容回退是否被真正暴露给用户。
- 问题:
  - [中] 其他: 资源池降级告警未向页面用户显示

### ms-silent-round2-template-autoparse · 轮次二：工艺模板自动解析与兼容回退暴露链复查

- 状态: 已完成
- 记录时间: 2026-04-02T17:57:19.948Z
- 已审模块: templates/process/list.html, web/routes/process_parts.py, core/services/process/part_service.py, core/services/common/safe_logging.py, templates/process/detail.html, core/services/scheduler/batch_service.py, web/routes/scheduler_batches.py, core/services/process/route_parser.py
- 摘要:

  第二轮聚焦 `process_parts -> PartService -> RouteParser` 与 `scheduler_batches -> BatchService -> PartService` 两条“自动解析模板”链。核对后确认有两层隐藏问题叠加：第一，零件创建页在非 strict_mode 下允许填写 `route_raw` 并“尝试自动解析”，但 `PartService.create()` 如果自动 `reparse_and_save()` 失败，只会调用 `safe_warning(self.logger, ...)`，随后仍返回创建成功；而 `web/routes/process_parts.py#create_part()` 既没有把失败信息 flash 给用户，也没有给 `PartService` 传入可用 logger，`safe_warning()` 在 `logger is None` 时直接无声返回。用户最终只会看到“已创建零件”，跳到详情页后也只是看到“如果还未解析，请重新解析”的泛化提示，没有原始解析错误。第二，批次创建/重建工序链路在缺少模板时会懒触发 `_default_template_resolver()`，它调用 `PartService.upsert_and_parse_no_tx()` / `reparse_and_save()` 却不返回 `ParseResult`，使 `RouteParser.parse()` 中的兼容 warning（例如未知工种默认 external、供应商周期回退等）在 `BatchService` 层直接被丢弃；最终 `scheduler_batches.create_batch()`、`generate_ops()` 也只 flash “已创建/已重建工序”，完全不告诉用户这次模板生成是否经过兼容降级。
- 结论:

  工艺模板自动解析链存在“成功态掩盖降级/失败细节”的问题，会把真实解析异常和兼容回退隐藏在后台。
- 证据:
  - `templates/process/list.html:26-38#content`
  - `web/routes/process_parts.py:67-79#create_part`
  - `core/services/process/part_service.py:162-170#PartService.create`
  - `core/services/common/safe_logging.py:6-26#safe_log/safe_warning`
  - `templates/process/detail.html:59-64#content`
  - `core/services/scheduler/batch_service.py:121-125#BatchService._default_template_resolver`
  - `core/services/scheduler/batch_service.py:142-157#BatchService._load_template_ops_with_fallback`
  - `web/routes/scheduler_batches.py:149-177#create_batch`
  - `web/routes/scheduler_batches.py:344-363#generate_ops`
  - `core/services/process/route_parser.py:207-255#RouteParser.parse`
  - `templates/process/list.html`
  - `web/routes/process_parts.py`
  - `core/services/process/part_service.py`
  - `core/services/common/safe_logging.py`
  - `templates/process/detail.html`
  - `core/services/scheduler/batch_service.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/process/route_parser.py`
- 下一步建议:

  最后一轮继续检查甘特图、资源排班中心以及历史摘要读取链里，是否还存在把坏数据直接洗成空集合或默认值的静默回退。
- 问题:
  - [中] 其他: 模板自动解析降级结果未向用户显式暴露

### ms-silent-round3-overdue-markers · 轮次三：甘特图与资源排班中心超期标记链复查

- 状态: 已完成
- 记录时间: 2026-04-02T18:03:27.341Z
- 已审模块: core/services/scheduler/gantt_service.py, core/services/scheduler/gantt_tasks.py, templates/scheduler/gantt.html, static/js/gantt_render.js, static/css/aps_gantt.css, core/services/scheduler/resource_dispatch_support.py, core/services/scheduler/resource_dispatch_service.py, core/services/scheduler/resource_dispatch_rows.py, templates/scheduler/resource_dispatch.html, static/js/resource_dispatch.js
- 摘要:

  最后一轮沿 `schedule_history.result_summary -> GanttService/ResourceDispatchService -> rows/tasks -> template/js` 复查“超期标记”是否会被静默洗掉。确认两条链路都存在同类问题：`core/services/scheduler/gantt_service.py#GanttService._overdue_batch_ids_from_history()` 在 `json.loads()` 失败时直接 `return []`，`get_gantt_tasks()` 随后仍正常构建合同；`gantt_tasks._build_one_task()` 用该空集合把所有任务的 `meta.is_overdue` 设成 `False`，于是 `static/js/gantt_render.js` 的“仅超期”筛选、tooltip 中的“超期：是/否”、以及 `static/css/aps_gantt.css` 的红色边框都一起失效。`templates/scheduler/gantt.html` 明确告诉用户“红色边框表示超期”“可配合仅超期快速定位问题”，但坏摘要只会表现为这些信号全部消失，而不是报错或警告。资源排班中心同样如此：`extract_overdue_batch_ids()` 在摘要为空或 JSON 解析失败时直接返回 `set()`；`ResourceDispatchService._load_overdue_set()` 与 `get_dispatch_payload()` 继续生成成功载荷，`resource_dispatch_rows.normalize_dispatch_row()` 因而把所有 `is_overdue` 置空，`build_dispatch_summary()` 的 `overdue_count` 变成 `0`，最终 `templates/scheduler/resource_dispatch.html` 的“超期任务”统计卡、`static/js/resource_dispatch.js` 的超期 badge、以及日历矩阵里的红色文字全部消失。整个页面仍返回成功数据，用户只会误以为该版本没有超期任务。
- 结论:

  坏 `result_summary` 目前会把甘特图与资源排班中心的超期信号静默抹平，属于能直接误导调度人员的真实风险。
- 证据:
  - `core/services/scheduler/gantt_service.py:52-69#GanttService._overdue_batch_ids_from_history`
  - `core/services/scheduler/gantt_service.py:152-159#GanttService.get_gantt_tasks`
  - `core/services/scheduler/gantt_tasks.py:170-209#_build_one_task`
  - `templates/scheduler/gantt.html:100-102#content`
  - `templates/scheduler/gantt.html:137-141#content`
  - `templates/scheduler/gantt.html:160-167#content`
  - `static/js/gantt_render.js:54-63#applyFilters`
  - `static/js/gantt_render.js:968-976#custom_popup_html`
  - `static/css/aps_gantt.css:78-82#css`
  - `core/services/scheduler/resource_dispatch_support.py:14-34#extract_overdue_batch_ids`
  - `core/services/scheduler/resource_dispatch_service.py:144-148#ResourceDispatchService._load_overdue_set`
  - `core/services/scheduler/resource_dispatch_service.py:256-293#ResourceDispatchService.get_dispatch_payload`
  - `core/services/scheduler/resource_dispatch_rows.py:113-151#normalize_dispatch_row`
  - `core/services/scheduler/resource_dispatch_rows.py:253-279#build_dispatch_tasks`
  - `core/services/scheduler/resource_dispatch_support.py:46-84#build_dispatch_summary`
  - `templates/scheduler/resource_dispatch.html:152-175#content`
  - `static/js/resource_dispatch.js:61-66#renderFlags`
  - `static/js/resource_dispatch.js:128-135#renderSummary`
  - `static/js/resource_dispatch.js:220-224#renderCalendar`
  - `core/services/scheduler/gantt_service.py`
  - `core/services/scheduler/gantt_tasks.py`
  - `templates/scheduler/gantt.html`
  - `static/js/gantt_render.js`
  - `static/css/aps_gantt.css`
  - `core/services/scheduler/resource_dispatch_support.py`
  - `core/services/scheduler/resource_dispatch_service.py`
  - `core/services/scheduler/resource_dispatch_rows.py`
  - `templates/scheduler/resource_dispatch.html`
  - `static/js/resource_dispatch.js`
- 下一步建议:

  三轮静默回退复查已完成；下一步应回到运行验证与最终收口，优先复现实锤的 6 个问题，再决定最终结论。
- 问题:
  - [中] 其他: 坏摘要会静默抹掉超期信号

## 最终结论

坏 `result_summary` 目前会把甘特图与资源排班中心的超期信号静默抹平，属于能直接误导调度人员的真实风险。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnhq4mcv-obrfu1",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "updatedAt": "2026-04-02T18:03:27.341Z",
  "finalizedAt": null,
  "status": "in_progress",
  "overallDecision": null,
  "header": {
    "title": "web与web_new_test三轮全面审查",
    "date": "2026-04-02",
    "overview": "按三轮方式审查网页层、视图模型层与测试样板目录，重点检查引用链、输入归一化、页面装配与潜在影响使用的缺陷。"
  },
  "scope": {
    "markdown": "# web与web_new_test三轮全面审查\n\n- 日期：2026-04-02\n- 范围：`web/`、`web_new_test/`，并按需追踪到相关服务层、模板层、静态资源层与测试文件。\n- 方法：分三轮推进；每完成一个有意义的模块级审查单元，立即记录里程碑；仅做只读分析，不修改业务代码。\n- 重点：引用链追踪、关键函数与变量流、可用性风险、潜在 BUG、测试与脚本覆盖迹象。\n\n## 初始结论\n\n审查已启动，待完成三轮逐步更新。"
  },
  "summary": {
    "latestConclusion": "坏 `result_summary` 目前会把甘特图与资源排班中心的超期信号静默抹平，属于能直接误导调度人员的真实风险。",
    "recommendedNextAction": "三轮静默回退复查已完成；下一步应回到运行验证与最终收口，优先复现实锤的 6 个问题，再决定最终结论。",
    "reviewedModules": [
      "web/routes/reports.py",
      "web/routes/scheduler_gantt.py",
      "web/routes/scheduler_week_plan.py",
      "web/routes/scheduler_analysis.py",
      "web/routes/scheduler_resource_dispatch.py",
      "core/services/report/report_engine.py",
      "core/services/scheduler/gantt_service.py",
      "core/services/scheduler/resource_dispatch_service.py",
      "data/repositories/schedule_repo.py",
      "web_new_test/templates/scheduler/batches.html",
      "web_new_test/templates/scheduler/batches_manage.html",
      "templates/scheduler/batches.html",
      "templates/scheduler/batches_manage.html",
      "web/routes/scheduler_run.py",
      "web/routes/scheduler_batches.py",
      "core/services/scheduler/batch_service.py",
      "web/bootstrap/factory.py",
      "core/services/common/safe_logging.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "web/ui_mode.py",
      "web_new_test/templates/base.html",
      "core/services/scheduler/resource_pool_builder.py",
      "core/services/scheduler/schedule_service.py",
      "tests/regression_schedule_summary_algo_warnings_union.py",
      "templates/process/list.html",
      "web/routes/process_parts.py",
      "core/services/process/part_service.py",
      "templates/process/detail.html",
      "core/services/process/route_parser.py",
      "core/services/scheduler/gantt_tasks.py",
      "templates/scheduler/gantt.html",
      "static/js/gantt_render.js",
      "static/css/aps_gantt.css",
      "core/services/scheduler/resource_dispatch_support.py",
      "core/services/scheduler/resource_dispatch_rows.py",
      "templates/scheduler/resource_dispatch.html",
      "static/js/resource_dispatch.js"
    ]
  },
  "stats": {
    "totalMilestones": 5,
    "completedMilestones": 5,
    "totalFindings": 6,
    "severity": {
      "high": 0,
      "medium": 5,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "ms-round3-version-chain",
      "title": "轮次三：报表与排程展示页的版本参数链路收尾",
      "status": "completed",
      "recordedAt": "2026-04-02T17:20:49.379Z",
      "summaryMarkdown": "继续沿 `reports -> report_engine -> schedule_repo`、`gantt/week_plan/analysis -> GanttService/HistoryQueryService`、`resource_dispatch -> ResourceDispatchService` 三条链路核对 `version` 参数口径。确认 `reports` 导出接口已通过 `_export_version_or_latest()` 把缺失、空值、非整数和 `<=0` 统一回退到最新版本，并已有 `tests/regression_reports_export_version_default_latest.py` 保护；但 `reports` 页面侧 `_page_version_or_latest()` 仅做整数转换，不拦截 `<=0`，`scheduler_gantt.py`、`scheduler_week_plan.py`、`scheduler_analysis.py` 也只做“能转整数”校验，随后把 `0/-1` 继续传入 `ReportEngine` / `GanttService` / 仓储层。结果是同一套页面与导出对非法版本的处理口径不一致：页面可能展示空数据、错误版本号，`week-plan/export` 在 `version=0` 时还会因为 `int(data.get('version') or 1)` 把文件名回写成 `v1`。相对地，`resource_dispatch` 已经通过 `_normalize_version()` + 无效参数清理回跳保持了稳定行为。",
      "conclusionMarkdown": "报表页、甘特图、周计划、排产分析在 `version<=0` 场景下存在统一性缺口，属于已确认的用户可见 BUG。",
      "evidence": [
        {
          "path": "web/routes/reports.py",
          "lineStart": 33,
          "lineEnd": 67,
          "symbol": "_export_version_or_latest/_page_version_or_latest"
        },
        {
          "path": "tests/regression_reports_export_version_default_latest.py",
          "lineStart": 76,
          "lineEnd": 124,
          "symbol": "main"
        },
        {
          "path": "web/routes/scheduler_gantt.py",
          "lineStart": 47,
          "lineEnd": 57,
          "symbol": "gantt_page"
        },
        {
          "path": "web/routes/scheduler_gantt.py",
          "lineStart": 95,
          "lineEnd": 110,
          "symbol": "gantt_data"
        },
        {
          "path": "web/routes/scheduler_week_plan.py",
          "lineStart": 52,
          "lineEnd": 69,
          "symbol": "week_plan_page"
        },
        {
          "path": "web/routes/scheduler_week_plan.py",
          "lineStart": 99,
          "lineEnd": 145,
          "symbol": "week_plan_export"
        },
        {
          "path": "web/routes/scheduler_analysis.py",
          "lineStart": 25,
          "lineEnd": 38,
          "symbol": "analysis_page"
        },
        {
          "path": "web/routes/scheduler_resource_dispatch.py",
          "lineStart": 72,
          "lineEnd": 101,
          "symbol": "_sanitize_dispatch_args_from_error/resource_dispatch_page"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py",
          "lineStart": 87,
          "lineEnd": 96,
          "symbol": "ResourceDispatchService._normalize_version"
        },
        {
          "path": "core/services/report/report_engine.py",
          "lineStart": 86,
          "lineEnd": 148,
          "symbol": "ReportEngine.overdue_batches/utilization"
        },
        {
          "path": "core/services/report/report_engine.py",
          "lineStart": 162,
          "lineEnd": 198,
          "symbol": "ReportEngine.downtime_impact/export_downtime_impact_xlsx"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 152,
          "lineEnd": 179,
          "symbol": "GanttService.get_gantt_tasks"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 194,
          "lineEnd": 207,
          "symbol": "GanttService.get_week_plan_rows"
        },
        {
          "path": "data/repositories/schedule_repo.py",
          "lineStart": 105,
          "lineEnd": 153,
          "symbol": "ScheduleRepository.list_overlapping_with_details"
        },
        {
          "path": "web/routes/reports.py"
        },
        {
          "path": "tests/regression_reports_export_version_default_latest.py"
        },
        {
          "path": "web/routes/scheduler_gantt.py"
        },
        {
          "path": "web/routes/scheduler_week_plan.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/scheduler_resource_dispatch.py"
        },
        {
          "path": "core/services/report/report_engine.py"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py"
        },
        {
          "path": "data/repositories/schedule_repo.py"
        }
      ],
      "reviewedModules": [
        "web/routes/reports.py",
        "web/routes/scheduler_gantt.py",
        "web/routes/scheduler_week_plan.py",
        "web/routes/scheduler_analysis.py",
        "web/routes/scheduler_resource_dispatch.py",
        "core/services/report/report_engine.py",
        "core/services/scheduler/gantt_service.py",
        "core/services/scheduler/resource_dispatch_service.py",
        "data/repositories/schedule_repo.py"
      ],
      "recommendedNextAction": "继续收口 web_new_test 覆盖页面与请求级日志链路，确认新界面与旧界面的功能对齐程度。",
      "findingIds": [
        "version-parameter-normalization"
      ]
    },
    {
      "id": "ms-round3-new-ui-and-logging",
      "title": "轮次三：新界面批次页对齐与请求级日志链路收尾",
      "status": "completed",
      "recordedAt": "2026-04-02T17:22:00.798Z",
      "summaryMarkdown": "继续对 `web_new_test` 覆盖页做旧界面/新界面对照，并回溯到对应路由、服务与应用启动链。核对结果表明：`web_new_test/templates/scheduler/batches.html` 和 `web_new_test/templates/scheduler/batches_manage.html` 在覆盖旧界面后，把旧模板已有的 `strict_mode` 开关整段删掉了，但后端 `scheduler_run.run_schedule()`、`scheduler_batches.create_batch()`、`scheduler_batches.generate_ops()` 仍会读取 `request.form['strict_mode']` 并把该标记下传到 `ScheduleService` / `BatchService.create_batch_from_template()`；因此新界面用户无法启用“严格调度参数校验”和“严格工艺解析”，同一功能在 `v1`/`v2` 两种界面下行为已经不再一致。与此同时，应用启动时虽然创建了 `app_logger`，但 `before_request` 只把 `g.db` 与 `g.op_logger` 写入请求上下文，没有写入 `g.app_logger`；而网页层多处却以 `logger=getattr(g, 'app_logger', None)` 构造服务。结合 `safe_logging.safe_log()` 与 `schedule_optimizer_steps.py` 中的 `if logger:` 分支，这意味着大量可选告警和降级提示会因为 `logger` 恒为 `None` 而直接静默丢失。对 `ui_mode` 的覆盖装配同时做了复核：`/static-v2` 与 `ui_v2_static.static` 链路本身可达，当前阻断点主要集中在功能对齐与日志可观测性，而不是静态资源注册。",
      "conclusionMarkdown": "`web_new_test` 已确认存在界面功能缺口；请求级应用日志对象未绑定则属于低级别但真实存在的可观测性缺陷。",
      "evidence": [
        {
          "path": "web_new_test/templates/scheduler/batches.html",
          "lineStart": 202,
          "lineEnd": 227,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/batches.html",
          "lineStart": 217,
          "lineEnd": 248,
          "symbol": "content"
        },
        {
          "path": "web_new_test/templates/scheduler/batches_manage.html",
          "lineStart": 15,
          "lineEnd": 65,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/batches_manage.html",
          "lineStart": 15,
          "lineEnd": 73,
          "symbol": "content"
        },
        {
          "path": "web/routes/scheduler_run.py",
          "lineStart": 33,
          "lineEnd": 47,
          "symbol": "run_schedule"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 149,
          "lineEnd": 175,
          "symbol": "create_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 344,
          "lineEnd": 360,
          "symbol": "generate_ops"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 415,
          "lineEnd": 471,
          "symbol": "BatchService.create_batch_from_template"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 216,
          "lineEnd": 224,
          "symbol": "create_app_core"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 279,
          "lineEnd": 281,
          "symbol": "_open_db"
        },
        {
          "path": "web/routes/scheduler_gantt.py",
          "lineStart": 55,
          "lineEnd": 63,
          "symbol": "gantt_page"
        },
        {
          "path": "core/services/common/safe_logging.py",
          "lineStart": 6,
          "lineEnd": 22,
          "symbol": "safe_log"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 193,
          "lineEnd": 201,
          "symbol": "_run_ortools_seed"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 118,
          "lineEnd": 179,
          "symbol": "init_ui_mode"
        },
        {
          "path": "web_new_test/templates/base.html",
          "lineStart": 44,
          "lineEnd": 47,
          "symbol": "head"
        },
        {
          "path": "web_new_test/templates/scheduler/batches.html"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "web_new_test/templates/scheduler/batches_manage.html"
        },
        {
          "path": "templates/scheduler/batches_manage.html"
        },
        {
          "path": "web/routes/scheduler_run.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/routes/scheduler_gantt.py"
        },
        {
          "path": "core/services/common/safe_logging.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web_new_test/templates/base.html"
        }
      ],
      "reviewedModules": [
        "web_new_test/templates/scheduler/batches.html",
        "web_new_test/templates/scheduler/batches_manage.html",
        "templates/scheduler/batches.html",
        "templates/scheduler/batches_manage.html",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_batches.py",
        "core/services/scheduler/batch_service.py",
        "web/bootstrap/factory.py",
        "web/routes/scheduler_gantt.py",
        "core/services/common/safe_logging.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "web/ui_mode.py",
        "web_new_test/templates/base.html"
      ],
      "recommendedNextAction": "整理最终结论并收口三轮审查结果，优先把版本参数统一化与新界面严格模式缺口列为修复项。",
      "findingIds": [
        "new-ui-missing-strict-mode-controls",
        "request-scope-app-logger-missing"
      ]
    },
    {
      "id": "ms-silent-round1-scheduler-warning-surface",
      "title": "轮次一：排产降级告警的页面暴露链复查",
      "status": "completed",
      "recordedAt": "2026-04-02T17:56:37.261Z",
      "summaryMarkdown": "围绕“静默回退是否真的被用户看到”先复查排产主链。沿 `resource_pool_builder -> schedule_service -> scheduler_run -> scheduler/batches.html` 追踪后确认：资源池构建失败时，`build_resource_pool()` 会把自动分配直接降级为关闭，并写入 warning；`ScheduleService` 也会把该 warning 合并进 `summary.warnings` / `result_summary`，现有回归 `tests/regression_schedule_summary_algo_warnings_union.py` 还专门保证了这条 warning 不会在摘要构建阶段丢失。但网页入口 `scheduler_run.run_schedule()` 只会把前缀为 `【冻结窗口】` 或 `【停机】` 的 warning flash 给用户，资源池 warning 不在白名单内；而 `templates/scheduler/batches.html` 的“最近一次排产”卡片也只展示超期和算法指标，不展示 warning 列表。结果是：一旦自动分配资源池构建失败，页面仍会提示“排产完成”，但用户既看不到 auto-assign 已被关闭，也不知道这次排产已经走了降级路径，只能去系统历史里手看原始摘要 JSON。这个回退虽然不完全无痕，但对主操作路径来说已经接近静默。",
      "conclusionMarkdown": "排产主链对资源池降级 warning 的页面暴露不完整，属于会隐藏调度语义变化的真实问题。",
      "evidence": [
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 189,
          "lineEnd": 253,
          "symbol": "build_resource_pool"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 389,
          "lineEnd": 405,
          "symbol": "ScheduleService._run_schedule_impl"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 453,
          "lineEnd": 505,
          "symbol": "ScheduleService._run_schedule_impl"
        },
        {
          "path": "web/routes/scheduler_run.py",
          "lineStart": 64,
          "lineEnd": 74,
          "symbol": "run_schedule"
        },
        {
          "path": "templates/scheduler/batches.html",
          "lineStart": 80,
          "lineEnd": 109,
          "symbol": "content"
        },
        {
          "path": "tests/regression_schedule_summary_algo_warnings_union.py",
          "lineStart": 74,
          "lineEnd": 104,
          "symbol": "main"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "web/routes/scheduler_run.py"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "tests/regression_schedule_summary_algo_warnings_union.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/schedule_service.py",
        "web/routes/scheduler_run.py",
        "templates/scheduler/batches.html",
        "tests/regression_schedule_summary_algo_warnings_union.py"
      ],
      "recommendedNextAction": "继续检查工艺路线自动解析、批次懒生成模板以及零件创建路径里，兼容回退是否被真正暴露给用户。",
      "findingIds": [
        "resource-pool-warning-hidden-from-web"
      ]
    },
    {
      "id": "ms-silent-round2-template-autoparse",
      "title": "轮次二：工艺模板自动解析与兼容回退暴露链复查",
      "status": "completed",
      "recordedAt": "2026-04-02T17:57:19.948Z",
      "summaryMarkdown": "第二轮聚焦 `process_parts -> PartService -> RouteParser` 与 `scheduler_batches -> BatchService -> PartService` 两条“自动解析模板”链。核对后确认有两层隐藏问题叠加：第一，零件创建页在非 strict_mode 下允许填写 `route_raw` 并“尝试自动解析”，但 `PartService.create()` 如果自动 `reparse_and_save()` 失败，只会调用 `safe_warning(self.logger, ...)`，随后仍返回创建成功；而 `web/routes/process_parts.py#create_part()` 既没有把失败信息 flash 给用户，也没有给 `PartService` 传入可用 logger，`safe_warning()` 在 `logger is None` 时直接无声返回。用户最终只会看到“已创建零件”，跳到详情页后也只是看到“如果还未解析，请重新解析”的泛化提示，没有原始解析错误。第二，批次创建/重建工序链路在缺少模板时会懒触发 `_default_template_resolver()`，它调用 `PartService.upsert_and_parse_no_tx()` / `reparse_and_save()` 却不返回 `ParseResult`，使 `RouteParser.parse()` 中的兼容 warning（例如未知工种默认 external、供应商周期回退等）在 `BatchService` 层直接被丢弃；最终 `scheduler_batches.create_batch()`、`generate_ops()` 也只 flash “已创建/已重建工序”，完全不告诉用户这次模板生成是否经过兼容降级。",
      "conclusionMarkdown": "工艺模板自动解析链存在“成功态掩盖降级/失败细节”的问题，会把真实解析异常和兼容回退隐藏在后台。",
      "evidence": [
        {
          "path": "templates/process/list.html",
          "lineStart": 26,
          "lineEnd": 38,
          "symbol": "content"
        },
        {
          "path": "web/routes/process_parts.py",
          "lineStart": 67,
          "lineEnd": 79,
          "symbol": "create_part"
        },
        {
          "path": "core/services/process/part_service.py",
          "lineStart": 162,
          "lineEnd": 170,
          "symbol": "PartService.create"
        },
        {
          "path": "core/services/common/safe_logging.py",
          "lineStart": 6,
          "lineEnd": 26,
          "symbol": "safe_log/safe_warning"
        },
        {
          "path": "templates/process/detail.html",
          "lineStart": 59,
          "lineEnd": 64,
          "symbol": "content"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 121,
          "lineEnd": 125,
          "symbol": "BatchService._default_template_resolver"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 142,
          "lineEnd": 157,
          "symbol": "BatchService._load_template_ops_with_fallback"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 149,
          "lineEnd": 177,
          "symbol": "create_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 344,
          "lineEnd": 363,
          "symbol": "generate_ops"
        },
        {
          "path": "core/services/process/route_parser.py",
          "lineStart": 207,
          "lineEnd": 255,
          "symbol": "RouteParser.parse"
        },
        {
          "path": "templates/process/list.html"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "core/services/process/part_service.py"
        },
        {
          "path": "core/services/common/safe_logging.py"
        },
        {
          "path": "templates/process/detail.html"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/process/route_parser.py"
        }
      ],
      "reviewedModules": [
        "templates/process/list.html",
        "web/routes/process_parts.py",
        "core/services/process/part_service.py",
        "core/services/common/safe_logging.py",
        "templates/process/detail.html",
        "core/services/scheduler/batch_service.py",
        "web/routes/scheduler_batches.py",
        "core/services/process/route_parser.py"
      ],
      "recommendedNextAction": "最后一轮继续检查甘特图、资源排班中心以及历史摘要读取链里，是否还存在把坏数据直接洗成空集合或默认值的静默回退。",
      "findingIds": [
        "template-autoparse-degradation-hidden"
      ]
    },
    {
      "id": "ms-silent-round3-overdue-markers",
      "title": "轮次三：甘特图与资源排班中心超期标记链复查",
      "status": "completed",
      "recordedAt": "2026-04-02T18:03:27.341Z",
      "summaryMarkdown": "最后一轮沿 `schedule_history.result_summary -> GanttService/ResourceDispatchService -> rows/tasks -> template/js` 复查“超期标记”是否会被静默洗掉。确认两条链路都存在同类问题：`core/services/scheduler/gantt_service.py#GanttService._overdue_batch_ids_from_history()` 在 `json.loads()` 失败时直接 `return []`，`get_gantt_tasks()` 随后仍正常构建合同；`gantt_tasks._build_one_task()` 用该空集合把所有任务的 `meta.is_overdue` 设成 `False`，于是 `static/js/gantt_render.js` 的“仅超期”筛选、tooltip 中的“超期：是/否”、以及 `static/css/aps_gantt.css` 的红色边框都一起失效。`templates/scheduler/gantt.html` 明确告诉用户“红色边框表示超期”“可配合仅超期快速定位问题”，但坏摘要只会表现为这些信号全部消失，而不是报错或警告。资源排班中心同样如此：`extract_overdue_batch_ids()` 在摘要为空或 JSON 解析失败时直接返回 `set()`；`ResourceDispatchService._load_overdue_set()` 与 `get_dispatch_payload()` 继续生成成功载荷，`resource_dispatch_rows.normalize_dispatch_row()` 因而把所有 `is_overdue` 置空，`build_dispatch_summary()` 的 `overdue_count` 变成 `0`，最终 `templates/scheduler/resource_dispatch.html` 的“超期任务”统计卡、`static/js/resource_dispatch.js` 的超期 badge、以及日历矩阵里的红色文字全部消失。整个页面仍返回成功数据，用户只会误以为该版本没有超期任务。",
      "conclusionMarkdown": "坏 `result_summary` 目前会把甘特图与资源排班中心的超期信号静默抹平，属于能直接误导调度人员的真实风险。",
      "evidence": [
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 52,
          "lineEnd": 69,
          "symbol": "GanttService._overdue_batch_ids_from_history"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 152,
          "lineEnd": 159,
          "symbol": "GanttService.get_gantt_tasks"
        },
        {
          "path": "core/services/scheduler/gantt_tasks.py",
          "lineStart": 170,
          "lineEnd": 209,
          "symbol": "_build_one_task"
        },
        {
          "path": "templates/scheduler/gantt.html",
          "lineStart": 100,
          "lineEnd": 102,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/gantt.html",
          "lineStart": 137,
          "lineEnd": 141,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/gantt.html",
          "lineStart": 160,
          "lineEnd": 167,
          "symbol": "content"
        },
        {
          "path": "static/js/gantt_render.js",
          "lineStart": 54,
          "lineEnd": 63,
          "symbol": "applyFilters"
        },
        {
          "path": "static/js/gantt_render.js",
          "lineStart": 968,
          "lineEnd": 976,
          "symbol": "custom_popup_html"
        },
        {
          "path": "static/css/aps_gantt.css",
          "lineStart": 78,
          "lineEnd": 82,
          "symbol": "css"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_support.py",
          "lineStart": 14,
          "lineEnd": 34,
          "symbol": "extract_overdue_batch_ids"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py",
          "lineStart": 144,
          "lineEnd": 148,
          "symbol": "ResourceDispatchService._load_overdue_set"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py",
          "lineStart": 256,
          "lineEnd": 293,
          "symbol": "ResourceDispatchService.get_dispatch_payload"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py",
          "lineStart": 113,
          "lineEnd": 151,
          "symbol": "normalize_dispatch_row"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py",
          "lineStart": 253,
          "lineEnd": 279,
          "symbol": "build_dispatch_tasks"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_support.py",
          "lineStart": 46,
          "lineEnd": 84,
          "symbol": "build_dispatch_summary"
        },
        {
          "path": "templates/scheduler/resource_dispatch.html",
          "lineStart": 152,
          "lineEnd": 175,
          "symbol": "content"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 61,
          "lineEnd": 66,
          "symbol": "renderFlags"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 128,
          "lineEnd": 135,
          "symbol": "renderSummary"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 220,
          "lineEnd": 224,
          "symbol": "renderCalendar"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "core/services/scheduler/gantt_tasks.py"
        },
        {
          "path": "templates/scheduler/gantt.html"
        },
        {
          "path": "static/js/gantt_render.js"
        },
        {
          "path": "static/css/aps_gantt.css"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_support.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py"
        },
        {
          "path": "templates/scheduler/resource_dispatch.html"
        },
        {
          "path": "static/js/resource_dispatch.js"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/gantt_service.py",
        "core/services/scheduler/gantt_tasks.py",
        "templates/scheduler/gantt.html",
        "static/js/gantt_render.js",
        "static/css/aps_gantt.css",
        "core/services/scheduler/resource_dispatch_support.py",
        "core/services/scheduler/resource_dispatch_service.py",
        "core/services/scheduler/resource_dispatch_rows.py",
        "templates/scheduler/resource_dispatch.html",
        "static/js/resource_dispatch.js"
      ],
      "recommendedNextAction": "三轮静默回退复查已完成；下一步应回到运行验证与最终收口，优先复现实锤的 6 个问题，再决定最终结论。",
      "findingIds": [
        "malformed-summary-erases-overdue-signals"
      ]
    }
  ],
  "findings": [
    {
      "id": "version-parameter-normalization",
      "severity": "medium",
      "category": "other",
      "title": "版本参数归一化不一致",
      "descriptionMarkdown": "`reports` 导出链路已经把缺失、空值、非法值和 `version<=0` 统一回退到最新版本，且有回归脚本保护；但页面侧 `reports._page_version_or_latest()`、`scheduler_gantt.gantt_page/gantt_data`、`scheduler_week_plan.week_plan_page/week_plan_export`、`scheduler_analysis.analysis_page` 只校验“能否转成整数”，不会拦截 `<=0`。后续 `ReportEngine` 与 `GanttService` 会直接以 `0/-1` 查询排程表，因此页面会出现空结果、错误版本号，和导出接口的行为不一致。`week_plan_export` 还会在 `version=0` 时把结果文件名写成 `v1`，进一步放大误导。对复制链接、书签、手工改参和陈旧页面参数来说，这是直接可见的异常表现。",
      "recommendationMarkdown": "抽出统一的版本解析辅助方法，至少在所有页面与导出入口上对 `version<=0` 执行同一策略（显式拒绝或回退最新版本二选一），并补充页面侧回归用例，覆盖 `0`、负数、空值、非整数四类输入。",
      "evidence": [
        {
          "path": "web/routes/reports.py",
          "lineStart": 33,
          "lineEnd": 67,
          "symbol": "_export_version_or_latest/_page_version_or_latest"
        },
        {
          "path": "tests/regression_reports_export_version_default_latest.py",
          "lineStart": 76,
          "lineEnd": 124,
          "symbol": "main"
        },
        {
          "path": "web/routes/scheduler_week_plan.py",
          "lineStart": 99,
          "lineEnd": 145,
          "symbol": "week_plan_export"
        },
        {
          "path": "web/routes/scheduler_resource_dispatch.py",
          "lineStart": 72,
          "lineEnd": 101,
          "symbol": "_sanitize_dispatch_args_from_error/resource_dispatch_page"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py",
          "lineStart": 87,
          "lineEnd": 96,
          "symbol": "ResourceDispatchService._normalize_version"
        },
        {
          "path": "core/services/report/report_engine.py",
          "lineStart": 86,
          "lineEnd": 148,
          "symbol": "ReportEngine.overdue_batches/utilization"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 152,
          "lineEnd": 207,
          "symbol": "GanttService.get_gantt_tasks/get_week_plan_rows"
        },
        {
          "path": "data/repositories/schedule_repo.py",
          "lineStart": 105,
          "lineEnd": 153,
          "symbol": "ScheduleRepository.list_overlapping_with_details"
        },
        {
          "path": "web/routes/reports.py"
        },
        {
          "path": "tests/regression_reports_export_version_default_latest.py"
        },
        {
          "path": "web/routes/scheduler_gantt.py"
        },
        {
          "path": "web/routes/scheduler_week_plan.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/scheduler_resource_dispatch.py"
        },
        {
          "path": "core/services/report/report_engine.py"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py"
        },
        {
          "path": "data/repositories/schedule_repo.py"
        }
      ],
      "relatedMilestoneIds": [
        "ms-round3-version-chain"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "new-ui-missing-strict-mode-controls",
      "severity": "medium",
      "category": "html",
      "title": "新界面缺少严格模式入口",
      "descriptionMarkdown": "旧界面 `templates/scheduler/batches.html` 和 `templates/scheduler/batches_manage.html` 都提供了 `strict_mode` 复选框，分别用于“严格调度参数校验”和“严格工艺解析”；但新界面覆盖模板 `web_new_test/templates/scheduler/batches.html`、`web_new_test/templates/scheduler/batches_manage.html` 把这些控件删掉了。后端路由 `scheduler_run.run_schedule()`、`scheduler_batches.create_batch()`、`scheduler_batches.generate_ops()` 仍然读取并下传 `strict_mode`，`BatchService.create_batch_from_template()` 也会基于该标记决定是否允许兼容性回退。结果是 `v2` 用户永久失去这组校验开关，和 `v1` 用户的业务行为不一致：同样的数据与配置问题，在旧界面可以被强制拒绝，在新界面却只能走兼容回退。",
      "recommendationMarkdown": "把旧界面已有的 `strict_mode` 控件补回所有已覆盖的新界面批次页，并增加界面对齐回归，至少校验 `v1`/`v2` 两套页面都能提交该字段。",
      "evidence": [
        {
          "path": "web_new_test/templates/scheduler/batches.html",
          "lineStart": 202,
          "lineEnd": 227,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/batches.html",
          "lineStart": 217,
          "lineEnd": 248,
          "symbol": "content"
        },
        {
          "path": "web_new_test/templates/scheduler/batches_manage.html",
          "lineStart": 15,
          "lineEnd": 65,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/batches_manage.html",
          "lineStart": 15,
          "lineEnd": 73,
          "symbol": "content"
        },
        {
          "path": "web/routes/scheduler_run.py",
          "lineStart": 33,
          "lineEnd": 47,
          "symbol": "run_schedule"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 149,
          "lineEnd": 175,
          "symbol": "create_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 344,
          "lineEnd": 360,
          "symbol": "generate_ops"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 415,
          "lineEnd": 471,
          "symbol": "BatchService.create_batch_from_template"
        },
        {
          "path": "web_new_test/templates/scheduler/batches.html"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "web_new_test/templates/scheduler/batches_manage.html"
        },
        {
          "path": "templates/scheduler/batches_manage.html"
        },
        {
          "path": "web/routes/scheduler_run.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/routes/scheduler_gantt.py"
        },
        {
          "path": "core/services/common/safe_logging.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web_new_test/templates/base.html"
        }
      ],
      "relatedMilestoneIds": [
        "ms-round3-new-ui-and-logging"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "request-scope-app-logger-missing",
      "severity": "low",
      "category": "maintainability",
      "title": "请求级应用日志未绑定",
      "descriptionMarkdown": "`create_app_core()` 会创建 `app_logger` 并把处理器挂到 `app.logger`，但请求生命周期中的 `_open_db()` 只写入了 `g.db` 与 `g.op_logger`，没有把应用日志对象写入 `g.app_logger`。与此同时，网页层大量服务构造仍以 `logger=getattr(g, 'app_logger', None)` 传参，因此这些服务在请求内拿到的文件日志对象恒为 `None`。结合 `safe_logging.safe_log()` 对 `None` 直接返回、以及 `schedule_optimizer_steps.py` 等代码里的 `if logger:` 分支，许多“已忽略但需要排障”的告警会完全丢失，现场只剩数据库操作留痕或什么都没有。该问题不会立刻改坏业务结果，但会明显削弱 Windows 单机现场的故障定位能力。",
      "recommendationMarkdown": "在 `_open_db()` 中显式绑定 `g.app_logger = current_app.logger`（或统一改为直接传 `current_app.logger`），并为至少一个会进入可选告警分支的页面链路补一条回归，防止再次出现静默失联。",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 216,
          "lineEnd": 224,
          "symbol": "create_app_core"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 279,
          "lineEnd": 281,
          "symbol": "_open_db"
        },
        {
          "path": "web/routes/scheduler_gantt.py",
          "lineStart": 55,
          "lineEnd": 63,
          "symbol": "gantt_page"
        },
        {
          "path": "core/services/common/safe_logging.py",
          "lineStart": 6,
          "lineEnd": 22,
          "symbol": "safe_log"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 193,
          "lineEnd": 201,
          "symbol": "_run_ortools_seed"
        },
        {
          "path": "web_new_test/templates/scheduler/batches.html"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "web_new_test/templates/scheduler/batches_manage.html"
        },
        {
          "path": "templates/scheduler/batches_manage.html"
        },
        {
          "path": "web/routes/scheduler_run.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/routes/scheduler_gantt.py"
        },
        {
          "path": "core/services/common/safe_logging.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web_new_test/templates/base.html"
        }
      ],
      "relatedMilestoneIds": [
        "ms-round3-new-ui-and-logging"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "resource-pool-warning-hidden-from-web",
      "severity": "medium",
      "category": "other",
      "title": "资源池降级告警未向页面用户显示",
      "descriptionMarkdown": "`build_resource_pool()` 失败时会把自动分配资源池直接降级为关闭，并生成“自动分配资源池构建失败，已降级为不自动分配” warning；`ScheduleService` 也会把这条 warning 合并进 `summary.warnings` 与历史摘要。但 `scheduler_run.run_schedule()` 只对 `【冻结窗口】`、`【停机】` 两类前缀做 flash，`templates/scheduler/batches.html` 也不显示 warning 列表，导致用户在主排产页面看到的仍然是普通成功提示，而不是“本次排产已关闭 auto-assign”的明确信号。对缺省资源较多的工单，这会直接改变排产结果，却没有同步暴露给主操作路径。",
      "recommendationMarkdown": "不要用前缀白名单筛掉非冻结/非停机的降级 warning；至少把资源池降级、自动分配关闭这类 warning 也展示到排产完成后的页面反馈中，或在“最近一次排产”卡片中增加 warning 摘要。",
      "evidence": [
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 189,
          "lineEnd": 253,
          "symbol": "build_resource_pool"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 389,
          "lineEnd": 405,
          "symbol": "ScheduleService._run_schedule_impl"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 453,
          "lineEnd": 505,
          "symbol": "ScheduleService._run_schedule_impl"
        },
        {
          "path": "web/routes/scheduler_run.py",
          "lineStart": 64,
          "lineEnd": 74,
          "symbol": "run_schedule"
        },
        {
          "path": "templates/scheduler/batches.html",
          "lineStart": 80,
          "lineEnd": 109,
          "symbol": "content"
        },
        {
          "path": "tests/regression_schedule_summary_algo_warnings_union.py",
          "lineStart": 74,
          "lineEnd": 104,
          "symbol": "main"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "web/routes/scheduler_run.py"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "tests/regression_schedule_summary_algo_warnings_union.py"
        }
      ],
      "relatedMilestoneIds": [
        "ms-silent-round1-scheduler-warning-surface"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "template-autoparse-degradation-hidden",
      "severity": "medium",
      "category": "other",
      "title": "模板自动解析降级结果未向用户显式暴露",
      "descriptionMarkdown": "零件创建和批次懒生成模板两条链路都会触发工艺路线自动解析，但当前实现把解析失败与兼容回退都压成了“成功态”。`PartService.create()` 在非 strict_mode 下若自动解析失败，只写一条 `safe_warning()` 后继续返回创建成功；而 `create_part()` 没有传 logger，也没有 flash 失败细节，导致这条 warning 实际会静默丢失。详情页也仅显示“如果还未解析，请重新解析”的泛化提示，没有原始错误。与此同时，`BatchService._default_template_resolver()` 直接丢弃 `upsert_and_parse_no_tx()/reparse_and_save()` 返回的 `ParseResult`，使 `RouteParser` 在兼容模式下产生的 warning 无法继续传到 `create_batch()` / `generate_ops()` 的页面反馈。用户可能以为模板和工序都是正常生成的，实际上内部/外协归类、外协周期等关键语义已经被兼容逻辑改写。",
      "recommendationMarkdown": "把自动解析的 warning/error 显式回传到网页层：零件创建至少在成功 flash 后补一条“解析失败/已兼容回退”的 warning；批次懒生成模板则不要丢弃 `ParseResult`，应把 warning 列表透传给 `create_batch()` / `generate_ops()` 页面反馈。",
      "evidence": [
        {
          "path": "templates/process/list.html",
          "lineStart": 26,
          "lineEnd": 38,
          "symbol": "content"
        },
        {
          "path": "web/routes/process_parts.py",
          "lineStart": 67,
          "lineEnd": 79,
          "symbol": "create_part"
        },
        {
          "path": "core/services/process/part_service.py",
          "lineStart": 162,
          "lineEnd": 170,
          "symbol": "PartService.create"
        },
        {
          "path": "core/services/common/safe_logging.py",
          "lineStart": 6,
          "lineEnd": 26,
          "symbol": "safe_log/safe_warning"
        },
        {
          "path": "templates/process/detail.html",
          "lineStart": 59,
          "lineEnd": 64,
          "symbol": "content"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 121,
          "lineEnd": 125,
          "symbol": "BatchService._default_template_resolver"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 142,
          "lineEnd": 157,
          "symbol": "BatchService._load_template_ops_with_fallback"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 149,
          "lineEnd": 177,
          "symbol": "create_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 344,
          "lineEnd": 363,
          "symbol": "generate_ops"
        },
        {
          "path": "core/services/process/route_parser.py",
          "lineStart": 207,
          "lineEnd": 255,
          "symbol": "RouteParser.parse"
        },
        {
          "path": "templates/process/list.html"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "core/services/process/part_service.py"
        },
        {
          "path": "core/services/common/safe_logging.py"
        },
        {
          "path": "templates/process/detail.html"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/process/route_parser.py"
        }
      ],
      "relatedMilestoneIds": [
        "ms-silent-round2-template-autoparse"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "malformed-summary-erases-overdue-signals",
      "severity": "medium",
      "category": "other",
      "title": "坏摘要会静默抹掉超期信号",
      "descriptionMarkdown": "甘特图与资源排班中心都把“超期”判定建立在 `schedule_history.result_summary` 的历史摘要上，但两条读取链在摘要损坏时都会直接回空集合而不发出任何信号。`GanttService._overdue_batch_ids_from_history()` 捕获 `json.loads()` 异常后返回 `[]`，`extract_overdue_batch_ids()` 也在解析失败时返回 `set()`；后续任务/行对象照常生成，只是所有 `is_overdue` 都变成 `False`。结果是甘特图上的红色边框、仅超期筛选、tooltip 的超期说明，以及资源排班中心里的超期统计卡、明细 badge、日历矩阵红字都会一起消失，而页面仍显示为成功加载。对调度员来说，这不是“功能小降级”，而是把真实存在的超期任务伪装成“无超期”的错误状态。",
      "recommendationMarkdown": "不要把摘要解析失败直接等价为“无超期”。至少应记录 warning/logger，并把“历史摘要损坏，超期标记可能不完整”的信号带到页面；更稳妥的是在合同里显式返回 `summary_parse_error` 一类标记，让甘特图和资源排班中心显示降级提示，而不是静默清零。",
      "evidence": [
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 52,
          "lineEnd": 69,
          "symbol": "GanttService._overdue_batch_ids_from_history"
        },
        {
          "path": "core/services/scheduler/gantt_service.py",
          "lineStart": 152,
          "lineEnd": 159,
          "symbol": "GanttService.get_gantt_tasks"
        },
        {
          "path": "core/services/scheduler/gantt_tasks.py",
          "lineStart": 170,
          "lineEnd": 209,
          "symbol": "_build_one_task"
        },
        {
          "path": "templates/scheduler/gantt.html",
          "lineStart": 100,
          "lineEnd": 102,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/gantt.html",
          "lineStart": 137,
          "lineEnd": 141,
          "symbol": "content"
        },
        {
          "path": "templates/scheduler/gantt.html",
          "lineStart": 160,
          "lineEnd": 167,
          "symbol": "content"
        },
        {
          "path": "static/js/gantt_render.js",
          "lineStart": 54,
          "lineEnd": 63,
          "symbol": "applyFilters"
        },
        {
          "path": "static/js/gantt_render.js",
          "lineStart": 968,
          "lineEnd": 976,
          "symbol": "custom_popup_html"
        },
        {
          "path": "static/css/aps_gantt.css",
          "lineStart": 78,
          "lineEnd": 82,
          "symbol": "css"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_support.py",
          "lineStart": 14,
          "lineEnd": 34,
          "symbol": "extract_overdue_batch_ids"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py",
          "lineStart": 144,
          "lineEnd": 148,
          "symbol": "ResourceDispatchService._load_overdue_set"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py",
          "lineStart": 256,
          "lineEnd": 293,
          "symbol": "ResourceDispatchService.get_dispatch_payload"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py",
          "lineStart": 113,
          "lineEnd": 151,
          "symbol": "normalize_dispatch_row"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_support.py",
          "lineStart": 46,
          "lineEnd": 84,
          "symbol": "build_dispatch_summary"
        },
        {
          "path": "templates/scheduler/resource_dispatch.html",
          "lineStart": 152,
          "lineEnd": 175,
          "symbol": "content"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 61,
          "lineEnd": 66,
          "symbol": "renderFlags"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 128,
          "lineEnd": 135,
          "symbol": "renderSummary"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 220,
          "lineEnd": 224,
          "symbol": "renderCalendar"
        },
        {
          "path": "core/services/scheduler/gantt_service.py"
        },
        {
          "path": "core/services/scheduler/gantt_tasks.py"
        },
        {
          "path": "templates/scheduler/gantt.html"
        },
        {
          "path": "static/js/gantt_render.js"
        },
        {
          "path": "static/css/aps_gantt.css"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_support.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_service.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py"
        },
        {
          "path": "templates/scheduler/resource_dispatch.html"
        },
        {
          "path": "static/js/resource_dispatch.js"
        }
      ],
      "relatedMilestoneIds": [
        "ms-silent-round3-overdue-markers"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:8f6e9302ff6f292c6993194de2538ec61268395867017152437d4f80338a71fd",
    "generatedAt": "2026-04-02T18:03:27.341Z",
    "locale": "zh-CN"
  }
}
```
