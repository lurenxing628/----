---
doc_type: feature-acceptance
feature: 2026-06-01-workbench-context-link-contract
status: accepted
summary: 工作台统一计划上下文和跨页链接合同已落地，第一阶段已通过 focused 回归、资源派工写入口护栏回归和相关旧链路回归。
tags: [aps, workbench, links, scheduler]
roadmap: aps-frontend-workbench
roadmap_item: workbench-context-link-contract
---

# workbench-context-link-contract acceptance

## 1. 接口契约核对

- 已新增 `web/viewmodels/scheduler_workbench_links.py`，提供 `build_workbench_plan_context()`、`build_workbench_link()`、`build_workbench_links()` 和中文映射函数。
- `TARGET_PAGE_PATHS` 固定 10 个 target page，包含 `week_plan`，测试已断言不会漂移。
- `WorkbenchLink` 输出包含 `label/url/target_page/context_summary/disabled/disabled_reason/required_params`。
- `execution_review` 在非正式方案、模拟预览或带 `scenario_id` 的上下文中禁用，并给中文原因。
- 正式采用方案进入 `execution_review` 时会保留 `plan_role=adopted`，但非正式方案不会携带 `scenario_id` 生成可点击复盘入口。
- `overdue_report` 和 `delay_diagnosis` 第一版复用 `/reports/overdue` 路由，合同通过 `target_page` 和中文文案区分入口意图。
- `execution_review` 不允许调用方通过 `disabled=False` 或 `extra_params` 绕开正式方案护栏。
- `build_workbench_links()` 遇到坏配置会直接报中文错误，不再静默跳过。
- `WorkbenchPlanContext` 默认不可写，必须拿到明确后端可写证据后才会输出可写状态。
- `execution_review` 的禁用判断只看是否为正式采用方案、是否模拟预览、是否带 `scenario_id`、是否对比参考或历史替代版本；它不复用现场记录写入口护栏，所以正式采用方案在现场记录暂不可写时仍能进入只读复盘。

## 2. 行为与决策核对

- 分析页候选方案链接已改为复用统一合同，同时保留旧有“设备甘特图、人员甘特图、周计划、资源排班”顺序，并追加“超期清单”入口，避免破坏既有页面路径。
- 资源派工页面下发 Excel 模板下载和实际情况导入地址前，必须通过 `can_emit_feedback_write_urls()`。非可写方案继续能查看排班，但不会拿到写入类地址。
- 写入地址护栏必须拿到明确的正式采用方案身份，不能只凭 `can_write_feedback=True` 放行。
- 资源派工页面的历史替代正式方案、候选方案和模拟预览都不会下发“计划和现场实际”可点击入口；当前正式采用方案即使现场记录暂不可写，仍保留只读复盘入口。
- 资源派工任务卡的“填写实际情况”按钮只在后端 `available_actions` 明确给出 `fill_actual` 时渲染；只读方案只显示“查看计划和实际”。
- 分析页候选方案链接缺少日期范围时会渲染为不可点击入口，并显示中文原因，不会输出空 `href`。
- 分析页保留的“周计划”入口已经接入统一 `week_plan` target page，补齐禁用状态、禁用原因、`week_start` 和必带参数清单，避免出现半截结构。
- 分析页候选方案链接和资源排班复盘入口都会保留 `batch_id` 上下文；资源排班数据、导出、执行任务卡、实际情况模板和导入接口也会按同一个 `batch_id` 过滤排班行，避免 URL 看起来定位到某个批次但后端按更大范围查询。
- 工作台链接现在按目标页可理解的字段保留 `query_date`、`period_preset`、`batch_id` 和资源上下文；首页、分析、甘特、周计划、资源排班、超期/延期、资源负荷、计划和现场实际、报表中心都被矩阵测试覆盖，避免“能跳转但上下文断链”。
- 资源派工工作台入口按 roadmap 矩阵保留 `date_from/date_to`；资源派工路由会把这组公开上下文字段解析成内部查询用的起止日期，避免链接合同和页面查询字段互相打架。
- 资源派工现场记录二级接口返回公开计划身份；写入请求由后端从页面查询参数重新解析真实计划身份，不再依赖前端公开 payload 携带内部字段。没有查询上下文的直连写入会被拒绝，即使请求体自称是正式方案也不能写入。
- 现场记录写入、模板下载和实际情况导入接口要求 URL 带完整资源派工查询上下文；只有 `version`、只有 `plan_role` 或只有二者时都会拒绝，避免后端静默回退到默认日期、默认视角或最新正式方案。
- 资源派工页面在正式方案但当前查询不可用时，不会渲染 `href="None"`、空下载链接、模板下载 URL 或导入 URL；下载模板按钮会禁用。
- 本阶段没有改排程算法、数据库、外部资源或前端框架。

## 3. 验收场景核对

