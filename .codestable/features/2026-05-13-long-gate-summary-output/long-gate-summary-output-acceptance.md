---
doc_type: feature-acceptance
feature: 2026-05-13-long-gate-summary-output
status: accepted
summary: long gate summary 输出和失败提示已完成
tags: [quality-gate, cache, summary, runner]
---

# long-gate-summary-output 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-13
> 关联方案 doc：`.codestable/features/2026-05-13-long-gate-summary-output/long-gate-summary-output-design.md`

## 1. 接口契约核对

**summary 文件逐项核对**：

- [x] 正式运行写 `evidence/QualityGate/long_gate/summary.json`。
- [x] 正式运行写 `evidence/QualityGate/long_gate/summary.md`。
- [x] explain 模式不写正式 summary。
- [x] `summary.json` 顶层包含 `schema_version`、`run_id`、`generated_at`、`repo_root`、`head_sha`、`worktree_clean`、`cache_enabled`、`cache_dir`、`mode`、`counts`、`entries`、`failure`。
- [x] 每个 entry 包含 `reason` 和 `invalidated_by`。
- [x] 失败结构包含 copyable command/nodeid、receipt、stdout/stderr log 和 tail。

**runner 逐项核对**：

- [x] 开头打印 `Long gate cache decisions`。
- [x] runner 只对当前已启用的 `pytest_collect_all` 调用 success cache 复用逻辑。
- [x] planned entry 只进 summary，不启用 success cache。
- [x] planned entry 如果作为真实门禁命令失败，summary 会记录 failure 证据，但仍不会启用 success cache。
- [x] summary 写入成功后才写新的 success cache。
- [x] summary 写入失败时不写新的 success cache。
- [x] `tests/test_long_gate_summary_output.py` 已纳入正式 quality gate 必跑集合，防止关键 summary 合同以后退化。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 维护者能从开头决策表看到 run / reuse / planned_only / disabled。
- [x] 维护者能从结束 summary 看到 executed / reused / failed / planned_only / disabled 数量。
- [x] 失败时能直接复制命令重跑，pytest nodeid 能提取时也会显示出来。
- [x] pytest nodeid 只从 pytest 命令输出中提取，生成 copyable command 时会做 shell quoting。
- [x] receipt、stdout/stderr log 路径和日志尾部都进入 summary。
- [x] dirty worktree 如实写入 summary，但不会写新的 success cache。

**明确不做逐项核对**：

- [x] 未启用 full-test-debt、startup、required、ruff、pyright、debt ledger、quickref success cache。
- [x] 未新增 `--long-gate-cache-dir` 或 force rerun 参数。
- [x] 未把 planned entry 改成 enabled。
- [x] 未把 explain 模式当 proof。

## 3. 验收场景核对

- [x] **S1/S2**：explain 模式只打印完整决策表，不执行、不写 success cache、不写正式 summary。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_explain_mode_prints_full_decision_table_and_writes_no_proof`。
  - 结果：通过。

- [x] **S3/S4/S5/S6/S8**：正式运行写 json/md、counts、reason、invalidated_by、planned_only。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_successful_run_writes_json_md_counts_and_reasons`。
  - 结果：通过。

- [x] **S7**：collect-only 复用时 summary 写 `reused_success_cache`。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_reused_collect_only_is_recorded_as_reused_success_cache`。
  - 结果：通过。

- [x] **S9**：cache disabled 时 summary 记录 disabled reason。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_disabled_entry_summary_keeps_reason_and_invalidated_by`。
  - 结果：通过。

- [x] **S10/S11/S12**：失败时记录 failure、copyable command/nodeid、receipt、stdout/stderr log 和 tail。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_failed_collect_records_failure_and_prints_copyable_command`。
  - 结果：通过。

- [x] **S12 补强**：planned long entry 失败时也记录 failure，不误报为 planned_only 成功。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_planned_long_entry_failure_records_summary_failure`。
  - 结果：通过。

- [x] **安全补强**：pytest nodeid 只从 pytest 命令提取，并在 copyable command 中做 shell quoting。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_extract_copyable_failure_quotes_pytest_nodeids_and_ignores_non_pytest_output`。
  - 结果：通过。

- [x] **S13**：stdout/stderr 很长时只截尾部。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_tail_text_keeps_only_last_lines`。
  - 结果：通过。

- [x] **S14**：summary 写入失败时不写新的 success cache。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_summary_write_failure_prevents_success_cache`。
  - 结果：通过。

- [x] **S15**：dirty worktree 时 summary 如实记录，但不写新的 success cache。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_dirty_worktree_summary_is_unbound_and_does_not_write_success_cache`。
  - 结果：通过。

- [x] **S16**：interrupted / partial_write 标记进入 summary。
  - 证据来源：`tests/test_long_gate_summary_output.py::test_interrupted_and_partial_write_flags_are_preserved`。
  - 结果：通过。

**验证命令**：

- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_summary_output.py`（13 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_collect_cache.py tests/test_run_quality_gate.py`（122 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`（74 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tools/long_gate_summary.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_cache.py tools/quality_gate_shared.py tools/test_registry.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tools/long_gate_summary.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_cache.py tools/quality_gate_shared.py tools/test_registry.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-13-long-gate-summary-output/long-gate-summary-output-checklist.yaml`
- [x] `git diff --check`

## 4. 术语一致性

- [x] `summary.json`、`summary.md`、`planned_only`、`disabled`、`executed`、`reused_success_cache`、`copyable command/nodeid` 均在设计和测试里保持同一口径。
- [x] `explain 不是 proof` 的口径保留在控制台输出和设计文档里。
- [x] `planned_only` 表示“没有启用 long gate success cache”，不是说真实质量门禁命令一定没有运行。

## 5. 架构归并

- [x] 不需要更新 `.codestable/architecture/ARCHITECTURE.md`。本 feature 只改质量门禁辅助输出，不改变 APS 业务架构。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 不新增用户可见业务能力。

## 7. roadmap 回写

- [x] `quality-gate-long-cache-items.yaml` 中 `long-gate-summary-output` 已绑定 `feature: 2026-05-13-long-gate-summary-output`。
- [x] 已把该 item 标为 `done`，并已在 roadmap 主文档变更日志追加完成记录。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 没暴露需要写入仓库级代理规则的新约束。

## 9. 遗留

- NEXT-2 的 cache-dir / force-rerun 参数仍未做。
- full-test-debt、startup、required、ruff、pyright、debt ledger、quickref 等 entry 仍然只是 planned，没有启用 success cache。
- 完整 clean-worktree proof 要等本次代码提交后再跑 `scripts/run_quality_gate.py --require-clean-worktree`，本验收报告不能提前宣称已有 clean proof。
