---
name: aps-full-selftest
description: 运行明确要求的 APS 全量自测，使用项目 .venv Python 在单个 pytest 进程中执行当前 tests 套件，不执行打包。指定局部测试时直接使用相应 pytest 入口，不自动扩大为全量。
---

# APS 全量自测（不打包）

## 范围与入口

遵循根目录 `AGENTS.md`，先区分本轮与已有改动，确认用户要求的是全量自测。仅在与失败定位或影响范围有关时读产品代码；“跑全量自测”不自动附加通读全仓。用户同时要求完整通读时，单独落实该范围。

使用项目 `.venv` Python；以下 `python` 为已激活环境后的简写：

```bash
python .limcode/skills/aps-full-selftest/scripts/run_full_selftest.py
```

可加 `--fail-fast --step-timeout 900`；`--fail-fast` 对应 pytest 的 `-x`，`--step-timeout` 单位为秒，非正值不设超时。提前停止时标明未完成全量，不能报告全量通过。

## 覆盖与硬约束

- runner 只启动一次 `.venv` Python 执行 `-m pytest tests -q --tb=short`，实际覆盖以当前 `tests/` 的收集与运行结果为准。
- 业务回归统一保留在 pytest 套件中；必跑分组仍以 `tools/test_registry_data.py` 及其分组登记为准。runner 不逐文件重复启动 pytest，不运行已移除的阶段 smoke、web smoke、旧 Excel E2E 或复杂用例 repeat 入口。命令与证据位置见 [reference.md](reference.md)。
- 不运行 PyInstaller、出包或 `validate_dist_exe.py`；打包是独立任务。
- 保持测试数据隔离，不把正式业务库用作测试库。缺少项目 `.venv` 或 pytest 时如实失败，不回退系统 Python；不擅自更改依赖版本或降低兼容要求。
- 汇总报告为 `evidence/FullSelfTest/logs/full_selftest_report.md`，属于 ignored 运行产物，不是 tracked clean proof。

## 验证层级与完成

启动前先确认当前工作区干净，再直接调用共同完整门禁 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume`（同 HEAD、干净工作区及仍匹配输入/环境/日志/输出的 long-gate v2 成功结果由共同门禁直接复用，缺证据或变化时由共同门禁实际重跑，禁用断点续跑跳过），并核验产出的 `evidence/QualityGate/v4/quality_gate_manifest.json`（`schema_version == 4`、`status == "passed"`、`head_sha` 一致且运行前后工作区干净）；工作区非干净或门禁失败时不运行后续 pytest。

本 runner 是专项全量自测，不等于统一质量门禁。日常快检、完整门禁、最终 clean proof 与快速静态预检以 [开发文档/README.md](../../../开发文档/README.md) 为准；不要为了自测结论自动叠跑所有模式，也不能用自测 PASS 替代要求的最终门禁。

回报实际运行范围、总体结果、耗时、失败项退出码/报告证据、跳过或提前停止项。环境失败与产品失败分开，已登记测试债务不能写成已修复。只读测试请求不自动授权修代码；已有修复授权时，按失败根因修复并完成相应验证。

默认在对话中给结论。只有用户要求保存审阅报告或已授权流程要求落档时，使用 `.codestable/audits/` 或当前流程的证据位置；FAIL 不自动追加长篇审计报告，脚本日志保持原路径。
