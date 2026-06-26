---
doc_type: roadmap
slug: scheduler-global-optimizer
status: active
created: 2026-06-26
last_reviewed: 2026-06-26
tags: [scheduler, optimizer, global-search, alns, benchmark, python38, win7]
related_requirements:
  - candidate-comparison-business-view
  - schedule-delay-diagnosis
  - shop-floor-execution-feedback
related_architecture:
  - ARCHITECTURE
---

# 排产全局优化搜索路线（非 OR-Tools 阶段）

## 1. 背景

本路线解决一个新的问题：在当前阶段不把 OR-Tools 作为新主线、不引入重依赖的前提下，继续提升排产算法质量，让系统从“局部换顺序”走向“更接近全局最优的多阶段搜索”。

这里的“全局最优”要讲清楚，不能写成口号：

- 小规模样例：用 exact oracle 或可靠下界证明是否达到最优。
- 中大规模真实排产：只在固定规则、固定时间预算、固定候选范围、同模型同目标同指标下报告可行解、下界、已知最好值、gap、baseline 改进和不劣化；不能把启发式搜索包装成数学全局最优证明。
- 生产主链：仍要先保证能跑出可行排程，不允许为了追求“看起来高级”而吞错、静默回退、绕过现有硬约束。

本路线继承现有排产主链，不重新发明入口：

```text
/scheduler/run
  -> ScheduleService.run_schedule()
  -> collect_schedule_run_input()
  -> orchestrate_schedule_run()
  -> optimize_schedule()
  -> GreedyScheduler.schedule()
  -> dispatch_batch_order() / dispatch_sgs()
```

调用链证据：

- `web/routes/domains/scheduler/scheduler_run.py:38-59`：页面运行排产入口。
- `core/services/scheduler/schedule_service.py:197-224`：服务层排产入口。
- `core/services/scheduler/schedule_service.py:321-327`：把 `optimize_schedule` 传入编排器。
- `core/services/scheduler/run/schedule_orchestrator.py:141-169`：`_run_optimizer_once` 调用优化函数。
- `core/services/scheduler/run/schedule_orchestrator.py:275-303`：正式编排入口在采纳结果前做 allowed op 与 payload 校验。
- `core/services/scheduler/run/schedule_optimizer.py:71-278`：当前优化器主入口。
- `core/algorithms/greedy/scheduler.py:70-139`：GreedyScheduler 主入口。
- `core/algorithms/greedy/scheduler.py:427-458`：batch_order / SGS 分流。
- `core/algorithms/greedy/dispatch/sgs.py:180-248`：SGS 每轮收集候选、打分、选一个、落位。

本轮外部调研结论：

- 不引入 OR-Tools 时，短期最适合的是 GRASP / Iterated Greedy、Simulated Annealing、VNS。
- 中期主线最适合的是 ALNS 外壳 + 现有 Greedy/SGS repair。
- Tabu Search、Beam Search、Shifting Bottleneck 有价值，但先作为后续候选，不做第一条主线。
- exact oracle 只用于小规模证明和 benchmark，不进入生产主链。
- 第三方库只作参考，不进当前主线依赖：`alns==7.0.0` 已要求 Python >=3.9；`alns==6.0.0` 虽支持 Python >=3.8，但会引入 NumPy / Matplotlib；`job-shop-lib==1.7.0` 要求 Python >=3.10 且依赖 OR-Tools。
- 本路线统一写 `Record-to-Record Travel` 或配置值 `record_to_record`；禁止使用英文缩写，避免和路径规划算法混淆。

参考资料：

