---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-15
nature: quality
severity: P3
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 15：退火接受名存实亡；自适应破坏规模单向漂移

## 速答

退火温标 = 首个主目标差值 × 起始比例 0.1，整数主目标下接受 +1 逾期的概率 progress=0 时 4.5e-5、progress=0.1 时 1.3e-7，所有运行 `walk_accepted_worse=0`；破坏规模步长 `f=1+1/sqrt(n+1)` 随次数衰减且只有停滞重启才 reset，连续 3 次失败降到 1 后需 47 次连续成功才回到 2、58 次回到 3，小实例每次被截止打断的迭代也记失败。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_acceptance.py:50-58,65-78`；`_contract.py:44-45`；`_neighborhoods.py:26-43,64-75,80-93`。
- 实测：`/tmp/aps-audit-20260918/S3/probe_sa_temp.py`、`probe_adaptive.py`。

## 影响

合同说"退火只影响行走"，实际行走也不接受更差解；规模反馈退化成常数 1。

## 修复方向

温标按次级分量或相对差定标；规模用浮点或最小规模下一次成功至少 +1，保持"原位无进展扩大、拒绝/中断/变差缩小、停滞重启重置规模保留统计"合同。

## 处理结果

2026-09-18 同日落地：默认温度比例 1.0 → 0.01，主目标持平时按次级差值退火（`secondary_temperature_scale` 上报，`_acceptance.py`、`_contract.py`）；`AdaptiveValue` 夹在尺寸区间内、步长因子变化次数封顶 8（`_neighborhoods.py`）。合同测试 `tests/algorithm/test_graph_ready_iterated_greedy_components_contract.py`（+3 条）；SMTWT-40 步进时钟与质量矩阵终分逐项相同。
