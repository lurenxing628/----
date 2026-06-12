---
doc_type: architecture
slug: ARCHITECTURE
scope: 项目架构总入口，覆盖 APS 整体结构、核心模块索引、关键架构决定和长期交付边界
summary: APS 在 Win7 x64、Python 3.8、离线交付约束下的系统地图入口
status: current
created: 2026-04-27
last_reviewed: 2026-06-12
tags: [aps, codestable, architecture, win7]
depends_on: []
implements: []
---

# 回转壳体单元智能排产系统（APS）架构总入口

> 状态：CodeStable 现状索引
> 创建日期：2026-04-27

## 1. 项目简介

本项目是面向 Win7 x64 离线单机与共享数据场景的本地 APS 智能排产系统。系统目标是在目标机不安装 Python、不依赖外网的前提下，完成基础资料维护、Excel 导入导出、批次排产、结果查看、报表导出、备份恢复和现场交付。

当前开发与打包基线保持在 Python 3.8，并继续服从 Win7 兼容边界。正式交付时，目标机通过安装包和本地浏览器运行时访问 APS 页面。

## 2. 核心概念 / 术语表

- APS：围绕批次、工序、设备、人员、日历、齐套约束和排产策略组织的智能排产系统。
- 界面：`templates/` 与 `static/` 下的统一侧栏布局页面体系（2026-06 双轨退役后唯一界面；历史上的经典/现代双轨与 `web_new_test/` 覆盖层已删除，决策见 compound ADR v2-sidebar-shell-promotion）。
- Win7 交付边界：目标机不要求安装 Python，页面和静态资源随应用本地交付，依赖升级必须考虑 Python 3.8 与 Win7。

## 3. 子系统 / 模块索引

