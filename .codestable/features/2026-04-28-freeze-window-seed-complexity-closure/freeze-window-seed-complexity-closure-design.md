---
doc_type: feature-design
feature: 2026-04-28-freeze-window-seed-complexity-closure
status: approved
summary: 只关闭 P1-14 的冻结窗口种子复杂度尾项，不改变冻结窗口对外行为。
tags: [scheduler, freeze-window, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: freeze-window-seed-complexity-closure
---

# freeze window seed complexity closure 设计

## 0. 承接边界

本任务只处理 P1-14：`core/services/scheduler/run/freeze_window.py::build_freeze_window_seed()` 复杂度仍高于阈值。

明确不做：

- 不修改 `core.services.scheduler.freeze_window.build_freeze_window_seed` 公开入口。
- 不改函数签名、三元返回值、`meta` 原地写入或 strict 模式的 `ValidationError(field="freeze_window")`。
- 不改 `disabled/degraded/active` 语义，不改 `freeze_application_status`。
- 不改 `seed_results` 字段、排序和 `frozen_op_ids` 锁定范围。
- 不处理 P1-24；它在 M7-B 只复核。
- 不处理 P1-25；它仍然证据不足。
- 不声明 full-test-debt 减少，当前 5 条 active xfail 不属于本任务。
- 不新增兜底、默认成功、静默吞错或新的异常吞掉路径。

## 1. 对外合同

- `build_freeze_window_seed()` 仍返回 `(frozen_op_ids, seed_results, warnings)`。
- `reschedulable_operations=None` 时仍使用 `operations` 作为可冻结范围。
- 显式传入 `reschedulable_operations` 子集时，冻结范围、上一版查询 op_ids、`frozen_op_ids` 和 `seed_results` 都只能来自该子集。
- `seed_results` 继续按 `(start_time, op_id)` 排序，并保留原字段。
- 上一版读取失败、坏行、缺前缀和非法时间段仍按原来的 degraded/strict 行为处理。

## 2. 实现策略

1. 先补合同测试，钉住默认范围、显式子集范围、结果排序和字段完整性。
2. 在 `freeze_window.py` 内新增私有 `_FreezeSeedScope`，只保存本次冻结种子计算需要的内部范围。
3. 把 `build_freeze_window_seed()` 内部拆成四段私有 helper：准备范围、读取上一版、套用批次前缀、整理结果。
4. 使用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 刷新台账，确认 P1-14 的复杂度登记移除。

## 3. 验收契约

- `build_freeze_window_seed()` 复杂度降到阈值以内，拆出的 helper 也都不超过阈值。
- P1-14 的 `complexity:core-services-scheduler-freeze_window-build_freeze_window_seed` 登记从台账中消失。
- `complexity_count` 从 32 降到 31。
- `silent_fallback_count` 不增加。
- full-test-debt 仍真实记录为 5 条 active xfail，不写成减少。
