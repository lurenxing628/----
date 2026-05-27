---
doc_type: feature-acceptance
feature: 2026-05-27-candidate-summary-delta-cards
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: candidate-summary-delta-cards
created: 2026-05-27
---

# 代表三方案摘要卡和总指标差值验收

## 验收结论

已完成。

本阶段把排产优化分析页的方案对比区域从“推荐结论 + 表格”增强成“推荐结论 + 三张摘要卡 + 表格”。三张卡固定对应正式采用方案、原算法代表方案、重点工序优先代表方案，并且每项指标都只和正式采用方案做对比。用户看到的是中文大白话，例如“比正式采用方案多了 3 小时”“和正式采用方案基本持平”“暂无数据”，不是程序里的内部字段或评分串。

## 已落地范围

- ViewModel 给候选方案行补上 `weighted_tardiness_hours`，用于加权拖期展示。
- 新增 `summary_cards` 展示数据，只包含模板需要的中文展示字段。
- 摘要卡展示失败工序、超期批次、总拖期、加权拖期、总工期、换型次数。
- 差异固定以正式采用方案为基准，不提供任意两方案对比参数。
- 模板把摘要卡放在推荐结论卡后、方案表格前，复用本地已有样式。
- 新增/扩展回归测试，覆盖三张卡数量、顺序、缺数据、内部字段不外露、非代表候选不进入摘要卡、模板字段白名单。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_graph_auto_selection_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py`
- `.venv/bin/python -m ruff check --force-exclude -- web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py`

## 子代理复审

- 调查阶段使用 4 个子代理分别检查了候选摘要数据来源、模板和用户文案、测试覆盖缺口、CodeStable 依赖和提交隔离。
- 实现后继续使用多名子代理做对抗性审核，重点检查三张卡是否只覆盖代表方案、差值是否固定相对正式采用方案、模板是否只读取公开字段、是否误把后续执行事件草稿混入本阶段。

## 2026-05-27 回溯补充验证

- 本轮第 4-9 项回溯总审查把第 5 项纳入“方案对比链路”整体复测，不只看单个补丁。
- 本轮按第 5 项单项重新做无导向回溯复审，使用 4 个只读子代理：
  - Huygens `019e6819-f10b-7da3-9fac-3eed310e4e92`：审候选摘要数据来源、缺失处理和差值计算，结论 OK，阻塞项 0。
  - Kant `019e6819-f228-7e22-b094-ab19123c0160`：审页面文案、模板和静态资源，结论 OK，阻塞项 0。
  - Ptolemy `019e6819-f319-7220-b9a6-6654b0254d82`：审相邻阶段边界、导出和可写边界，结论 OK，阻塞项 0。
  - Newton `019e6819-f3e2-7272-8723-e0bc8da22e9f`：审 CodeStable 产物和禁区，发现当前工作区叠加了 `schema.sql` 执行事件改动和第 4 项推荐卡状态保护改动，要求补充第 5 项隔离证据。
- 已补充隔离证据：历史提交 `f053ac54 完成第5阶段：增加代表方案摘要卡和中文差值` 只改了第 5 项文档、items.yaml、候选对比模板、候选分析 ViewModel 和候选摘要测试，没有修改 `schema.sql`、`core/algorithms/`、`installer/`、`vendor/`。当前 `schema.sql` dirty 属于执行事件相关阶段；正式采用行失败/跳过时不展示推荐卡的当前 diff 已归入第 4 项验收，不归入第 5 项。
- 补充隔离证据后再次按第 5 项整项范围复审，使用 4 个只读子代理：
  - Mill `019e6822-2434-70f2-a176-a54e1e13df73`：审候选摘要数据来源、缺失处理和差值计算，结论 OK，阻塞项 0。
  - James `019e6822-2518-7081-bf16-786e6578b635`：审页面文案、模板和静态资源，结论 OK，阻塞项 0。
  - Peirce `019e6822-261d-7c63-b63f-3d2c65c3ca35`：审相邻阶段边界、导出和可写边界，结论 OK，阻塞项 0。
  - Boyle `019e6822-2727-7741-b496-7f2efe9dcf8c`：审 CodeStable 产物、测试命令、禁区和兼容性，结论 OK，阻塞项 0。
- 第 5 项最终复审阻塞项为 0，可以进入第 6 项回溯式对抗审查。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_feedback_routes.py tests/regression_migrations.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes`
  - 结果：`106 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-candidate-summary-delta-cards --require doc_type --require status`
  - 结果：`3 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_analysis_candidates.py web/routes/domains/scheduler/scheduler_analysis_links.py web/routes/report_plan_preview.py web/routes/reports.py core/services/report/report_engine.py core/services/scheduler/schedule_delay_diagnosis_service.py core/services/scheduler/schedule_result_view_context.py core/services/scheduler/resource_dispatch_service.py core/services/scheduler/resource_dispatch_excel.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：本阶段相关 Python 文件未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 未做

- 不展示全部 3/5/7 档候选明细。
- 不做任意两个候选方案自由比较。
- 不做批次级影响清单或资源级变化清单。
- 不新增导出。
- 不改排程算法。
- 不改数据库、迁移或现场执行事件。