- `core/`：核心领域、算法、基础设施、服务与插件运行框架。
- `data/`：数据访问层。
- `web/`：Flask 启动、路由、页面装配、界面模式与 viewmodel。
- `templates/`、`static/`：页面模板与本地静态资源。
- `templates_excel/`：交付 Excel 模板。
- `plugins/`：自研插件目录，当前插件默认关闭。
- `tests/`：自动化测试。
- `tools/`、`scripts/`：质量门禁、治理台账、辅助检查脚本。
- `开发文档/`、`audit/`、`evidence/`：开发说明、审计记录和验证证据。
- `.codestable/architecture/ui-gantt.md`：甘特图结果查看页面、缩放协议、只读边界、模拟预览身份传递和本地 Frappe 补丁治理现状。
- 车间执行事件基础：`OperationExecutionEvents`、执行事件仓储、执行反馈服务和执行状态读模型记录现场开工、暂停、继续、完工、报异常这些事实。
- 资源派工现场记录：资源派工页用户入口叫“现场记录”，支持单条填写实际情况、下载填写模板、导入实际情况 Excel；普通页面是一键导入，后台先整批检查，有错不写库并返回错误明细，无错才事务写入；route 拆在 `scheduler_resource_dispatch_execution_routes.py`，业务编排拆在 `resource_dispatch_actual_*` service 文件。页面把计划员查看排班和计划员代录现场事实分成两个区域；执行区 JS 按 context、cards、actual、import 和 coordinator 拆分，任务卡公开图号/物料、计划/实际时间偏差，执行流水把 `created_at/source_table` 转成中文记录时间和来源。
- 重排执行事实快照：普通重排和甘特模拟方案发布在写新正式计划前，都会按同一批工序复算现场状态，现场状态变化时拒绝写入。
- APS 工作台上下文链接合同：`web/viewmodels/scheduler_workbench_links.py` 统一封装工作台计划上下文、跨页链接、中文标签映射和现场写入地址护栏；`web/viewmodels/scheduler_workbench_link_query.py` 集中维护各目标页要带的版本、方案、日期、批次和资源参数矩阵；`core/services/scheduler/resource_dispatch_page_context.py` 装配资源派工页面的版本、方案身份、筛选条件和可查询状态等只读查询上下文；`web/routes/domains/scheduler/scheduler_resource_dispatch.py` 接线资源派工只读复盘入口和写入入口状态。第 1 阶段已用于排产分析候选方案跳转、周计划入口、资源派工现场记录写入口控制和现场记录二级接口公开身份脱敏，避免这些页面各自拼 URL 时丢版本、方案、日期、批次或资源对象，也避免把内部计划身份交给前端当作写入凭证。壳层另有计划上下文胶囊（fusion-plan-context-capsule，契约 4.2）：`templates/base.html` top-header 常驻一行「版本 · 方案身份 · 生成时间 · 策略 · 数据范围」只读回显，`web/viewmodels/plan_context_capsule.py` 装配、模板全局 `workbench_plan_capsule` 注入；`build_workbench_plan_context` 扩 `generated_at_label/strategy_label` 两公开字段（_UNSET sentinel 区分「未喂参显示 -」与「喂了缺失值走词表缺失态」），6 个发布点（首页/甘特/分析/周计划/报表/资源派工）喂 raw 值、label 转换只在合同内一处；无 version 页面零渲染，URL 直入页面两项显示「-」不查库补。
- 顶层计划工作台入口：唯一壳 `templates/base.html`（2026-06 双轨退役后的侧栏壳）top-header 内挂载 `ui.workbench_nav_menu()`（包 `<nav class="top-header-workbench">`，因菜单链接样式选择器要求 nav 祖先）；宏定义在 `templates/components/ui_macros.html`，样式在 `static/css/ui_contract.css`，浅色/暗色 header 适配在 `static/css/style.css` 的「V1 收编区」。它用原生 `<details>/<summary>` 展开“计划工作台”快捷菜单，提供首页值班台、报表中心、排产分析、设备甘特图、人员甘特图、资源派工、计划和现场实际 7 个只读页面入口；不新增独立工作台页面，不依赖外部 JS/CSS，不输出现场记录写入、Excel 导入、模板下载或表单写入地址。门禁 `tests/web_pages/test_workbench_nav_entry_contract.py` 断言挂载结构与默认真渲染。
- 首页计划员值班台：首页 `templates/dashboard.html` 由 `web/routes/dashboard.py` 读取最新排产、正式采用方案范围、今日计划任务和现场事实，再交给 `web/viewmodels/dashboard_workbench.py` 与 `web/viewmodels/dashboard_workbench_cards.py` 生成风险卡、今日待处理和快捷入口。「当前查看排产」卡的时间由路由侧 `format_public_datetime` 单点格式化为公开口径（坏值显示“时间记录异常”、缺失显示“-”），模板只消费 `latest_history_time_display`，不裸渲染 DB 的 `schedule_time`。首页值班台只展示实时生成的待处理，不保存已处理状态，不直接写现场记录，不新增数据库表，不改排产算法；所有跨页动作继续使用 `WorkbenchLink`，页面只显示中文计划身份和中文业务文案，内部字段只留在 URL、隐藏参数或服务端日志里。现场事实读取失败时，首页显示“现场情况暂时读不到”这类数据缺口提醒，不把读取失败误判成“现场情况待确认”。首页顶部另有备份健康提示：`web/viewmodels/dashboard_backup_health.py` 纯只读扫描备份目录（不实例化 BackupManager，避开其建目录副作用）取 `aps_backup_*.db` 最大 mtime，超 `BACKUP_STALE_DAYS=7` 个日历日或从未备份时渲染琥珀 `ui.notice`，备份目录读取失败时明示“备份状态读取失败”而非静默装健康；健康时零渲染（fusion-backup-health-hint）。
- 排产分析行动入口：`web/routes/domains/scheduler/scheduler_analysis.py` 在候选方案链接绑定后调用 `web/viewmodels/scheduler_analysis_action_hub.py`，把已有推荐结论、代表方案摘要、诊断摘要和下一步入口整理成首屏行动区；`templates/scheduler/analysis_parts/_action_hub.html` 展示该行动区，`templates/scheduler/analysis.html` 的选中版本顺序为版本身份、行动区、告警、详细方案对比、完整诊断、指标、优化过程。行动区只复用已有 `candidate_comparison_display`、`diagnostic_sections` 和 `WorkbenchLink`，不重算候选方案、不改算法、不新增数据库，也不把候选方案变成可写现场记录入口。
- 甘特任务详情区：`/scheduler/gantt/data` 由 `GanttService` 读取排程明细，并通过 `ExecutionFactProvider` 按 `op_id` 聚合现场执行事实；`core/services/scheduler/gantt_tasks.py` 输出公开任务标题、计划时间、现场实际小结、超期提示和资源/工序/图号字段；`web/viewmodels/scheduler_gantt_task_detail.py` 追加资源派工、计划和现场实际、超期清单链接；`static/js/gantt_render.js` 点击任务后刷新 `#ganttTaskDetail`，`static/js/gantt_popup.js` 继续维护旧弹窗和新详情区。详情区和旧弹窗只展示公开字段，关键链 edge 保留内部 `from/to` 做连线，同时用 `from_label/to_label` 给用户看，避免缺 `op_code` 时把 `op_<数字>` 露出来。现场事实可视化（fusion-gantt-execution-visuals，契约 4.10）：`gantt_tasks._execution_visuals` 以 `has_execution_record` 为门槛产出条形视觉——progress 只允许 completed→100（红线禁部分进度估算伪装精度），`custom_class` 按四态白名单 frozenset{processing/paused/exception/completed} 追加 `execution-<status>`（词表 not_started 与未知码零类，DOM 不收垃圾串；raw 状态码只在服务端消费一次，meta 仍只出中文公开标签）；无事实=计划行 payload 原样（preview/候选身份永远无事实自动满足）。视觉通道分离：fill 归四种配色模式（--aps-bar-color inline），完工=半透明绿罩接管 `.bar-progress`（普通/hover/active 三态选择器一组写齐，否则 frappe 默认紫会在悬停时闪回），processing/paused/exception=描边 accent 且选择器自带 `:not(.overdue)` 守卫（超期红边优先由选择器语义保证、不依赖书写顺序），暗色主题块内重申描边规则（dark 基础 .bar stroke 特异性更高会盖掉）；零新增裸 hex 全走 --ui-* token。侧栏详情补优先级/加工方式/时长三行、popup 补现场摘要一行（双向互缺收口），图例标记行含四执行状态样例。CSS 写法由 tests/gantt/test_gantt_execution_visuals_contract.py 正则锁选择器+token 值。
- 周计划页增强（fusion-week-plan-enrich，契约 4.6 容量口径首个落地实例）：`core/services/scheduler/gantt_week_plan.py` 的 `build_week_plan_rows` 在 `_split_by_day` 拆分前按 `op_id` 注入「现场状态」列（拆分后段行丢 op_id），词表走 `core/models/operation_execution_labels` 单源，同工序跨日段行同状态；调用方不提供事实显示「-」，提供后无事实的计划行显示「待开工」（没有事实=尚未开工，不是数据缺口）。函数改双返回 `(BuildOutcome, minutes_by_date)`——按日聚合分钟数走旁路不进段行 dict，公开段行恰好八个中文键零内部字段。每日合计行由 `core/services/scheduler/week_plan_daily_summary.py` 装配（路由层调用、calendar 取 `g.services.calendar_service`，gantt_service 零 calendar 接触）：容量分母=正午采样的 `shift_hours×efficiency`，禁直调 `calculations.capacity_hours`（其 midnight 采样在跨午夜班次把当日容量归属前一日，测试 grep 守卫钉死）；页面汇总条固定明示「容量按全局工作日历估算，未按单台设备/单人细分」，容量 0 或算不出时显示「利用率暂时算不了」诚实降级；Excel 导出同列但不含合计行（合计是页面阅读辅助，不破坏导出行语义）。空周提示升级在 `web/routes/domains/scheduler/scheduler_week_plan_preview.py`（从路由文件拆出的纯装配模块）：版本有计划行时按 `plan_role_resolution` 的真实方案身份（selected_role/scenario_id 透传，不误当 adopted）查计划区间并给「跳到计划区间」WorkbenchLink；无计划行版本保持现有空文案零跳转；坏时间过滤态清空跳转链接（问题是数据不是选错周）；span 读取失败 logger.warning 留痕回落，不把锦上添花变成新故障点。周派工单打印（fusion-dispatch-print-sheet，模块 N）：`/scheduler/week-plan/print` 独立打印路由（`scheduler_week_plan_print.py` 新文件+registrar 登记），复用周计划全量行经 `core/services/scheduler/week_plan_print_sheet.py` 纯函数按设备/人员展示串重分组（段内自带 日期→时段 排序——上游排序键无时段；「外协 {supplier}」串无 supplier_id 且供应商名无唯一约束，双视图外协/未派行统一归「外协/未分配」兜底段排最后防重名错并组）；行只含 7 个计划字段+空白备注列，「现场状态」刻意不进纸（4.11：纸面零现场事实，纸上状态会立刻过期误导）；模板独立不 extends base.html，段页眉放 thead（跨物理纸每页重复版本·方案身份·生成时间·范围·筛选条件），`is_current_executable_official_version` 为假即印「历史正式方案，已被新版本替代/非正式方案，不得下发执行」警示进纸面（只看 selected_role 会漏历史正式方案——正撞贴旧纸误用）；group_by/day 参数错误 ValidationError 明示不静默回落；全仓首个 `window.print()` 调用方。
- 报表工作台回跳：`/reports/`、超期、资源负荷、计划和现场实际、停机影响由 `web/viewmodels/scheduler_reports_workbench.py` 统一装配入口卡、页面级链接、行级动作和保守空状态，并继续复用 `WorkbenchLink` 保留版本、方案、计划身份、返回地址、日期、批次和资源上下文；排产主导航、报表顶部导航、报表筛选隐藏字段和全局计划工作台导航由 `web/viewmodels/scheduler_navigation_links.py` 统一从当前请求生成，模板不再手拼 URL，带上下文进入“首页值班台”也不会丢 plan_id 或 back_to。`ReportEngine`、`execution_review`、`schedule_plan_query_service` 和 `schedule_plan_query_repo` 承接底层过滤，页面和 Excel 导出共用同一批 `batch_id`、`resource_type`、`resource_id` 条件，并把资源负荷、停机影响和计划实际复盘的批次/资源条件下推到计划明细 SQL，避免只把 URL 做好看而数据没过滤。当前 `resource_type/resource_id` 主资源筛选只支持设备和人员，班组上下文进入首页值班台、排产分析、周计划和报表类目标时会禁用链接，不生成会跳 400 的 URL；资源派工继续使用 `scope_type/scope_id/team_id` 保留班组上下文；甘特图不携带班组筛选。排产分析、甘特和周计划通过 `scheduler_navigation_publish.py` 发布导航上下文时，会复制服务端方案身份护栏字段，并把报表行跳转带来的批次和资源范围继续发布给顶部导航，避免旧正式版本、对比方案、模拟预览误启用计划和现场实际入口，也避免用户从具体批次/资源跳转后再导航回全量范围。资源派工现场实际写入地址由 `scheduler_resource_dispatch_query.py` 按服务端归一化 filters 生成，前端不再用裸路径叠加地址栏原始查询串来补 `query_date` 等关键上下文。报表展示、执行复盘、延期诊断遇到坏数字时抛 `ValidationError`，导出行数和阈值额外拒绝负数和小数，不静默按 0 处理；计划和现场实际仍只复盘正式采用方案；停机影响第一版只做设备级说明和设备级回跳，不做任务级明细；内部追踪字段只留在请求参数或服务端内部，不进入页面正文、普通 HTML 属性、导出表头或公开 payload。排产历史页行级 5 链接与排产分析版本选择器两条甘特链也已收编入 `WorkbenchLink`（fusion-handrolled-links-adoption）：历史行由路由层逐版本读 adopted 计划日期跨度（先分页后装配、同版本缓存去重、单行坏历史只禁用该行并明示原因），`web/viewmodels/system_history_links.py` 纯数据变换装配；分析选择器用 `resolve_navigation_plan_context` 全量方案身份装配，场景预览跳甘特保留 `scenario_id` 不再掉回正式视角，裸模拟预览禁用明示。`TARGET_PAGE_PATHS` 扩至 13 目标：`history`（version 可选筛选）与 `batch_detail`（路径参数型目标，`{batch_id}` 占位 quote 替换、缺参 fail-loud）；两目标的 query 合同（version 可选+back_to / 仅 back_to）由 extra_params 禁键集守护，不可被调用方绕过。
- 系统管理运行日志与诊断包：`/system/runtime-logs` 运行日志页只读查看 logs/ 文件日志（aps_error.log 默认/aps.log/launcher.log 三文件白名单严格匹配，与「操作日志」的业务审计语义并列不合并），读取层 `core/services/system/runtime_log_reader.py` 纯函数做字节层尾读+时间戳锚点切分+UTF-8 边界处理+超长条目弃中段巡锚（256KB 内存上限/4MB 巡锚 IO 预算），刻意不提供删除/清空（报错证据由轮转管大小）；`/system/runtime-logs/diagnostic-package` 一键诊断包白名单收 `*.log`+数字分卷+显式 aps_launch_error.txt 并附环境信息与最近 200 条操作日志，结构性排除 aps_secret_key.txt 且拒 symlink（安全测试 `tests/web_pages/test_diagnostic_package_security.py` 双登记进 required 守卫）；临时 zip 走 mkstemp→os.close→send_file(direct_passthrough=False)→call_on_close 清理的生命周期；错误页（templates/error.html 与 error_boundary minimal 兜底）显示与日志同格式的发生时刻并以裸路径接门运行日志页。
- 排产词表唯一字源（fusion-label-single-source，2026-06-12）：result_status/strategy 的中文词表唯一字源在 `web/viewmodels/scheduler_summary_result_state.py`（`result_status_display_labels()` 展示字典 + `resolve_result_status()` 别名归一——ok/fail 是历史库输入别名不进展示字典，ok2 死键已删走 unknown 诚实降级「有问题，需检查」）与 `scheduler_history_summary.py::_STRATEGY_LABELS`（4 配置合法值 + manual/improve/greedy 历史展示兼容值）；模板一律消费 `decorate_history_version_options` 行级标签（result_status_label/strategy_label），禁止内联中文字典（回潮守卫 `tests/web_pages/test_label_single_source_contract.py`，required）；概念身份证见 `.codestable/semantics/concept-registry.yaml` 的 schedule_result_status / schedule_strategy 两条（check_concept_registry.py 对账）。
- 设计令牌单一真相源（fusion-tokens-single-source，2026-06-12）：`static/css/00-tokens.css` 是全仓唯一允许新增裸 hex 的 CSS 文件（base.html 链首加载）——五段结构：--ui-* 语义层（2026-06-12 语义色三值合一定版 success #16a34a/warning #d97706/danger #dc2626）、壳层结构 token（sidebar/--font-family 等原名）、暗色纯 token 重赋值块（非 token 特例红线 ≤10）、迁移期别名块（--primary-color/--aps-* 映射 var(--ui-*)，hex-migration 后评估删除）；其余 CSS 的裸 hex 由 `tests/web_pages/test_css_token_source_contract.py` per-file 冻结白名单守卫（只降不升）；负荷阈值唯一真相源在 `web/viewmodels/dashboard_workbench_cards.py` 的 LOAD_WARNING_RATIO/LOAD_DANGER_RATIO（CSS 只消费 severity-* 类名）；全局 :focus-visible 焦点环已上岗（ui_contract.css 末尾）。
- 改版基线三件套（fusion-anchor-baseline-prep，2026-06-12）：`.codestable/roadmap/aps-frontend-fusion/drafts/anchor-baseline.md` 是动模板/静态 feature 开工前必查的 LIVE 导览档——六类高危测试锚（dashboard 正则/EXPECTED_PAGE_SIGNALS/language_polish 依赖面/全模板扫描/manual 系脚本/CDP 探针 JS 硬锚）+ 缓存税机制 + 打印介质回归清单，每节附可重跑命令；亮/暗双主题截图基线由手跑工具 `tests/_scripts_e2e/capture_ui_baseline.py`（CDP Page.captureScreenshot，复用几何探针管线）产出 `output/ui_baseline/<时间戳>/` 40 张 PNG（不入 git，人工 A/B 比对，刻意无像素 diff 门禁）；print.css 隐藏名单含 `.sidebar`（2026-06-12 修复打印侧栏占位缺陷，`tests/web_pages/test_print_css_contract.py` 防回潮）。
- 工作台主流程回归保护：第一版工作台主流程由 `tests/regression_aps_workbench_flow_contract.py` 锁住“首页值班台 -> 分析 / 甘特 / 资源派工 / 报表 / 计划和现场实际”的用户路线，`tests/regression_scheduler_historical_plan_label_contract.py`、`tests/regression_scheduler_plan_identity_summary_guardrail.py` 和 `tests/regression_web_silent_fallback_contract.py` 锁住历史正式方案、缺失版本、坏摘要、非正式方案不能冒充当前可执行正式方案；`tests/ui_geometry_contract_data.py` 维护关键页面几何路径，`tools/test_registry_data.py` 与 `tools/test_registry_groups_scheduler.py` 负责把这些回归纳入质量门禁登记。测试只证明第一版主流程和护栏现状，不代表第二阶段的现场事实延期解释、甘特资源负荷摘要、停机任务级明细或牵连订单影响面已经完成。

