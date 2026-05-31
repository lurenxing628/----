---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-09"
classification: CONFLICT_OR_RISK
nature: maintainability
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 09：工作台验收测试和质量门禁覆盖不足

## 结论

items.yaml 已经规划了多个工作台专项测试，但当前测试门禁还没覆盖这些页面级流程。更麻烦的是，部分旧测试锁的是旧页面口径，会拦住新设计。

## 证据

- 设计稿要求几何覆盖首页、分析、甘特、资源派工、报表中心和报表明细。
- 当前 `tests/ui_geometry_contract_data.py:5` 只列旧页面，没有工作台核心页面。
- HTML 合同测试循环 `FULL_UI_CONTRACT_PATHS`：`tests/test_ui_geometry_html_contract.py:106`。
- 浏览器 smoke 只测 `1024` 和 `768` 两档宽度：`tests/regression_ui_browser_geometry_smoke.py:1136`。
- Chrome 来自本机或 `APS_CHROME_PATH`，没有锁 Chrome 109：`tests/regression_ui_browser_geometry_smoke.py:214`。
- 质量门禁从 `iter_quality_gate_required_tests()` 取必跑测试：`scripts/run_quality_gate.py:95`。
- 必跑清单来自 `QUALITY_GATE_GUARD_TESTS`：`tools/test_registry.py:32`。
- 资源派工旧测试禁止预览/确认入口：`tests/regression_resource_dispatch_site_records_frontend_contract.py:34`。用户已确认 Excel 预览短期不做，所以这条旧测试当前可以继续保留。
- 首页旧测试固定工作区分组和按钮清单：`tests/regression_manual_entry_scope.py:42`、`:57`。
- 候选方案旧测试固定链接数量和内部字段禁用口径：`tests/regression_scheduler_candidate_analysis_contract.py:345`、`tests/regression_scheduler_candidate_plain_language.py:172`。

## 影响

如果只新增页面，不补测试，质量门禁可能完全没挡住工作台主流程断裂。旧测试里关于 Excel 预览禁止的部分当前不需要改；真正会拦新设计的，是首页旧结构、候选方案链接数量、非正式方案复盘口径、现场动作字段这些地方。

## 建议

- 新增 `regression_workbench_nav_entry_contract.py`。
- 新增 `regression_dashboard_workbench_contract.py`。
- 新增 `regression_scheduler_workbench_links_contract.py`。
- 新增 Gantt 详情区和资源负荷摘要测试。
- 新增资源派工车道合同测试；Excel 预览短期不做，不新增预览合同测试。
- 新增报表回链测试。
- 把工作台路径加入 `tests/ui_geometry_contract_data.py` 和质量门禁注册表。
- 修改旧测试口径前要在对应 feature design 里说明“为什么旧断言要变”。