- ALNS RCPSP 示例：<https://alns.readthedocs.io/en/latest/examples/resource_constrained_project_scheduling_problem.html>
- ALNS operator selection：<https://alns.readthedocs.io/en/latest/api/select.html>
- ALNS acceptance：<https://alns.readthedocs.io/en/latest/api/accept.html>
- ALNS stopping：<https://alns.readthedocs.io/en/latest/api/stop.html>
- alns PyPI：<https://pypi.org/project/alns/>
- alns 6.0.0 PyPI：<https://pypi.org/project/alns/6.0.0/>
- job-shop-lib PyPI：<https://pypi.org/project/job-shop-lib/>
- Muller 2009 RCPSP ALNS：<https://backend.orbit.dtu.dk/ws/files/4002776/mic09-152-Muller_b.pdf>
- FJSP LNS：<https://backend.orbit.dtu.dk/ws/files/54505265/Large_Neighborhood_Search_and_Adaptive_Randomized.pdf>
- Giffler-Thompson active schedule：<https://pubsonline.informs.org/doi/10.1287/opre.8.4.487>
- Carlier-Pinson JSP branch-and-bound：<https://pubsonline.informs.org/doi/10.1287/mnsc.35.2.164>
- Brucker/Jurisch/Sievers JSP 下界与 B&B：<https://www.dcs.gla.ac.uk/~pat/cpM/choco4/jsspResearch/papers/1-s2.0-0166218X94902046-main.pdf>
- Hartmann 1999 RCPSP 启发式：<https://www.hsba.de/fileadmin/user_upload/bereiche/_dokumente/6-forschung/profs-publikationen/Hartmann_1999_Heuristic_Algorithms_for_solving_the_resource-constrained_project_scheduling_problem.pdf>
- JobShopLib SA 教程（只作实现参考，不作为依赖）：<https://job-shop-lib.readthedocs.io/en/v1.6.0/tutorial/03-Simulated-Annealing.html>
- Shifting Bottleneck 原论文：<https://doi.org/10.1287/mnsc.34.3.391>
- 科学计算最佳实践：<https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.1001745>
- 契约式设计：<https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf>

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 建立不写 tracked evidence 的算法评测底座。
- 增加 tiny exact oracle / lower bound / best-known / gap 口径，并把每个证明口径绑定到具体目标和指标。
- 为 optimizer 增加 `stop_reason`、seed、搜索统计和候选拒绝原因。
- 在现有 Greedy/SGS 之上做非 OR-Tools 多阶段搜索。
- 做 GRASP / Iterated Greedy 候选构造。
- 做业务邻域：关键链、延期批次、瓶颈设备、换型块、资源替换、时间窗 repair。
- 做轻量 SA / VNS 改良。
- 做 ALNS 外壳，并用现有 SGS 作为 repair。
- 把图指标转成 destroy/repair 的内部输入，但不把完整图对象外泄。
- 把最终候选继续接回现有 `OptimizationOutcome`、候选比较和 summary 链路。

### 明确不做

- 本阶段不新增 OR-Tools 作为算法依赖，也不把 OR-Tools 变成主引擎。
- 不引入 NumPy、SciPy、Pandas、GPU、云服务、DRL、现代浏览器专属能力。
- 不把 `alns` 包或 `job-shop-lib` 包作为当前主线依赖；它们只能作为算法设计参考，不能进入 Win7 / Python 3.8 离线交付主包。
- 不承诺任意规模都数学证明全局最优；只承诺 tiny oracle 可证明，中大规模只报告同目标、同指标、同模型口径下可比较的 gap 和不劣化。
- 不拿 `makespan` 下界证明 `min_overdue`、`min_tardiness`、`min_changeover` 等非同一目标的“全局最优”。
- 不绕过 `ScheduleService -> orchestrator -> optimize_schedule -> GreedyScheduler` 主链。
- 不直接改写 `Schedule` 正式计划表、`results`、`result_summary`、start/end 时间或任何持久化结果来试算法；算法只能先产出 order / seed / override 这类候选决策，再重进现有 Greedy/SGS 主链并走 summary / diagnostics 合同。
- 新算法不得为 mutable operations 构造 `ScheduleResult`、`start_time`、`end_time` 或带时间的 `seed_results`；允许传入的 seed 只能是已存在、受保护、执行态固定的历史 / 正式排程片段，可变范围内的新候选只能表达为 `batch_order_override`、资源 / 规则 override、repair request 或 mutable scope。
- 不把 `op_id`、`schedule_id`、`scenario_id`、`candidate_id`、`source_table`、`op:...` 节点 id 暴露到页面正文、普通 HTML、导出、文件名或公开 payload。
- 不把 `resource_matching` 当前的 report-only 诊断结果直接当成资源分配结果。
- 不伪造资源资格：没有资格数据就失败或拒绝候选，不能回退成“所有设备/所有人员都可用”。
- 不吞掉 repair 失败：repair 失败必须成为 `candidate_rejected` 或 fail-loud，不能返回原方案假装成功。
- 不让 ALNS 局部 repair 绕过 `schedule_output_allowed_op_ids`、`payload_validation_operations`、payload 合同和执行态保护。
- 不把可选候选的失败包装成正常得分方案。
- 不把相同候选、相同排程结果、相同 fingerprint 的重复尝试包装成“探索到了很多不同方案”。
- 不让候选方案、模拟方案、历史正式方案开放现场写入入口。

## 3. 模块拆分（概设）

```text
scheduler-global-optimizer
├── 证明与评测底座：先证明什么叫更好，避免盲目改算法
├── 搜索合同与可观测层：stop_reason、seed、trace、候选拒绝原因
├── 候选构造层：GRASP / Iterated Greedy 生成更多可行起点
├── 业务邻域层：关键链、延期、瓶颈、换型、资源替换、窗口 repair
├── ALNS 搜索层：destroy / repair / acceptance / operator weight
├── SGS repair 适配层：复用现有 Greedy/SGS 落位和硬约束
├── 接入与展示边界层：接回 OptimizationOutcome、summary、候选比较
└── 长跑调参与门禁层：固定 benchmark、阈值、nightly/long gate
```

