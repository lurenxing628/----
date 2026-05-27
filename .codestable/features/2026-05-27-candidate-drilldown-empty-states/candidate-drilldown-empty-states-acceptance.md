---
doc_type: feature-acceptance
feature: 2026-05-27-candidate-drilldown-empty-states
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: candidate-drilldown-empty-states
created: 2026-05-27
---

# 方案对比钻取、空状态和失败状态验收

## 验收结论

已完成。

本阶段把方案对比的“能不能点进去看明细”从简单看角色存在，改成先看这套方案是否真的有可查看明细。没有保存候选明细时，页面不再给假跳转，而是直接用中文告诉用户“这套对比参考方案没有保存明细，当前无法查看明细。”正式采用方案仍然可以正常跳到甘特图、周计划和资源排班。

## 已落地范围

- 分析页方案对比行新增 `detail_saved`、`can_open_detail` 和中文不可查看原因。
- 链接生成层只在方案身份存在且明细可打开时生成设备甘特图、人员甘特图、周计划、资源排班四个入口。
- 模板无链接时展示 ViewModel 给出的中文原因，不自己读取内部字段判断。
- 资源负荷页和停机影响页的摘要与“当前方案”统一使用模拟预览公开名称；没有名称时显示“模拟预览（未命名）”。
- 超期清单、资源负荷和停机影响在模拟预览下可以导出，导出按模拟方案明细取数，不会悄悄导出正式采用方案。
- 模拟预览报表导出的 Excel 增加“查询摘要”，只写中文方案名、提示、版本和日期范围，不显示模拟方案内部编号。
- 报表导出测试补充文件名、工作表名、表头和工作簿内容的内部字段防泄漏检查。
- 测试补充候选方案 stream 导出，防止大数据导出路径漏出内部字段。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_reports_export_version_default_latest.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_report_export_size_mode_selection.py`

## 子代理复审

- 调查阶段使用 5 个子代理，分别检查分析页跳转链路、周计划页面和导出、资源负荷与停机影响报表、测试覆盖、CodeStable 和提交隔离。
- 实现后第一轮使用 4 个子代理做对抗性审核，分别检查假跳转、报表导出、提交隔离、用户可见文案和离线资源。
- 第一轮复审发现的阻塞点已经修复：补 CodeStable 回写，补未命名模拟预览提示条精确测试，补候选方案 stream 导出防泄漏测试，提交时排除后续执行事件和 schema 草稿。
- 修复后已补同范围第二轮复审：子代理 `019e6722-e7f5-7280-8e35-9f7cfc0c2b58` 复查方案对比钻取、空状态、报表导出、用户可见中文、离线资源和提交隔离，结论 OK，无阻塞项。

## 2026-05-27 回溯补充验证

- 本轮第 4-9 项回溯总审查把第 6 项纳入“推荐卡、摘要差值、钻取/空状态/导出”整条链路复测。
- 本轮按第 6 项单项重新做无导向回溯复审，使用 4 个只读子代理：
  - Curie `019e682d-efb9-73d3-aa05-85e9b4c04d6d`：发现候选失败或跳过时，只要 `detail_saved=yes` 仍会生成甘特图、周计划和资源派工跳转；这是阻塞项。
  - Singer `019e682d-f02f-75a0-a373-426b3ff55f31`：审周计划页面和导出，结论 OK，阻塞项 0。
  - Sartre `019e682d-f0e1-78a1-899e-1cb07f88a9d6`：审资源负荷、停机影响页面和导出，结论 OK，阻塞项 0。
  - Sagan `019e682d-f1fd-7273-ab45-9e048d9db3ce`：审 CodeStable 产物、测试命令、禁区和兼容性，结论 OK，阻塞项 0；提示旧验证数字需更新。
- 已修复阻塞项：`can_open_detail` 现在要求方案身份存在、明细保存且候选状态为 `completed`；失败、跳过、缺状态或状态未识别时不生成跳转，并显示中文原因。
- 已新增回归：`test_analysis_candidate_links_are_hidden_when_representative_candidate_did_not_complete` 覆盖代表方案失败和跳过时不生成跳转。
- 修复后第二轮整项复审继续使用 4 个只读子代理：
  - Beauvoir `019e6836-3357-7673-9238-2331c62c72fc`：审分析页钻取和空状态，结论 OK，阻塞项 0。
  - Hilbert `019e6836-33c8-7220-b30d-ba2ae0b5c70e`：审周计划页面和导出，结论 OK，阻塞项 0。
  - Parfit `019e6836-343e-70f1-b7d8-1f4c1ccbd804`：发现资源负荷和停机影响页面顶部导航只在有 `scenario_id` 时保留方案上下文；候选方案 `plan_role=baseline_best` 页面互跳会丢身份并回到正式采用方案，这是阻塞项。
  - Noether `019e6836-34a8-7dd0-965b-2cbe6fd5fb25`：审 CodeStable 产物、测试命令、禁区和兼容性，结论 OK，阻塞项 0。
- 已修复第二轮阻塞项：报表导航现在只要当前页带有 `version / plan_role / scenario_id / start_date / end_date`，互跳到超期清单、资源负荷、停机影响时都会保留这些上下文。
- 已新增回归：候选方案资源负荷页跳停机影响、停机影响页跳资源负荷时，链接继续带 `version=17&plan_role=baseline_best&start_date=2026-01-03&end_date=2026-01-03`。
- 修复后第三轮整项复审继续使用 4 个只读子代理：
  - Aquinas `019e6842-4a8d-7c71-af96-3d012bb96a2b`：发现排产主导航只在有 `scenario_id` 时保留方案上下文；普通候选方案从周计划、甘特图、资源排班互跳会丢 `version / plan_role`，这是阻塞项。
  - Feynman `019e6842-7509-7ea0-9687-baddcfce726e`：发现同一个排产主导航丢身份阻塞；另提示周计划 Excel 无数据是否写“暂无数据”需要产品口径，当前设计未硬要求，记为非阻塞风险。
  - Einstein `019e6842-a934-7973-8bdb-3a48ecd0c4c2`：发现底层方案解析未校验候选状态；失败或跳过候选只要残留 `detail_saved=yes` 和明细行，手工访问资源负荷、停机影响和导出仍可能读出候选明细，这是阻塞项。
  - Godel `019e6842-d832-7452-9311-5a7381600ce1`：发现同一个排产主导航丢身份阻塞；提示当前 dirty worktree 不是 clean-worktree 证据，记为提交隔离风险。
- 已修复第三轮阻塞项：
  - 排产主导航现在只要当前页带 `version / plan_role / scenario_id`，就会在资源排班、设备甘特图、人员甘特图、周计划互跳时继续保留，不再要求必须有 `scenario_id`。
  - 统一方案解析现在要求 `candidate_rows` 方案来自 `completed` 候选；失败、跳过、缺状态或未知状态即使残留明细，也会用中文拒绝查看，报表页面和导出不能绕过。
  - 分析页只读方案列表遇到未完成候选时仍保留页面展示所需信息，让 ViewModel 显示中文不可查看原因，但不会生成跳转。
- 已新增回归：
  - 周计划页主导航里的资源排班、设备甘特图、人员甘特图、周计划链接都继续带 `version=7&plan_role=baseline_best`。
  - `SchedulePlanQueryService.resolve_plan()` 遇到未完成候选方案时拒绝解析。
  - 超期清单、资源负荷、停机影响页面和导出接口直接访问未完成候选方案时返回中文错误，不展示候选设备或候选明细。
- 修复后第四轮整项复审继续使用 4 个只读子代理：
  - Hypatia `019e684e-9644-7ca3-a183-f217a7bcb491`：审方案对比页、候选方案钻取、甘特图、周计划和资源排班链路，结论 OK，阻塞项 0。
  - Volta `019e684e-c6b7-7883-8cfb-673d54f5b3f1`：发现分析页在历史摘要写 `completed`、数据库方案选项写失败或跳过时，仍可能显示跳转，点进去后才被底层拒绝，这是阻塞项。
  - Leibniz `019e684e-f9dc-74f0-9282-bc73819b7097`：审超期、资源负荷、停机影响、报表导航、导出和取数链路，结论 OK，阻塞项 0。
  - Ohm `019e684f-40a2-7d51-ba57-ec4d08a86323`：发现对比方案若读取正式 `Schedule`，但对应候选状态不是已完成，统一方案解析仍会放行，这是阻塞项。
- 已修复第四轮阻塞项：
  - 分析页现在合并历史摘要状态和数据库方案选项状态；任一边不是已完成，都不生成跳转，并显示中文不可查看原因。
  - 统一方案解析现在要求所有非正式采用方案先确认对应候选状态为 `completed`；即使 `source_table=schedule`，也不能绕过未完成候选状态。
- 已新增回归：
  - 历史摘要仍写完成、数据库方案选项写失败时，分析页不生成候选跳转。
  - `baseline_best` 读取正式 `Schedule` 但候选状态跳过时，`SchedulePlanQueryService.resolve_plan()` 拒绝解析。
  - 报表页面和导出接口在对比方案读取正式 `Schedule` 但候选未完成时返回中文错误，不展示正式或候选明细。
- 修复后第五轮整项复审继续使用只读子代理；其中报表切片多次遇到网络断线，断线代理不计入通过：
  - Lovelace `019e685b-eae9-76c0-9cc2-dda919ac0120`：发现从甘特图、周计划、资源排班点回“排产优化分析”时，主导航没有带 `version / plan_role`，会回到默认版本或最新版本，这是阻塞项。
  - Gauss `019e685c-29fd-7151-ba2a-eadd65da1acd`：审周计划页面、周计划导出、候选方案上下文、空状态和导出内容，结论 OK，阻塞项 0。
  - Gibbs `019e685c-a19f-7760-a978-079a7bbcee6a`：审 CodeStable 产物、items 回写、兼容性、内部字段防泄漏和测试证据，结论 OK，阻塞项 0；它额外跑了第 6 项 items 里的回归命令，结果 `48 passed`，供子代理侧参考。
  - Nash `019e685c-69b8-79d0-86cb-9092d718362a`、Lagrange `019e6862-4735-75e3-98c8-b8a29e83d525`、Schrodinger `019e6863-3da8-7860-a31b-539b05f8da66`、Euler `019e6864-a106-7b73-8ead-36ee3b4ff499`、Ramanujan `019e6864-d3d7-7d03-9c4f-08aeeec8a3d7`：报表相关复审过程中网络断线，均已关闭，不计入“无阻塞通过”结论。
- 已修复第五轮阻塞项：
  - 排产主导航里的“排产优化分析”现在会保留当前 `version / plan_role`；从周计划或甘特图回分析页时，不会悄悄切到默认版本。
- 已新增回归：
  - 周计划页顶部“排产优化分析”链接继续带 `version=7&plan_role=baseline_best`。
  - 甘特图页顶部“排产优化分析”链接继续带 `version=7&plan_role=baseline_best`。
- 修复后第六轮整项复审继续使用 5 个只读子代理：
  - Erdos `019e6877-02a4-7a42-8cdc-a74bb161de89`：审方案对比页、候选方案钻取、甘特图、周计划、资源排班链路，结论 OK，阻塞项 0。
  - Maxwell `019e6877-3c68-73f0-aaea-3b33e8094ddf`：审周计划页面、周计划导出、候选方案上下文、空状态和导出内容，结论 OK，阻塞项 0。
  - Galileo `019e6877-8392-7402-9ce9-a02cc0391f6f`：发现历史摘要和数据库方案选项只要一边是 `completed`、另一边缺状态，分析页仍可能生成跳转，点进去后底层再报错，这是阻塞项。
  - Nietzsche `019e6877-da2e-7171-8c83-92997ad17f72`：审超期清单、资源负荷、停机影响导出、报表取数和内部字段防泄漏，结论 OK，阻塞项 0。
  - Linnaeus `019e6878-1a6f-75d1-8cb1-1a4500d9e14f`：审 CodeStable 产物、roadmap/items 回写、测试覆盖、禁区、Win7/Python 3.8/Chrome 109/离线资源和中文文案，结论 OK，阻塞项 0。
- 已修复第六轮阻塞项：
  - 分析页现在要求历史摘要和数据库方案选项都明确是 `completed` 才允许生成跳转；任一边缺状态或不是已完成，都显示中文不可查看原因。
- 已新增回归：
  - 数据库方案选项 `candidate_status` 为空、历史摘要为完成时，不生成跳转，并提示状态没有确认。
  - 历史摘要候选 `status` 为空、数据库方案选项为完成时，不生成跳转，并提示状态没有确认。
- 回溯发现 `ReportEngine.overdue_delay_diagnosis_context()` 在 `critical_best` 缺明细回退正式方案时，会把延期诊断证据链接改成 `plan_role=adopted`。已修复为使用解析后的计划身份生成诊断，用户仍看到正式方案数据，但链接保留原请求 `plan_role=critical_best`，不会跳到另一套计划。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_feedback_routes.py tests/regression_migrations.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes`
  - 结果：第 4-9 项整段回归组合 `106 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-candidate-drilldown-empty-states --require doc_type --require status`
  - 结果：`3 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_analysis_candidates.py web/routes/domains/scheduler/scheduler_analysis_links.py web/routes/report_plan_preview.py web/routes/reports.py core/services/report/report_engine.py core/services/scheduler/schedule_delay_diagnosis_service.py core/services/scheduler/schedule_result_view_context.py core/services/scheduler/resource_dispatch_service.py core/services/scheduler/resource_dispatch_excel.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：本阶段相关 Python 文件未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。
- 第 6 项 scoped 暂存隔离证据：
  - 已只暂存第 6 项相关路径和 items.yaml 的第 6 项回写 hunk，没有暂存 `schema.sql`、`core/algorithms/`、`installer/`、`vendor/`。
  - `git diff --cached --name-only | rg '^(core/algorithms/|schema\\.sql$|installer/|vendor/)' || true`
  - 结果：无输出。
  - `git diff --cached --unified=0 -- .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml | rg -n "reschedule-minimum-execution-guardrails|status: done|feature: 2026-05-27-reschedule|schedule_input_runtime_support|scheduler_run_surfaces_resource_pool_warning" || true`
  - 结果：无输出。
  - `git diff --cached --check`
  - 结果：无空白格式问题。

## 2026-05-27 最终验证更新

- 第七轮 CodeStable 产物复审发现：旧验收记录里最后一条整段回归命令缺少当前第 6 项 items 已要求的 `tests/regression_scheduler_candidate_week_plan_contract.py` 和 `tests/regression_scheduler_candidate_plan_query_contract.py`，且旧 `48 passed` 已不能代表当前新增回归后的最终证据。
- 第八轮整项复审继续使用只读子代理：
  - McClintock `019e6895-f06b-7a91-8128-8e3a7f65c272`：审页面跳转、分析页、甘特图、周计划、资源排班、报表页面链路，结论 OK，阻塞项 0。
  - Aristotle `019e6896-4864-7b51-bd77-0a4a1ad8254d`：审周计划页面、导出、资源负荷、停机影响导出和测试证据，结论 OK，阻塞项 0。
  - Averroes `019e6896-946b-7732-8849-3d7b1880ad32`：审报表页面切片，结论 OK，阻塞项 0。
  - Pauli `019e6896-d81b-7960-b8cd-69ef71205286`：发现 `reports.py` 仍调用 `reject_scenario_export()`，`ReportEngine` 三个导出函数也没有 `scenario_id` 参数；这会导致第 6 项设计里“导出继续保留 scenario_id”的口径和实现冲突，是阻塞项。
  - Anscombe the 2nd `019e6897-1908-7d53-a74b-b806dd72bf8d`：审 CodeStable、禁区、测试证据和兼容性，结论 OK，阻塞项 0；提示工作区非 clean 需要最终提交隔离确认。
- 已修复第八轮阻塞项：
  - 超期清单、资源负荷和停机影响导出不再拒绝模拟预览，路由会把 `scenario_id` 传到服务层。
  - `ReportEngine.export_overdue_xlsx()`、`export_utilization_xlsx()`、`export_downtime_impact_xlsx()` 支持 `scenario_id`，复用统一方案解析读取模拟明细。
  - 模拟预览报表导出文件名使用公开中文方案名；Excel 增加“查询摘要”，只写中文方案名、提示、版本和日期范围，不写 `scenario_id`。
  - 模拟预览报表导出不再留下 openpyxl 默认英文空白工作表 `Sheet`，用户看到的工作表都改成中文业务表名。
- 已新增或更新回归：
  - `tests/regression_scenario_preview_secondary_outputs.py` 覆盖超期清单、资源负荷、停机影响模拟预览导出成功、取数来自模拟明细、未命名模拟预览文件名和查询摘要兜底。
  - `tests/regression_scenario_preview_secondary_outputs.py` 同时覆盖三类模拟预览导出工作簿不能出现默认空白表 `Sheet`。
  - `tests/regression_scheduler_candidate_reports_contract.py` 覆盖未知模拟方案导出返回中文错误，不把内部字段名给用户看。
  - `tests/regression_report_delay_diagnosis_plain_language.py` 覆盖超期清单延期诊断导出支持模拟预览且不泄露内部字段。
  - `tests/regression_reports_layout_contract.py` 覆盖报表页提示文案从“不能导出”更新为“导出按模拟方案生成”。
  - `tests/regression_report_export_size_mode_selection.py` 更新导出大数据模式假对象，继续覆盖 direct / stream 和候选方案导出脱敏。
- 已先针对第八轮阻塞项补跑精准验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scenario_preview_secondary_outputs.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_reports_layout_contract.py tests/regression_report_export_size_mode_selection.py`
  - 结果：`17 passed`