## 4. 关键架构决定

- CodeStable 从 2026-04-27 起作为新的 AI 协作工作流入口。
- `.limcode/` 暂不删除，保留为旧工作流归档、历史计划、历史审查和 APS 专项技能资料库。
- 新增功能、问题修复、重构、知识沉淀等新工作默认落到 `.codestable/` 下；只有需要引用历史资料或 APS 专项技能时，再回看 `.limcode/`。

## 5. 已知约束 / 硬边界

- 面向用户默认使用简体中文。
- Win7 x64、Python 3.8、离线交付是长期约束。
- 页面、导出、文件名、提示语和帮助文档不能直接展示 `scenario_id`、`plan_role`、`source_table`、`candidate_id` 这类程序内部字段；这些字段可以留在 URL、隐藏字段、请求参数和日志里用于对齐同一套计划，但用户可见位置必须转成中文大白话。
- 报表和工作台页面同样不能在正文、按钮、普通 HTML 属性、导出列或公开 payload 里展示 `op_id`、`schedule_id` 这类工序内部定位字段；需要跨页定位时优先使用批次、设备、人员、日期这些业务对象。
- 非正式方案、候选方案、模拟预览和历史正式方案不能下发现场记录写入入口、Excel 导入地址或模板下载地址。后端校验仍是最后防线，但页面层也要避免让用户看到“好像能写”的入口。
- 资源派工导出当前同时提供矩阵表和日历明细表：矩阵表用于看资源与日期的大盘，`日历明细` 按一条日历任务一行展开，继续只展示中文业务字段，不展示 `op_id`、`schedule_id`、`state_revision`、`execution_snapshot_revision` 等内部追踪字段。当前证据在 `core/services/scheduler/resource_dispatch_excel.py` 和 `tests/regression_resource_dispatch_public_output_contract.py`。
- 质量门禁入口仍以仓库现有 `scripts/run_quality_gate.py` 为准。
- 旧 `.limcode/plans/`、`.limcode/review/` 里有大量历史上下文，迁移初期不得批量删除或搬动。