### 模块 A · 证明与评测底座

- **职责**：给算法升级建立“能不能证明更好”的标准，包括 tiny oracle、lower bound、best-known、gap、回归阈值、不写 tracked evidence 的 benchmark check 模式，以及 benchmark public/diagnostics 分层。
- **承载的子 feature**：`optimizer-proof-harness`、`benchmark-ratchet-quality-gate`、`long-run-tuning-evidence`
- **触碰的现有代码 / 模块**：`tests/_scripts_e2e/benchmark_fjsp.py`、`tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py`、`evidence/Benchmark/` 使用口径、`tools/test_registry_data.py`、新增算法测试工具。

### 模块 B · 搜索合同与可观测层

- **职责**：让每次优化都说明“试了什么、为什么停、为什么没选、有没有拒绝候选”，并固定随机种子、候选指纹和运行统计；现有 baseline fallback、optional warm-start failure、return best 出口也必须进入同一份 report。
- **承载的子 feature**：`optimizer-search-report-contract`
- **触碰的现有代码 / 模块**：`core/services/scheduler/run/schedule_optimizer.py`、`optimizer_search_state.py`、`optimizer_attempt_records.py`、summary 组装链路。
- **前置边界**：新增 trace / attempts / diagnostics 前，必须先完成 `diagnostic-public-id-boundary-fix`，否则内部 id 暴露面会被放大。

### 模块 C · 候选构造层

- **职责**：在不引入 OR-Tools 的前提下，用 GRASP / Iterated Greedy 思路生成更多可行起点，而不是只枚举固定排序策略和 3/5/7 图权重档位；在起点扩展前先定义 distinct candidate / fingerprint，防止重复候选冒充搜索空间变大。
- **承载的子 feature**：`optimizer-candidate-profile-contract`、`distinct-candidate-fingerprint-contract`、`grasp-ig-candidate-construction`
- **触碰的现有代码 / 模块**：`schedule_candidate_specs.py`、`schedule_candidate_runner.py`、`schedule_optimizer_steps.py`、`sort_strategies.py`、`dispatch_rules.py`。

### 模块 D · 业务邻域层

- **职责**：把 local search 从“随机 swap / insert / block 批次顺序”升级成围绕业务瓶颈的邻域：关键链、延期批次、瓶颈设备、同换型块、资源替换、时间窗 repair；configured/effective 预算、迭代上限、no-op/fallback move 都必须可报告。
- **承载的子 feature**：`business-neighborhood-registry`、`vns-sa-local-search-upgrade`
- **触碰的现有代码 / 模块**：`optimizer_local_search.py`、`core/algorithms/greedy/dispatch/sgs.py`、`sgs_scoring.py`、`auto_assign.py`、`schedule_graph_dispatch_context.py`。

### 模块 E · ALNS 搜索层

- **职责**：实现纯 Python 的 ALNS 外壳：选择 destroy/repair 算子、记录算子权重、按 acceptance 接受或拒绝候选、持续维护 best/current。
- **承载的子 feature**：`alns-state-operators-core`、`alns-selection-acceptance-trace`
- **触碰的现有代码 / 模块**：新增 `core/services/scheduler/run/alns_*` 或同级窄职责模块；不直接放进 GreedyScheduler 内部。

### 模块 F · SGS repair 适配层

- **职责**：先定义 ALNS 局部拆修合同，再把被删掉的一小块工序交回现有 Greedy/SGS repair；repair 结果必须复用正式排产的 allowed-op、payload validation 和执行态保护语义。
- **承载的子 feature**：`alns-partial-repair-contract`、`alns-sgs-repair-adapter`
- **触碰的现有代码 / 模块**：`schedule_signature_support.py`、`schedule_optimizer_steps.py`、`GreedyScheduler.schedule()` 调用合同、`graph_ready_context` 合同、`schedule_input_collector.py`、`schedule_payload_contract.py`、`schedule_execution_persistence_guard.py`。

### 模块 G · 接入与展示边界层

- **职责**：让新算法候选接回 `OptimizationOutcome`、候选比较、summary、diagnostics，同时修掉已知内部 id 泄漏风险。
- **承载的子 feature**：`diagnostic-public-id-boundary-fix`、`optimizer-integration-auto-selection`
- **触碰的现有代码 / 模块**：`scheduler_analysis_diagnostic_*`、`schedule_summary_*`、`schedule_candidate_*`、OperationLogs 投影。

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 `OptimizationSearchReport`

**方向**：搜索合同层 -> summary / diagnostics / candidate comparison
**形式**：纯 dict，挂到 `OptimizationOutcome` 后再由 summary 层投影。

**契约**：