- 已按当前 items.yaml 和本阶段真实改动补跑最终精准验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_reports_layout_contract.py`
  - 结果：`75 passed`
- 已补跑 YAML 校验：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-candidate-drilldown-empty-states --require doc_type --require status`
  - 结果：`3 passed`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml`
  - 结果：`1 passed`
- 已补跑第 6 项相关 Python 3.8 语法扫描：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/routes/domains/scheduler/scheduler_analysis_links.py web/routes/domains/scheduler/scheduler_analysis_read.py web/routes/domains/scheduler/scheduler_week_plan.py core/services/scheduler/week_plan_excel.py core/services/scheduler/schedule_plan_query_service.py web/routes/report_plan_preview.py web/routes/reports.py core/services/report/report_engine.py core/services/report/exporters/xlsx.py web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_reports_layout_contract.py`
  - 结果：扫描 22 个 Python 文件，0 个 Python 3.8 兼容风险。
- `git diff --check`
  - 结果：无空白格式问题。
- 第九轮整项复审继续使用 5 个只读子代理：
  - Peirce the 2nd `019e68b8-a624-7c51-939e-505010d779b4`：审分析页方案对比、候选状态、跳转链接、空状态和用户可见文案，结论 OK，阻塞项 0。
  - Epicurus the 2nd `019e68b8-f322-7091-be81-1ef3014cfd34`：审周计划、甘特图、资源排班、排产主导航和相关导出，结论 OK，阻塞项 0；它额外跑了相关测试，结果 `25 passed`。
  - Maxwell the 2nd `019e68b9-3c2f-78a3-95d7-7237bade348a`：审超期清单、资源负荷、停机影响页面、导出、文件名、工作簿内容和用户可见中文，结论 OK，阻塞项 0。
  - Singer the 2nd `019e68b9-8f30-7201-89f9-b35c571acf05`：审统一方案解析、服务层取数、手工 URL 绕过防护和 repository 查询链路，结论 OK，阻塞项 0；它额外跑了相关测试，结果 `27 passed`。
  - Parfit the 2nd `019e68b9-e5f0-7042-85d3-bd2a366ef11b`：发现第 6 项暂存区误包含 `web/routes/domains/scheduler/scheduler_week_plan.py` 里模拟排产遇到现场开工/完工事实时不生成可查看版本的后续项 hunk；这是第 10 项最小现场护栏内容，不属于第 6 项，属于提交隔离阻塞项。
