---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-02
nature: performance
severity: P0
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 02：日历算术按天循环并重复解析同一时刻的策略，占解码 35–40%

## 速答

`add_working_hours` / `adjust_to_working_time` 都按天循环，循环里反复调 `_policy_for_datetime`，一次时隙估算内同一时刻的策略被解析 3～5 次；自动派工 1000 工序实测 `_policy_for_datetime` 2440 万次（每估算 42 次），而策略缓存只有 356 条、SQL 只有 360 次，说明瓶颈是纯 Python 重复解析而不是数据库。

## 关键证据

- `core/services/scheduler/calendar_engine.py:298-364` —— `while remaining > 0` 逐天循环，`:326/:337/:346/:353/:362` 反复 `adjust_to_working_time`。
- `core/services/scheduler/calendar_engine.py:265-296,239-254` —— `adjust_to_working_time` 逐天循环，每天 `_policy_for_datetime`，跨午夜判断还要再查前一天。
- `core/algorithm_runtime/internal_slot.py:246-254` —— `_estimate_attempt` 对同一 `earliest` 先 `get_efficiency` 再 `add_working_hours`（内部再 `adjust`），`_shifted_start` 再 `adjust`。
- `core/services/scheduler/calendar_service.py:262-263` —— `certified_slot_window` 又做一次 `policy_for_datetime` + `isoformat`。
- 主代理 cProfile（1000 工序单机）：`_policy_for_datetime` 2,582,830 次 2.67s、`_policy_for_date` 2,598,380 次 1.19s、`add_working_hours` 574,396 次 2.58s、`adjust_to_working_time` 1,148,792 次 2.0s。

## 影响

日历是每次时隙估算的常数因子，任何上层剪枝都省不掉它；多班次、人员日历、效率差场景下天数更多，占比更高。

## 修复方向

按 (operator|全局, priority) 惰性构建"工作窗有序数组 + 容量前缀和"，`adjust` = bisect，`add_working_hours` = bisect + 前缀和差分，`get_efficiency` = bisect；必须复刻跨午夜归属、`shift_hours<=0` 跳日、`1e-9` 容差、`available<=0` 分支。退一步的低风险版本：一次估算内缓存 (date, operator, priority) → DayPolicy/工作窗，避免同一时刻反复解析。两种都需要与旧实现的差分/属性测试。

## 建议动作

`cs-refactor`，行为等价的热路径重写，用属性测试对比旧实现。

## 处理结果

2026-09-14 同日落地（第二阶段）。先测量：一次 1000 工序自动派工解码里 `adjust_to_working_time` 231 万次调用只有 9,366 组不同参数，`add_working_hours` 重复 96.5%，`get_efficiency` 重复 99.3%。因此不改 `CalendarEngine` 的按天算术，而是在 `core/algorithm_runtime/calendar_timing_memo.py` 做解码内纯函数备忘，只对时序方法可证明原生的日历启用（`CalendarEngine` 谱系守卫、`CalendarService` 守卫，覆盖层与任何覆写不启用）。1000 工序自动派工日历侧约 7.2s 降到约 1s，解码整体 23.5s → 4.94s，结果哈希不变。设计与证据见 `.codestable/refactors/2026-09-14-scheduler-decode-speed-and-candidate-dedup/` §5。
