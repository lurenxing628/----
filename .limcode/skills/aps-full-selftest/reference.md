# APS 全量自测（不打包）参考

## 当前测试入口

runner 先在干净工作区委托执行 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume` 并核验完整质量门禁绑定后，使用项目 `.venv` Python 启动一个 pytest 进程：

```bash
.venv/bin/python -m pytest tests -q --tb=short
```

Windows 使用 `.venv\Scripts\python.exe`。`--fail-fast` 为该命令追加 `-x`；`--step-timeout` 约束这一次 pytest 的耗时。

套件以当前 `tests/` 为准，必跑回归分组由 `tools/test_registry_data.py` 及其分组登记维护。runner 不再固定调用旧阶段 smoke、web smoke、Excel E2E 或 complex-repeat，不再为每个登记文件单独启动 pytest。

## 证据与判定

- `evidence/FullSelfTest/logs/full_selftest_report.md`：汇总报告，包含 HEAD、工作区状态、质量门禁清单，以及 `quality_gate_binding` 与 `pytest_tests` 两步结果、实际退出码和总执行耗时。
- `evidence/FullSelfTest/logs/01_pytest_tests.log.txt`：实际 pytest 命令及标准输出/错误。
- `evidence/FullSelfTest/logs/00_quality_gate_binding.log.txt`：前置完整质量门禁命令的标准输出/错误与绑定核验结论；工作区不干净或门禁绑定失败时不运行 pytest。

以上均为 ignored 运行产物，不参与 clean proof 的 tracked 状态。历史 `evidence/Phase*/`、`FullE2E/` 和 `ComplexExcelCases/` 报告只记录对应旧运行，不表示当前套件覆盖。

pytest 非零退出、未收集到用例、超时或缺少运行环境都判为失败。完整门禁绑定直接委托 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume` 执行并核验生成的 v4 manifest，不再维护独立的 manifest 重放器；专项自测 PASS 不替代要求的最终 clean proof。
