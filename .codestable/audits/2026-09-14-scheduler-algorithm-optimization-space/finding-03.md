---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-03
nature: performance
severity: P1
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 03：忙段闭包的"每跳认证税"远大于闭包收益，且对自动派工探测基本不生效

## 速答

2026-09-12 忙段闭包（`advance_busy_block`）为了防 monkeypatch，每一跳都做 `inspect.getattr_static` + 方法字典逐项比对 + 策略查询；固定资源 1000 工序里认证花 2.39s（24%），闭包真正干活的 `_native_union_end` 只花 0.15s。带 `abort_after` 的探测直接绕过闭包，所以自动派工 P 对里有 P−1 对拿不到收益。

## 关键证据

- `core/algorithm_runtime/busy_block_skip.py:31-42,53` —— 每跳 `_certified_window` → `getattr_static` + `certified_slot_window`。
- `core/algorithms/greedy/dispatch/../calendar_native_timing.py:16-35`（`core/services/scheduler/calendar_native_timing.py`）—— `_NATIVE_METHODS_UNCHANGED` 逐项 `is` 比较 MRO/类字典。
- `core/algorithm_runtime/busy_block_skip.py:51` —— `abort_after is not None → return shift_to`。
- 实测（S1）：fixed-1000 `_certified_window` 2.39s vs `_native_union_end` 0.15s；auto-1000 `_certified_window` 10.0s（10.6%）；auto-288 中 `advance_busy_block` 213,529 次里只有 40,514 次进入认证。主代理 cProfile：`inspect.getattr_static` 321,314 次 1.08s、`calendar_native_timing.supported` 285,246 次 0.81s。

## 影响

固定资源路径 15～20%、自动派工路径 8～10% 的纯开销；多班次跨午夜日历下 `certified_slot_window` 返回 None，闭包整体失效。

## 修复方向

认证从"每跳"上提为"每次估算一次"乃至"每趟 SGS 一次"（结果挂到 `SlotOverlapReuse` / reuse scope 上）；论证带 `abort_after` 时启用闭包的等价性（跳得更远只会更早满足 `earliest > abort_after`，`_pair_score` 对 abort 结果只看 `abort_after_hit`，`auto_assign.py:402-403`）。

## 建议动作

`cs-refactor`，结果不变，只改变对运行中 monkeypatch 的检测粒度。

## 处理结果

2026-09-14 同日落地（第二阶段）。没有改认证粒度，而是把每跳的 `inspect.getattr_static` 换成 `core/algorithm_runtime/static_attribute.py` 的逐项等价快速读取（实例字典优先级、数据描述符、`__dict__` 遮蔽、谱系变更后失效均与 `inspect` 相同，类对象与自定义元类回落 `inspect`），`resource_quality._plain_operation_type` 同步切换。1000 工序自动派工里 101 万次调用约 4.3s 的反射开销降到约 0.4s。"带 `abort_after` 的探测绕过闭包"一节已被机人对备忘取代：SGS 轮次内探针只做无早停的完整试算并备忘，早停语义按开工时刻复现。设计与证据见 `.codestable/refactors/2026-09-14-scheduler-decode-speed-and-candidate-dedup/` §6。
