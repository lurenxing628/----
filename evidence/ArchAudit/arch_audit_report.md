# APS 架构合规审计报告

- 生成时间：2026-05-08 01:57:53 +0800
- 仓库根目录：`/Users/lurenxing/Documents/GitHub/----`
- 本次用途：记录前端说明书补强 follow-up 后，架构门禁相关证据的当前状态。

## 总结

- 质量门禁里的架构体检：PASS。
- 验证命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py --tb=short -p no:cacheprovider`
- 验证结果：`20 passed`。
- 说明：本文件不再保留 2026-05-07 旧报告里的“page_manuals_scheduler.py 仍超 500 行”结论，因为该文件已拆分，当前质量门禁已通过。

## 本轮已消除的旧红灯

- `web/viewmodels/page_manuals_scheduler.py` 已拆出排产结果类说明到 `web/viewmodels/page_manuals_scheduler_outputs.py`，不再触发文件超限门禁。
- `core/services/common/excel_templates.py` 已拆出默认模板清单到 `core/services/common/excel_template_defaults.py`，并把旧模板刷新判断拆成小函数，不再触发复杂度门禁。
- `tests/test_architecture_fitness.py::test_file_size_limit` 已通过。
- `tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold` 已通过。

## 仍需区分的历史项

- `core/services/personnel/operator_machine_service.py` 仍超过 500 行，但它是治理台账中已有登记项，当前质量门禁不会把它当成本轮新增红灯。
- 旧版 ArchAudit 报告里列出的裸字符串枚举、命名问题、潜在死代码等，是历史审计项；本轮前端说明书补强没有承诺清理这些问题。
- 最终是否可作为干净证明，仍以 `scripts/run_quality_gate.py --require-clean-worktree` 生成的机器证明为准；`evidence/QualityGate/quality_gate_manifest.json` 在 `.gitignore` 中，不作为普通源码提交文件。

## 本轮相关验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_excel_template_contracts.py`：PASS。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_page_manual_registry.py`：PASS。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_config_manual_markdown.py`：PASS。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_batch_template_warning_surface.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_scheduler_batches_presenter_contract.py --tb=short -p no:cacheprovider`：PASS，`45 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py --tb=short -p no:cacheprovider`：PASS，`20 passed`。