- 正式采用方案链接保留版本、方案、日期和资源参数：`tests/regression_scheduler_workbench_links_contract.py` 覆盖。
- 模拟预览保留查看类上下文，但禁用计划和现场实际入口：`tests/regression_scheduler_workbench_links_contract.py` 覆盖。
- 延期说明目标页虽然复用超期清单路由，仍以 `target_page=delay_diagnosis` 被单独覆盖，避免同路由导致测试无法分辨入口意图。
- 资源派工写入地址护栏：`can_emit_feedback_write_urls()` 单测覆盖，并通过资源派工/模拟预览相关旧回归；只读复盘入口另有正式采用但不可写场景覆盖。
- 资源派工只读页面不输出复盘 href、现场记录写入 URL、模板下载 URL 或 Excel 导入 URL：`tests/regression_resource_dispatch_site_records_frontend_contract.py` 覆盖。
- 分析页无日期范围时禁用候选方案跳转并给中文原因：`tests/regression_scheduler_candidate_analysis_contract.py` 覆盖。
- 分析页候选方案、资源排班复盘入口和资源排班后端接口保留并消费批次上下文：`tests/regression_scheduler_candidate_analysis_contract.py`、`tests/regression_resource_dispatch_site_records_frontend_contract.py`、`tests/regression_scheduler_candidate_resource_dispatch_contract.py` 覆盖。
- 资源派工现场记录二级接口不暴露内部计划身份，且实际写入只从当前查询条件解析身份：`tests/regression_operation_execution_feedback_routes.py` 覆盖。
- 写入类直连缺完整资源派工查询上下文时被拒绝，模板下载和 Excel 导入同样拒绝不完整上下文：`tests/regression_operation_execution_feedback_routes.py`、`tests/regression_resource_dispatch_actual_import.py` 覆盖。
- 资源派工当前查询不可用时不输出 `None` 下载链接、直连写入请求不能靠 body 方案身份绕过后端护栏：`tests/regression_resource_dispatch_site_records_frontend_contract.py`、`tests/regression_operation_execution_feedback_routes.py` 覆盖。
- 旧分析页候选方案链接顺序、超期清单入口和 URL 兼容性：`tests/regression_scheduler_candidate_analysis_contract.py`、`tests/regression_scheduler_analysis_candidate_links_and_roles.py` 覆盖。

## 4. 术语一致性

- 用户可见文案使用“正式采用方案”“模拟预览（未命名）”“人员视角”“设备甘特”等中文业务话。
- 内部字段 `plan_role`、`scenario_id` 只作为 URL / 参数传递，不作为按钮文案或普通摘要文案。

## 5. 架构归并

- 已更新 `.codestable/architecture/ARCHITECTURE.md`：
  - 新增 APS 工作台上下文链接合同现状。
  - 明确 `web/viewmodels/scheduler_workbench_links.py` 是跨页链接统一出口。
  - 明确 `web/viewmodels/scheduler_workbench_link_query.py` 集中维护 10 个目标页的参数矩阵。
  - 明确 `core/services/scheduler/resource_dispatch_page_context.py` 只装配资源派工页面只读查询上下文；资源派工只读复盘入口和写入入口状态由 `web/routes/domains/scheduler/scheduler_resource_dispatch.py` 接线。
  - 补充非正式方案不能下发现场记录写入入口、Excel 导入地址或模板下载地址的页面层约束。

## 6. requirement 回写

- 本阶段是 `aps-frontend-workbench` roadmap 的基础合同，不单独升级 requirements。后续首页值班台、甘特详情、报表回跳等用户可见能力完成后再归并到对应需求文档。

## 7. roadmap 回写

- 已把 `aps-frontend-workbench-items.yaml` 中 `workbench-context-link-contract` 标记为 `done`。
- 已给 roadmap 主文档子 feature 清单补充状态列，并把第 1 条标为 `done`。
- 已在 roadmap 变更日志记录本阶段结果。

## 8. attention.md 候选盘点

- 候选：本项目的 CodeStable YAML 校验需要用 `.venv/bin/python`，系统 Python 缺 PyYAML。是否沉淀为 attention 由后续统一收尾决定。

## 9. 遗留

- 顶层计划工作台入口和首页值班台还没做，按路线图第 2、3 阶段继续。
- 分析页行动入口、甘特详情、资源派工执行分层和报表回跳仍是后续阶段。
- 本阶段实现期拆出的 `scheduler_workbench_link_query.py` 和 `resource_dispatch_page_context.py` 是行为不变拆分，用来让链接参数矩阵和资源派工页面只读查询上下文不继续挤在大文件里；其中 `resource_dispatch_page_context.py` 不承载复盘入口、写入入口状态或资源派工执行链路分层。

## 验证附录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_workbench_links_contract.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_resource_dispatch_actual_import.py tests/regression_operation_execution_feedback_routes.py tests/regression_resource_dispatch_actual_records.py tests/regression_operation_execution_exception_feedback.py tests/test_architecture_fitness.py`：139 passed
- `node --check static/js/resource_dispatch_shared.js && node --check static/js/resource_execution.js`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py web/viewmodels/scheduler_workbench_links.py web/viewmodels/scheduler_workbench_link_query.py web/routes/domains/scheduler/scheduler_analysis.py web/routes/domains/scheduler/scheduler_analysis_links.py web/routes/domains/scheduler/scheduler_resource_dispatch.py web/routes/domains/scheduler/scheduler_resource_dispatch_query.py web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py core/services/scheduler/resource_dispatch_service.py core/services/scheduler/resource_dispatch_page_context.py core/services/scheduler/resource_dispatch_execution_service.py web/viewmodels/scheduler_resource_dispatch_execution.py tests/regression_scheduler_workbench_links_contract.py tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_resource_dispatch_actual_records.py tests/regression_resource_dispatch_actual_import.py tests/regression_operation_execution_exception_feedback.py`：0 findings
- `.venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-06-01-workbench-context-link-contract/workbench-context-link-contract-checklist.yaml --yaml-only`
- `.venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml --yaml-only`
