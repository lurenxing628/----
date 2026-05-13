---
doc_type: feature-acceptance
feature: 2026-05-13-full-test-debt-success-cache
status: accepted
summary: full-test-debt 整项成功缓存已完成
tags: [quality-gate, cache, full-test-debt, evidence]
---

# full-test-debt-success-cache 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-13
> 关联方案 doc：`codestable/features/2026-05-13-full-test-debt-success-cache/full-test-debt-success-cache-design.md`

## 1. 接口契约核对

**启用范围核对**：

- [x] `pytest_collect_all` 仍是 enabled。
- [x] `full_test_debt` 已新增为 enabled。
- [x] startup、required、ruff、pyright、architecture、debt ledger、quickref 仍是 planned。
- [x] 未新增 `full_test_debt_node_cache.json`，未实现 NEXT-5 nodeid 级增量。

**输入范围核对**：

- [x] 覆盖 `tests/**/*.py`、`core/**/*.py`、`web/**/*.py`、`data/**/*.py`、`plugins/**/*.py`、`app.py`、`app_new_ui.py`、`config.py`、`schema.sql`。
- [x] 覆盖模板、静态资源、Excel 模板、docs/audit/evidence README、assets、installer、Win7 build bat、`.limcode` skills/plans、CodeStable 工具、开发文档和债务台账。
- [x] 覆盖 collector/checker/registry、quality gate shared/support、runner、pytest 配置和依赖文件。
- [x] `collect_nodeids.json` 不只看文件 hash，还校验 schema、status、nodeids、nodeid_count、nodeid_hash 和 nodeids_by_file。

**输出证据核对**：

- [x] `check_full_test_debt.py` 成功时写 `evidence/QualityGate/full_test_debt_summary.json`。
- [x] success cache 绑定 `current_full_test_debt.json` 和 `full_test_debt_summary.json` 两个输出文件。
- [x] 输出文件缺失或 hash 不一致时不复用。
- [x] stdout/stderr 日志缺失、hash 不一致或非 UTF-8 时不复用。

## 2. 行为与决策核对

- [x] 无缓存时真实执行 `python tools/check_full_test_debt.py`。
- [x] 输入完全不变、证据完整可信时复用整项成功结果。
- [x] tests/core/web/data/plugins/app/config/schema、模板、静态资源、Excel 模板、安装脚本、文档、台账、工具、pytest 配置或依赖变化时整体重跑。
- [x] `collect_nodeids.json` 缺失、损坏、结构不一致或 nodeid hash 变化时整体重跑。
- [x] 同一轮 collect 先刷新 `collect_nodeids.json` 后，runner 会重新计算 `full_test_debt` 决策。
- [x] 同一轮 collect 修好缺失的 nodeids 后，如果旧 success cache 仍完整可信，可以安全复用。
- [x] 同一轮 collect 让 nodeid hash 变化后，`full_test_debt` 会整项重跑。
- [x] timeout/interrupted/partial_write 不会复用。
- [x] `--long-gate-force-rerun full_test_debt` 只强制 full-test-debt 刷新。
- [x] `--long-gate-force-rerun-all` 只刷新 enabled entry，不启用 planned entry。
- [x] `--long-gate-cache-explain` 只打印决策，不写 proof。

## 3. 验证命令

- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_full_test_debt_cache.py`（52 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py tests/test_check_full_test_debt.py`（195 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check scripts/run_quality_gate.py tools/check_full_test_debt.py tools/long_gate_cache.py tools/long_gate_fingerprint.py tools/long_gate_manifest.py tools/quality_gate_shared.py tools/quality_gate_support.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright scripts/run_quality_gate.py tools/check_full_test_debt.py tools/long_gate_cache.py tools/long_gate_fingerprint.py tools/long_gate_manifest.py tools/quality_gate_shared.py tools/quality_gate_support.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-13-full-test-debt-success-cache/full-test-debt-success-cache-checklist.yaml`
- [x] `git diff --check`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`（提交后 clean-worktree proof；最终以 amend 后再次运行结果为准）

## 4. roadmap 回写

- [x] `quality-gate-long-cache-items.yaml` 中 `full-test-debt-success-cache` 已绑定 `feature: 2026-05-13-full-test-debt-success-cache`。
- [x] 已把该 item 标为 `done`。
- [x] 已同步 roadmap 主文档当前 enabled 范围、NEXT-4 章节、子 feature 清单和变更日志。
- [x] NEXT-5 `full-test-debt-nodeid-cache` 仍保持 planned。

## 5. 遗留和最终证明

- [x] 不需要更新 `codestable/architecture/ARCHITECTURE.md`。本 feature 是质量门禁工具链内部能力。
- [x] 不需要更新 `codestable/requirements/`。没有新增 APS 业务功能。
- [x] 当前未提交阶段的验证已完成。
- [x] 完整 clean-worktree proof 已用 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree` 绑定最终 HEAD。
