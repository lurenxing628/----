---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: performance-17
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 17：有在制工序时整套认证加速全部失效

## 速答

`ExecutionResourceCalendar` 用 `__getattr__` 代理包裹日历，只注册了检查点快照、没注册 timing guard；`calendar_timing_memo` 按 MRO 查守卫得 False，连带日历备忘、共享槽位、优先级剪枝、忙段闭包、尾段复用全关，只剩见证缓存与机人对备忘。

## 关键证据

- `core/services/scheduler/run/schedule_execution_reservations.py:68-101`；`core/algorithm_runtime/calendar_timing_memo.py:82-91`；`core/algorithms/greedy/dispatch/sgs_score_cache.py:164-165`；`sgs_priority_pruning.py:26-29`；`core/algorithm_runtime/busy_block_skip.py:31-34`；`sgs_decode_acceleration.py:43-44`。
- 实测（`/tmp/aps-audit-20260918/S1/perf_probe.py`，同实例只加 1 条在制预留）：

| 实例 | 无预留 | 加 1 条预留 | 全关 |
|---|---:|---:|---:|
| 单机 300 工序 | 2.36s | 8.20s | 8.21s |
| 图固定键 200 工序 | 0.08s | 1.59s | – |
| 共享槽位压力 | 0.88s | 2.07s | – |

## 影响

生产中只要有未选中的在制（PROCESSING/PAUSED）工序，重排产就退回 09-14 之前的解码速度，千级工序场景重新把 IG/修补挤出预算。

## 修复方向

让覆盖层成为可认证对象：显式定义时序方法（静态属性读取看不到 `__getattr__` 委托）、注册 timing guard（底层通过守卫 + 覆盖层方法未改写）、`certified_slot_window` 在 dt < release 时返回 None 否则委托；备忘键须含 operator_id。或治本地把人员释放下限注入为时间线占用段。

## 处理结果

2026-09-18 同日落地：`ExecutionResourceCalendar` 显式定义 adjust / add_working_hours / get_efficiency / certified_slot_window，证书在放行时刻之前返回 None、之后委托底层并把窗口起点抬到放行点；`native_execution_overlay_timing` 做类型精确、类成员未改、实例无遮蔽、放行表为 str→naive datetime、底层本身可认证五重校验后注册进时序守卫与断点证书表（`schedule_execution_reservations.py:44-162`）。合同测试 `tests/algorithm/test_execution_calendar_certified_overlay.py`。实测：覆盖层 single-300 8.20s → 2.29s、graphfix 1.59s → 0.07s、shared 2.07s → 0.91s；240 实例差分（含 10 个覆盖层实例）全开/全关一致。