## 6. 排产工序图分析现状

- `core/services/scheduler/graph/` 是排产工序图的内部分析模块，当前负责把已整理好的待排工序转成图节点、构建同批次前后工序边、校验 DAG / 环、计算拓扑顺序、关键路径和节点指标，并导出普通 dict 摘要。
- `graph_analysis_mode=off` 是默认关闭模式。关闭时排产主链不导入图模块，不要求安装 NetworkX，也不会在 `result_summary` 里写 `graph_analysis`。
- `graph_analysis_mode=report` 已作为旁路报告接入 `core/services/scheduler/run/schedule_orchestrator.py`。接入点在原排产算法已经算完、`validated_schedule_payload` 已经生成之后，图报告判断、错误投影和采样投影收在 `core/services/scheduler/run/schedule_graph_report.py`，只读取 `ScheduleRunInput.cfg`、`algo_ops_to_schedule`、`batches` 和 `resource_pool`。
- report 模式只把公开小摘要写进 `result_summary["algo"]["graph_analysis"]`，把采样诊断写进 `result_summary["diagnostics"]["graph_analysis"]`。OperationLogs 沿用现有 `detail["algo"]` 小摘要路径，因此只能看到 `algo.graph_analysis`，不能看到完整 nodes、edges、node_metrics、topological_order 或 raw 对象。
- `graph_analysis_mode=on` 当前已经接入 PR-5 ready 队列和 PR-6 图评分：可用 DAG 会在 optimizer 前生成 plain `graph_ready_context`，SGS 候选集合只从图 ready 工序里取；当 `graph_critical_weight` 或 `graph_impact_weight` 大于 0 时，图模块会计算 full `node_metrics`，在 service 层预先转成 `graph_priority_key_by_op_id`，算法层只拼普通 tuple，不反向依赖 scheduler service。`on + 有环 + graph_block_on_cycle=yes` 会在 version 分配前阻止排产；`on + 有环 + graph_block_on_cycle=no` 会继续旧 SGS 逻辑，但 public 摘要会写明图增强和图评分未启用。候选方案链路已经接入 3/5/7 档权重试跑、自动选择、候选落库和代表三方案页面切换；第一版只承诺正式采用方案、原算法代表方案和重点工序优先代表方案的查看与对比，不承诺全候选明细大屏、任意两方案自由对比、批次级或资源级差异清单。

