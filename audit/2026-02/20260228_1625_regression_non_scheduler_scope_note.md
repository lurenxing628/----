## 非 Scheduler 变更：范围与最小回归留痕（补充）

- 时间：2026-02-28 16:25
- 背景：在实现 scheduler 闭环修复时，发现工作区/分支同时包含大量 **非 scheduler** 变更（routes/services/repositories/templates/static 等）。为避免“只测 scheduler 但实际改动远超 scheduler”导致回归遗漏，本文件补充记录：**范围事实** 与 **已执行的最小回归**。

---

## 1) 范围事实（非 exhaustive）

除 `core/services/scheduler/` 外，本分支还包含以下类别改动（用于解释为何需要跨域回归）：

- Route 层：`web/routes/` 多个文件从直连 Repository 调整为经 Service 访问
- Service/Repo：`core/services/*`、`data/repositories/*` 多处补齐查询/导入服务以支撑 Route 调整
- Excel 导入执行器：`core/services/common/excel_import_executor.py` 行为与参数增强（影响多域导入链路）
- 前端资源：`templates/`、`static/js/`、`static/css/` 有拆分/契约调整（影响页面加载与交互）

---

## 2) 已执行的最小回归（均 OK）

门禁/对标：

- `python -m pytest tests/test_architecture_fitness.py -v`（9/9 PASSED）
- `python tests/generate_conformance_report.py`（OK；证据：`evidence/Conformance/conformance_report.md`）

执行器/契约回归（脚本型）：

- `python tests/regression_excel_import_executor_status_gate.py`（OK）
- `python tests/regression_batch_detail_linkage.py`（OK；覆盖 `operatorMachines=null` + JS fallback）
- `python tests/regression_auto_assign_persist_truthy_variants.py`（OK；覆盖 `auto_assign_persist='1'` 的回写）

跨域最小 E2E（覆盖 Excel 导入链路 + 关键页面/接口 + OperationLogs 断言）：

- `python tests/smoke_e2e_excel_to_schedule.py`（OK；证据：`evidence/FullE2E/excel_to_schedule_report.md`）

---

## 3) 结论

- 当前分支在“包含非 scheduler 变更”的前提下，已通过门禁/对标与最小跨域回归集，显著降低回归遗漏风险。

