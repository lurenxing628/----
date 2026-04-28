---
doc_type: feature-acceptance
feature: 2026-04-28-freeze-window-seed-complexity-closure
status: accepted
roadmap: p1-scheduler-debt-cleanup
roadmap_item: freeze-window-seed-complexity-closure
accepted_at: 2026-04-29
---

# freeze window seed complexity closure 验收

## 1. 验收结论

P1-14 已按最终尾项完成。`build_freeze_window_seed()` 仍是原来的公开入口，外面调用不用改；内部从一个大函数拆成准备冻结范围、读取上一版排程、套用批次前缀、整理返回结果四段。

这次只处理复杂度事实源，不把 P1-24 写成 bug，不处理 P1-25，也不声明 full-test-debt 减少。

## 2. 改动范围

- `core/services/scheduler/run/freeze_window.py`：新增私有 `_FreezeSeedScope`，并拆出 `_prepare_freeze_seed_scope()`、`_load_previous_schedule_for_freeze()`、`_apply_freeze_prefixes()`、`_finish_freeze_seed_result()`。
- `tests/regression_freeze_window_fail_closed_contract.py`：新增三条合同测试，覆盖默认使用 `operations`、显式子集范围、`seed_results` 排序和字段完整性。
- `开发文档/技术债务治理台账.md`：刷新受控结构块，移除 P1-14 对应复杂度登记。
- `codestable/roadmap/p1-scheduler-debt-cleanup/`：回填 P1-14 尾项、source-map 和 roadmap 收尾说明。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| P1-14 | `fixed-by-final-P1-tail` |
| `build_freeze_window_seed()` 复杂度 | 从 26 降到 3 |
| 拆出 helper 最高复杂度 | 9 |
| `complexity_count` | 从 32 降到 31 |
| `silent_fallback_count` | 154，未增加 |
| full-test-debt | 仍为 5 条 active xfail |
| P1-24 | 保持 `rechecked-by-M7-B` |
| P1-25 | 保持 `evidence-insufficient` |

## 4. 已运行验证

- `tests/regression_freeze_window_fail_closed_contract.py`：21 passed。
- 计划内冻结窗口关联回归 8 个文件：39 passed。
- `python -m radon cc -s core/services/scheduler/run/freeze_window.py`：主函数复杂度 3，最高 helper 复杂度 9。
- `tests/test_architecture_fitness.py` 指定 3 项与 `tests/test_sp05_path_topology_contract.py`：通过。
- `python -m ruff check core/services/scheduler/run/freeze_window.py tests/regression_freeze_window_fail_closed_contract.py`：通过。
- `python -m pyright core/services/scheduler/run/freeze_window.py tests/regression_freeze_window_fail_closed_contract.py`：通过。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`：通过，`complexity_count=31`，`silent_fallback_count=154`。
- `scripts/sync_debt_ledger.py check`：通过。
- `tools/check_full_test_debt.py`：通过，active xfail 仍为 5。
- `codestable/tools/validate-yaml.py` 校验 roadmap 与本 feature 目录：通过。
- `git diff --check`：通过。

最终 clean gate 证明要绑定在归档提交之后的干净工作区上运行。也就是说，本文件记录 P1-14 feature 自身的验收结果；归档文档提交完成后，再以 `scripts/run_quality_gate.py --require-clean-worktree` 的结果作为最终证明，并在最终交付说明里记录对应 HEAD，避免写入证明后又改变 HEAD。

## 5. 收尾说明

P1 当前可执行事实源已收尾：能在当前代码、台账或测试里找到明确事实源的 P1 项已经处理、锁证或复核；P1-25 仍是证据不足，不把它包装成已修。

后续如果继续改冻结窗口，只能基于新的私有 helper 和现有合同测试推进；不能再引用旧的 P1-14 open 结论，也不能把这次复杂度下降说成 full-test-debt 减少。