```python
OptimizationSearchReport = {
    "schema_version": 1,
    "algorithm_profile": "baseline|grasp|ig|vns|sa|alns",
    "seed": 0,
    "stop_reason": "baseline_scheduled|completed|time_budget|iteration_limit|no_improvement|target_reached|all_candidates_rejected|optional_warmstart_failed|repair_failed|validation_error",
    "best_origin": "baseline|ortools_warmstart|multi_start|local_search|grasp|ig|vns|sa|alns",
    "time_budget_seconds": 0,
    "runtime_ms": 0,
    "iterations": 0,
    "evaluated_candidates": 0,
    "distinct_candidates": 0,
    "accepted_candidates": 0,
    "accepted_distinct_candidates": 0,
    "rejected_candidates": 0,
    "initial_fingerprint": None,
    "best_fingerprint": None,
    "best_fingerprint_changed": False,
    "best_score": [],
    "objective_name": "min_overdue",
    "attempts": [],
    "improvement_trace": [],
}
```

**约束**：

- `stop_reason` 必填，不能靠缺字段表示“正常结束”。
- `seed` 必填；随机算法必须只使用由该 seed 派生出的 RNG。
- `best_origin` 必填；baseline、warm-start、multi-start、local-search、GRASP/IG/VNS/SA/ALNS 的最优来源必须可解释。
- `distinct_candidates` 和 `accepted_distinct_candidates` 必须来自同一套 `CandidateFingerprint` 合同；不能把同一个排序或同一个解码结果重复计成不同候选。
- `best_fingerprint_changed=False` 时，public summary 必须写明“本轮未得到不同的更优方案”，不能把跑过搜索包装成改进成功。
- `attempts` 仍保留最多 12 条公开摘要；完整内部 trace 只能进入 diagnostics，不能进入 public 页面。
- `repair_failed` 不能返回原方案假装成功。
- `validation_error` 在主候选 / strict 模式下必须 fail-loud；在可选候选里只能记录为 `candidate_rejected`。
- 现有 optimizer 的每个 return 分支都必须进入同一份 report；不能只给新算法写 report，让 baseline fallback 或 optional failure 留在旧盲区。

**现有退出路径映射**：

| 真实路径 | `stop_reason` | `best_origin` | public 摘要 | diagnostics |
| --- | --- | --- | --- | --- |
| `state.best is None` 后跑 baseline 并成功 | `baseline_scheduled` | `baseline` | 说明未采纳增强候选，使用基础排产 | baseline 触发原因、输入规模、strict 状态 |
| 所有可选候选都被拒绝，但已有 baseline / best | `all_candidates_rejected` 或 `no_improvement` | 当前 best 来源 | 候选数、拒绝数、最终使用来源 | 聚合拒绝原因 |
| OR-Tools warm-start disabled / 无结果 / 非 strict 失败 | 不覆盖最终成功原因；attempt 记 `optional_warmstart_failed` | 当前 best 来源 | 可选 warm-start 未采纳 | 禁用/无结果/异常分类，不能含内部 id |
| local search 因 `algo_mode != improve`、`best is None`、order 太短而未进入 | 不覆盖最终成功原因；report 记 `skipped_phases` | 当前 best 来源 | 局部搜索未执行 | skip 原因、输入规模、当前 best 来源 |
| deadline 到达导致 local search 未进入或提前停止 | `time_budget` | 当前 best 来源 | 时间预算触发 | 预算、已用时、未执行阶段 |
| 达到迭代上限 | `iteration_limit` | 当前 best 来源 | 迭代上限触发 | configured/effective 迭代数 |
| strict 模式候选校验失败 | `validation_error` 后 fail-loud | 无 | 失败而非成功 outcome | 校验类型和安全摘要 |
| repair 失败 | `repair_failed` 或 `candidate_rejected` | 当前 best 来源 | repair 未采纳 | repair 失败分类，不能返回原方案假装成功 |

### 4.2 `BenchmarkReference`

**方向**：benchmark harness -> 测试门禁 / evidence / roadmap 评估
**形式**：JSON / dict，默认输出到 stdout 或临时目录。

**契约**：

```python
BenchmarkReference = {
    "reference_type": "proven_optimum|lower_bound|best_known|external_ub|folded_not_comparable",
    "objective_name": "min_overdue",
    "objective_metric_keys": ["overdue_count", "weighted_tardiness_hours", "total_tardiness_hours", "makespan_hours", "changeover_count"],
    "bound_metric": "makespan_hours",
    "bound_scope": "same_model|folded_fjsp|external_reference",
    "bound_is_objective_comparable": False,
    "oracle_status": "proven_optimal|timeout|node_limit|not_run",
    "oracle_optimum": None,
    "actual_metric_value": None,
    "lower_bound_value": None,
    "lower_bound_sources": ["critical_path", "machine_workload"],
    "best_known_upper_bound": None,
    "gap_to_oracle_pct": None,
    "gap_to_bound_pct": None,
    "gap_to_best_known_pct": None,
    "oracle_stats": {
        "nodes": 0,
        "pruned_by_bound": 0,
        "pruned_by_dominance": 0,
        "runtime_ms": 0,
    },
    "public": {
        "case_slug": "mk01",
        "status": "reference|not_comparable|failed",
        "aggregate_counts": {},
    },
    "diagnostics_ref": None,
}
```