- 已修复第九轮阻塞项：
  - 已把 `web/routes/domains/scheduler/scheduler_week_plan.py` 从第 6 项 staged diff 中移出，代码仍保留在工作区，留给后续条目继续使用。
  - 重新检查第 6 项 staged diff：禁区 `schema.sql`、`core/algorithms/`、`installer/`、`vendor/` 无输出；items.yaml staged hunk 不包含 `reschedule-minimum-execution-guardrails` 的状态和测试回写。
- 修复后已重跑验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_reports_layout_contract.py`
  - 结果：`75 passed`
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/routes/domains/scheduler/scheduler_analysis_links.py web/routes/domains/scheduler/scheduler_analysis_read.py web/routes/domains/scheduler/scheduler_week_plan.py core/services/scheduler/week_plan_excel.py core/services/scheduler/schedule_plan_query_service.py web/routes/report_plan_preview.py web/routes/reports.py core/services/report/report_engine.py core/services/report/exporters/xlsx.py web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_reports_layout_contract.py`
  - 结果：扫描 22 个 Python 文件，0 个 Python 3.8 兼容风险。
- 第十轮整项复审继续使用 5 个只读子代理：
  - Kant the 2nd `019e68c1-b526-7161-99b8-21f1f710b23b`：审分析页方案对比、候选状态、跳转链接、空状态和用户可见文案，结论 OK，阻塞项 0；它额外跑了相关测试，结果 `18 passed`。
  - Meitner the 2nd `019e68c1-fc5d-7591-a5cd-d52ea7be8a48`：审周计划、甘特图、资源排班、排产主导航和相关导出，结论 OK，阻塞项 0；它额外跑了相关测试，结果 `25 passed`。
  - Gibbs the 2nd `019e68c2-4635-7b71-8f0f-e2c60e8e77c8`：审超期清单、资源负荷、停机影响页面、导出、文件名、工作簿内容和用户可见中文，结论 OK，阻塞项 0；它额外跑了相关测试，结果 `17 passed`。
  - Curie the 2nd `019e68c2-95ee-7c40-a11b-ac15bb4aaffb`：审统一方案解析、服务层取数、手工 URL 绕过防护和 repository 查询链路，结论 OK，阻塞项 0；它额外跑了相关测试，结果 `27 passed`。
  - Mendel the 2nd `019e68c2-ede3-7740-b455-55cf1acb09c0`：审 CodeStable 产物、items.yaml 回写、测试命令、禁区、兼容性和 staged 提交隔离证据，结论 OK，阻塞项 0；确认当前第 6 项 staged diff 没有触碰 `schema.sql` 等 forbidden paths，也没有混入第 10 项 staged hunk。
- 第十轮复审阻塞项为 0。第 6 项回溯复审闭环完成，可以进入第 7 项回溯复审。

## 未做

- 不新增候选方案全量明细大屏。
- 不做任意两个候选方案自由比较。
- 不开放派工确认、开工、完工或报异常。
- 不改排程算法。
- 不改数据库、迁移或现场执行事件。
