---
doc_type: feature-acceptance
feature: 2026-05-13-required-regression-cache
requirement:
roadmap: quality-gate-long-cache
roadmap_item: required-regression-cache
status: accepted
accepted_at: 2026-05-13
tags: [quality-gate, cache, required, regression]
---

# required-regression-cache 验收记录

## 1. 验收结论

本 feature 已完成 NEXT-7：`required_regressions` 支持整组成功复用。

当前 enabled long gate entry 是：

- `pytest_collect_all`
- `full_test_debt`
- `startup_runtime_regressions`
- `required_regressions`

仍然保持 planned，没有在本 feature 启用的是：

- `ruff_check_full`
- `pyright_gate_full`
- `pyright_tools_full`
- `architecture_fitness`
- `debt_ledger_sync`
- `quickref_vs_routes`

本 feature 只做 required 整组复用，不做 required nodeid 级增量。

## 2. 已实现范围

- `tools/long_gate_manifest.py` 只把 `ENTRY_REQUIRED_REGRESSIONS` 加入 enabled，不启用 NEXT-8 或后续 entry。
- required entry 从真实 `build_quality_gate_command_plan()` 定位。
- required target 从当前 manifest entry 的 `args[4:]` 派生。
- 缓存 proof 和 target hash 不复制 `QUALITY_GATE_REQUIRED_TESTS`。
- required 指纹覆盖测试文件、被测源码、模板、静态资源、Excel 模板、真实读取的文档、`.limcode` 自测脚本、质量门禁工具、pytest 配置、依赖文件和关键环境变量。
- 无关普通 markdown 没有被宽泛纳入 required 指纹。
- required 成功执行后写 `evidence/QualityGate/required_regressions.json`。
- `.gitignore` 和本地提交保护禁止把 required proof 当源码提交。

## 3. proof 和重跑边界

`evidence/QualityGate/required_regressions.json` 会记录：

- schema、status、entry、generated_at、HEAD、run id。
- `quality_gate_plan_hash`、`command_index`、display、args、command hash。
- required target 数量、路径和 hash。
- fingerprint schema 和 fingerprint hash。
- returncode、pytest exit code、execution mode、duration。
- stdout/stderr 长期 success cache 日志路径和 hash。
- timed_out、interrupted、partial_write。

只要下面任何一项不可信，就不复用旧成功，整组重跑 required：

- required proof 缺失、JSON 损坏、schema 不匹配或字段缺失。
- stdout/stderr 长期日志缺失或 hash 不一致。
- required 测试文件变化。
- `core/`、`web/`、`data/`、`plugins/`、`app.py`、`app_new_ui.py`、`config.py`、`schema.sql` 变化。
- 模板、静态资源、Excel 模板、required 测试真实读取的文档或 `.limcode` 脚本变化。
- `tools/test_registry.py`、`tools/quality_gate_shared.py`、runner、cache、schema、fingerprint、manifest、summary、debt ledger 相关门禁工具变化。
- pytest 配置、依赖文件或关键环境变量变化。

## 4. 验证结果

已通过：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_required_regression_cache.py`
  - 结果：`82 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_required_regression_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py tests/test_long_gate_full_test_debt_cache.py tests/test_git_hook_checks.py`
  - 结果：`374 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
  - 结果：通过；显示 required 已 enabled，NEXT-8 和后续仍 planned。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tools/quality_gate_shared.py tools/quality_gate_support.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/git_hook_checks.py tests/test_long_gate_required_regression_cache.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_startup_regression_cache.py tests/test_git_hook_checks.py`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tools/quality_gate_shared.py tools/quality_gate_support.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/git_hook_checks.py tests/test_long_gate_required_regression_cache.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_startup_regression_cache.py tests/test_git_hook_checks.py`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-13-required-regression-cache/required-regression-cache-checklist.yaml`
  - 结果：通过。
- `git diff --check`
  - 结果：通过。

## 5. 复审结果

只读对抗复审先发现两个阻塞风险：

- required 指纹没有覆盖 required 测试会导入的部分质量门禁工具。
- required 指纹没有覆盖 `tests/test_sp05_path_topology_contract.py` 和 `tests/test_run_full_selftest_report_metadata.py` 实际读取的文档与 `.limcode` 脚本。

已修复并补测试锁住：

- required 工具范围改为绑定 `QUALITY_GATE_TOOL_PATHS`。
- required 输入范围补入实际读取的开发文档、`.limcode` plan 和 full-selftest 脚本。
- 专项测试补了这些路径变化必须让 required 整组重跑。

修复后再次只读复审：未发现阻塞问题。

## 6. clean proof 状态

本 acceptance 记录的是提交前验收结果。

本 feature 的最终 clean-worktree proof 必须在最终提交完成后运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

只有这条命令在最终 commit 上通过，才能说 clean gate 绑定最终 HEAD。如果提交后又 amend，必须重新运行这条命令。

## 7. 回滚方式

如果 NEXT-7 后发现 required 复用有问题，回滚方式是：

- 把 `ENTRY_REQUIRED_REGRESSIONS` 从 enabled 列表移回 planned。
- 删除 required output 绑定和 required proof 写入。
- 保留 NEXT-1 到 NEXT-6 的 collect、full-test-debt、startup 复用能力。