## 7. 车间执行事件基础现状

- `OperationExecutionEvents` 是现场事实表，记录工序、批次、正式计划身份、动作、反馈时间、实际设备、实际人员、异常信息、幂等键、服务端指纹、写入前状态版本和反馈人。
- 执行事件只追加。`schedule_id` 和 `op_id` 仍保留外键用于审计对齐，但不使用级联删除，避免删除计划行时把现场事实一起带走。
- `data/repositories/operation_execution_event_repo.py` 负责执行事件的全部 SQL，并按 `op_id` 聚合 `OperationExecutionState`。service 不直接拼写事件表 SQL。
- `core/services/scheduler/operation_execution_feedback_service.py` 负责正式计划身份校验、幂等键优先判断、状态版本校验、合法状态流转和事件写入。
- 资源派工页的用户入口叫“现场记录”，普通操作区使用“填写实际情况”“下载填写模板”“导入实际情况 Excel”“查看计划和实际”“暂停时间”“异常记录”这些说法，不把 `op_id`、`schedule_id`、`state_revision`、`execution_snapshot_revision` 等内部追踪字段放到用户可见模板和普通页面里。
- 单条填写和 Excel 导入最终都追加 `OperationExecutionEvents`。单条填写由 `ResourceDispatchActualRecordService.record_actual_situation()` 编排；Excel 模板和读取在 `resource_dispatch_actual_excel.py`，预览校验在 `resource_dispatch_actual_import.py`，共享值对象和字段解析在 `resource_dispatch_actual_records.py`。
- Excel 普通页面采用一键导入。后端先做任务匹配、时间格式、完工早于开工、暂停重叠、可能重复等检查；有错误就返回行级错误并且不写数据库，整批无错误才在同一事务里追加事件。预览 / 确认写入接口保留为兼容入口，但不作为普通页面主流程。
- 反馈人对用户可空。写入事件时 service 使用内部兜底值满足数据库非空约束，但页面不强迫用户填写。
- 暂停/继续生产在页面上不作为醒目的实时控制按钮展示；用户填写的是暂停开始、暂停结束或暂停时长，系统仍按事件模型追加暂停和继续生产事件。
- 状态读模型按事件流聚合：`last_event_*` 表示最后一条现场事件，`latest_exception_*` 表示最近一次报异常；两组字段分开计算。
- 程序动作 `report_exception` 入库为 `event_type=exception`，页面和返回值显示“报异常”；现场状态 `exception` 显示“异常中”，两套中文映射分开维护。

