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

## 未做

- 不做三方案摘要卡和总指标差值。
- 不做批次级、资源级影响清单。
- 不新增导出。
- 不改排程算法。
- 不新增派工确认、开工、完工、暂停、异常反馈。
