---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-11
nature: quality
severity: P1
confidence: high
suggested_action: cs-feat
status: open
---

# Finding 11：图指标与"关键块"全部资源不感知，没有解码后析取图

## 速答

生产工序图只有批次内线性前后序边，`dag_longest_path` 算出来的"关键路径"就是总工时最长的那一个批次链，`impact_count` 是链内剩余工序数，瓶颈分是静态负荷；修补的"关键块"定义也只是资源时间线上相邻且首尾相接 + CPM 关键路径/尾部/换型，不是析取图上的关键块。解码结果里其实已经有每台机的工序序列，加一层机台顺序弧做一次前向/后向传播就能得到资源感知的松弛与真实关键块。

## 关键证据

- `core/services/scheduler/run/schedule_graph_report.py:174`、`core/services/scheduler/graph/precedence_builder.py:15-37` —— 只有 `build_linear_edges_by_batch`。
- `core/services/scheduler/graph/metrics.py:81-93,143-164` —— `get_critical_path` = `dag_longest_path`；瓶颈分静态。
- `core/services/scheduler/run/optimizer_graph_ready_operation_neighbors.py:86-94,123-129` —— `_resource_timelines` 已按资源排序；`_is_critical_block_pair` 非析取图定义。
- `core/services/scheduler/run/optimizer_candidate_fingerprint.py:182-194` —— 解码结果含 machine/operator/start/end。

## 影响

v2 特征（due_pressure、residual_capacity 等）都是静态窗口，修补的关键块邻域命中率受限；这是"达最优率停在 18%"在图路径上的对应原因。

## 修复方向

新增"解码后析取图"投影：产出 `resource_slack_by_op_id`、关键块序列；用于替换 `critical_signal`、只在关键块上生成 N5 式首尾交换、生成一个"析取图 LST 优先级"候选（属 repair 的 operation_order 决策，不写时间，符合 roadmap 边界）。

## 建议动作

`cs-feat`，挂到 roadmap `alns-domain-neighborhood-operators` 前置，或作为 GraphReady v2 修补的独立子项。