## 8. 重排执行事实快照现状

- `core/services/scheduler/execution_snapshot.py` 负责把一批工序的执行状态版本整理成可复算快照。快照包含 `execution_snapshot_revision`、`execution_snapshot_op_ids` 和 `execution_snapshot_op_count`。
- 普通重排在 `schedule_input_collector.py` 读取执行事实：生产中和暂停中工序作为现场固定 seed，已完工工序保留真实时间并从待排输入剔除，异常中工序阻止普通自动重排。
- 候选比较、多起点、局部搜索、优化器和图排程 ready queue 复用同一批执行 seed；执行 seed 的来源标记为 `execution_fact`，和冻结窗口 seed 分开。
- 普通重排写正式计划前会在 `schedule_persistence.py` 复算执行快照并校验固定工序、已完工工序和下游时间。现场状态变化时返回中文冲突提示，不写 `Schedule`、`ScheduleHistory` 或版本号。
- 甘特模拟方案保存时会在 `ScheduleAdjustmentScenario` 里记录执行快照；正式采用模拟方案前会用保存时同一批工序复算，现场状态变化时拒绝发布并回滚发布状态。
- 执行快照字段是开发和测试追溯信息，不直接给普通用户看；页面和普通接口只返回中文消息、名称、预览或查看链接等用户需要的信息。
