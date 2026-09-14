---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-05
nature: performance
severity: P1
confidence: high
suggested_action: cs-issue
status: superseded
---

# Finding 05：2026-09-12 增量评分证书在生产输入类型下结构性不可达，命中 0 仍付开销

## 速答

评分证书缓存只认 `Batch` / `BatchOperation` / exact `SimpleNamespace`，而生产 `GreedyScheduler.schedule()` 拿到的工序对象是 `OpForScheduleAlgo` dataclass，`_record` 直接判 UNSUPPORTED、`create_native_sgs_reuse` 返回 None。即使放行类型，"资源在就绪集中独占"门槛也只让约 1% 候选进缓存；有在制工序时 `ExecutionResourceCalendar` 包裹日历会整趟关闭。这解释了 09-12 批次"1000 工序四方案 -0.66% 基本持平"。

## 关键证据

- `core/algorithms/greedy/dispatch/sgs_reuse.py:34` —— `_RECORD_TYPES = (Batch, BatchOperation, SimpleNamespace)`；`:123-128,393-399` 判 UNSUPPORTED → None。
- `core/services/scheduler/run/schedule_input_builder.py:22-45,196-223` —— 生产工序对象是 `OpForScheduleAlgo`。
- `core/algorithms/greedy/dispatch/sgs_reuse.py:93-109` —— `can_skip_native_sgs_reuse` 对未知类型返回 False，仍走 OwnedTimeline 包装与每轮 `begin_round/supported()`。
- `core/algorithms/greedy/dispatch/sgs_reuse.py:341-356` —— 独占门槛；实测 fixed-1000 62,944 次评分只有 490 次进入 `score_token`（0.8%），hits=84。
- `core/services/scheduler/run/schedule_input_collector.py:322-325`、`schedule_execution_reservations.py:67-94` —— 在制工序时日历被代理包裹，`type(calendar)` 不在注册表。
- 实测（S1，`/tmp/aps-audit-20260914/s1_check_prod_types.py`）：同一 288 工序固定资源用例，`SimpleNamespace` 版 hits=747/misses=112，`OpForScheduleAlgo` 版 hits=0/misses=0。主代理 1000 工序 cProfile 评分/估算次数与 09-12 记录的"旧代码"一字不差。

## 影响

09-12 的 C 项在生产上是零收益负开销（约 5%）；apply-notes 里所有命中数据都来自 SimpleNamespace 夹具，验收结论对生产不成立。

## 修复方向

finding-01 的依赖失效方案落地后，该证书缓存应被替代或退役；短期至少让 `can_skip_native_sgs_reuse` 对 `OpForScheduleAlgo` 也走"整趟跳过"以省掉包装开销，并在 refactor 记录里回写"生产类型不可达"。

## 建议动作

`cs-issue`，因为这是已落地优化的验收口径与生产现实不符，需要先纠正记录再决定退役还是放行。

## 处理结果

2026-09-14：不再让证书复用覆盖生产类型，而是由见证缓存服务证书证明不了的候选（`sgs_reuse.NativeSgsReuse.score(..., fallback=)`）；证书复用仍保留给原生 BatchOperation/SimpleNamespace 输入。
