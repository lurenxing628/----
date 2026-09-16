---
doc_type: refactor-apply-notes
refactor: 2026-09-14-scheduler-decode-speed-and-candidate-dedup
status: completed
summary: 见证缓存、机人对备忘与再验证、放置交接、解码内日历备忘、快速静态属性读取与外层去重全部落地；等价性用结果哈希与质量矩阵分数逐位相同证明；工作区脏，只做了定向验证。
---

# 实施与证据

## 改动文件

- 新增：`core/algorithms/greedy/dispatch/sgs_score_cache.py`、`core/services/scheduler/run/schedule_candidate_dedup.py`、`tests/algorithm/test_sgs_score_cache_equivalence.py`、`tests/candidate/test_scheduler_candidate_dedup_contract.py`。
- 修改：`core/algorithm_runtime/auto_assign_contract.py`（`pair_tie_occurred`）、`resource_quality.py`（`neighbor_witness`）、`sgs_estimate_reuse.py`（handoff 作用域）、`core/algorithms/greedy/auto_assign.py`（并列标记、合格资源集、原生守卫、备忘接入）、`dispatch/sgs.py`、`dispatch/sgs_scoring.py`、`dispatch/sgs_reuse.py`（`score(..., fallback=)`）、`internal_operation.py`、`run_context.py`（`sgs_score_cache` 字段）、`scheduler.py`（挂缓存、`_last_sgs_score_cache_stats`）、`core/services/scheduler/run/schedule_candidate_runner.py`、`schedule_candidate_summary.py`。
- 测试口径更新：`tests/algorithm/test_sgs_native_score_reuse.py`（被插桩日历/子类/上下文覆写场景下的评分与试算次数按新机制），`tests/algorithm/test_optimizer_shared_budget.py`（假图候选各给独立上下文）、`tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py`（环图场景 5 档只搜 1 次）、`tests/algorithm/test_optimizer_end_to_end_matrix_contract.py` 与 `tests/_support/optimizer_end_to_end_{runner,compare}.py`（复用记账）。

### 第二阶段（同日，用户要求"把前两项都做了"）

- 新增：`core/algorithm_runtime/calendar_timing_memo.py`（守卫注册 + `MemoizedTimingCalendar`）、`core/algorithm_runtime/static_attribute.py`、`tests/algorithm/test_sgs_calendar_memo_and_pair_revalidation.py`、`tests/algorithm/test_static_attribute_contract.py`。
- 修改：`core/algorithm_runtime/internal_slot.py`（handoff 备忘日历、扫描区间上报、`refresh_changeover_penalty`）、`downtime.py`（`occupy_resource` 上报占用）、`busy_block_skip.py` 与 `resource_quality.py`（改用快速静态读取）、`core/algorithms/greedy/dispatch/sgs_score_cache.py`（备忘日历、占用日志、`_PairEntry` 再验证、7 项统计）、`auto_assign.py`（探针一次取 handoff 传给 `_pair_score`）、`core/services/scheduler/calendar_engine.py`（`NATIVE_TIMING_METHODS`、注册谱系守卫）、`calendar_native_timing.py`（复用共享身份守卫、`make_timing_memo_guard`）、`calendar_service.py`（注册服务守卫）。
- 测试口径更新：`tests/algorithm/test_sgs_score_cache_equivalence.py` 只断言四项核心计数；`tests/algorithm/test_gap_resource_quality.py` 的"朴素记录不走反射"断言把补丁目标从 `inspect.getattr_static` 换成 `static_attribute` / `static_class_attribute`，意图不变。

## 等价性证据（结果逐位相同）

| 场景 | 前 | 后 | 结果 |
|---|---|---|---|
| `tests/_support/sgs_slot_reuse_case.make_case(36,8)` 固定机人 / 图模式 | 0.56s / 0.71s | 0.17s / 0.18s | 排程哈希相同 |
| 同上 自动派工 / 自动派工+图 | 3.74s / 4.62s，试算 50,580 / 87,156 次 | 1.37s / 1.74s，试算 7,340 / 11,331 次 | 排程哈希相同 |
| 质量矩阵 8 例（tiny、medium_shift_pool × 4 目标） | medium_shift_pool 6.85s | 5.13s | 基线/改进分数与解码计数全部相同 |
| 1000 工序单机密集工作台画像（1 基线 + 3 图档） | 22.56s，4 次优化器 | 7.71s，2 次优化器（2 档复用） | `candidate_payload_sha256` 相同 `d47139…` |
| 端到端 5 场景（5 档、5 秒预算，min_overdue） | 6 次优化器 | tiny 2、wide 2、frozen 5、shift_pool 6 | 选中方案分数全部相同 |

