---
doc_type: issue-fix
issue: 2026-04-27-review-contract-hardening
path: fast-track
fix_date: 2026-04-27
tags: [quality-gate, full-test-debt, codestable, python38]
---

# 当前分支 review 机器合同返修记录

## 1. 问题描述

当前分支 deep review 发现 9 个问题，核心都是机器合同不够硬：新增 active xfail 可以靠抬高数字绕过，未登记 xfail 可以混进 proof，baseline 可以缺少可追溯提交号，CodeStable 搜索工具会吞坏 YAML，Python 3.8 下两个 CodeStable 工具也不能保证启动。

## 2. 根因

这些问题不是业务算法本身坏了，而是边界检查只看了“数量像不像对”，没有把“哪些 nodeid 被允许”“报告里有没有未登记 xfail”“baseline 来自哪个提交”“坏 YAML 能不能继续搜索”这些机器事实一起锁住。

## 3. 修复方案

把检查改成显式失败合同：台账 active xfail 只允许当前 5 条历史 P0 nodeid；proof 中任何 xfail 痕迹都必须匹配台账 active 登记；导入 baseline 必须有 40 位 Git SHA 且候选不能为空；CodeStable 工具在 Python 3.8 下可启动，并在坏 YAML 时直接失败；regression 文件读取失败改成 pytest 收集错误。

## 4. 改动文件清单

- `tools/quality_gate_shared.py`
- `tools/quality_gate_ledger.py`
- `tools/check_full_test_debt.py`
- `tools/test_debt_registry.py`
- `tools/collect_full_test_debt.py`
- `codestable/tools/search-yaml.py`
- `codestable/tools/validate-yaml.py`
- `tests/conftest.py`
- `tests/test_check_full_test_debt.py`
- `tests/test_full_test_debt_registry_contract.py`
- `tests/test_sync_debt_ledger.py`
- `tests/test_regression_main_isolation_contract.py`
- `tests/test_codestable_tools_contract.py`
- `audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`
- `.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`
- `codestable/architecture/ARCHITECTURE.md`
- `codestable/compound/2026-04-27-decision-codestable-default-workflow.md`

## 5. 验证结果

- `.venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py tests/test_check_full_test_debt.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_regression_main_isolation_contract.py --tb=short -p no:cacheprovider`：154 passed。
- `.venv/bin/python -m pytest -q tests/test_codestable_tools_contract.py --tb=short -p no:cacheprovider`：10 passed。
- `python3.8 codestable/tools/search-yaml.py --help`：通过。
- `python3.8 codestable/tools/validate-yaml.py --help`：通过。
- `.venv/bin/python tools/check_full_test_debt.py`：status=passed，active_xfail_count=5，fixed_count=0，max_registered_xfail=5，collected_count=690，collection_error_count=0。
- `.venv/bin/python scripts/sync_debt_ledger.py check`：通过。
- `git diff --check`：通过。

## 6. 遗留事项

`scripts/run_quality_gate.py --require-clean-worktree` 当前被本次未提交修复拦住，报错为工作区不干净。代码合入本地提交后，需要在干净工作区重跑这条 clean proof。

## 7. 二次 deep review 返修

后续 deep review 又确认了 4 个必须补硬的点：full pytest 债务 proof 不能只看 call 阶段，CodeStable YAML fallback 必须能读常见多行列表，目录校验不能把 markdown frontmatter 要求套到 checklist.yaml 上，旧 baseline 不能继续冒充当前证明。

本次补充的合同是：未登记 `xfail(run=False)` 必须失败，已登记的 setup 阶段 xfail 必须通过，fixed 债务只要还在 setup 阶段 xfail 就不能被当成修好；采集报告新增 `xfail_marker_run`；CodeStable 工具在无 PyYAML 时也能搜索 block list，遇到坏 block list 和非独立 `---` 分隔符会直接失败。
