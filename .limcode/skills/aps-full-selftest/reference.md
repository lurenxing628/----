# APS 全量自测（不打包）参考

## 脚本清单（默认）

- smoke phases：`tests/smoke_phase0_phase1.py` ~ `tests/smoke_phase10_sgs_auto_assign.py`
- web smoke：`tests/smoke_web_phase0_5.py`、`tests/smoke_web_phase0_6.py`
- FullE2E：`tests/smoke_e2e_excel_to_schedule.py`
- regressions：`tests/regression_*.py`
- complex cases：`tests/run_complex_excel_cases_e2e.py`

## 证据输出（常见路径）

- `evidence/Phase*/`：各阶段 smoke 报告（脚本内写入）
- `evidence/FullE2E/excel_to_schedule_report.md`：FullE2E 报告
- `evidence/ComplexExcelCases/complex_cases_report.md`：复杂 Excel 用例报告（仓库 `.gitignore` 仅保留 report/summary，忽略每次运行的大量产物）
- `evidence/FullSelfTest/full_selftest_report.md`：本技能 runner 生成的汇总报告（新增）

## 已知注意点

- `tests/smoke_phase10_sgs_auto_assign.py` 的失败可能只写入报告而不一定以非零退出码结束；runner 会额外读取 `evidence/Phase10/smoke_phase10_report.md` 进行兜底判定。