**约束**：

- 如果 `oracle_status != proven_optimal`，报告里禁止写“已证明全局最优”。
- 每个 `lower_bound_value` 必须声明 `objective_name`、`objective_metric_keys`、`bound_metric`、`bound_scope` 和 `bound_is_objective_comparable`。
- 只有同模型、同目标、同指标的 reference 才能用于证明 objective gap；`makespan_hours` 下界不能证明 `min_overdue`、`min_tardiness`、`min_changeover` 的全目标最优。
- FJSP 折叠样本、外部 UB/BKS 或指标不匹配的 lower bound 只能标记为参考，不能写成全局最优证明。
- 如果实际 `actual_metric_value < lower_bound_value`，说明下界或指标错误，必须 fail。
- 多指标 objective 只能在所有目标分量都有可比较 reference 时报告全目标 gap；否则只能报告单指标参考 gap。
- `public` 只允许 case slug、objective、metric、reference_type、gap、status、aggregate counts、runtime 这类摘要。
- raw `op_id`、`node_id`、`candidate_id`、`source_table`、`op:...`、内部 sample 只能进 diagnostics；stdout、Markdown、CI artifact 和 tracked evidence 默认都不得输出 raw internal id。
- `diagnostics_ref` 只能指向 ignored/temp 目录或受控 diagnostics artifact；不能让页面、导出、OperationLogs 直接渲染。
- benchmark 默认不能写 `evidence/Benchmark/*.md`；只有显式 `--write-report` 才能写 tracked evidence。
- `--write-report` 写 tracked evidence 前必须通过 public sanitization check。
- tracked evidence 被更新后，最终 clean proof 必须重新跑质量门禁。

### 4.3 `SearchProfile`

**方向**：配置 / candidate specs -> optimizer
**形式**：纯 dict；字段进入 optimizer 前必须 strict 校验。

**契约**：

```python
SearchProfile = {
    "profile": "baseline|grasp|ig|vns|sa|alns",
    "enabled": True,
    "seed": 0,
    "configured_time_budget_seconds": 0,
    "effective_time_budget_seconds": 0,
    "configured_max_iterations": 0,
    "effective_max_iterations": 0,
    "iteration_limit_source": "user|profile_default|system_limit",
    "restart_after_iterations": 0,
    "neighborhoods": ["critical_chain", "tardy_window", "bottleneck_machine"],
    "acceptance": "improve_only|threshold|record_to_record|simulated_annealing",
    "repair": "sgs",
    "system_limit_applied": False,
    "system_limit_reason": None,
}
```

**约束**：

- 未知 `profile`、`neighborhood`、`acceptance`、`repair` 必须 `ValidationError`。
- 本路线内 `repair` 只允许 `sgs`；不允许偷偷接 OR-Tools 或新重依赖。
- `record_to_record` 表示 Record-to-Record Travel 接受准则；文档、配置和 trace 都不得使用容易误解的英文缩写。
- 时间预算、迭代次数、破坏比例必须有上限；非法值不能静默改默认。
- 合法配置被系统上限截断时，必须报告 configured/effective 值、`iteration_limit_source` 和 `system_limit_reason`。
- no-op 邻域、小规模无法移动、`swap_fallback` 这类 fallback move 必须进入 trace，标记 `fallback_reason` 或 `candidate_rejected=noop_neighbor`；不能让用户误以为目标邻域真的执行成功。
- 达到时间预算必须 `stop_reason=time_budget`，达到迭代上限必须 `stop_reason=iteration_limit`；不能只返回当前 best。

### 4.4 `CandidateFingerprint`

**方向**：candidate construction / local search / ALNS -> search report / benchmark
**形式**：稳定生成的内部 dict；public 只能展示计数和“是否真的变了”，不能展示内部 id 组成。

**契约**：

```python
CandidateFingerprint = {
    "schema_version": 1,
    "fingerprint_scope": "decision|decoded_output",
    "objective_name": "min_overdue",
    "decision_fingerprint": "stable-hash",
    "output_fingerprint": "stable-hash",
    "parent_fingerprint": None,
    "same_as_parent": False,
    "same_as_seen": False,
    "fingerprint_changed": True,
}
```

**约束**：

