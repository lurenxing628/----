---
doc_type: feature-acceptance
feature: 2026-05-27-candidate-recommendation-card
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: candidate-recommendation-card
created: 2026-05-27
---

# 方案对比推荐结论卡验收

## 验收结论

已完成。

本阶段只在排产优化分析页的方案对比区域增加“推荐结论卡”。用户进入页面后，可以先看到系统建议采用哪套代表方案、为什么建议采用，以及其它代表方案只能对照查看，不能直接派工或提交现场反馈。三方案摘要卡、指标差值、钻取空状态留给后续 roadmap 条目，不在本阶段提前实现。

## 已落地范围

- 方案对比 ViewModel 新增 `recommendation_card` 展示字段。
- 推荐卡只从正式采用方案行生成，不从候选参考方案里猜结论。
- 推荐理由复用现有 `selection_reason_code` 的中文解释，不新增算法、不重算评分。
- 模板在方案对比表格前展示推荐卡，推荐卡只读取 `eyebrow / title / candidate_label / reason / note` 这些公开中文字段。
- 候选未开启、候选记录不完整、跳转关系不完整、缺少正式采用方案等场景都不会伪造推荐卡。
- 新增回归测试锁住用户可见文案、内部字段不外露、模板不偷读内部字段，以及本阶段不展示差值卡内容。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_frontend_offline_static_assets.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_graph_auto_selection_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frontend_ui_language_polish.py::test_scheduler_analysis_gantt_and_logs_do_not_surface_internal_terms tests/regression_frontend_ui_language_polish.py::test_scheduler_analysis_hides_internal_schema_and_attempt_tags`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_analysis_candidates.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items`
- `git diff --check`

## 子代理复审

- 调查阶段使用 4 个子代理分别检查了候选数据链路、模板和用户文案、路由和计划身份、现有测试覆盖。
- 实现后使用 4 个子代理做对抗性审核，分别检查了 ViewModel 与测试、路由跳转和计划身份、模板离线与不越界、CodeStable 回写和提交隔离。
- 第一轮审核发现“不完整方案对比最好直接断言不生成推荐卡”和“CodeStable 尚未回写”两个收尾问题。
- 修复后再次进行同范围复审，确认推荐卡没有提前做摘要差值卡，没有把后续现场执行事件草稿混入本阶段。

## 2026-05-27 回溯补充验证

- 本轮第 4-9 项回溯总审查把第 4 项纳入“推荐卡、摘要差值、钻取/空状态/导出”整条链路复测。
- 本轮按第 4 项单项重新做无导向回溯复审，使用 4 个只读子代理：
  - Heisenberg `019e6806-7686-7421-9680-919cff1fb381`：发现正式采用候选行如果是失败或跳过，推荐卡仍会显示“系统建议采用”；这是阻塞项。
  - Meitner `019e6806-76eb-7082-bd86-88169b24bc3f`：审页面文案、模板和静态资源，结论 OK。
  - Bacon `019e6806-778c-7333-8157-a04cfbde1e8d`：审相邻阶段边界和计划身份口径，结论 OK。
  - Ampere `019e6806-780a-74c1-a048-046f0ee21a22`：审 CodeStable 产物、测试命令、禁区和兼容性，结论 OK。
- 已修复阻塞项：推荐卡现在要求正式采用行状态必须是 `completed`；如果正式采用行是失败、跳过、缺状态或未知状态，页面不展示“系统建议采用”，只显示中文提醒让用户复核方案对比记录。
- 已新增回归：`test_candidate_recommendation_card_is_not_faked_when_adopted_candidate_did_not_complete` 覆盖正式采用行失败和跳过两种情况。
- 修复后再次按第 4 项整项范围复审，使用 4 个只读子代理：
  - Zeno `019e6813-6b66-7960-93dd-557215f5f144`：审实现链路，结论 OK，阻塞项 0。
  - Epicurus `019e6813-6bd6-7581-ada8-46cb0382150a`：审页面文案、模板和静态资源，结论 OK，阻塞项 0。
  - Confucius `019e6813-6c48-7f92-b0f1-123815d0cf74`：审相邻阶段边界和计划身份口径，结论 OK，阻塞项 0。
  - Pasteur `019e6813-6cc6-7fe2-a7fa-e4d81485130b`：审 CodeStable 产物、测试命令、禁区和兼容性，结论 OK，阻塞项 0。
- 第 4 项最终复审阻塞项为 0，可以进入第 5 项回溯式对抗审查。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_operation_execution_event_foundation.py tests/regression_operation_execution_state_revision.py tests/regression_operation_execution_feedback_routes.py tests/regression_migrations.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes`
  - 结果：`104 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py`
  - 结果：`40 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-candidate-recommendation-card --require doc_type --require status`
  - 结果：`3 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_analysis_candidates.py web/routes/domains/scheduler/scheduler_analysis_links.py web/routes/report_plan_preview.py web/routes/reports.py core/services/report/report_engine.py core/services/scheduler/schedule_delay_diagnosis_service.py core/services/scheduler/schedule_result_view_context.py core/services/scheduler/resource_dispatch_service.py core/services/scheduler/resource_dispatch_excel.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py`
  - 结果：本阶段相关 Python 文件未发现 Python 3.8.10 之后才支持的语法或注解风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 未做

- 不做三方案摘要卡和总指标差值。
- 不做批次级、资源级影响清单。
- 不新增导出。
- 不改排程算法。
- 不新增派工确认、开工、完工、暂停、异常反馈。
