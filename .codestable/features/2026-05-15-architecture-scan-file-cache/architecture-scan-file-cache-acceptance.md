---
doc_type: feature-acceptance
feature: 2026-05-15-architecture-scan-file-cache
roadmap: quality-gate-long-cache
roadmap_item: architecture-scan-file-cache
status: accepted
accepted_at: 2026-05-15
---

# architecture-scan-file-cache 验收记录

## 1. 完成范围

- 新增 `tools/architecture_scan_cache.py`，负责架构扫描文件级 fact cache。
- cache 只保存单文件事实：行数、无最终 ID 的 silent fallback 原料、radon 复杂度块、request service 直接装配命中、repository bundle drift 命中。
- `tools/quality_gate_scan.py` 拆出 `scan_silent_fallback_fact_entries()`；旧 `scan_silent_fallback_entries()` 仍保留公开行为，继续返回带 ID 的结果。
- `tools/quality_gate_operations.py` 的架构 wrapper、账本校验、账本刷新、fixed 状态拒绝、startup sample 校验都从 `scan_files_with_cache()` 取单文件事实，然后每次重新 aggregate 和判断。
- `.gitignore`、`tools/git_hook_checks.py`、`tests/test_git_hook_checks.py` 已覆盖 `evidence/QualityGate/architecture_scan_cache.json`，运行产物不能进提交。
- `tests/test_architecture_scan_cache.py` 覆盖 cache miss、复用、文件变化、新增/删除、坏 JSON、缺字段、未知 fact_kinds、明细缺字段、sha mismatch、scanner/schema/Python/radon 变化、ledger 重新 aggregate、silent ID 稳定、planned entry 守护和运行产物拦截。

## 2. 明确未做

- 没有缓存 `architecture_fitness` 的 pass/fail。
- 没有缓存 `tests/test_architecture_fitness.py` 的 pytest 成功结果。
- 没有写 `architecture_fitness.success.json`。
- 没有把 `architecture_fitness` 加进 enabled long gate success cache。
- 没有启用 ruff、pyright、debt ledger、quickref 等 planned entry。
- 没有把 daily fast gate 或 `--long-gate-cache-explain` 写成 clean proof。

## 3. 对抗审查

- 第一轮指出账本校验/刷新路径仍绕过 cache；已改为所有 architecture scan fact 都从 `scan_files_with_cache()` 进入，并把相关测试改成 patch cache provider。
- 第二轮指出坏 cache 的未知 `fact_kinds` 会抛错；已改成判坏重扫。
- 第三轮指出 fact 明细缺字段会被误复用；已增加 silent、complexity、request、repository 四类明细 validator，并补测试。
- 最终复审未发现阻塞问题。

## 4. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_scan_cache.py`：通过，10 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py`：通过，21 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_cli_controls.py tests/test_run_quality_gate.py tests/test_git_hook_checks.py`：通过，181 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sync_debt_ledger.py tests/regression_quality_gate_scan_contract.py`：通过，112 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/quality_gate_scan.py tools/quality_gate_operations.py tools/architecture_scan_cache.py tests/test_architecture_scan_cache.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/quality_gate_scan.py tools/quality_gate_operations.py tools/architecture_scan_cache.py tests/test_architecture_scan_cache.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-15-architecture-scan-file-cache/architecture-scan-file-cache-checklist.yaml`：通过。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`：通过，只用于确认缓存决策，不是 proof。

## 5. Proof 口径

- 本次没有宣称完整 clean-worktree full proof。
- 若要声明完整最终质量门禁通过，需要在最终 HEAD 且干净工作区上运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，或等价 final gate。