- `decision_fingerprint` 至少覆盖 `objective_name`、`dispatch_mode`、`dispatch_rule`、`batch_order`、资源 override、locked seed 范围和 mutable scope。
- `output_fingerprint` 至少覆盖被正式 SGS 解码后的排程结构摘要：排入 / 失败数量、工序-资源-时间归一化签名、主目标指标签名；内部 op/resource id 只能进 diagnostics。
- `evaluated_candidates` 可以统计 decode 调用次数；`distinct_candidates` 只能统计 `decision_fingerprint` 或 `output_fingerprint` 未见过的候选，二者口径必须在 report 中声明。
- `same_as_parent=True` 或 `same_as_seen=True` 时，结果只能是 `no_change` / `candidate_rejected=same_fingerprint` / `feasible_but_not_accepted`，不能记成 improvement。
- 宣称 `improved=True` 必须同时满足：fingerprint 改变、按当前 objective 的 `score` 严格更优、且通过 acceptance；缺一项都只能报告为未改进。
- fingerprint 生成必须确定性可复现，不得依赖 dict 随机遍历顺序、对象内存地址、当前时间或非 seed 派生随机数。

### 4.5 `NeighborhoodMove`

**方向**：业务邻域层 -> local search / ALNS
**形式**：内部 dict，只能进 diagnostics，public 只能看中文汇总。

**契约**：

```python
NeighborhoodMove = {
    "name": "critical_chain|tardy_window|bottleneck_machine|changeover_block|resource_alternative|time_window",
    "scope": "batch|operation|machine|time_window",
    "selected_operation_ids": [],
    "selected_batch_ids": [],
    "selected_machine_ids": [],
    "reason": "critical_path|overdue|unmatched_resource|changeover|random",
}
```

**约束**：

- `selected_operation_ids`、`selected_machine_ids` 这类内部 id 不得进入页面正文、导出或 public payload。
- move 只负责提出“动哪一块”，不能直接写开始结束时间。
- 最终落位必须走现有 `GreedyScheduler.schedule()` / SGS / `estimate_internal_slot()` 链路。

### 4.6 `PartialRepairContract`

**方向**：ALNS destroy/repair -> SGS repair -> 候选评分 / 采纳
**形式**：内部 dict，创建 repair request 时必须完整传入。

**契约**：

```python
PartialRepairContract = {
    "repair_scope": "time_window|critical_chain|bottleneck_machine|tardy_batch|changeover_block",
    "removed_operation_ids": [],
    "protected_operation_ids": [],
    "schedule_output_allowed_op_ids": [],
    "payload_validation_operation_ids": [],
    "execution_fixed_op_ids": [],
    "execution_completed_op_ids": [],
    "requires_payload_validation": True,
    "requires_execution_guard": True,
    "mutable_seed_results_allowed": False,
}
```

**约束**：

- `removed_operation_ids` 必须全部出现在 `schedule_output_allowed_op_ids` 内；不在范围内的工序不能被拆、不能被重排。
- `execution_fixed_op_ids`、`execution_completed_op_ids`、冻结工序和历史正式计划不能作为 destroy 对象。
- `seed_results` 只能承载 `protected_operation_ids`、`execution_fixed_op_ids`、`execution_completed_op_ids` 这类不可变片段；`removed_operation_ids` / mutable scope 内不得由新算法预先生成带时间的 `ScheduleResult`。
- mutable scope 内的新方案只能通过 `batch_order_override`、资源 / 规则 override、repair request 进入 Greedy/SGS；start/end 必须由 `estimate_internal_slot()` 和正式 dispatch 链产生。
- repair 结果进入评分前，必须复用 `build_validated_schedule_payload()` 等价校验语义；进入正式采纳前，还必须通过执行态保护语义。
- repair 后如果出现漏工序、重复工序、越界工序、资源缺失、前后顺序冲突或执行态冲突，只能 `candidate_rejected` / `repair_failed`，不能降级成原方案成功。

### 4.7 `ALNSOperatorResult`

**方向**：ALNS 搜索层 -> 搜索合同与 diagnostics
**形式**：内部 dict。

**契约**：

```python
ALNSOperatorResult = {
    "destroy_operator": "critical_path_removal",
    "repair_operator": "serial_sgs_repair",
    "removed_count": 0,
    "repair_status": "ok|rejected|failed",
    "accepted": False,
    "fingerprint_changed": True,
    "score_before": [],
    "score_after": [],
    "operator_reward": 0.0,
}
```

**约束**：

- repair 必须把被删工序全部放回，或者明确 `repair_status=failed`。
- 任何重复工序、漏工序、破坏前后顺序、资源冲突，都必须拒绝候选。
- `fingerprint_changed=False` 时不能发放 improvement reward，只能按 no-change / rejected 口径统计。
- operator reward 只影响后续选择概率，不能直接覆盖 objective score。

### 4.8 Public / Diagnostics 分层协议

**方向**：optimizer / graph / ALNS -> 页面 / OperationLogs

**public 允许**：

