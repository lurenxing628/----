---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-01
nature: performance
severity: P0
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 01：SGS 每步对全部就绪候选全量重评分，没有依赖失效

## 速答

`_run_sgs_loop` 每放一道工序就把整个就绪集重新做一遍时隙估算加评分，但一步只改动一台机、一个人、一个批次的状态，绝大多数候选的评分输入没变。1000 工序实测每步评 63～95 个候选，其中真正受影响的约 10 个。

## 关键证据

- `core/algorithms/greedy/dispatch/sgs.py:257-308` —— `_score_candidates` 对 `candidates` 逐个调 `score()`，无跨步复用。
- `core/algorithms/greedy/dispatch/sgs_scoring.py:200-209,243-255,426-430` —— 固定资源候选评分输入 = 静态字段 + `batch_progress[batch]` + `machine_timeline[m]` / `operator_timeline[o]` / `last_op_type_by_machine[m]` + 静态规则参数。
- `core/algorithms/greedy/internal_operation.py:93-94`、`core/algorithm_runtime/run_state.py:97-102`、`runtime_state.py:45-46` —— 一步只写 `occupy_resource(m)`、`occupy_resource(o)`、`advance_batch(batch)`、`MachineTypeState.record(m)`。
- `core/algorithms/greedy/auto_assign.py:283-315` —— 自动派工候选每次评分对全部 (机,人) 对各估算一次，再对胜出对复算一次。
- 实测（S1，真实 CalendarService）：fixed-1000 评分 62,944 次 / 估算 63,748 次 / 解码 5.1s；auto-1000 评分 63,061 次 / 估算 576,549 次 / 解码 55.6s。主代理 1000 工序单机密集 cProfile：`_score_candidates` 3000 次 → `score` 285,150 次 → `estimate_internal_slot` 289,150 次，占 21.7s 中的 16.2s。

## 影响

单次解码成本决定 5 秒预算里能试几个方案。千级工序下 improve 模式退化为一次解码；所有上层搜索（多起点、GRASP/IG、图候选池、精英修补、局搜）在生产规模一次都轮不到。

## 修复方向

按"本步被触碰的资源集合"做依赖失效：每步只重评 `{machine==m} ∪ {operator==o} ∪ {batch==b} ∪ 新就绪}`，其余沿用上一步的 key；自动派工候选的依赖集是其合格对涉及的全部机/人，并把 `ResourceDemand` 平局提示的 revision 纳入失效条件。预期评分与估算调用数下降一个数量级，解码时间 -70% 以上。必须给出行为等价证明（同输入 payload 哈希一致）。

## 建议动作

`cs-refactor`，因为这是行为不变的性能重构，等价性可用现有 native-comparison 收据口径证明。

## 处理结果

2026-09-14 同日落地：`core/algorithms/greedy/dispatch/sgs_score_cache.py` 见证缓存 + 机人对试算备忘，见 `.codestable/refactors/2026-09-14-scheduler-decode-speed-and-candidate-dedup/`。
