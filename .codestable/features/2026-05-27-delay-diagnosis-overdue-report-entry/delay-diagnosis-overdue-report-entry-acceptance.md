---
doc_type: feature-acceptance
feature: 2026-05-27-delay-diagnosis-overdue-report-entry
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: delay-diagnosis-overdue-report-entry
created: 2026-05-27
---

# 超期清单延期解释入口验收

## 验收结论

已完成。

本阶段把上一阶段的只读延期诊断服务接到超期清单和超期导出里。用户现在可以在超期清单里点开“查看为什么晚了”，看到系统按现有数据给出的保守解释：晚了多久、建议先核对哪里、证据够不够、还缺什么数据、下一步去哪里看。页面不会说“已经找到唯一原因”，也不会把程序内部字段直接给普通用户看。

## 已落地范围

- 超期清单页面新增“延期解释”列，每条超期批次可以展开“查看为什么晚了”。
- 详情区只展示 5 类用户能看懂的信息：晚了多久、建议先复核、证据等级、证据缺口、下一步。
- 新增报表展示转换层，把诊断服务内部结构转成页面和 Excel 都能使用的中文说明。
- 超期导出继续使用原有 `/reports/overdue/export`，保留“超期清单”工作表，新增“诊断依据”工作表。
- “诊断依据”工作表表头使用“本次诊断编号”“生成依据摘要”“核对信息”“证据来源”“证据缺口”“生成时间”“筛选条件”等中文大白话。
- 模拟预览下的超期、资源负荷、停机影响导出继续拒绝，并统一提示“模拟预览暂不支持导出，请切换到正式采用方案。”
- 用户手册、页面说明和 V2 镜像手册同步说明“查看为什么晚了”和“诊断依据”工作表。
- 大范围导出拒绝会先发生，通过后才生成诊断依据，避免本该快速拒绝时提前跑完整诊断。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_delay_diagnosis_contract.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_frontend_offline_static_assets.py tests/regression_gantt_partial_overdue_summary_surfaces_warning.py tests/regression_dashboard_overdue_count_tolerance.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_report_export_size_mode_selection.py tests/regression_report_export_large_scope_rejects_need_async.py tests/regression_reports_export_version_default_latest.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_reports_layout_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_page_manual_registry.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/services/report/delay_diagnosis_presentation.py core/services/report/report_engine.py core/services/report/exporters/xlsx.py web/routes/reports.py web/routes/report_plan_preview.py web/viewmodels/page_manuals_reports.py tests/regression_report_delay_diagnosis_plain_language.py tests/regression_report_export_size_mode_selection.py tests/regression_report_export_large_scope_rejects_need_async.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_page_manual_registry.py tests/regression_reports_layout_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items`
- `git diff --check`

## 子代理复审

- 调查阶段使用子代理检查了超期页面和 route/viewmodel 链路、导出和模拟预览链路、用户说明和测试覆盖链路。
- 第一轮实现后对抗审核使用子代理检查了用户可见文案、导出追溯、CodeStable 回写、模拟预览拒绝和大范围导出拒绝顺序。
- 审核发现并修复了详情小标题过多、用户可见禁词测试不够、资源负荷/停机影响模拟预览拒绝断言缺失、页面说明注册测试缺失、大范围超期导出先跑诊断再拒绝等阻塞项。
- 修复后再次派子代理复审页面文案、导出拒绝顺序、CodeStable 回写和提交隔离，确认本阶段无阻塞后再提交。

## 未做

- 不改延期诊断核心规则。
- 不改排程算法。
- 不新增车间开工、完工、暂停、异常反馈。
- 不提前做候选方案推荐卡、三方案差值卡或钻取空状态。
