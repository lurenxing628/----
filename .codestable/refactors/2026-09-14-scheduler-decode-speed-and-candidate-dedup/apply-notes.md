---
doc_type: refactor-apply-notes
refactor: 2026-09-14-scheduler-decode-speed-and-candidate-dedup
status: completed
summary: 见证缓存、机人对备忘、放置交接与外层去重全部落地；等价性用结果哈希与质量矩阵分数逐位相同证明；工作区脏，只做了定向验证。
---

# 实施与证据

## 改动文件

- 新增：`core/algorithms/greedy/dispatch/sgs_score_cache.py`、`core/services/scheduler/run/schedule_candidate_dedup.py`、`tests/algorithm/test_sgs_score_cache_equivalence.py`、`tests/candidate/test_scheduler_candidate_dedup_contract.py`。
- 修改：`core/algorithm_runtime/auto_assign_contract.py`（`pair_tie_occurred`）、`resource_quality.py`（`neighbor_witness`）、`sgs_estimate_reuse.py`（handoff 作用域）、`core/algorithms/greedy/auto_assign.py`（并列标记、合格资源集、原生守卫、备忘接入）、`dispatch/sgs.py`、`dispatch/sgs_scoring.py`、`dispatch/sgs_reuse.py`（`score(..., fallback=)`）、`internal_operation.py`、`run_context.py`（`sgs_score_cache` 字段）、`scheduler.py`（挂缓存、`_last_sgs_score_cache_stats`）、`core/services/scheduler/run/schedule_candidate_runner.py`、`schedule_candidate_summary.py`。
- 测试口径更新：`tests/algorithm/test_sgs_native_score_reuse.py`（被插桩日历/子类/上下文覆写场景下的评分与试算次数按新机制），`tests/algorithm/test_optimizer_shared_budget.py`（假图候选各给独立上下文）、`tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py`（环图场景 5 档只搜 1 次）、`tests/algorithm/test_optimizer_end_to_end_matrix_contract.py` 与 `tests/_support/optimizer_end_to_end_{runner,compare}.py`（复用记账）。

## 等价性证据（结果逐位相同）

| 场景 | 前 | 后 | 结果 |
|---|---|---|---|
| `tests/_support/sgs_slot_reuse_case.make_case(36,8)` 固定机人 / 图模式 | 0.56s / 0.71s | 0.17s / 0.18s | 排程哈希相同 |
| 同上 自动派工 / 自动派工+图 | 3.74s / 4.62s，试算 50,580 / 87,156 次 | 1.37s / 1.74s，试算 7,340 / 11,331 次 | 排程哈希相同 |
| 质量矩阵 8 例（tiny、medium_shift_pool × 4 目标） | medium_shift_pool 6.85s | 5.13s | 基线/改进分数与解码计数全部相同 |
| 1000 工序单机密集工作台画像（1 基线 + 3 图档） | 22.56s，4 次优化器 | 7.71s，2 次优化器（2 档复用） | `candidate_payload_sha256` 相同 `d47139…` |
| 端到端 5 场景（5 档、5 秒预算，min_overdue） | 6 次优化器 | tiny 2、wide 2、frozen 5、shift_pool 6 | 选中方案分数全部相同 |

16 组随机混合负载（固定/自动/仅机台固定、weekend、效率、停机、窗口、slack/cr/atc、图开关）缓存开关结果相同，见 `test_random_mixed_workloads_match_full_rescoring`。

## 已执行的局部验证

- `tests/algorithm tests/scheduler_graph tests/candidate tests/calendar_maintenance tests/workbench/test_run_compute_contracts.py tests/workbench/test_run_progress_ledger.py`：见最终汇报里的通过数。
- 端到端矩阵合同 28 passed；A3 目录环边界测试通过（新模块未加入被钉死的 8 成员文件环）。
- 未跑全量质量门禁（用户此前明令全门禁耗时数小时不可接受），工作区含他人 1000+ 未提交改动，不构成 clean-worktree proof。

## 已知边界

- 见证缓存假定一次解码期间输入对象与日历回答不变（与原有“评估期间不得变异时间轴”合同一致）。
- 机人对备忘在输入违反“段集有序”合同时会把原生早停会掩盖的 `max_shifts` 越界暴露成异常（fail-loud 方向）。
- 复用候选沿用兄弟在其预算片内搜到的结果；确定性时钟下与自己再搜一遍完全相同。
