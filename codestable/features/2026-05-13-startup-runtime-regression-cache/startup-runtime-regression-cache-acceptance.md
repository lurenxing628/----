---
doc_type: feature-acceptance
feature: 2026-05-13-startup-runtime-regression-cache
roadmap: quality-gate-long-cache
roadmap_item: startup-runtime-regression-cache
status: accepted
accepted_at: 2026-05-13
tags: [quality-gate, cache, startup, runtime]
---

# startup-runtime-regression-cache 验收报告

## 1. 验收结论

NEXT-6 已完成：`startup_runtime_regressions` 现在支持整组成功复用。

本次只新增启用 startup 这一项。当前 enabled long gate entry 是：

- `pytest_collect_all`
- `full_test_debt`
- `startup_runtime_regressions`

以下条目仍保持 planned，没有启用 success cache：

- `required_regressions`
- `ruff_check_full`
- `pyright_gate_full`
- `pyright_tools_full`
- `architecture_fitness`
- `debt_ledger_sync`
- `quickref_vs_routes`

## 2. 实现核对

- startup 命令来自真实 `build_quality_gate_command_plan()`，manifest 通过实际 pytest args 识别 `startup_runtime_regressions`。
- 缓存逻辑没有复制 startup 测试清单，也没有新增 nodeid 级增量。
- startup 成功执行后写 `evidence/QualityGate/startup_runtime_regressions.json`，该文件已加入 `.gitignore`，不会提交运行产物。
- startup proof 记录 schema、entry、动态 command plan hash、命令序号、display、args、command hash、fingerprint hash、returncode、pytest exit code、测试数量、HEAD、run id、长期 stdout/stderr 日志路径和 hash。
- 通用 success cache 会继续校验 command、fingerprint、stdout/stderr 长期日志、startup proof 输出文件 hash、schema、repo identity、runner/tooling hash。
- proof 缺失、JSON 损坏、schema 不匹配、stdout/stderr 日志缺失或 hash 不一致、输入变化或环境变化时，startup 必须整组重跑。
- `--long-gate-cache-explain` 只打印决策，不写 proof；`--no-long-gate-cache` 不读写 startup cache；force rerun 会让 startup 整组执行。
- startup 失效不会拖着 `full_test_debt` 一起重跑，NEXT-5 的整项复用、nodeid 增量和 ledger-only 路径仍由既有测试覆盖。

## 3. 验证记录

已通过：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_startup_regression_cache.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py tests/test_long_gate_full_test_debt_cache.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/quality_gate_shared.py tools/quality_gate_support.py tools/long_gate_manifest.py scripts/run_quality_gate.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_startup_regression_cache.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/quality_gate_shared.py tools/quality_gate_support.py tools/long_gate_manifest.py scripts/run_quality_gate.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_startup_regression_cache.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-13-startup-runtime-regression-cache/startup-runtime-regression-cache-checklist.yaml`

仍需在最终本地提交后执行：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`

说明：clean-worktree proof 必须绑定最终提交后的 HEAD。提交前的测试只能说明当前实现和回归合同通过，不能替代最终 clean proof。

## 4. 回滚方式

如果 NEXT-6 需要回滚：

- 从 `tools/long_gate_manifest.py` 的 enabled 列表移除 `ENTRY_STARTUP_RUNTIME_REGRESSIONS`。
- 删除 startup 的 output file 绑定和 `scripts/run_quality_gate.py` 中的 startup proof 写入分支。
- 保留 NEXT-5 的 `full_test_debt` 整项复用、nodeid 增量和 ledger-only 能力。