16 组随机混合负载（固定/自动/仅机台固定、weekend、效率、停机、窗口、slack/cr/atc、图开关）缓存开关结果相同，见 `test_random_mixed_workloads_match_full_rescoring`。

### 第二阶段证据

| 场景 | 缓存关 | 第一阶段 | 第二阶段 | 结果 |
|---|---|---|---|---|
| `make_case(125,8)` 固定机人（1000 工序） | 3.29s | 1.2s | 0.52s | 排程哈希 `ae2c1a28…` 与缓存关相同 |
| `make_case(125,8)` 自动派工（1000 工序） | 35.97s | 23.5s | 4.94s | 排程哈希 `9fbc7ed7…` 与缓存关相同 |
| `make_case(36,8)` 固定 / 图 / 自动 / 自动+图 | 0.56 / 0.71 / 3.74 / 4.62s | 0.17 / 0.18 / 1.37 / 1.74s | 0.10 / 0.10 / 0.50 / 0.84s | 32 个等价测试 + 16 随机种子相同 |
| 质量矩阵 8 例 | medium_shift_pool improve 6.8–7.4s | 5.13s | 3.4–3.6s | 除 `*_runtime_ms` 外逐字段相同 |
| 1000 工序密集工作台画像 | 22.56s | 7.71s | 6.93s | `candidate-payloads.json` sha256 `d47139…` 相同 |

自动派工 1000 工序一次解码的缓存统计：候选键命中 13,265 / 未命中 49,802；机人对备忘命中 378,747、再验证 46,955、完整试算 22,516（第一阶段 69,471）；日历备忘命中 1,482,824 / 未命中 63,064。

## 已执行的局部验证

- `tests/algorithm tests/scheduler_graph tests/candidate tests/calendar_maintenance tests/workbench/test_run_compute_contracts.py tests/workbench/test_run_progress_ledger.py`：见最终汇报里的通过数。
- 端到端矩阵合同 28 passed；A3 目录环边界测试通过（新模块未加入被钉死的 8 成员文件环）。
- 未跑全量质量门禁（用户此前明令全门禁耗时数小时不可接受），工作区含他人 1000+ 未提交改动，不构成 clean-worktree proof。

### 第二阶段验证

- `tests/algorithm/test_static_attribute_contract.py` + `test_busy_block_boundaries.py` + `test_busy_union_closure.py`：88 passed；`test_sgs_calendar_memo_and_pair_revalidation.py`：11 passed；`test_sgs_score_cache_equivalence.py`：32 passed；`test_gap_resource_quality.py`：41 passed。
- A1/A2/A3 依赖边界合同 26 passed（新模块与新导入未改变被钉死的目录环与 8 成员文件环）。
- 广域回归 `tests/algorithm tests/scheduler_graph tests/candidate tests/calendar_maintenance tests/workbench/test_run_compute_contracts.py tests/workbench/test_run_progress_ledger.py` 3263 passed。
- 仍未跑全量质量门禁；工作区仍含他人未提交改动。

## 已知边界

- 见证缓存假定一次解码期间输入对象与日历回答不变（与原有“评估期间不得变异时间轴”合同一致）。
- 机人对备忘在输入违反“段集有序”合同时会把原生早停会掩盖的 `max_shifts` 越界暴露成异常（fail-loud 方向）。
- 复用候选沿用兄弟在其预算片内搜到的结果；确定性时钟下与自己再搜一遍完全相同。
- 日历备忘与见证缓存共享"一次解码内日历回答不变"的假设；只有 09-12 的证书复用才快照策略内容。测试里在解码中途改策略字段属于证书复用的合同，不属于这两者。
- 机人对再验证依赖 `occupy_resource` 是解码内唯一的时间线写入口；绕过它的写法（直接 append、整体替换）只会让再验证失效并退回完整试算，不会给出错误结果。
- 改进阶段按时间预算搜索，解码变快后同一预算内的迭代数会变，质量矩阵 8 例本轮分数仍相同，但这不是合同；解码级等价才是本轮证明的内容。
