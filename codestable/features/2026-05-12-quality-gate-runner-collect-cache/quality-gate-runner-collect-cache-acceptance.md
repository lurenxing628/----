---
doc_type: feature-acceptance
feature: 2026-05-12-quality-gate-runner-collect-cache
status: accepted
summary: collect-only 成功缓存已接入 run_quality_gate.py，完成最小可复用闭环
tags: [quality-gate, collect-only, cache, runner]
---

# quality-gate-runner-collect-cache 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-12
> 关联方案 doc：`codestable/features/2026-05-12-quality-gate-runner-collect-cache/quality-gate-runner-collect-cache-design.md`

## 1. 接口契约核对

**CLI 逐项核对**：

- [x] `--long-gate-cache`：启用 collect-only success cache 判断。
- [x] `--no-long-gate-cache`：与启用开关互斥，用于显式关闭。
- [x] `--long-gate-cache-explain`：只输出决策，不执行命令。

**runner 逐项核对**：

- [x] 只对 `pytest_collect_all` entry 做复用判断。
- [x] success cache 判定为 `reuse` 时读取缓存 stdout/stderr，并继续走 collect proof 解析。
- [x] collect-only 执行分支通过后写 `collect_nodeids.json` 和 long gate success cache。
- [x] 复用时写本次 QualityGate receipt，而不是复用旧 receipt。
- [x] 新写 receipt 包含 `started_at`、`ended_at`、`duration_s`、`timed_out`、`interrupted`、`partial_write`。
- [x] 失败续跑前缀写本次 QualityGate receipt，并标明 `execution_mode: resumed_success_prefix`。
- [x] dirty 快速反馈只给本次诊断用，不写入 long gate success cache。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] explain 模式输出 `Long gate cache decisions`。
- [x] 普通 `--long-gate-cache` 运行开头输出 `pytest_collect_all: RUN/REUSE`。
- [x] 第二次输入不变时不再调用 `python -m pytest --collect-only -q tests`。
- [x] 复用 receipt 写 `execution_mode: reused_success_cache`。
- [x] 新写 receipt 写耗时和完整性字段，旧 receipt 缺这些字段时仍由现有读取逻辑兼容。
- [x] `--long-gate-cache-explain` 明确提示 explain 不是质量门禁证明。

**明确不做逐项核对**：

- [x] 未复用 full-test-debt、回归组、ruff、pyright。
- [x] 未实现完整 `summary.json` / `summary.md`，留给 roadmap PR-9。
- [x] 未删除现有失败续跑逻辑。

## 3. 验收场景核对

- [x] **S1**：explain 模式只输出决策表，不执行任何门禁命令。
  - 证据来源：`tests/test_run_quality_gate.py::test_main_long_gate_cache_explain_prints_decision_without_running`。
  - 结果：通过。

- [x] **S2/S3**：第一次无缓存走 collect-only 执行分支，第二次输入不变复用 collect-only。
  - 证据来源：`tests/test_run_quality_gate.py::test_main_long_gate_cache_reuses_collect_only_success`。
  - 结果：通过。

- [x] **S4**：复用 receipt 明确写 `execution_mode` 和 `reused_from.fingerprint_hash`。
  - 证据来源：`tests/test_run_quality_gate.py::test_main_long_gate_cache_reuses_collect_only_success`。
  - 结果：通过。

- [x] **S5**：普通 `--long-gate-cache` 输出决策表。
  - 证据来源：同一双跑测试断言输出包含 `RUN` 和 `REUSE`。
  - 结果：通过。

- [x] **S6**：`collect_nodeids.json` 不会污染 clean-worktree proof。
  - 证据来源：`tests/test_run_quality_gate.py::test_main_rebuilds_ignored_receipts_without_dirtying_clean_worktree`。
  - 结果：通过。

- [x] **S7**：新写 receipt 包含耗时和完整性字段。
  - 证据来源：`tests/test_run_quality_gate.py::test_main_long_gate_cache_reuses_collect_only_success`。
  - 结果：通过。

- [x] **S8**：输入文件变化时 collect-only 不复用，会重新执行。
  - 证据来源：`tests/test_run_quality_gate.py::test_main_long_gate_cache_reruns_collect_when_input_changes`。
  - 结果：通过。

- [x] **S9**：失败续跑前缀优先于 long gate cache，并写 `resumed_success_prefix` receipt。
  - 证据来源：`tests/test_run_quality_gate.py::test_resume_success_prefix_wins_before_long_gate_cache`。
  - 结果：通过。

- [x] **S10**：dirty 快速反馈不会写 long gate success cache。
  - 证据来源：`tests/test_run_quality_gate.py::test_dirty_long_gate_cache_does_not_write_success_cache`。
  - 结果：通过。

## 4. 验证命令

- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_collect_cache.py`
- [x] `.venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_collect_cache.py tests/test_run_quality_gate.py`（100 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tests/test_run_quality_gate.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_cache.py tools/long_gate_collect.py tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_collect_cache.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tests/test_run_quality_gate.py tools/long_gate_manifest.py tools/long_gate_fingerprint.py tools/long_gate_cache.py tools/long_gate_collect.py tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_collect_cache.py`

## 5. 架构归并

- [x] 不需要更新 `codestable/architecture/ARCHITECTURE.md`。本 feature 只改质量门禁 runner 的技术辅助能力。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 不新增用户可见业务能力。

## 7. roadmap 回写

- [x] 已把 `codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `quality-gate-runner-collect-cache` 改为 `done`。
- [x] 已把 roadmap 主文档第 5 节对应条目同步为 `done`，并补变更日志。
- [x] 已运行 CodeStable YAML 校验。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 没暴露需要写入仓库级代理规则的新约束。

## 9. 遗留

- 下一步 `full-test-debt-success-cache` 才会把 `python tools/check_full_test_debt.py` 纳入整项成功复用。
- 完整 `summary.json`、`summary.md`、executed/reused/failed 数量统计和失败 copyable command 仍在 roadmap PR-9。