- `status`
- `stop_reason`
- `algorithm_profile`
- `runtime_ms`
- `iterations`
- `best_score`
- `objective_name`
- `evaluated_candidates`
- `accepted_candidates`
- `distinct_candidates`
- `improved`
- `best_fingerprint_changed`
- `attempts_public`
- 中文说明

**diagnostics 允许**：

- 内部 move 样本
- operator weight
- rejected candidate origin
- 内部 op_id / node_id 采样
- benchmark 内部样本和 proof harness 诊断 artifact

**约束**：

- diagnostics 不得直接被页面普通模板渲染。
- 已知的 `critical_path_sample` / `node_metrics_sample.node_id` / `unmatched_operation_ids_sample` 需要先修 public 边界。
- `optimizer-search-report-contract` 及任何新增 attempts / trace / move 样本都必须依赖这条边界修复完成。
- public 只能展示 `attempts_public`，且每条只允许 `tag`、`strategy`、`dispatch_mode`、`dispatch_rule`、`score`、`failed_ops`、`candidate_status`、安全中文说明；不得把原始 `attempts` dict 整包投到 public。
- `optimizer-proof-harness` 的 stdout / JSON / Markdown / CI artifact / tracked evidence 也必须遵守 public / diagnostics 分层。
- OperationLogs 只收 public 小摘要，不收完整图、完整 trace、完整 operator 样本。

## 5. 子 feature 清单

1. **optimizer-proof-harness** — 建立 tiny oracle、lower bound 和不写 tracked evidence 的 benchmark check 模式。
   - 所属模块：证明与评测底座
   - 依赖：无
   - 状态：planned
   - 对应 feature：未启动
   - 备注：最小闭环；每条 gap 必须绑定目标和指标，benchmark public 输出必须脱敏，没有它，后续算法增强无法证明收益。

2. **diagnostic-public-id-boundary-fix** — 修复诊断页展示 `op:...`、数字 `op_id`、内部样本的 public 边界问题。
   - 所属模块：接入与展示边界层
   - 依赖：无
   - 状态：planned
   - 对应 feature：未启动
   - 备注：新增 trace / attempts / move / benchmark 样本前必须先修。

3. **optimizer-search-report-contract** — 给 optimizer 增加 `stop_reason`、seed、搜索统计、候选拒绝原因和 trace 合同。
   - 所属模块：搜索合同与可观测层
   - 依赖：`optimizer-proof-harness`、`diagnostic-public-id-boundary-fix`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：baseline fallback、optional warm-start failure、return best、all rejected、time budget、iteration limit 都必须有明确 stop_reason / best_origin。

4. **optimizer-candidate-profile-contract** — 定义非 OR-Tools 搜索 profile，收紧配置校验和非法参数 fail-loud 合同。
   - 所属模块：候选构造层
   - 依赖：`optimizer-search-report-contract`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：configured/effective budget、iteration、restart、system limit 必须可报告；非法值不能静默 clamp。

5. **distinct-candidate-fingerprint-contract** — 定义候选指纹、去重计数、same-fingerprint 拒绝和 improved 判定。
   - 所属模块：候选构造层
   - 依赖：`optimizer-candidate-profile-contract`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：防止重复顺序、重复解码结果或返回原方案被包装成“探索到很多不同方案”。

6. **grasp-ig-candidate-construction** — 用 GRASP / Iterated Greedy 生成更多可行起点，仍由现有 SGS 落位。
   - 所属模块：候选构造层
   - 依赖：`distinct-candidate-fingerprint-contract`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：只生成 order / priority / rule 候选，不生成 `ScheduleResult`、start/end 或 mutable seed。

7. **business-neighborhood-registry** — 建立关键链、延期批次、瓶颈设备、换型块、资源替换、时间窗 repair 的邻域注册表。
   - 所属模块：业务邻域层
   - 依赖：`distinct-candidate-fingerprint-contract`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：邻域只描述 mutable scope 和 move reason，不提前写任何可变工序时间。

8. **vns-sa-local-search-upgrade** — 把现有 local search 升级为 VNS / SA 后处理，先做轻量可复现版本。
   - 所属模块：业务邻域层
   - 依赖：`grasp-ig-candidate-construction`、`business-neighborhood-registry`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：no-op 邻域和 fallback move 必须 trace；Record-to-Record Travel 必须写全称；达到预算或迭代上限必须给 stop_reason。

9. **alns-partial-repair-contract** — 定义 ALNS 局部拆修的 allowed-op、payload validation 和执行态保护复用合同。
   - 所属模块：SGS repair 适配层
   - 依赖：`business-neighborhood-registry`
   - 状态：planned
   - 对应 feature：未启动

10. **alns-state-operators-core** — 建立 ALNS state、destroy/repair operator 接口、operator reward 和权重更新。
   - 所属模块：ALNS 搜索层
   - 依赖：`alns-partial-repair-contract`
   - 状态：planned
   - 对应 feature：未启动

