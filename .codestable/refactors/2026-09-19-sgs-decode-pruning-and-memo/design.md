---
doc_type: refactor-design
refactor: 2026-09-19-sgs-decode-pruning-and-memo
status: approved
scope: SGS 图优先剪枝开放给自动派工；非图路径评分备忘（台账/机人对分数/派工键跳过）按画像决定
summary: 行为等价地把图模式解码每步的候选评分从"全部就绪候选"降到"最小图键组"，解码次数级提速；非图路径的增量备忘作为第二步按实测决定范围。
---

# SGS 解码降本：剪枝开放自动派工 + 非图路径备忘

## 背景与选择

2026-09-19 预算/邻域深度研究（记忆 `scheduler-budget-depth-measurements-2026-09-19`）确认生产规模的瓶颈是单次解码成本：480 道工序 2.0 s，默认 5 s 预算只买 2 次解码。cProfile 95% 在 SGS 每步对全部就绪候选的自动派工探针。图模式下派工键排在图键之后，只做同组平手裁决，因此"只评最小图键组"是精确的；仓库已有该剪枝但限定固定机人（2026-09-15 决定第 4 条）。本项按 cs-refactor 执行：先固化基线收据，再最小改动开放剪枝，再按画像决定是否做非图路径备忘。

## 第一步：剪枝开放自动派工（已实施）

- `core/algorithms/greedy/dispatch/sgs_priority_pruning.py`：`_fixed_operation` 拆成 `_certified_internal`（内部工序、id/seq、工时）与 `_certified_resources`（固定 → True；自动派工经缓存认证的原生资源池 + `eligible_auto_assign_resources` 静态给出机与人 → False；否则 None 不支持）；`_certify_operations` 承接循环并维护 `fixed_resources`；`for_cache` 从 `SgsScoreCache` 取 `_pool` 与 `_probe.eligible_resources`，不新增 dispatch→auto_assign 导入。
- `core/algorithms/greedy/dispatch/sgs_decode_acceleration.py`：`tail_eligible` 增加 `pruning.fixed_resources`。
- `core/algorithms/greedy/dispatch/sgs_priority_frontier.py`：仅 docstring。
- `sgs.py`、`sgs_scoring.py`、`auto_assign.py` 未改。
- 合同：`tests/algorithm/test_sgs_priority_pruning.py`（自动派工 × 规则 × 窗口、并列组、件级作用域、生产 DTO、静态不可派四种首错相同、认证标志单元测试）；`tests/resource_dispatch/test_sgs_checkpoint_tail.py` 既有的 shift_pool 用例锁住尾段复用拒绝自动派工。
- 决定：`.codestable/compound/2026-09-19-decision-graph-priority-pruning-auto-assign.md`。

## 第二步：非图路径备忘（画像后判定本轮不做）

适用基线解码（`score_enabled=False`）、多起点换规则（图键并列时）、无图上下文运行、最小组内评分。设计见计划文件与设计代理报告：轮次变更台账（`sgs_change_ledger.py`）、机人对分数备忘（`sgs_pair_memo.py`，`_choose_best_pair` 不动）、派工键跳过（`reuse_dispatch_key`）；预期 1.5–2 倍。剪枝落地后画像：图模式每步只评 1 个候选，备忘无复用对象；每次 improve 只有 1 次基线解码走全量评分，占 5 s 预算的比例在 480 道工序约 40%、192 道约 8%，备忘最多再省其中一半，本轮不实施。

## 验证方式

- `measure.py --tag <tag>`：8 个工况剪枝开/关 payload SHA-256 相同、与改前相同；cProfile 调用数；交替计时。
- 定向 pytest（`env -u FORCE_COLOR .venv/bin/python`）：SGS 缓存/检查点/尾段/门禁元测试；不跑全量门禁。
- QM 8 例与 e2e 20 例真实时钟重跑：更快意味着更多解码，允许分数变好，不允许基线解码变化。

## 边界

- 未在 Win7 实机计时；工作区含大量他人未提交改动，只能报局部验证。
- `fallback_counts` 的自动派工尝试计数随剪枝减少（诊断量）。
