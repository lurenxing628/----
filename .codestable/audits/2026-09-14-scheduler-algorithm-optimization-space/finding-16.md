---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: arch-drift-16
nature: arch-drift
severity: P1
confidence: high
suggested_action: cs-arch
status: open
---

# Finding 16：run/ 深钻算法层内部而非文档声称的 façade 且无 fitness 守卫；service-scheduler.md §4/§10 脱节；大小门禁不覆盖算法层

## 速答

三个架构偏离子项合并记录（S5 A1–A3）：

1. **依赖面与文档不符、无守卫**：`service-scheduler.md` §4 写 run/ "对外依赖 `core.algorithms` 根 façade"，实际 run/ 直接 import `core.algorithms.evaluation`（9 文件）、`greedy.algo_stats`（7）、`value_domains`（5）、`objective_specs`（3）、`greedy.seed`（2）、`greedy.scheduler`、`greedy.schedule_params` 等；`optimizer_multi_start_dedup.py:32,143` 读合同层私有属性 `StrategyFactory._strategies`，`:33-42` 以 `cls.__dict__` 逐项 identity 比对做"原生类证书"。`tests/gate_meta/test_architecture_fitness.py` 与 `test_algorithms_a3_dependency_boundary.py:207-230` 都没有"core/services 只可 import algorithms 根 + 两叶子"的约束。三层算法叶子自身零反向 import、56 个 optimizer 模块零环，方向是干净的。
2. **文档脱节**：§4 规模数字 36→54 个 optimizer 文件、73/17686→95/20771 行、run→config 3→4 处；"仅 `graph/scoring.py` 引 `ready_queue`"从未成立（一直在 `graph/ready_queue.py:11`）；§10 17 条行号锚点 5 条漂移。
3. **门禁盲区**：`tools/quality_gate_shared.py:225` `FILE_SIZE_LIMIT = 500`，但 `:228-235 CORE_DIRS` 不含 `core/algorithms`、`core/algorithm_runtime`、`core/algorithm_contracts`；`greedy/scheduler.py` 492、`dispatch/sgs_graph.py` 491、`schedule_params.py` 467、`dispatch/sgs.py` 464、`dispatch/sgs_scoring.py` 458 无人登记，拆分压力单向传到 run/。

## 影响

A3 解耦定义的边界从 services 一侧被重新打穿；`_native_class` 逐项比对使任何算法层重构都会静默让多起点去重失效（退化为全量解码）；读者按 §4/§10 找代码会落空。

## 修复方向

要么扩展 `core/algorithms/__init__.py` façade 并加 fitness 测试，要么把 §4 改写为真实允许面并把私有属性读取换成公开 API；规模数字改脚本生成并标提交号，锚点用 `file::symbol`；把三个算法目录纳入 `CORE_DIRS`，现存超线者进 `oversize_allowlist` 带退出条件。

## 建议动作

`cs-arch`（文档与守卫）+ `cs-refactor`（façade 与门禁范围）。