11. **alns-sgs-repair-adapter** — 把 ALNS repair 接到现有 SGS，确保 repair 后完整校验并返回候选结果。
   - 所属模块：SGS repair 适配层
   - 依赖：`alns-state-operators-core`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：`seed_results` 只能放保护/执行态固定片段，mutable operations 必须由 SGS 重新落位。

12. **alns-selection-acceptance-trace** — 实现 ALNS operator 选择、threshold / Record-to-Record Travel / SA acceptance、segment 权重更新和 trace 输出。
    - 所属模块：ALNS 搜索层
    - 依赖：`alns-sgs-repair-adapter`
    - 状态：planned
    - 对应 feature：未启动

13. **optimizer-integration-auto-selection** — 把 GRASP/IG/VNS/SA/ALNS 候选接回 `OptimizationOutcome`、候选比较和 summary。
    - 所属模块：接入与展示边界层
    - 依赖：`diagnostic-public-id-boundary-fix`、`vns-sa-local-search-upgrade`、`alns-selection-acceptance-trace`
    - 状态：planned
    - 对应 feature：未启动

14. **benchmark-ratchet-quality-gate** — 把 tiny oracle、非劣化阈值、稳定性统计纳入轻/中/长三层门禁。
    - 所属模块：证明与评测底座
    - 依赖：`optimizer-integration-auto-selection`
    - 状态：planned
    - 对应 feature：未启动

15. **long-run-tuning-evidence** — 建立长跑调参、operator 权重、不同 seed 的统计证据和归档口径。
    - 所属模块：长跑调参与门禁层
    - 依赖：`benchmark-ratchet-quality-gate`
    - 状态：planned
    - 对应 feature：未启动

**最小闭环**：第 1 条 `optimizer-proof-harness` 做完后，系统能在不改写 tracked evidence 的前提下，运行 tiny oracle / lower bound / 当前算法对比，并明确输出“是否证明最优、gap 绑定的是哪个目标和指标、是否只能参考”。

## 6. 排期思路

默认顺序按“先证明，再修 public 边界，再加可观测，再扩搜索，再接 ALNS，最后进门禁”推进。

1. **先做证明与评测**：否则所有算法增强都只能凭感觉说更好。
2. **先修诊断 public 边界**：新增 trace 前先堵住内部 id 样本外露。
3. **再做搜索合同**：没有 `stop_reason`、seed 和 trace，调不清楚，也没法解释为什么没变好。
4. **先做候选指纹，再做 GRASP/IG 和业务邻域**：先保证“不同候选”有统一口径，再扩大起点和邻域；它们最贴近现有 Greedy/SGS，改动面比完整 ALNS 小。
5. **再做 VNS/SA**：作为现有 local search 的升级，不先碰持久化和页面。
6. **再做 ALNS**：先完成 `alns-partial-repair-contract`，再引入 destroy/repair/weight 外壳。
7. **最后进质量门禁**：避免性能和随机性把普通 PR 门禁拖垮；轻/中/长三层分开。

## 7. 观察项

- `.codestable/roadmap/networkx-scheduler-graph-introduction/` 已经完成图分析引入，本路线不能重复“再引入图算法”，只能消费已有图指标。
- `.codestable/roadmap/aps-three-gap-directions/` 当时明确“不重写排程算法”，那是面向方案解释和现场反馈的范围；本路线是新的算法搜索能力，不能塞进旧路线。
- `schedule-delay-diagnosis` requirement 仍是 draft，但相关能力在多个路线里已有实现片段，后续可能需要单独 `cs-req update`。
- `candidate-comparison-business-view` 已是 current，但 `VISION.md` 中状态可能需要刷新。
- `diagnostic-public-id-boundary-fix` 更像 issue/安全边界修复；本路线把它列为新增 search report / diagnostics 的前置 feature，也可以单独走 `cs-issue` 先完成。
- 当前工作区已有未提交改动和 benchmark evidence 修改，任何 clean proof 都必须在最新 HEAD 与干净工作区上重新跑。

## 8. 变更日志

- 2026-06-26：创建 roadmap。基于本地调用链、9 个只读 Sub Agent、Exa 深研和现有 CodeStable 路线整理；本阶段明确不引入 OR-Tools，主线为 proof harness + public 边界修复 + GRASP/IG + VNS/SA + ALNS with SGS repair。
- 2026-06-26：根据线上审阅补强 `APPROVE_WITH_CHANGES` 三项：optimizer 退出路径映射、SearchProfile configured/effective 报告、benchmark public/diagnostics 分层。
- 2026-06-26：吸收非 OR-Tools 深研报告审阅意见：新增 `distinct-candidate-fingerprint-contract`，收紧全局最优口径、第三方库依赖边界、Record-to-Record Travel 全称命名和 same-fingerprint 不得伪成功合同。
