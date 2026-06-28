---
doc_type: roadmap
slug: scheduler-global-optimizer
status: active
created: 2026-06-26
last_reviewed: 2026-06-28
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

- 本阶段不新增 OR-Tools 作为算法依赖，也不把 OR-Tools 变成主引擎。注意 OR-Tools **当前已作为可选 warm-start 分支存在但默认关闭**（`ortools_enabled` 默认 `no`，且仅在 `algo_mode=improve` 下尝试，不进 `requirements.txt`，缺包走可见降级）；本条约束的是“不把这个已有可选分支升级成主引擎 / 必选依赖”，而非声称仓库内不存在 ortools 代码。
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
    "public_attempt_summary": [],
    "improvement_trace": [],
    "skipped_phases": [],
    "rejection_summary": {},
}
```

**约束**：

- `stop_reason` 必填，不能靠缺字段表示“正常结束”。
- `seed` 必填；随机算法必须只使用由该 seed 派生出的 RNG。
- `best_origin` 必填；baseline、warm-start、multi-start、local-search、GRASP/IG/VNS/SA/ALNS 的最优来源必须可解释。
- `distinct_candidates` 和 `accepted_distinct_candidates` 必须来自同一套 `CandidateFingerprint` 合同；不能把同一个排序或同一个解码结果重复计成不同候选。
- `best_fingerprint_changed=False` 时，public summary 必须写明“本轮未得到不同的更优方案”，不能把跑过搜索包装成改进成功。
- `attempts` 仍保留最多 12 条公开摘要；完整内部 trace 只能进入 diagnostics，不能进入 public 页面。
- 本仓库 public 脱敏清单已把 `attempts_public` 视为内部禁用字段；等价 public 白名单摘要落为 `algo.attempts` 与 `search_report.public_attempt_summary`，raw `attempts` 只进入 diagnostics。
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
- 内部 id 脱敏口径统一见 4.8；本契约只补一条 benchmark 专属：stdout、Markdown、CI artifact 和 tracked evidence 默认都不得输出 raw internal id。
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

> **本阶段落地（item 4，2026-06-28）**：契约已落为 `core/services/scheduler/run/optimizer_candidate_profile.py` 的 `CandidateProfile`，作为 `OptimizationSearchReport.candidate_profile` 嵌套字段。与上方"前瞻契约"的差异均为「只锁现有能力」的有意收敛，非违反：①`profile` 取值现仅 `baseline`/`multi_start_local_search`（对应 algo_mode greedy/improve），`grasp/ig/vns/sa/alns` 待 item 6-10 落地再纳入，未知值仍 `ValidationError`；②`acceptance` 现仅 `improve_only`（局搜 score 严格更优的贪心接受），`threshold/record_to_record/simulated_annealing` 待 item 8；③`neighborhoods` 现仅 `swap/insert/block`（现有 batch_order 重排算子），业务邻域待 item 7；④`repair` 仅 `sgs`。另落地三个前瞻契约未列、但本阶段需要的诚实字段：`seed_source`（标 seed 由 version 派生）、`candidate_strategy_family`（multi_start/single_shot）、`validation_status`、`ortools_warmstart_enabled`（仅 improve 下且配置开启才 true，baseline 恒 false）。迭代上限 configured（time_budget×20）vs effective（钳到 [200,5000]）已区分，钳制如实写 `system_limit_reason`；`derive_iteration_limits` 是该公式唯一真相源，局搜与 profile 共用。

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
- `output_fingerprint` 至少覆盖被正式 SGS 解码后的排程结构摘要：排入 / 失败数量、工序-资源-时间归一化签名、主目标指标签名；内部 op/resource id 只能进 diagnostics（脱敏口径见 4.8）。
- `evaluated_candidates` 可以统计 decode 调用次数；`distinct_candidates` 只能统计 `decision_fingerprint` 或 `output_fingerprint` 未见过的候选，二者口径必须在 report 中声明。
- `same_as_parent=True` 或 `same_as_seen=True` 时，结果只能是 `no_change` / `candidate_rejected=same_fingerprint` / `feasible_but_not_accepted`，不能记成 improvement。
- 宣称 `improved=True` 必须同时满足：fingerprint 改变、按当前 objective 的 `score` 严格更优、且通过 acceptance；缺一项都只能报告为未改进。
- fingerprint 生成必须确定性可复现，不得依赖 dict 随机遍历顺序、对象内存地址、当前时间或非 seed 派生随机数。

> **本阶段落地（item 5，2026-06-28）**：契约已落为 `core/services/scheduler/run/optimizer_candidate_fingerprint.py`，并接入 `OptimizationSearchReportState`。`decision_fingerprint` 仍保留候选决策维度（objective、strategy/params、dispatch mode/rule、batch_order、resource、locked seed、mutable scope），但 `distinct_candidates` / `accepted_distinct_candidates` 已明确改为 `decoded_output` 口径：按正式解码后的 `output_fingerprint` 去重。`output_fingerprint` 只把正式 `ScheduleResult` 的工序-资源-时间签名、summary 数量和当前 objective score 放入 hash 输入；hash 和 fingerprint 事件只进 diagnostics，public / OperationLogs / size guard 只展示计数、`best_fingerprint_changed`、`improved` 与口径说明。`improved` 已显式拆为三条件：`fingerprint_changed` + `score_strictly_better` + `acceptance_passed`，其中 acceptance 复用 item 4 的 `candidate_profile.acceptance=improve_only`。`same_as_parent` / `same_as_seen` 会记 `same_fingerprint` 拒绝，不再把同一解码结果包装成不同候选或 improvement。

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

- `selected_operation_ids`、`selected_machine_ids` 这类内部 id 不得进入页面正文、导出或 public payload（脱敏口径见 4.8）。
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

> **成熟度（BDUF 收口）**：本契约服务 item 10-12（ALNS 最深、最远期的一段），下面的字段是**前瞻接口占位**。`operator_reward`、`score_before/after`、trace 形状须等 item 6-8（GRASP/IG/VNS/SA）实际落地、看清真实需要后，在 item 10 启动时再定稿，避免在消费者出现前过早逐字段钉死。与此相对，4.6 `PartialRepairContract` 不属于投机设计——它主要把现有正式排产守门链（allowed-op / payload 校验 / repair 失败不许伪成功）提前锁住，是对既有安全不变式的防御，保持现状即可。

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

> **单一真相源**：本节是 public/diagnostics **展示边界与内部 id 脱敏**的唯一权威。其他契约（4.2 / 4.4 / 4.5 / 4.6）凡涉及“内部 id 只进 diagnostics、public 只放摘要”一律**引用本节口径**，不再各自复述；各契约自身只保留其**业务语义**规则（如 repair 失败不许伪成功、same-fingerprint 不算改进、operator reward 不覆盖 score），那些不收敛到本节。

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
- `algo.attempts` / `search_report.public_attempt_summary` 这类等价 public 白名单摘要
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
- public 只能展示 `algo.attempts` / `search_report.public_attempt_summary` 这类等价 public 白名单摘要，且每条只允许 `tag`、`strategy`、`dispatch_mode`、`dispatch_rule`、`score`、`failed_ops`、`candidate_status`、安全中文说明；不得把原始 `attempts` dict 整包投到 public；当前脱敏清单禁止新建名为 `attempts_public` 的 public 字段。
- `optimizer-proof-harness` 的 stdout / JSON / Markdown / CI artifact / tracked evidence 也必须遵守 public / diagnostics 分层。
- OperationLogs 只收 public 小摘要，不收完整图、完整 trace、完整 operator 样本。
- 2026-06-26 本轮已把 public algo 摘要、图分析摘要、候选方案展示、普通 HTML、导出 filters 和 OperationLogs 普通用户投影收紧为显式白名单；`attempts` 非 list 时直接从 public 输出移除，不能把原始 dict 原样带出。

## 5. 子 feature 清单

1. **optimizer-proof-harness** — 建立 tiny oracle、lower bound 和不写 tracked evidence 的 benchmark check 模式。
   - 所属模块：证明与评测底座
   - 依赖：无
   - 状态：done
   - 对应 feature：`2026-06-26-optimizer-proof-harness`
   - 备注：最小闭环；每条 gap 必须绑定目标和指标，benchmark public 输出必须脱敏，没有它，后续算法增强无法证明收益。

2. **diagnostic-public-id-boundary-fix** — 修复诊断页展示 `op:...`、数字 `op_id`、内部样本的 public 边界问题。
   - 所属模块：接入与展示边界层
   - 依赖：无
   - 状态：done
   - 对应 feature：`2026-06-26-diagnostic-public-id-boundary-fix`
   - 备注：public 只保留安全摘要；diagnostics/internal 仍可保留内部调试信息，但不得进入普通页面、普通 HTML、导出和 OperationLogs public 投影。

3. **optimizer-search-report-contract** — 给 optimizer 增加 `stop_reason`、seed、搜索统计、候选拒绝原因和 trace 合同。
   - 所属模块：搜索合同与可观测层
   - 依赖：`optimizer-proof-harness`、`diagnostic-public-id-boundary-fix`
   - 状态：done
   - 对应 feature：`2026-06-27-optimizer-search-report-contract`
   - 备注：已新增 `OptimizationSearchReport` 归一模块和 public 投影：baseline fallback、multi-start、optional warm-start failure、ValidationError candidate_rejected、local search skipped/noop、time budget、iteration limit、no improvement 都有明确 `stop_reason` / `best_origin` / seed / 统计字段。public 只展示安全摘要；raw attempts、内部 fingerprint、完整 trace 留 diagnostics；summary size guard 的最小摘要路径也保留 search_report public 小摘要。未做 item 4 candidate profile、item 5 完整 CandidateFingerprint，也未引入 GRASP / IG / VNS / SA / ALNS。

4. **optimizer-candidate-profile-contract** — 定义非 OR-Tools 搜索 profile，收紧配置校验和非法参数 fail-loud 合同。
   - 所属模块：候选构造层
   - 依赖：`optimizer-search-report-contract`
   - 状态：done
   - 对应 feature：`2026-06-28-optimizer-candidate-profile-contract`
   - 备注：已新增 `core/services/scheduler/run/optimizer_candidate_profile.py`（`CandidateProfile` + `build_candidate_profile` + `derive_iteration_limits`），并作为嵌套字段接入 `OptimizationSearchReport.candidate_profile`，`algorithm_profile` 改由 profile 稳定派生（删除旧模糊串函数）。configured/effective 的 time budget 与 max_iterations 已区分；迭代 `[200,5000]` 系统钳制如实写 `system_limit_applied`/`system_limit_reason`（`iteration_floor`/`iteration_ceiling`）/`iteration_limit_source`；`derive_iteration_limits` 是迭代上限/重启阈值唯一真相源，`optimizer_local_search` 改为共用、行为逐位不变。未知 `profile`/`repair`/`acceptance`/`neighborhood` 与非法 `budget` 一律 fail-loud（与 strict 无关）。profile public 只投白名单安全摘要（`profile_public`），配置来源/邻域等只进 `profile_diagnostics`；size guard 最小摘要保留 `profile_public`。`seed` 如实标记为 version 派生（`seed_source`）。**本阶段 profile 取值限 `baseline`/`multi_start_local_search`**（§4.3 full enum 的 `grasp/ig/vns/sa/alns` 待 item 6-10 扩展，未知值仍 `ValidationError`）；`repair` 仅 `sgs`、`acceptance` 仅 `improve_only`、`neighborhoods` 仅 `swap/insert/block`。未做 item 5 完整 CandidateFingerprint，也未引入新搜索算法。

5. **distinct-candidate-fingerprint-contract** — 定义候选指纹、去重计数、same-fingerprint 拒绝和 improved 判定。
   - 所属模块：候选构造层
   - 依赖：`optimizer-candidate-profile-contract`
   - 状态：done
   - 对应 feature：`2026-06-28-distinct-candidate-fingerprint-contract`
   - 备注：已新增 `CandidateFingerprint` 合同并接入 search report；distinct 统一按 `decoded_output` 去重并在 public/minimal 摘要声明口径；decision/output hash 与 fingerprint 事件只进 diagnostics；`improved` 显式要求 fingerprint 改变、score 严格更优、通过 `improve_only` acceptance；same-fingerprint 只记拒绝/未改进。未新增候选构造、未引入 GRASP / IG / VNS / SA / ALNS。

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

## 6. 排期思路：两段式 + 证据闸门

本路线**不是一条线性深链**。它分两段，中间用第 1 条 proof harness 产出的证据做闸门——这正是把 harness 排在最前的意义：先有量尺，再决定要不要投最贵的搜索。

### Phase A · 近期可交付段（贴现有主链，低风险，逐项独立集成）

覆盖 item 1-6（proof-harness、public 边界修复已 done）：proof 底座 → public 边界修复 → 搜索可观测合同 → 候选 profile/指纹 → GRASP/IG 候选构造。它们都紧贴现有 Greedy/SGS，改动面小、各自能独立产生价值。

排期要点：
1. **proof harness（item 1，done）**：先有量尺，否则一切“更好”都是凭感觉。
2. **public 边界修复（item 2，done）**：它是后续一切 trace/attempt/move/benchmark 样本的硬前置；后续 item 3 起新增 public 字段必须复用本轮投影函数，不能在模板或导出层临时拼过滤。
3. **搜索可观测合同（item 3）**：补 `stop_reason`、显式 seed、候选拒绝原因、trace；多为把现有 attempts/`candidate_rejected`/version→RNG 半成品**显式化归一**，不是从零造。
4. **候选 profile + 指纹（item 4-5）**：先把“不同候选”口径钉死，再扩起点。
5. **GRASP/IG（item 6）**：贴现有 SGS 落位，改动面最小。

**增量集成（关键，避免价值被劫持）**：GRASP/IG 一旦在 item 6 可用，应作为**自己的集成里程碑**当即接回 `OptimizationOutcome`/候选比较，**不要**等到 item 13 跟全套 ALNS 一起大爆炸上线。即 item 13 的职责收敛为“多算法统一自动选择”，而每个算法的生产接入是增量的。

### 证据闸门（Phase A → Phase B 的启动条件）

Phase B（VNS/SA 深化 + 完整 ALNS + 长跑调参）**不无条件启动**。先决条件：Phase A 完成后，用 proof harness + benchmark 在目标 case 上给出证据，**证明 GRASP/IG + 现有 SGS 距 oracle/可靠下界仍留有值得用 ALNS 去填的 gap**。

- 若证据显示 Phase A 已逼近下界 / gap 很小：Phase B 降级为“后续候选研究”，不挤占主线，不为“看起来高级”硬上纯 Python ALNS。
- 若证据显示 gap 显著且稳定：才解锁 Phase B，并继续用同一套 harness 度量每一步是否真的不劣化。

这条闸门让 item 9-15 的高风险投入**由数据解锁而非提前承诺**，否则就违背了 item 1 存在的理由。

### Phase B · 证据解锁段（高风险 / 研究型，单独立项推进）

覆盖 item 7-15：业务邻域 → VNS/SA → 完整 ALNS 外壳（state/operator/selection/acceptance + SGS repair adapter）→ 统一自动选择 → 三层门禁 → 长跑调参证据。其中 ALNS 子链（item 9-12）是刚性四连，且在 Python3.8/Win7/无 numpy 的离线包里纯 Python 手写，投入大、收益须靠长跑证据才能证；务必在闸门放行后再启动，避免它堵死前段交付。

## 7. 观察项

- `.codestable/roadmap/networkx-scheduler-graph-introduction/` 已经完成图分析引入，本路线不能重复“再引入图算法”，只能消费已有图指标。
- `.codestable/roadmap/aps-three-gap-directions/` 当时明确“不重写排程算法”，那是面向方案解释和现场反馈的范围；本路线是新的算法搜索能力，不能塞进旧路线。**算法范围互不冲突，但契约面有真实重叠且须治理**：该路线已 completed 并定稿了 candidate-comparison（`CandidateCard`/`CandidateMetrics`、`diff=current-adopted`）、summary delta、`OverdueDiagnosisReport` 诊断、以及 program-field-vs-user-visible-text 的 public/id 边界。本路线模块 G（`diagnostic-public-id-boundary-fix`、`optimizer-integration-auto-selection`）会改到这四处共享契约——**这不是绿地，改动前必须回 aps-three-gap-directions 走它的 update gate（其 roadmap 明确“改字段/状态/路由/错误码前先回来 update”），不得单方面改动**。`diagnostic-public-id-boundary-fix` 因此是动他人已定稿契约的前置治理项，等级高于普通 issue（口径以那条 roadmap 文档为准：completed + 合同定稿 + update gate 存在；不等于已逐项核对所有相关代码面都已上线）。
- `schedule-delay-diagnosis` requirement 仍是 draft，但相关能力在多个路线里已有实现片段，后续可能需要单独 `cs-req update`。
- `candidate-comparison-business-view` 已是 current，但 `VISION.md` 中状态可能需要刷新。
- `diagnostic-public-id-boundary-fix` 更像 issue/安全边界修复；本路线把它列为新增 search report / diagnostics 的前置 feature，也可以单独走 `cs-issue` 先完成。
- 当前工作区已有未提交改动和 benchmark evidence 修改，任何 clean proof 都必须在最新 HEAD 与干净工作区上重新跑。
- 2026-06-26 经 proof-harness（item 1）实测发现：现有 `improve` 局部搜索在 SGS 派工模式下是**结构性 no-op**。其唯一邻域是 swap/insert/block 重排 `batch_order`（`core/services/scheduler/run/optimizer_local_search.py:15-61`），但 SGS 只把 `batch_order` 当 `build_dispatch_key` 末位平手决胜键（`core/algorithms/dispatch_rules.py:33-36`、`core/algorithms/greedy/dispatch/sgs.py:44-48,99,215`），slack/atc 近似连续几乎不平手，故批次顺序重排几乎总解出同一张表。证据：SMTWT 同起点重排批次顺序 300 次 overdue 零变化，而 `batch_order` 派工模式下 206/300 更好（34→28）；默认 `dispatch_mode=batch_order` 经多起点扩展后 sgs 起点总胜出、局搜继承胜出起点模式（`optimizer_local_search.py:253`），导致局搜恒 0 改进且空烧满 `time_budget`（budget 5/20s 结果一致）。
    - 治理归属：no-op 如实记 + 到预算止损归 **item 3 `optimizer-search-report-contract`**（§4.3 已明文要求 `candidate_rejected=noop_neighbor` 与 `stop_reason=time_budget`）；搜索空间本身的修复（让局搜搜在 SGS 决策空间上）归 **item 8 `vns-sa-local-search-upgrade`**（Phase B，受证据闸门约束）。本条为发现归档，按裁决本轮只归档、不改生产代码。
- 2026-06-26 目标↔基准覆盖盘点（决定后续换目标时拿什么证明）：系统当前有 4 个目标（`core/models/objective.py:18-46`）——`min_overdue` / `min_tardiness` / `min_weighted_tardiness` / `min_changeover`，**没有 makespan 目标**（`makespan_hours` 仅作各目标 5 元组里的低位平手决胜键，从不是主优化项）。
    - **可比覆盖现状**：目前只有 `min_overdue` 的**首分量 `overdue_count`** 有同模型同指标的精确最优基准（SMTWT + Moore-Hodgson，`tests/_support/optimizer_benchmark_grading.py`），且当前只给 **greedy** 打分、未给 improve 打分；`min_overdue` 后 4 个 tie-break 分量、以及其余 3 个目标**都没有可比的已证明最优基准**。
    - **拖期/加权拖期缺口**：SMTWT 自带的 `wtopt` 是**自由权重（1–10）的加权拖期**最优，而 APS 加权拖期只有 3 档（critical/urgent/normal），两套权重不同**不可比**；无权重的 1‖ΣT_j 是 NP-hard、本仓库无 oracle。故 `min_tardiness` / `min_weighted_tardiness` 短期只能用下界 / best-known 做参考，做不了"精确最优"对照。
    - **换型缺口**：`min_changeover` 量的是换型次数，**SMTWT / JSP / RCPSP 一个都不涉及换型**；要证明它须另引**顺序相关换型时间（SDST）基准**（如 OR-Library SDST 集），目前未下。
    - **makespan 基准（JSP/RCPSP/FJSP）定位**：它们量 makespan，而系统无 makespan 目标，故只能当 `folded_not_comparable` 参考；**仅当将来真新增 makespan 族目标时才会翻成可打分基准**。本系统以交期 / 换型为导向，makespan 是否值得设为目标存疑——建议保持参考态，不为"凑基准"硬加目标。
    - 归属：本盘点是 **item 14 `benchmark-ratchet-quality-gate`** 的前置输入（每个目标要单独配齐"同目标同指标的量尺"才能纳入非劣化门禁，且应把 improve 也纳入打分）；属观察归档，本轮不改代码。

- 2026-06-28 经 item 3 review + Codex 对抗复审：确认 item 3 落地的 `distinct_candidates` 与 `improved` 是**过渡口径**，正确实现归 **item 5 `distinct-candidate-fingerprint-contract`**（其 description 即「候选指纹、去重计数、same-fingerprint 拒绝和 improved 判定合同」）。**已在 item 5（2026-06-28）修复**。
    - `distinct_candidates`：原 `candidate_report_fingerprint` 把 `order`/`origin` 编入指纹（旧 `core/services/scheduler/run/optimizer_search_report.py:36-51`），叠加本节已记的 SGS 解码塌缩（不同 batch_order 解出同一张表），会让 distinct 在 improve 默认模式下系统性虚高。item 5 已改为 `output_fingerprint` / `decoded_output` 口径去重，并在 public / minimal search_report 里保留 `distinct_fingerprint_scope` 与中文口径说明。
    - `improved`：原 `improved = best_fingerprint_changed` 是单条件隐式耦合。item 5 已显式输出 `improvement_conditions`，并仅在 `fingerprint_changed`、`score_strictly_better`、`acceptance_passed` 三条件同时成立时 `improved=True`；当前 acceptance 与 item 4 的 `candidate_profile.acceptance=improve_only` 对齐。
    - `same_as_parent` / `same_as_seen`：item 5 已把重复 decoded output 记为 `same_fingerprint` 拒绝，不再计入新的 distinct，也不计入 improvement。
    - 同轮清理本 item 引入的两处代码债（非 item 5 范围）：删除 `finalize` 中 best 非空但无 accept 记录时的兜底 `mark_candidate_accepted`（生产不可达 + 破坏 `accepted_distinct ≤ distinct` 不变式，连带删 `finalize` 的 best 形参）、删除 `_runtime_ms` 的 `except Exception` 静默兜底（改为 clock 异常 fail-loud）；补 `no_improvement` / `all_candidates_rejected` 两个 stop_reason 回归测试。

- 2026-06-28 item 5 review 收尾（OPUS 子代理定向+盲审 + Codex 对抗复审，实跑 48+352 测试全绿、质量门禁 17/17）：确认 distinct/improved/public 边界实质达标，无破坏正确性或泄漏内部 id 的 blocker；按裁决根治 1 个崩溃缺陷并清理代码债——路线图无后续 item 覆盖的就地处理、已覆盖的留给对应 item。
    - **B1（崩溃缺陷，已修）**：`optimizer_candidate_fingerprint.py` 的 `_result_signature` 用类型不稳定的 `op_id` 作排序键首元素（旧 `_identity_value`：正整数→`int`、`0`/`None`→`""`），`results` 中 `op_id` 同时含正整数与 `0`/`None` 时排序抛 `TypeError`、中断整条 finalize 报告链。已删 `_identity_value`、签名内 `op_id` 统一 `str`，排序键类型恒定；补 op_id 混合回归测试。
    - **死代码/兜底清理**：删 `_resource_override_payload` 三个无写入方 key 别名（O1）；删孤儿函数 `candidate_report_fingerprint`/`attempt_report_fingerprint`/`stable_report_fingerprint`（O3，dead-code 岛屿 358→355）；删 `mark_candidate_rejected`/`mark_optional_warmstart_failed` 的 dead `attempt` 形参 + 4 调用点（O4）；删 report 层与 `distinct_fingerprint_scope` 值重复的冗余 `fingerprint_scope` 字段（M2）。补候选缺 `results`/非有限 score/非法 `seed_result_count` 三条 fail-loud 测试。
    - **M1（未改逻辑，已加注释）**：`acceptance_passed = accepted_candidates>1` 当前与 score 严格更优同真同假、结果正确，但未独立检验接受准则；归 **item 8 `vns-sa-local-search-upgrade`**（引入 threshold/Record-to-Record Travel/SA 接受非改进解后必须改为依据真实 acceptance 判定）。O2（`_mutable_scope_payload` fallback）复查为测试可达的优雅降级，撤回不删；I1/I2（`_jsonable` 有损降级）仅影响 diagnostics、`output_fingerprint` 不经该分支，仅加注释。
    - **遗留钉子（排产引擎层，非 item 5 范围，本轮不改）**：`batch_order` 落位（improve 默认重排）对 `op_id<=0` 无校验，而 SGS 经 `ready_queue` 对 `op_id<=0` fail-loud，二者不一致；根因是 `BatchOperation.id: Optional[int]` + `_build_internal_result`（`core/algorithms/greedy/internal_operation.py:211`）把 `None`/`0` 落成 `op_id=0`。B1 修复后指纹层对任意 op_id 已健壮（不再崩），引擎层"op_id=0 能否进正式 results"的不一致建议另立 issue 评估是否在 batch_order 也对齐 SGS 的 op_id 正整数 fail-loud。

## 8. 变更日志

- 2026-06-26：创建 roadmap。基于本地调用链、9 个只读 Sub Agent、Exa 深研和现有 CodeStable 路线整理；本阶段明确不引入 OR-Tools，主线为 proof harness + public 边界修复 + GRASP/IG + VNS/SA + ALNS with SGS repair。
- 2026-06-26：根据线上审阅补强 `APPROVE_WITH_CHANGES` 三项：optimizer 退出路径映射、SearchProfile configured/effective 报告、benchmark public/diagnostics 分层。
- 2026-06-26：吸收非 OR-Tools 深研报告审阅意见：新增 `distinct-candidate-fingerprint-contract`，收紧全局最优口径、第三方库依赖边界、Record-to-Record Travel 全称命名和 same-fingerprint 不得伪成功合同。
- 2026-06-26：完成 `optimizer-proof-harness` 最小闭环：新增 tiny exact oracle / objective_score 证明、makespan lower bound 参考字段、FJSP 折叠不可比引用口径和默认 stdout 的 check 脚本；默认不写 tracked evidence。
- 2026-06-26：经两轮深度 review + Codex 对抗核实后重构排期与契约口径。① 给 proof harness 补 `assert_oracle_decoder_matches_greedy` fail-loud 守卫，把 `same_model` 从字段声明改为每次运行由构造强制（oracle 解码须复现 greedy 实际所选排程，否则禁止声称证明）。② 排期改为 Phase A（item 1-6 贴主链、逐项增量集成）/ Phase B（item 7-15 由 harness 证据闸门解锁），item 2 标可并行，item 13 收敛为“统一自动选择”而非大爆炸集成。③ 4.7 `ALNSOperatorResult` 标注为前瞻接口占位（待 item 10 定稿），4.6 保持（属防御既有安全边界）。④ 4.8 设为 public/id 脱敏单一真相源，其余契约引用而非复述。⑤ OR-Tools 措辞精确化为“已有可选 warm-start 不升级为主引擎”。⑥ 把与已 completed 的 `aps-three-gap-directions` 的契约重叠升级为显式跨路线 update-gate 治理前置。
- 2026-06-26：完成 `diagnostic-public-id-boundary-fix`。public algo / graph / candidate / HTML / export / OperationLogs 统一走安全摘要投影；`attempts` 只允许 list 形态下的白名单字段，非 list 原始 dict 直接从 public 输出移除；第二轮定向复审与盲审均未发现 blocker。
- 2026-06-26：proof-harness 实测暴露现有 improve 局搜在 SGS 下结构性 no-op + 空烧 time_budget（证据见 §7 观察项）；确认机制治理归 item 3、搜索空间修复归 item 8，本轮只归档不改代码。
- 2026-06-26：补"目标↔基准覆盖盘点"（§7）：系统 4 目标无 makespan；仅 `min_overdue` 首分量 `overdue_count` 有精确可比基准且只测 greedy；拖期/加权拖期因权重口径不一致 + NP-hard 缺 oracle、换型缺 SDST 基准、JSP/RCPSP 属 makespan 休眠参考；列为 item 14 前置输入。本轮只归档不改代码。
- 2026-06-27：完成 `optimizer-search-report-contract`。新增 `core/services/scheduler/run/optimizer_search_report.py`、`core/services/scheduler/run/optimizer_step_report_hooks.py` 和 `core/services/scheduler/summary/optimizer_public_search_report.py`，`OptimizationOutcome`、orchestrator、candidate plan、summary、summary size guard 最小摘要和 OperationLogs 小摘要均接入 search report；新增 `tests/algorithm/test_optimizer_search_report_contract.py` 并登记 test registry，同时收紧 size guard 回归测试。验证覆盖 report 基础字段、baseline fallback、multi-start 成功、optional warm-start failure、strict ValidationError fail-loud、non-strict candidate_rejected、local search time_budget / iteration_limit / skipped、public/diagnostics 分层、size guard 最小摘要保留 public search_report 和 OperationLogs 摘要；proof harness 回归仍通过。边界：本轮只做报告合同，不做 item 4 candidate profile、item 5 完整 CandidateFingerprint，不做 GRASP / IG / VNS / SA / ALNS。
- 2026-06-28：item 3 `optimizer-search-report-contract` 收尾 review（3 个只读 OPUS 子代理 + Codex 对抗复审，实跑 52 项相关测试全绿）。总裁定：无破坏正确性或泄漏内部 id 的硬 blocker。按裁决本轮清理本 item 代码债（删 `finalize` 兜底 + best 形参、删 `_runtime_ms` 静默兜底）、补 `no_improvement` / `all_candidates_rejected` stop_reason 测试；`distinct_candidates` / `improved` 过渡口径归 item 5，已在 §7 钉遗留，本轮不改其实现。
- 2026-06-28：完成 `optimizer-candidate-profile-contract`（item 4）。新增 `core/services/scheduler/run/optimizer_candidate_profile.py`（`CandidateProfile` 合同 + `build_candidate_profile` fail-loud 校验 + `derive_iteration_limits` 迭代上限单一真相源），接入 `OptimizationSearchReport.candidate_profile`，`algorithm_profile` 改由 profile 稳定派生并删除旧 `_algorithm_profile` 模糊串函数；`optimizer_local_search` 的内联迭代/重启公式改为共用 `derive_iteration_limits`（逐位等价、零行为变化）；summary 层新增 `profile_public`/`profile_diagnostics` 白名单分层投影，size guard 最小摘要保留 `profile_public`。新增 `tests/algorithm/test_optimizer_candidate_profile_contract.py`（23 用例）并登记 test registry。验证覆盖 configured/effective budget&iteration 区分、系统钳制 floor/ceiling 如实报告、未知 profile/repair/acceptance/neighborhood + 非法 budget fail-loud（与 strict 无关）、baseline 不升 OR-Tools 主引擎、seed version 派生标注、public 无内部 id 泄漏、四出口（页面/OperationLogs/size guard/algo summary）分层不破。执行者记录中含 4 层 OPUS 对抗审查摘要，但仓库当前未附独立审查产物；如需作为可复核 proof，应补原始审查记录或链接。质量门禁 17/17 步通过（`--allow-dirty-worktree`，dirty/unbound proof，非 clean proof）。边界：profile 取值本阶段限 `baseline`/`multi_start_local_search`，repair 仅 `sgs`、acceptance 仅 `improve_only`、neighborhoods 仅 `swap/insert/block`；未做 item 5 完整 CandidateFingerprint，未引入 GRASP/IG/VNS/SA/ALNS。
- 2026-06-28：完成 `distinct-candidate-fingerprint-contract`（item 5）。新增 `core/services/scheduler/run/optimizer_candidate_fingerprint.py`，定义 `CandidateFingerprint`、decision/output 双指纹、decoded output 去重口径和 score 严格更优判定；`OptimizationSearchReportState` 改用 `output_fingerprint` 统计 `distinct_candidates` / `accepted_distinct_candidates`，public/minimal 摘要新增 distinct 口径说明，fingerprint hash 与事件留 diagnostics；`improved` 改为 fingerprint 改变 + score 严格更优 + acceptance 通过三条件，acceptance 对齐 item 4 `improve_only`；same-fingerprint 记 `same_fingerprint` 拒绝。新增 `tests/algorithm/test_optimizer_candidate_fingerprint_contract.py` 并登记 test registry；同步收紧 search_report、public boundary、size guard 与内部 id 脱敏测试。边界：未新增候选构造、未引入 GRASP / IG / VNS / SA / ALNS，未做业务邻域 registry。
- 2026-06-28：`distinct-candidate-fingerprint-contract`（item 5）review 收尾。根治 B1 指纹排序崩溃（`op_id` 在签名内统一 `str`、删 `_identity_value`，治本于指纹层）；清理死代码与兜底：删 `_resource_override_payload` 三个无写入方别名、删 3 个孤儿指纹函数（dead-code 岛屿 358→355）、删 `mark_candidate_rejected`/`mark_optional_warmstart_failed` 的 dead `attempt` 形参（含 4 调用点）、删 report 层冗余 `fingerprint_scope` 字段与 `FINGERPRINT_SCOPE` 常量；补缺 `results`/非有限 score/非法 `seed_result_count` 三条 fail-loud 测试 + op_id 混合回归。M1（`acceptance_passed` 间接代理）已加注释并归 item 8；I1/I2（`_jsonable` 有损降级，仅 diagnostics）仅加注释；O2（`_mutable_scope_payload` fallback）复查为测试可达的优雅降级，撤回不删。遗留：`batch_order` 引擎层 `op_id<=0` 不拦（与 SGS `ready_queue` fail-loud 不一致，根因 `BatchOperation.id: Optional[int]`），归排产引擎另立 issue。实跑 48+352 测试全绿、质量门禁 17/17 通过（`--allow-dirty-worktree`，dirty/unbound proof）。
