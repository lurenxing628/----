---
doc_type: feature-acceptance
feature: 2026-05-13-long-gate-cli-controls
status: accepted
summary: long gate cache CLI 控制参数已完成
tags: [quality-gate, cache, cli, runner]
---

# long-gate-cli-controls 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-13
> 关联方案 doc：`.codestable/features/2026-05-13-long-gate-cli-controls/long-gate-cli-controls-design.md`

## 1. 接口契约核对

**CLI 参数逐项核对**：

- [x] 已新增 `--long-gate-cache-dir PATH`。
- [x] 已新增 `--long-gate-force-rerun ENTRY_ID`，并支持重复传入。
- [x] 已新增 `--long-gate-force-rerun-all`。
- [x] `--long-gate-cache-explain` 会展示参数影响后的决策，但不执行命令、不写 summary、不写 success cache。

**缓存目录逐项核对**：

- [x] 默认目录仍是 `evidence/QualityGate/long_gate`。
- [x] 自定义目录必须位于 repo root 内。
- [x] 自定义目录必须位于 `evidence/QualityGate/long_gate` 本身或它的子目录下。
- [x] 不满足安全规则时直接失败，不会偷偷回退到默认目录。
- [x] summary 顶层 `cache_dir` 会记录本次实际使用的 success cache 目录。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 指定安全 cache dir 后，`pytest_collect_all.success.json` 会写到自定义目录下。
- [x] 指定 force entry 后，即使旧 success cache 可复用，也会真实执行 collect-only。
- [x] force all 只影响当前 enabled entry。
- [x] force planned entry 时，只在 summary 里记录“force 被忽略”，不会启用 success cache。
- [x] force 不改真实 QualityGate command plan。

**明确不做逐项核对**：

- [x] 未启用 full-test-debt、startup、required、ruff、pyright、debt ledger、quickref success cache。
- [x] 未修改 `_CACHE_ENABLED_ENTRY_TYPES`。
- [x] 未把 planned entry 改成 enabled。
- [x] 未把 explain 模式当 proof。

## 3. 验收场景核对

- [x] **S1**：安全 `--long-gate-cache-dir` 可读写，summary 记录目录。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_custom_cache_dir_reads_writes_success_cache_and_summary`。
  - 结果：通过。

- [x] **S2**：repo 外目录和默认 long gate 外目录会失败。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_unsafe_cache_dir_fails_without_running_commands`。
  - 结果：通过。

- [x] **S3/S4**：force 指定 `pytest_collect_all` 时真实执行，并可刷新 success cache。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_force_rerun_entry_executes_instead_of_reusing_and_refreshes_cache`。
  - 结果：通过。

- [x] **S5**：force all 不启用 planned entry。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_force_all_only_invalidates_enabled_entries_and_keeps_planned_entries`。
  - 结果：通过。

- [x] **S6**：force planned entry 仍保持 planned_only。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_force_planned_entry_is_reported_but_does_not_enable_cache`。
  - 结果：通过。

- [x] **S8**：explain 打印 cache-dir / force 后决策，但不写 proof。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_explain_prints_cache_dir_and_force_decision_without_writing_proof`。
  - 结果：通过。

- [x] **未知 ENTRY_ID**：直接失败，避免用户以为 force 生效。
  - 证据来源：`tests/test_long_gate_cli_controls.py::test_unknown_force_rerun_entry_fails_before_running`。
  - 结果：通过。

- [x] **S9**：损坏或不完整旧 cache 会重新执行。
  - 证据来源：既有 `tests/test_long_gate_cache.py` 仍全量通过，覆盖损坏 JSON、非 UTF-8 JSON、缺字段、日志/输出缺失、hash 不一致、路径逃逸、自定义 cache dir 日志跨目录、symlink repo root 证据路径规范等场景。
  - 结果：通过。

**验证命令**：

- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cli_controls.py`（8 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`（129 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tools/long_gate_cache.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_summary.py tools/test_registry.py tests/test_long_gate_cli_controls.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tools/long_gate_cache.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_summary.py tools/test_registry.py tests/test_long_gate_cli_controls.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain --long-gate-cache-dir evidence/QualityGate/long_gate/manual --long-gate-force-rerun pytest_collect_all`

## 4. 术语一致性

- [x] `cache dir`、`force rerun`、`force rerun all`、`enabled entry`、`planned entry` 在设计、测试、README 和 roadmap 中保持同一口径。
- [x] `planned_only` 继续表示“尚未启用 success cache”，不是说真实命令不会运行。
- [x] `explain 不是 proof` 的口径保留在控制台输出、设计和文档里。

## 5. 架构归并

- [x] 不需要更新 `.codestable/architecture/ARCHITECTURE.md`。本 feature 只增强质量门禁本地 CLI 控制，不改变 APS 业务架构。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 不新增用户可见业务能力。

## 7. roadmap 回写

- [x] `quality-gate-long-cache-items.yaml` 中 `long-gate-cli-controls` 已绑定 `feature: 2026-05-13-long-gate-cli-controls`。
- [x] 已把该 item 标为 `done`。
- [x] 已同步 roadmap 主文档的当前状态、NEXT-2 章节、子 feature 清单和变更日志。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 没暴露需要写入仓库级代理规则的新约束。

## 9. 遗留

- full-test-debt、startup、required、ruff、pyright、debt ledger、quickref 等 entry 仍然只是 planned，没有启用 success cache。
- 共用缓存安全和证据链集中化留给 NEXT-3。
- 完整 clean-worktree proof 需要等本次改动提交后，在干净工作区运行 `scripts/run_quality_gate.py --require-clean-worktree`。
