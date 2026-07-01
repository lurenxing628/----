---
doc_type: roadmap
slug: scheduler-global-optimizer
status: active
created: 2026-06-26
last_reviewed: 2026-07-01
tags: [scheduler, optimizer, global-search, graph-ready, alns, benchmark, python38, win7]
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

本轮外部调研和基准复核结论：

- 不引入 OR-Tools 时，短期最适合的是 GRASP / Iterated Greedy、Simulated Annealing、VNS。
- 2026-06-29 基准复核后，后续主线先转向工序图就绪队列派工：在有工序前后关系的柔性作业车间样例上，工序图就绪队列派工已经明显优于批次顺序派工和普通串行派工；而在单工序或资源碎片压力样例上基本持平，说明收益来自“看懂工序前后关系”，不是来自通用重排框架。
- 中期仍保留自适应大邻域拆修搜索外壳 + 现有 Greedy/SGS repair，但它排在工序图局部搜索、图权重比较、自动选择和基准门禁之后。
- 2026-06-29 Exa MCP 补强调研后，路线不推翻：柔性作业车间和资源受限排程资料仍支持“先做工序图就绪队列派工，再做大邻域拆修搜索”的顺序。外部资料补充的主要不是换主线，而是给后续补上换型 / 序列相关准备时间基准、禁忌记忆、移动瓶颈和单解自适应权重局搜这些候选方向。
- 禁忌搜索（Tabu Search）、束搜索（Beam Search）、移动瓶颈法（Shifting Bottleneck）有价值，但先作为后续候选，不做第一条主线；其中禁忌记忆可以作为自适应大邻域拆修搜索或单解局搜的轻量组件，不能单独绕开现有候选指纹和 SGS 落位合同。
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
- FJSP 综述：<https://www.sciencedirect.com/science/article/pii/S037722172300382X>
- FJSP 智能调度综述：<https://link.springer.com/article/10.1007/s12555-023-0578-1>
- 大邻域搜索与自适应随机分解用于 FJSP：<https://exa.ai/library/publication/72224654252>
- 禁忌搜索 + 移动瓶颈法：<https://www2.cs.sfu.ca/CourseCentral/417/havens/papers/Parviz/esi14.pdf>
- 加权拖期 + 序列相关准备时间基准：<https://www.cicirello.org/publications/wtsbenchmarks.pdf>
- 序列相关准备时间 FJSP 拖期优化：<https://doi.org/10.1080/00207543.2012.746480>
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
- 做工序图就绪队列派工的局部搜索、图权重多起点比较、自动选择和基准门禁。
- 做自适应大邻域拆修搜索外壳，并用现有 SGS 作为 repair。
- 把图指标先用于就绪候选排序和权重比较；后续拆修搜索可以消费图指标，但不把完整图对象外泄。
- 把最终候选继续接回现有 `OptimizationOutcome`、候选比较和 summary 链路。
- 把换型 / 序列相关准备时间基准作为后续门禁补强方向，用来覆盖 `min_changeover` 当前没有可比基准的问题；本补强只定义路线，不下载新数据、不写实现。

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
- 不让自适应大邻域拆修搜索的局部 repair 绕过 `schedule_output_allowed_op_ids`、`payload_validation_operations`、payload 合同和执行态保护。
- 不把可选候选的失败包装成正常得分方案。
- 不把相同候选、相同排程结果、相同 fingerprint 的重复尝试包装成“探索到了很多不同方案”。
- 不让候选方案、模拟方案、历史正式方案开放现场写入入口。

### 剪枝策略包定位：不新增独立剪枝算法路线

本路线不新增一条独立的“剪枝算法”主线。这里的剪枝只作为现有排产优化搜索里的候选过滤、邻域缩小、重复解拒绝、预算控制、trace 统计和证明门禁能力存在，统一称为“剪枝策略包”。

大白话说：剪枝不是另起一个新算法来直接排产，而是在现有搜索里少试一些明显没用、重复、不可行、超预算或不可比较的候选，省时间、少误报。但只要某个候选最后要被采纳，它仍然必须回到正式排产链里重排一遍，由正式 objective score 和 CandidateFingerprint 来裁判。

剪枝必须遵守以下边界：

- 剪枝只能减少“要完整跑正式排产链的候选数量”，不能替代正式 `ScheduleService -> orchestrator -> optimize_schedule -> GreedyScheduler -> SGS/Greedy` 主链。
- 剪枝不能直接写 `ScheduleResult`、`start_time`、`end_time`、正式计划表或持久化结果。
- 候选被剪掉，只能说明“没有进入正式评估”或“按明确规则被拒绝”，不能说明“已证明不会更好”。
- 因时间、top-K、邻居数或全局 deadline 不足而没生成 / 没评估的候选，必须记为 `skipped_by_budget`，不能记为证明型 `pruned_by_bound`。
- 只有同目标、同指标、同模型口径下的安全下界，才允许进入 bound 类剪枝；不可比下界只能写 `not_comparable`。
- `makespan` 下界不能证明 `min_overdue`、`min_tardiness`、`min_changeover` 等非同目标改进。
- 同 decision、同 decoded output、同 fingerprint 的重复候选必须进入 duplicate / same_fingerprint 拒绝统计，不能包装成探索了多个不同方案。
- 所有被采纳候选必须重新走正式 SGS / Greedy 解码、CandidateFingerprint、candidate_is_preferred、search_report 和 benchmark gate。
- operator reward、邻域权重、剪枝命中率只能影响后续候选选择概率，不能直接覆盖正式 objective score。
- 组合候选池的事后最优结果只能按组合池语义报告，不能偷归因给单个剪枝规则或单个算法。

剪枝策略包分别承载在现有 item 中，不新增 `pruning-algorithm` item：

- `graph-ready-v2-elite-local-repair`：先落生产级 GraphReady v2 前 K 精英候选轻量修补剪枝。
- `graph-ready-v2-portfolio-integration`：把 `graph_ready_v2_repaired` 作为统一候选池来源接入，不把修补 / 剪枝包装成独立算法。
- `graph-ready-v2-comparative-ratchet-gate`：只做证明门禁，防止不可比下界、dirty proof、预算未评估候选被包装成证明。
- `alns-graph-ready-bridge-contract`、`alns-partial-repair-contract`、`alns-sgs-repair-adapter`：保证剪枝只影响候选范围，不绕过图桥接、局部 repair 合同和 SGS repair 适配。
- `alns-state-operators-core`：定义通用 pruning report、candidate accounting、rule version、安全状态和算子接口。
- `alns-domain-neighborhood-operators`、`alns-setup-aware-neighborhoods`：定义关键块、移动瓶颈、联合机器-排序、换型感知等领域邻域剪枝规则。
- `alns-selection-acceptance-trace`：记录每条剪枝规则、每条候选拒绝原因、operator reward 和归因边界。

## 3. 模块拆分（概设）

```text
scheduler-global-optimizer
├── 证明与评测底座：先证明什么叫更好，避免盲目改算法
├── 搜索合同与可观测层：stop_reason、seed、trace、候选拒绝原因
├── 候选构造层：GRASP / Iterated Greedy 生成更多可行起点
├── 业务邻域层：关键链、延期、瓶颈、换型、资源替换、窗口 repair
├── 工序图就绪优化层：就绪候选排序、图权重调参、图局部搜索
├── 自适应大邻域拆修搜索层：图桥接 / destroy / repair / acceptance / operator weight
├── SGS repair 适配层：复用现有 Greedy/SGS 落位和硬约束
├── 接入与展示边界层：接回 OptimizationOutcome、summary、候选比较
└── 长跑调参与门禁层：固定 benchmark、阈值、nightly/long gate
```

### 模块 A · 证明与评测底座

- **职责**：给算法升级建立“能不能证明更好”的标准，包括 tiny oracle、lower bound、best-known、gap、回归阈值、不写 tracked evidence 的 benchmark check 模式，以及 benchmark public/diagnostics 分层。
- **承载的子 feature**：`optimizer-proof-harness`、`benchmark-ratchet-quality-gate`、`long-run-tuning-evidence`
- **2026-06-29 增补承载**：`benchmark-reference-diagnostics-baseline`，只补同目标下界、不可比诊断和换型基准准备，不重复已有 noop / same-fingerprint / improved 合同。
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

### 模块 E · 工序图就绪优化层

- **职责**：在已有工序图 report/on 能力之上，优化“这一轮哪些工序已经具备排产资格、多个就绪工序之间先排谁”。本层只调就绪候选排序、图权重和候选选择，不重新引入图分析主链，也不提前写任何可变工序的开始/结束时间。
- **剪枝补充职责**：GraphReady v2 elite repair 只对已经正式 SGS 解码并进入候选池的前 K 个精英候选生成有限邻居；邻居必须重新走正式 SGS 解码、CandidateFingerprint 和严格 score 比较。未生成、重复、超预算、不可行和 same_fingerprint 候选必须分别进入 repair / pruning 统计，不能写成已证明无改进。
- **承载的子 feature**：`graph-ready-local-search-contract`、`graph-ready-priority-tuning`、`graph-ready-v2-objective-feature-contract`、`graph-ready-v2-bottleneck-resource-score`、`graph-ready-v2-candidate-portfolio`、`graph-ready-v2-elite-local-repair`
- **触碰的现有代码 / 模块**：`schedule_graph_dispatch_context.py`、`core/algorithms/greedy/dispatch/sgs_graph.py`、`core/algorithms/greedy/dispatch/sgs.py`、`sgs_scoring.py`、`optimizer_local_search.py`、`optimizer_candidate_profile.py`、`optimizer_search_report.py`。

### 模块 F · 自适应大邻域拆修搜索层

- **职责**：实现纯 Python 的自适应大邻域拆修搜索外壳：选择 destroy/repair 算子、记录算子权重、按 acceptance 接受或拒绝候选、持续维护 best/current。
- **剪枝补充职责**：本层负责统一候选计数、剪枝规则版本、剪枝安全状态、预算跳过和 operator pruning trace；剪枝只影响 destroy / repair 候选生成与评估顺序，不能绕过 SGS repair，也不能直接改 objective score。
- **承载的子 feature**：`alns-graph-ready-bridge-contract`、`alns-state-operators-core`、`alns-selection-acceptance-trace`
- **2026-06-29 增补承载**：`alns-domain-neighborhood-operators`、`alns-setup-aware-neighborhoods`，只在 SGS repair 适配和基准量尺到位后补领域算子，不提前写可变工序时间。
- **触碰的现有代码 / 模块**：新增 `core/services/scheduler/run/alns_*` 或同级窄职责模块；不直接放进 GreedyScheduler 内部。

### 模块 G · SGS repair 适配层

- **职责**：先定义局部拆修合同，再把被删掉的一小块工序交回现有 Greedy/SGS repair；repair 结果必须复用正式排产的 allowed-op、payload validation 和执行态保护语义。
- **承载的子 feature**：`alns-partial-repair-contract`、`alns-sgs-repair-adapter`
- **触碰的现有代码 / 模块**：`schedule_signature_support.py`、`schedule_optimizer_steps.py`、`GreedyScheduler.schedule()` 调用合同、`graph_ready_context` 合同、`schedule_input_collector.py`、`schedule_payload_contract.py`、`schedule_execution_persistence_guard.py`。

### 模块 H · 接入与展示边界层

- **职责**：让新算法候选接回 `OptimizationOutcome`、候选比较、summary、diagnostics，同时修掉已知内部 id 泄漏风险。当前先覆盖 GRASP/IG、VNS/SA 和工序图候选；后续自适应大邻域拆修搜索完成时再接入同一合同。
- **承载的子 feature**：`diagnostic-public-id-boundary-fix`、`optimizer-integration-auto-selection`、`graph-ready-v2-portfolio-integration`
- **触碰的现有代码 / 模块**：`scheduler_analysis_diagnostic_*`、`schedule_summary_*`、`schedule_candidate_*`、OperationLogs 投影。

### 模块 I · 长跑调参与门禁层

- **职责**：把工序图就绪队列派工、图权重组合、自动选择结果和后续拆修搜索都纳入同一套基准门槛，防止今天看起来更好、明天被别的改动退回去。
- **承载的子 feature**：`benchmark-ratchet-quality-gate`、`long-run-tuning-evidence`、`graph-ready-v2-comparison-baseline-contract`、`graph-ready-v2-comparative-ratchet-gate`
- **触碰的现有代码 / 模块**：`tests/_scripts_e2e/benchmark_fjsp.py`、`tests/_scripts_e2e/benchmark_smtwt_localsearch.py`、`tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py`、`evidence/Benchmark/` 使用口径、质量门禁脚本和 benchmark public/diagnostics 投影。

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 `OptimizationSearchReport`

**方向**：搜索合同层 -> summary / diagnostics / candidate comparison
**形式**：纯 dict，挂到 `OptimizationOutcome` 后再由 summary 层投影。

**契约**：

```python
OptimizationSearchReport = {
    "schema_version": 1,
    "algorithm_profile": "baseline|grasp|ig|vns|sa|graph_ready|alns",
    "seed": 0,
    "stop_reason": "baseline_scheduled|completed|time_budget|iteration_limit|no_improvement|target_reached|all_candidates_rejected|optional_warmstart_failed|repair_failed|validation_error",
    "best_origin": "baseline|ortools_warmstart|multi_start|local_search|grasp|ig|vns|sa|graph_ready|alns",
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
- `best_origin` 必填；baseline、warm-start、multi-start、local-search、GRASP/IG/VNS/SA、工序图就绪队列派工、自适应大邻域拆修搜索的最优来源必须可解释。
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

### 4.1.1 `OptimizationPruningReport`

**方向**：候选生成 / 邻域 / ALNS operator -> `OptimizationSearchReport` -> diagnostics / benchmark gate
**形式**：纯 dict，作为 `OptimizationSearchReport["pruning_report"]` 或阶段级 `candidate_profile["..."]["pruning"]` 的结构化子对象。public 只展示安全聚合摘要，raw rule trace 只能进入 diagnostics。

**契约**：

```python
OptimizationPruningReport = {
    "schema_version": 1,
    "phase": "graph_ready_v2_elite_repair|alns_destroy_repair|alns_domain_neighborhood|selection_acceptance",
    "pruning_enabled": False,
    "pruning_strategy": "none|elite_top_k|domain_scope_filter|duplicate_decision|bound|dominance|budget_guard|hybrid",
    "pruning_rule_version": "none",
    "candidate_space_total": None,
    "candidate_space_total_status": "exact|upper_bound|estimated|unknown",
    "generated_candidates": 0,
    "evaluated_candidates": 0,
    "pruned_candidates": 0,
    "rejected_candidates": 0,
    "skipped_by_budget": 0,
    "pruned_by_rule": {},
    "rejected_by_reason": {},
    "duplicate_decision_pruned": 0,
    "duplicate_output_rejected": 0,
    "same_fingerprint_rejected": 0,
    "pruned_by_bound": 0,
    "pruned_by_dominance": 0,
    "pruned_by_feasibility_guard": 0,
    "pruned_by_scope_filter": 0,
    "pruning_safety_status": "not_applicable|safe_exact|safe_duplicate|safe_feasibility|heuristic_scope_reduction|budget_only|not_comparable|unsafe_disallowed",
    "objective_name": "min_overdue",
    "objective_compatibility": "same_objective|not_comparable|not_applicable",
    "bound_metric": None,
    "bound_value": None,
    "bound_reason": None,
    "budget_ms": None,
    "runtime_ms": 0,
    "rule_trace": [],
}
```

**字段语义**：

- `candidate_space_total`：当前 phase 理论候选空间大小；算不清必须写 `None`，并把 `candidate_space_total_status` 写成 `unknown`，不能编造精确值。
- `generated_candidates`：已经显式生成出来、可被评估或剪掉的候选数量。
- `evaluated_candidates`：真正调用正式 Greedy / SGS 解码并产生 `results` / `summary` / `metrics` / `score` 的候选数量。
- `pruned_candidates`：生成后、正式解码前，因为明确剪枝规则没有进入评估的候选数量。
- `rejected_candidates`：已经评估或校验后被拒绝的候选数量。
- `skipped_by_budget`：因为时间、邻居数、top-K 或迭代预算没有生成 / 没有评估的候选数量；这不是证明型剪枝。
- `duplicate_decision_pruned`：同一 phase 内重复 decision key，尚未正式解码即可跳过。
- `duplicate_output_rejected` / `same_fingerprint_rejected`：正式解码后发现 output fingerprint 重复，只能算 rejected，不能默认算 pre-evaluation pruning。
- `pruned_by_bound`：只能在 bound 与当前 `objective_name` 同目标、同指标、同模型时使用；否则必须写 `objective_compatibility=not_comparable`。
- `pruning_safety_status=heuristic_scope_reduction` 表示只是启发式缩小邻域，不能被 benchmark gate 当成数学证明。
- `budget_only` 表示只是预算截断，不能写成“已证明没必要试”。

**计数约束**：

```python
generated_candidates >= evaluated_candidates
generated_candidates >= pruned_candidates
generated_candidates >= evaluated_candidates + pruned_candidates
skipped_by_budget >= 0
```

`evaluated_candidates` 必须等于本 phase 中真实调用正式排产解码的次数。`same_fingerprint_rejected` 只能来自 decoded output fingerprint，不得在未解码候选上伪造。

**安全约束**：

- 剪枝报告不得包含 raw `op_id`、`schedule_id`、`candidate_id`、`source_table` 或 fingerprint hash 进入 public 页面。
- public 只展示计数、规则名、中文摘要和安全状态。
- diagnostics 可保留 rule trace，但仍要遵守内部 id 边界。

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
- 内部 id 脱敏口径统一见 4.9；本契约只补一条 benchmark 专属：stdout、Markdown、CI artifact 和 tracked evidence 默认都不得输出 raw internal id。
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
    "profile": "baseline|grasp|ig|vns|sa|graph_ready|alns",
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

> **本阶段落地（item 4，2026-06-28；item 6/7/8 扩展，2026-06-28；2026-06-29 口径校正）**：契约已落为 `core/services/scheduler/run/optimizer_candidate_profile.py` 的 `CandidateProfile`，作为 `OptimizationSearchReport.candidate_profile` 嵌套字段。当前已锁现有能力：①`profile` 取值为 `baseline` / `multi_start_local_search` / `grasp_ig` / `vns_sa`，其中默认 `improve` 已扩展到 `vns_sa`，`candidate_strategy_families=["multi_start","grasp","iterated_greedy"]`，未知 profile 仍 `ValidationError`；②`acceptance` 允许 `improve_only`、`threshold`、`record_to_record`、`simulated_annealing`，未知 acceptance 仍 fail-loud；③`configured_neighborhoods` 默认且仅允许 item 7 业务邻域 `critical_chain/tardy_window/bottleneck_machine/changeover_block/resource_alternative/time_window`，旧 `swap/insert/block` 不在正式 registry 和 profile 白名单里，未知邻域仍 fail-loud；④SGS 模式实际执行邻域必须另报为 `effective_neighborhoods=["sgs_dispatch_rule"]`，不能把配置里的六个业务邻域冒充成实际执行；⑤`repair` 仅 `sgs`。另落地诚实字段：`seed_source`（标 seed 由 version 派生）、`candidate_strategy_family`、`candidate_strategy_families`、`candidate_construction`、`validation_status`、`ortools_warmstart_enabled`（仅 improve 下且配置开启才 true，baseline 恒 false）。迭代上限 configured（time_budget×20）vs effective（钳到 [200,5000]）已区分，钳制如实写 `system_limit_reason`；`derive_iteration_limits` 是该公式唯一真相源，局搜与 profile 共用。GRASP/IG 构造预算由 `derive_grasp_ig_limits` 从同一 time budget 派生并钳制，public 只投策略族、configured/effective 邻域名称、acceptance 名称和基础预算摘要，具体构造预算仅进 diagnostics。

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
- `output_fingerprint` 至少覆盖被正式解码后的排程结构摘要：排入 / 失败数量、工序-资源-时间归一化签名、主目标指标签名；内部 op/resource id 只能进 diagnostics（脱敏口径见 4.9）。
- `evaluated_candidates` 可以统计 decode 调用次数；`distinct_candidates` 只能统计 `decision_fingerprint` 或 `output_fingerprint` 未见过的候选，二者口径必须在 report 中声明。
- `same_as_parent=True` 或 `same_as_seen=True` 时，结果只能是 `no_change` / `candidate_rejected=same_fingerprint` / `feasible_but_not_accepted`，不能记成 improvement。
- 宣称 `improved=True` 必须同时满足：fingerprint 改变、按当前 objective 的 `score` 严格更优、且通过 acceptance；缺一项都只能报告为未改进。
- fingerprint 生成必须确定性可复现，不得依赖 dict 随机遍历顺序、对象内存地址、当前时间或非 seed 派生随机数。

> **本阶段落地（item 5，2026-06-28；item 8 校正 acceptance 来源，2026-06-28）**：契约已落为 `core/services/scheduler/run/optimizer_candidate_fingerprint.py`，并接入 `OptimizationSearchReportState`。`decision_fingerprint` 仍保留候选决策维度（objective、strategy/params、dispatch mode/rule、batch_order、resource、locked seed、mutable scope），但 `distinct_candidates` / `accepted_distinct_candidates` 已明确改为 `decoded_output` 口径：按正式解码后的 `output_fingerprint` 去重。`output_fingerprint` 只把正式 `ScheduleResult` 的工序-资源-时间签名、summary 数量和当前 objective score 放入 hash 输入；hash 和 fingerprint 事件只进 diagnostics，public / OperationLogs / size guard 只展示计数、`best_fingerprint_changed`、`improved` 与口径说明。`improved` 已显式拆为三条件：`fingerprint_changed` + `score_strictly_better` + `acceptance_passed`；item 8 后 `acceptance_passed` 来自真实 best acceptance 事件，不再用 `accepted_candidates>1` 代理。`same_as_parent` / `same_as_seen` 会记 `same_fingerprint` 拒绝；local search 更新 best 时还要求候选 `output_fingerprint` 既不是 parent 也不是 seen，防止同一解码结果被包装成 improvement。

### 4.5 `NeighborhoodMove`

**方向**：业务邻域层 -> local search / ALNS
**形式**：内部 dict，只能进 diagnostics，public 只能看中文汇总。

**契约**：

```python
NeighborhoodMove = {
    "name": "critical_chain|tardy_window|bottleneck_machine|changeover_block|resource_alternative|time_window|sgs_dispatch_rule",
    "scope": "batch|operation|machine|time_window",
    "selected_operation_ids": [],
    "selected_batch_ids": [],
    "selected_machine_ids": [],
    "reason": "critical_path|overdue|unmatched_resource|changeover|random",
}
```

**约束**：

- `selected_operation_ids`、`selected_machine_ids` 这类内部 id 不得进入页面正文、导出或 public payload（脱敏口径见 4.9）。
- move 只负责提出“动哪一块”，不能直接写开始结束时间。
- 最终落位必须走现有 `GreedyScheduler.schedule()` / SGS / `estimate_internal_slot()` 链路。

> **本阶段落地（item 7，2026-06-28；2026-06-29 口径校正）**：契约已落为 `core/services/scheduler/run/optimizer_neighborhood_moves.py`、`optimizer_neighborhood_registry.py` 与 `optimizer_neighborhood_move_support.py`。`NeighborhoodMove` 现包含 `schema_version`、`neighborhood_name`、`move_kind`、`input_scope`、`changed_decision_count`、`expected_effect`、`noop`、`fallback_used`、`fallback_reason`、`candidate_rejected`、`diagnostics` 等字段；默认配置仍是六个业务邻域：关键链、延期窗口、瓶颈设备、换型块、资源替代、时间窗修复。另有 SGS 专用邻域 `sgs_dispatch_rule`，只用于 `dispatch_mode=sgs` 时切换 SGS 派工规则。registry 只负责校验和生成 move，不做 acceptance、不决定 improved、不直接写 public；局搜拿到 move 后仍调用现有 SGS 正式解码。无可移动目标时返回 `noop_neighbor`，短块移动回退时写明 `fallback_reason`，未知邻域 `ValidationError` fail-loud。`OptimizationSearchReport` 新增 `neighborhood_moves` diagnostics 与 `neighborhood_summary` public 小摘要，public/OperationLogs/size guard 只展示邻域名称和计数，并分开展示 configured/effective 邻域，不展示 raw move、内部 op/resource id 或 fingerprint hash。

> **VNS 使用关系（item 8，2026-06-28；2026-06-29 口径校正）**：`core/services/scheduler/run/optimizer_vns.py` 只负责 current neighborhood index、no-improve 计数、shake 次数和切换原因；它消费 item 7 registry 的邻域名称，不注册新邻域，也不做 acceptance 或 improved 判定。局搜每轮从 current solution 通过 registry 生成一个 `NeighborhoodMove`，再交给当前派工模式正式解码；若 current 是 `sgs`，effective 邻域固定为 `sgs_dispatch_rule`，不会轮询 critical_chain/tardy_window 等业务邻域；若 current 是 `batch_order`，才按配置的业务邻域切换。`OptimizationSearchReport` 新增 `vns_events` diagnostics 与 `vns_summary` public 小摘要。

### 4.6 `GraphReadyOptimizationProfile`

> **当前状态（2026-06-29）**：第一版图 ready 候选搜索已随 `scheduler-global-optimizer-items-9-13` 落地。它已经能消费既有 `graph_ready_context`、用 9 组图权重 profile 生成 SGS ready 排序候选，并通过统一候选比较接回 optimizer。当前已知缺口是：第一版仍偏“结构重要性排序”，在 `min_overdue` 场景下缺少交期压力、可救批次、剩余工时和目标感知瓶颈分，因此会赢过贪心基线，但可能输给 GRASP/IG 或允许 `atc` 的局部搜索。下一阶段以 4.6.1 的 GraphReady v2 计划补齐，不回改本节已完成的一版记录。

**方向**：工序图就绪优化层 -> SGS ready 候选排序 / 搜索报告 / 候选比较
**形式**：纯 dict；进入 optimizer 前必须 strict 校验，public 只能展示中文摘要和聚合计数。

**契约**：

```python
GraphReadyOptimizationProfile = {
    "schema_version": 1,
    "graph_analysis_mode": "on",
    "dispatch_mode": "sgs",
    "candidate_origin": "graph_ready_base|graph_ready_weight_grid|graph_ready_local_search",
    "weight_profile_slug": "balanced",
    "priority_weights": {
        "critical_path": 0.0,
        "successor_count": 0.0,
        "downstream_work_hours": 0.0,
        "bottleneck_machine": 0.0,
    },
    "candidate_policy": "fixed_weights|weight_grid|local_search",
    "max_weight_profiles": 0,
    "graph_unavailable_policy": "skip_candidate|candidate_rejected",
    "selection_tiebreaker": ["objective_score", "failed_ops", "runtime_ms", "profile_order"],
    "required_context_fields": [
        "schedulable_op_ids",
        "fixed_op_ids",
        "predecessor_op_ids_by_op_id",
        "successor_op_ids_by_op_id",
        "sort_key_by_op_id",
        "graph_priority_key_by_op_id",
    ],
    "public_summary": {},
    "diagnostics_ref": None,
}
```

**约束**：

- 本合同只消费已有工序图 report/on 能力产出的 `graph_ready_context`、关键路径、后续影响、下游工时、瓶颈资源等摘要；不得重新在 optimizer 内部新建另一套图分析主链。
- 工序图候选只能改变 ready 候选排序、图权重组合、候选策略和局部搜索动作；不能直接构造可变工序的 `ScheduleResult`、`start_time`、`end_time`。
- 最终落位仍必须走现有 SGS / `estimate_internal_slot()` 链路；图权重只影响“多个就绪工序先排谁”，不能绕过前后置约束、资源资格、冻结和执行态保护。
- 图不可用、有环、缺少必要节点指标、权重非法、候选重复或解码后同一张表时，必须写清 `skipped` / `candidate_rejected` 原因，不能把原方案包装成图优化成功。
- `priority_weights` 必须确定性可复现；同一 seed、同一输入、同一权重组合必须得到同一候选顺序。
- public 只展示“用了哪类图策略、试了几组、是否得到更优结果、基准差距变化”等摘要；完整节点 id、内部 op/resource id、图样本和 raw trace 只能进入 diagnostics。
- 基准门禁必须同时覆盖“有工序前后关系的样例”和“没有可利用图关系的样例”：前者防止收益丢失，后者防止无关场景被拖慢或改坏。
- 历史跳过原因 `graph_ready_requires_graph_neighborhood` 已随第一版落地替换为 `graph_ready_uses_graph_candidate_phase`；后续文档和测试如果仍看到旧原因，要先判断是否是 stale fixture / stale 文档，而不是继续按“图邻域未实现”解释现状。

**输入字段硬合同**：

`GraphReadyOptimizationProfile.required_context_fields` 是第 9 项的最低输入清单。进入 optimizer 的图候选必须先校验这些字段：

| 字段 | 用途 | 缺失 / 非法时怎么处理 |
| --- | --- | --- |
| `schedulable_op_ids` | 本轮允许被 SGS 排的可变工序集合 | 主图候选 `candidate_rejected=graph_ready_missing_schedulable_ops`；strict 主路径 fail-loud |
| `fixed_op_ids` | 已固定、已执行或不可移动工序集合 | `candidate_rejected=graph_ready_missing_fixed_ops` |
| `predecessor_op_ids_by_op_id` | 判断某工序是否已经就绪 | `candidate_rejected=graph_ready_missing_predecessors` |
| `successor_op_ids_by_op_id` | 更新 ready frontier，并计算后续影响 | `candidate_rejected=graph_ready_missing_successors` |
| `sort_key_by_op_id` | 保留已有 deterministic ready 排序底座 | `candidate_rejected=graph_ready_missing_sort_key` |
| `graph_priority_key_by_op_id` | 图评分进入 SGS 评分键 | `candidate_rejected=graph_ready_missing_priority_key` |

缺字段、字段类型错误、权重非法、NaN/Inf、图上下文和待排工序不一致，都不能静默降级成普通 SGS 成功；只能成为明确的 `skipped_phase` / `candidate_rejected` / strict fail-loud。只有图分析本身按配置关闭、且本候选是可选候选时，才允许写 `skipped_phase=graph_ready_unavailable` 后继续比较其他候选。

**默认图权重表（item 10 第一版）**：

图权重比较必须先有固定、可复现的默认表，再允许后续局部搜索微调。第一版最多跑 9 组候选，超过时必须按 `profile_order` 截断并写明 `max_weight_profiles`。

| `weight_profile_slug` | `critical_path` | `successor_count` | `downstream_work_hours` | `bottleneck_machine` | 目的 |
| --- | ---: | ---: | ---: | ---: | --- |
| `balanced` | 2.0 | 1.0 | 1.0 | 1.0 | 默认均衡，先看关键路径但不压死瓶颈设备 |
| `critical_path_first` | 4.0 | 1.0 | 1.0 | 0.5 | 优先压关键路径，适合前后置链很深的样例 |
| `successor_fanout_first` | 1.0 | 3.0 | 1.0 | 0.5 | 优先释放后继多的工序，减少后续等待 |
| `downstream_work_first` | 1.0 | 1.0 | 3.0 | 0.5 | 优先释放下游工时大的链路 |
| `bottleneck_relief` | 1.0 | 0.5 | 1.0 | 3.0 | 优先缓解瓶颈设备排队 |
| `critical_bottleneck` | 3.0 | 0.5 | 1.0 | 2.0 | 兼顾关键路径和瓶颈设备 |
| `fanout_downstream` | 0.5 | 2.0 | 2.0 | 0.5 | 优先打开后续工作面 |
| `bottleneck_downstream` | 0.5 | 1.0 | 2.0 | 2.0 | 下游工时和瓶颈设备同时偏重 |
| `graph_neutral` | 0.0 | 0.0 | 0.0 | 0.0 | 作为图候选的中性对照，不能包装成图优化收益 |

权重必须是有限非负数。归一化只允许在评分函数内部做，不得把用户输入或 profile 字段静默改写；如果需要归一化，必须在 diagnostics 写 `raw_weights` 和 `effective_weights`。同一候选的 `CandidateFingerprint` 必须覆盖 `weight_profile_slug`、四个原始权重、候选策略、seed 和正式 SGS 解码后的 output fingerprint。

**自动选择规则（item 11 第一版）**：

统一自动选择不是另建一个排序口径，而是把 GRASP/IG、VNS/SA、工序图候选都放回同一个 `OptimizationSearchReport` 和候选比较合同。候选优先级固定为：

1. 先排除 fail-loud / validation error / repair failed / forbidden public leak 的候选。
2. 再排除同一 `output_fingerprint` 的重复候选；重复候选只能累计 `same_fingerprint` 证据。
3. 先比较 `failed_ops`，失败工序少者优先。
4. 再比较当前 `objective_name` 的完整 `objective_score` 元组，按既有 objective score 顺序 lexicographic 比较。
5. 同分时比较 `best_fingerprint_changed=True` 优先，避免把原方案包装成改进。
6. 仍同分时比较 `runtime_ms`，更快者优先。
7. 仍同分时按 `candidate_origin` 稳定顺序：`baseline` -> `grasp` -> `ig` -> `vns` -> `sa` -> `graph_ready_base` -> `graph_ready_weight_grid` -> `graph_ready_local_search` -> `alns`。

第 11 项会触碰 candidate comparison、summary delta、诊断和 public/id 边界，执行前必须回 `.codestable/roadmap/aps-three-gap-directions/` 做 update gate 复核；如果该路线的字段、状态、路由或错误码合同需要变化，必须先更新那条路线图，不得在实现里单方面绕开。

### 4.6.1 GraphReady v2 目标感知候选与多算法对比合同

**方向**：工序图就绪优化层 v2 -> 候选组合池 -> 多算法 benchmark / ratchet
**对应子 feature**：`graph-ready-v2-comparison-baseline-contract`、`graph-ready-v2-objective-feature-contract`、`graph-ready-v2-bottleneck-resource-score`、`graph-ready-v2-candidate-portfolio`、`graph-ready-v2-elite-local-repair`、`graph-ready-v2-portfolio-integration`、`graph-ready-v2-comparative-ratchet-gate`
**新增前置量尺**：`benchmark-reference-diagnostics-baseline`

GraphReady v2 的目标不是把 9 组图权重再调细一点，而是把 `graph_ready` 从“结构重要性排序器”升级为“目标函数感知候选来源”。第一版的失败样例已经证明：真实 SGS 可以解出更优顺序，最终 objective 也能选中更优候选，问题在于候选池没有生成那个区域的顺序。当前前置量尺、修改前多算法基准、目标感知特征、瓶颈资源分和候选家族已经落地；后续重点是生产级 elite repair、统一候选池接入和最新 HEAD 上的对比门禁证明。

**v2 候选 profile 形状**：

```python
GraphReadyV2CandidateProfile = {
    "schema_version": 1,
    "algorithm_version": "graph_ready_v2",
    "candidate_policy": "objective_rule|graph_due_hybrid|bottleneck_due|moore_like|perturbed|elite_repair|portfolio_all",
    "objective_name": "min_overdue",
    "objective_features": {
        "due_pressure": True,
        "slack_hours": True,
        "remaining_work_hours": True,
        "saveability": True,
        "processing_time_rank": True,
        "sacrifice_penalty": True,
    },
    "bottleneck_features": {
        "residual_capacity": True,
        "split_load": True,
        "min_candidate_load": True,
        "flexibility_discount": True,
        "due_gate": True,
        "bottleneck_on": True,
        "bottleneck_release": True,
    },
    "rule_family": "edd|spt|min_slack|critical_ratio|atc_like|saveability|sacrifice_long|graph_due_hybrid|bottleneck_due_gated",
    "perturbation": {
        "enabled": False,
        "seed": 0,
        "top_k": 0,
        "noise_scale": 0.0,
    },
    "elite_repair": {
        "enabled": False,
        "top_k": 0,
        "max_neighbors_per_elite": 0,
        "time_budget_ms": 0,
        "moves": ["adjacent_ready_swap", "single_insert", "tardy_boundary_move"],
        "pruning_strategy": "elite_top_k|duplicate_decision|budget_guard",
        "pruning_report": "OptimizationPruningReport",
    },
    "comparison_baseline_ref": "BenchmarkAlgorithmComparisonSnapshot",
}
```

**v2 特征约束**：

- `objective_features` 必须按当前 `objective_name` 派生。`min_overdue` 第一优先级是减少超期批次数，因此至少要能表达“这个批次是否还救得回来”“单位剩余工时能救多少交付风险”“容量不足时谁应被放到后面牺牲”。
- `min_overdue` 的候选排序解释必须保留完整 objective score 字典序：超期批次数 -> 加权拖期 -> 总拖期 -> makespan -> 换型。v2 特征可以帮助生成候选，但最终比较仍只能用正式 SGS 解码后的完整 `objective_score`，不能把 makespan 或单个启发式分数提前冒充主目标。
- `due_pressure`、`slack_hours`、`remaining_work_hours`、`saveability`、`processing_time_rank`、`sacrifice_penalty` 是 v2 的最低目标特征；缺少这些字段时，v2 候选只能 `skipped` / `candidate_rejected`，不能静默降级为 v1 成功。
- `bottleneck_machine_score` 不能继续只表达“能跑瓶颈机”。v2 必须拆出 `bottleneck_on` 和 `bottleneck_release`：前者表示本工序消耗稀缺资源，后者表示本工序完成后能释放下游瓶颈路径。
- 柔性资源必须做负荷分摊、最小候选负荷和灵活性降权：一个工序如果可以去空闲机器，就不能因为它也能去瓶颈机而被误判为必须优先。
- 瓶颈分必须有交期门控。瓶颈很忙但相关批次交期很松时，只能作为 tie-break；瓶颈忙且批次交期紧、仍可救时，才允许进入主排序。
- 所有特征进候选排序前必须做 rank / percentile 归一化或等价的量纲处理；不能把分钟数、比例、布尔值和指数分直接裸加，避免某个大数值天然压倒其他特征。

**v2 候选组合约束**：

- v2 不替代 GRASP/IG、VNS/SA 或 v1；它是候选来源之一。最终仍由真实 SGS + 当前 `objective_score` 做裁判。
- 候选家族至少覆盖：旧 9 组图权重、EDD、SPT、最小松弛时间、关键比率、ATC-like、可救批次优先、长尾牺牲、交期门控瓶颈、图 + 交期混合。
- EDD、最小松弛时间、关键比率、ATC-like 不能只停留在名字：item 17 设计时必须写明每个规则的输入字段、计算公式、同分规则、缺字段时的 skipped / candidate_rejected 原因，并把公式版本写进 diagnostics，避免后续实现各自猜。
- 不允许写死当前 4 工序样例的赢家顺序。v2 要抽象为“保护更多可准交批次、必要时牺牲长尾批次”，并用反例样例防过拟合。
- 小规模扰动只能在分数接近的 ready 候选之间做，必须 seed 派生、可复现、进 diagnostics；扰动不能绕过前后置、资源资格、冻结、执行态保护。
- v2 后接轻量局部修补时，只能对 top-K elite 候选做有限邻域，如相邻 ready swap、single insert、tardy boundary move；每个候选必须有硬 `max_neighbors_per_elite` 和 `time_budget_ms`，只接受真实 objective 严格改进。repair 过程必须输出 `OptimizationPruningReport`，分清 `generated_candidates`、`evaluated_candidates`、`pruned_candidates`、`rejected_candidates` 和 `skipped_by_budget`，不能把预算没跑写成 bound proof。

**多算法同台比较要求**：

- v2 已有可复跑的多算法基准合同和当前“修改前”对照。后续只要代码、基准或 HEAD 发生变化,就必须按同一合同重跑并更新证明口径,避免“先改完再找证据”。
- 同一个 case、同一个 seed、同一个 time budget、同一个 objective 下，至少比较：`greedy`、`local_search`、`grasp_ig`、`graph_ready_v1`、`graph_ready_v2_no_repair`、`graph_ready_v2_with_repair`；`portfolio_all` 只能作为这些真实算法跑完后的事后上界行，必须标 `comparison_semantics=posthoc_upper_bound`，不能伪装成同预算普通算法。
- 每行结果必须包含：`case_group`、`case_slug`、`algorithm_profile`、`algorithm_version`、`seed`、`time_budget_seconds`、`objective_name`、`objective_score`、`failed_ops`、`runtime_ms`、`evaluated_candidates`、`distinct_candidates`、`accepted_candidates`、`candidate_rejections`、`best_origin`、`best_order` 或安全顺序摘要、`comparison_to_current_baseline`、`comparison_to_graph_ready_v1`、`comparison_to_portfolio_best`。
- 多算法 ratchet key 至少包含 `case_group + case_slug + algorithm_profile + algorithm_version + seed`。当前只用 `case_group + case_slug` 的轻门禁键不能承载多算法同台比较，否则不同算法会互相覆盖。
- 汇总必须报告胜 / 平 / 负，不只报告“赢 greedy”。尤其要单列 v2 对 `local_search`、`grasp_ig`、`graph_ready_v1` 的胜负；v2 对 `portfolio_all` 只能报告差距、贡献来源和是否进入最终最优路径，普通胜平负必须标 `not_comparable`。
- 如果某算法缺跑、缺关键字段、目标不可比、或 dirty baseline 被包装成 clean proof，则该比较报告必须 fail-loud 或标 `not_comparable`，不能算通过。

### 4.7 `PartialRepairContract`

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

### 4.8 `ALNSOperatorResult`

**方向**：ALNS 搜索层 -> 搜索合同与 diagnostics
**形式**：内部 dict。

> **成熟度（BDUF 收口）**：本契约服务自适应大邻域拆修搜索最后一段，下面的字段是**前瞻接口占位**。`operator_reward`、`score_before/after`、trace 形状须等工序图局部搜索、图权重比较和自动选择实际落地、看清真实需要后，在 `alns-state-operators-core` 启动时再定稿，避免在消费者出现前过早逐字段钉死。与此相对，4.7 `PartialRepairContract` 不属于投机设计——它主要把现有正式排产守门链（allowed-op / payload 校验 / repair 失败不许伪成功）提前锁住，是对既有安全不变式的防御，保持现状即可。

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

### 4.9 Public / Diagnostics 分层协议

**方向**：optimizer / graph / ALNS -> 页面 / OperationLogs

> **单一真相源**：本节是 public/diagnostics **展示边界与内部 id 脱敏**的唯一权威。其他契约（4.2 / 4.4 / 4.5 / 4.6 / 4.7）凡涉及“内部 id 只进 diagnostics、public 只放摘要”一律**引用本节口径**，不再各自复述；各契约自身只保留其**业务语义**规则（如 repair 失败不许伪成功、same-fingerprint 不算改进、operator reward 不覆盖 score），那些不收敛到本节。

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

### 4.10 基准门禁矩阵

**方向**：benchmark harness -> item 12 / item 13 / 后续拆修搜索复用

第 12 项不是“跑几个 benchmark 看看”，而是把轻 / 中 / 长三层门槛写进仓库。首次落地时允许先生成 ratchet baseline snapshot，后续所有改动都和这份快照比；如果更新 tracked evidence，最终必须重新跑最新 HEAD 的质量门禁。

| 层级 | 必须覆盖 | 命令 / 脚本要求 | 通过门槛 |
| --- | --- | --- | --- |
| 轻门禁 | tiny exact oracle + tiny DAG 工序图样例 + 图合同异常样例 | item 12 必须提供可由普通质量门禁调用的快速命令；每个 case 默认 stdout，不写 tracked evidence | tiny oracle 可证明样例 `gap_to_oracle_pct=0`；图不可用、有环、缺字段、非法权重、重复候选都必须有明确 `skipped` / `candidate_rejected` / fail-loud |
| 中门禁 | FJSP 5 样例图就绪矩阵 + SMTWT 无图关系持平 + 大资源池性能 | 复用或扩展 `tests/_scripts_e2e/benchmark_fjsp.py`、`benchmark_smtwt_localsearch.py`、`benchmark_sgs_large_resource_pool.py`；缺少字段时 item 12 负责补脚本 | FJSP 技术参考口径不得差于首次 ratchet baseline；SMTWT `overdue_count` 不劣化；大资源池 `failed_ops=0` 且耗时不超过 ratchet baseline 125% |
| 长门禁 | 多 seed、多预算、多样例集的图权重稳定性 | item 13 必须提供长跑命令，默认写 ignored / temp 目录 | 至少 10 个 seed；同一图权重策略不得只靠单 seed 取胜；均值、最差值、标准差、重复候选率、候选拒绝率都必须入报告 |
| 同目标量尺补强 | Jackson 单机抢占参考下界 + WTSDS / Cicirello / SDST 换型基准准备 + 不可比诊断 | `benchmark-reference-diagnostics-baseline` 只定义装载、评分、脱敏和默认 stdout / ignored 输出口径；不下载 tracked 数据 | 可比时才进入 gap；不可比时必须标 `not_comparable`；不得重复 item 3/5/7/8 已有 no-op、same-fingerprint、improved 合同 |
| GraphReady v2 多算法对比 | 当前基准 + greedy / local_search / GRASP/IG / graph_ready_v1 / graph_ready_v2 同台比较，并附 `portfolio_all` 事后上界 | 新增或扩展多算法对比脚本；比较键必须包含 case、算法、算法版本和 seed；默认 stdout / ignored evidence，不写 tracked evidence | 不能只证明 v2 赢 greedy；必须报告 v2 对 local_search、GRASP/IG、v1 的胜 / 平 / 负；`portfolio_all` 不能参与普通胜平负，只能作为 posthoc upper bound 报告差距、来源和 `not_comparable`；缺算法、缺指标或不可比必须失败或标 `not_comparable` |
| 后续拆修复用 | ALNS / 拆修搜索接入后的同一套样例 | GraphReady v2 之后复用本矩阵，不得另建不可比 benchmark | ALNS 候选必须同时报告相对 graph-ready v2 ratchet baseline 和相对当前自动选择基线的改善 / 持平 / 退步 |

**当前推荐 ratchet 字段**：

```python
BenchmarkRatchetSnapshot = {
    "schema_version": 1,
    "generated_at": "2026-06-29T00:00:00",
    "git_commit": "dirty-or-commit-hash",
    "dirty_worktree": True,
    "case_group": "tiny|fjsp|smtwt|large_pool|long_run|sdst_changeover",
    "case_slug": "mk01",
    "algorithm_profile": "graph_ready",
    "algorithm_version": "graph_ready_v1",
    "candidate_origin": "graph_ready_weight_grid",
    "seed": 0,
    "time_budget_seconds": 0,
    "objective_name": "min_overdue",
    "objective_score": [],
    "failed_ops": 0,
    "makespan_hours": None,
    "overdue_count": None,
    "weighted_tardiness_hours": None,
    "total_tardiness_hours": None,
    "changeover_count": None,
    "runtime_ms": 0,
    "distinct_candidates": 0,
    "same_fingerprint_rejections": 0,
    "candidate_rejections": {},
    "evaluated_candidates": 0,
    "accepted_candidates": 0,
    "best_origin": "graph_ready_weight_grid",
    "best_order": [],
    "reference_type": "proven_optimum|lower_bound|best_known|folded_not_comparable|ratchet_baseline",
    "comparison_to_meta_baseline": {
        "metric": "overdue_count|makespan_hours|runtime_ms",
        "baseline_value": None,
        "actual_value": None,
        "delta_abs": None,
        "delta_pct": None,
        "status": "improved|same|degraded|not_comparable",
    },
    "comparison_to_current_baseline": {
        "baseline_algorithm_profile": "graph_ready",
        "baseline_algorithm_version": "graph_ready_v1",
        "metric": "objective_score",
        "status": "improved|same|degraded|not_comparable",
    },
    "comparison_to_portfolio_best": {
        "portfolio_algorithm_profile": "portfolio_all",
        "metric": "objective_score",
        "status": "winner|tied|lost|not_comparable",
    },
}
```

FJSP 的 `makespan_hours` 只作为技术参考和图关系收益证据，不得证明 `min_overdue`、`min_tardiness`、`min_weighted_tardiness` 或 `min_changeover` 已全局最优。SMTWT 当前只可用于 `min_overdue` 首分量 `overdue_count` 的同目标可比证明。`min_changeover` 的同目标证据需要后续引入加权拖期 + 序列相关准备时间或 SDST 类基准；在那之前只能写“换型基准缺口已知”，不能写“换型目标已被 benchmark 证明”。

**GraphReady v2 多算法对比强制口径**：

- 当前 `benchmark-ratchet-baseline.json` 是 v1 的脏工作区快照，只能作为历史参考;GraphReady v2 的修改前多算法基准已转到 `graph-ready-v2-comparison-baseline.json`。任何后续比较都必须报告 `dirty_worktree`、`git_commit` 和脚本命令,且不能把 `unbound_dirty_worktree` 包装成 clean proof。
- 多算法比较必须用同一个 case 集、同一个 seed 集、同一个 time budget、同一个 objective。不能拿 v2 的长预算结果去比 GRASP/IG 的短预算结果。
- `graph_ready_v2` 必须至少拆成 `graph_ready_v2_no_repair` 和 `graph_ready_v2_with_repair` 两列，避免局部修补收益被误写成纯候选生成收益。
- `portfolio_all` 是所有候选来源统一入池后按真实 objective 择优的事后上界结果，它不是 GraphReady 独占收益，也不是同预算普通算法。报告里必须标 `posthoc_upper_bound`，普通胜平负必须标 `not_comparable`，并区分 `graph_ready_generated_best`、`graph_ready_repaired_best`、`graph_ready_seeded_other_best` 和 `graph_ready_not_in_best_path`。
- 轻门禁可以只跑小样本和核心对比；中门禁必须跑 FJSP / SMTWT / 大资源池；长门禁至少 10 seed，并报告均值、最差值、标准差、重复候选率、候选拒绝率和每个算法族胜 / 平 / 负。
- `pruning_enabled=true` 时，必须存在 `pruning_report` 或阶段级 pruning summary；`evaluated_candidates` 必须等于真实正式 SGS / Greedy 解码次数，不能把 pruned / skipped 候选算进去。
- `skipped_by_budget` 必须单独报告，不能计入 `pruned_by_bound`；如果出现 `pruned_by_bound > 0`，必须同时报告 `objective_name`、`bound_metric`、`objective_compatibility=same_objective`，否则门禁失败或强制 `not_comparable`。
- 如果 `bound_metric=makespan` 且 `objective_name` 属于 `min_overdue` / `min_tardiness` / `min_changeover`，必须标 `not_comparable`，不能进入 gap / improved 证明。
- `duplicate_decision_pruned` 和 `same_fingerprint_rejected` 必须分开计数；后者只能来自正式 decoded output fingerprint，不能在未解码候选上伪造。

### 4.11 工序图到拆修搜索桥接合同

**方向**：工序图闭环 -> 自适应大邻域拆修搜索
**对应子 feature**：`alns-graph-ready-bridge-contract`

自适应大邻域拆修搜索不能重新发明图算法。它只能消费第 9-13 项已经稳定下来的工序图摘要，以及 GraphReady v2 在第 14-21 项沉淀出的目标感知 ready rank、瓶颈资源分、多算法对比和门禁证据。

```python
GraphReadyRepairBridge = {
    "schema_version": 1,
    "source_graph_profile": "balanced",
    "source_candidate_origin": "graph_ready_weight_grid",
    "critical_operation_ids": [],
    "bottleneck_machine_ids": [],
    "downstream_work_by_op_id": {},
    "ready_rank_by_op_id": {},
    "allowed_destroy_scopes": ["critical_chain", "bottleneck_machine", "tardy_window", "changeover_block"],
    "repair_contract_ref": "PartialRepairContract",
    "benchmark_ratchet_ref": "BenchmarkRatchetSnapshot",
}
```

**桥接约束**：

- 桥接项必须在 `alns-partial-repair-contract` 之前完成；否则拆修搜索不能消费图指标。
- `critical_operation_ids`、`bottleneck_machine_ids`、`downstream_work_by_op_id`、`ready_rank_by_op_id` 只能来自第 9-13 项和 GraphReady v2 已校验过的图上下文、目标感知特征或 diagnostics，不能在 ALNS 内部重新跑另一套图分析主链。
- 图桥接只能帮助选择 destroy scope 或 repair 优先级；不能直接写可变工序 `start_time` / `end_time`。
- GraphReady v2 的 ready rank、elite repair 结果和 `pruning_report` 只能作为 ALNS destroy scope / repair priority 的输入摘要。
- 桥接层不得重新解释 GraphReady 剪枝为数学证明，也不得把 `graph_ready_v2_repaired` 的胜出结果拆成单个剪枝规则的独立算法胜利。
- 进入 ALNS 的只应是脱敏后的候选摘要、rank、scope 和统计字段，不传 raw graph 对象或 public 禁止 id。
- 拆修搜索完成后必须以 `algorithm_profile=alns`、`best_origin=alns`、`candidate_origin=alns_*` 接回第 11 项和第 19 项同一套自动选择合同。
- 拆修搜索接入后，item 21 的多算法基准矩阵必须原样复用，并新增 repair 失败、重复候选、同一张表、图不可用、图桥接缺字段五类异常样例。
- 主候选的非法 score、非法 repair 输出、非法 seed_results 必须 fail-loud；只有 diagnostics 展示排序这类只读辅助面可以做容错展示，且必须明确“不参与采纳”。

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
   - 备注：已新增 `core/services/scheduler/run/optimizer_candidate_profile.py`（`CandidateProfile` + `build_candidate_profile` + `derive_iteration_limits`），并作为嵌套字段接入 `OptimizationSearchReport.candidate_profile`，`algorithm_profile` 改由 profile 稳定派生（删除旧模糊串函数）。configured/effective 的 time budget 与 max_iterations 已区分；迭代 `[200,5000]` 系统钳制如实写 `system_limit_applied`/`system_limit_reason`（`iteration_floor`/`iteration_ceiling`）/`iteration_limit_source`；`derive_iteration_limits` 是迭代上限/重启阈值唯一真相源，`optimizer_local_search` 改为共用、行为逐位不变。未知 `profile`/`repair`/`acceptance`/`neighborhood` 与非法 `budget` 一律 fail-loud（与 strict 无关）。profile public 只投白名单安全摘要（`profile_public`），配置来源/邻域等只进 `profile_diagnostics`；size guard 最小摘要保留 `profile_public`。`seed` 如实标记为 version 派生（`seed_source`）。item 4 初始边界只覆盖 `baseline`/`multi_start_local_search`、`repair=sgs`、`acceptance=improve_only` 与旧 `swap/insert/block` 邻域；当前生产能力已由 item 6/7/8 扩展为 `grasp_ig`/`vns_sa`、六个业务邻域 + SGS 专用 `sgs_dispatch_rule`，以及 `improve_only`/`threshold`/`record_to_record`/`simulated_annealing` acceptance，未知值仍 `ValidationError`。未做 item 5 完整 CandidateFingerprint，也未引入新搜索算法。

5. **distinct-candidate-fingerprint-contract** — 定义候选指纹、去重计数、same-fingerprint 拒绝和 improved 判定。
   - 所属模块：候选构造层
   - 依赖：`optimizer-candidate-profile-contract`
   - 状态：done
   - 对应 feature：`2026-06-28-distinct-candidate-fingerprint-contract`
   - 备注：已新增 `CandidateFingerprint` 合同并接入 search report；distinct 统一按 `decoded_output` 去重并在 public/minimal 摘要声明口径；decision/output hash 与 fingerprint 事件只进 diagnostics；`improved` 显式要求 fingerprint 改变、score 严格更优、通过 `improve_only` acceptance；same-fingerprint 只记拒绝/未改进。未新增候选构造、未引入 GRASP / IG / VNS / SA / ALNS。

6. **grasp-ig-candidate-construction** — 用 GRASP / Iterated Greedy 生成更多可行起点，仍由现有 SGS 落位。
   - 所属模块：候选构造层
   - 依赖：`distinct-candidate-fingerprint-contract`
   - 状态：done
   - 对应 feature：`2026-06-28-grasp-ig-candidate-construction`
   - 备注：已新增 GRASP/IG 候选构造模块；候选只生成批次顺序候选并通过 `batch_order` 派工解码，正式 `ScheduleResult`、start/end、资源时间落位仍由现有 `GreedyScheduler.schedule(...)` 完成。候选来源用 `origin=grasp/ig` 接入 `OptimizationSearchReport`，`best_origin` 可如实显示 `grasp` 或 `ig`；`CandidateProfile` 默认 improve 扩展为 `grasp_ig`，并记录 configured/effective 的 GRASP restart、RCL size、IG restart、destruction size。`CandidateFingerprint` 继续以 decision/output 双指纹工作：不同构造决策可区分，解码后同一张表仍按 `decoded_output` 合并，same-fingerprint 不计 improvement。public、OperationLogs、size guard 只展示策略族、计数、口径和安全中文标签；候选原始顺序、fingerprint hash、内部 op/resource id 与 raw trace 不进 public。不保留不可达的 GRASP/IG `sgs` 候选分支。未做业务邻域 registry、VNS/SA、ALNS。

7. **business-neighborhood-registry** — 建立关键链、延期批次、瓶颈设备、换型块、资源替换、时间窗 repair 的邻域注册表。
   - 所属模块：业务邻域层
   - 依赖：`distinct-candidate-fingerprint-contract`
   - 状态：done
   - 对应 feature：`2026-06-28-business-neighborhood-registry`
   - 备注：已新增业务邻域 registry 与 `NeighborhoodMove` 合同；支持关键链、延期窗口、瓶颈设备、换型块、资源替代、时间窗修复六类业务邻域，另注册 SGS 专用 `sgs_dispatch_rule` 用于切换 SGS 派工规则；旧 `swap/insert/block` 不在正式 registry 和 profile 白名单里。邻域只描述 mutable scope 和 move reason，不提前写任何可变工序时间；local search 仍把候选交给现有正式解码链。no-op 写 `candidate_rejected=noop_neighbor`，fallback 写 `fallback_reason`；public 只投 `neighborhood_summary` 和 profile 中的 configured/effective 安全邻域名称。未做 VNS/SA acceptance，未做 ALNS。

8. **vns-sa-local-search-upgrade** — 把现有 local search 升级为 VNS / SA 后处理，先做轻量可复现版本。
   - 所属模块：业务邻域层
   - 依赖：`grasp-ig-candidate-construction`、`business-neighborhood-registry`
   - 状态：done
   - 对应 feature：`2026-06-28-vns-sa-local-search-upgrade`
   - 备注：已新增 `optimizer_acceptance.py`、`optimizer_local_search_state.py`、`optimizer_vns.py` 与 `optimizer_local_search_report_hooks.py`；local search 维护 current/best 分离状态，VNS 按业务邻域切换，threshold/record_to_record/simulated_annealing 可接受非改进候选为 current。2026-06-29 统一候选择优后，best 更新复用 `failed_ops`、`objective_score`、`best_fingerprint_changed`、`runtime_ms`、`candidate_origin` 顺序；同分但正式输出指纹变化的候选可以成为 best，但 `improved` 仍要求 score 严格更优并通过 acceptance，不把“换了一个同分方案”包装成业务改进。`OptimizationSearchReport` 新增 acceptance/VNS trace 与 public 安全摘要，并修复 `acceptance_passed` 代理问题。未做 ALNS。

9. **graph-ready-local-search-contract** — 定义工序图就绪队列派工的局部搜索合同、候选口径和 public/diagnostics 边界。
   - 所属模块：工序图就绪优化层
   - 依赖：`vns-sa-local-search-upgrade`
   - 状态：done
   - 对应 feature：`2026-06-29-scheduler-global-optimizer-items-9-13`
   - 备注：已落地图 ready 候选搜索合同；生产只消费既有 `graph_ready_context` 和 `node_metrics_by_op_id`，不重跑图主链；候选只改变图优先级权重和 SGS ready 排序，正式时间仍由 SGS 解码；图上下文字段、指标和重复 output fingerprint 均有 skipped / candidate_rejected / strict fail-loud 证据。

10. **graph-ready-priority-tuning** — 围绕关键路径、后续影响、下游工时和瓶颈资源做工序图权重多起点比较。
   - 所属模块：工序图就绪优化层
   - 依赖：`graph-ready-local-search-contract`
   - 状态：done
   - 对应 feature：`2026-06-29-scheduler-global-optimizer-items-9-13`
   - 备注：已落 9 组默认图权重 profile，并通过正式 SGS 解码与 `CandidateFingerprint` 去重；生产 `bottleneck_machine_score` 已提前吸收后续 v2 中“候选资源分摊负荷、最小候选负荷、灵活性降权”的基础部分。当前已知缺口是权重仍偏结构重要性，不能覆盖 `min_overdue` 下的目标感知候选区域，v2 仍需补交期压力、可救性、残余容量和候选组合。

11. **optimizer-integration-auto-selection** — 把 GRASP/IG/VNS/SA 和工序图候选接回 `OptimizationOutcome`、候选比较和 summary。
    - 所属模块：接入与展示边界层
    - 依赖：`diagnostic-public-id-boundary-fix`、`vns-sa-local-search-upgrade`、`graph-ready-priority-tuning`
    - 状态：done
    - 对应 feature：`2026-06-29-scheduler-global-optimizer-items-9-13`
    - 备注：已通过 `OptimizerRuntime.run_graph_ready_candidates` 和 `run_heuristic_candidate_phases` 接回 optimizer；候选比较统一按 `failed_ops`、`objective_score`、`best_fingerprint_changed`、`runtime_ms`、`candidate_origin`，并已覆盖 GraphReady、GRASP/IG、VNS/SA 的 best 更新；重复 output fingerprint 只记 same_fingerprint。

12. **benchmark-ratchet-quality-gate** — 把 tiny oracle、非劣化阈值、稳定性统计纳入轻/中/长三层门禁。
    - 所属模块：证明与评测底座
    - 依赖：`optimizer-integration-auto-selection`
    - 状态：done
    - 对应 feature：`2026-06-29-scheduler-global-optimizer-items-9-13`
    - 备注：已新增轻/中/长门禁脚本和 baseline snapshot；当前 tracked baseline 和 actual snapshot 均为 dirty worktree 时,`--check-baseline` 会按合同失败并返回 `unbound_dirty_worktree`,不能写成通过证明或 clean proof；当前门禁能证明 v1 graph_ready 赢自己的贪心基线，但不能证明赢 `local_search`、GRASP/IG 或 `portfolio_all`，v2 多算法对比另列后续 item。

13. **long-run-tuning-evidence** — 建立工序图权重、不同 seed、不同基准集的长跑统计证据和归档口径。
    - 所属模块：长跑调参与门禁层
    - 依赖：`benchmark-ratchet-quality-gate`
    - 状态：done
    - 对应 feature：`2026-06-29-scheduler-global-optimizer-items-9-13`
    - 备注：已新增长跑脚本和 ignored evidence 口径；当前长跑主要重复 graph_ready 单一案例，不是多算法公平横评，v2 的多算法长跑由 item 21 扩展。

14. **benchmark-reference-diagnostics-baseline** — 补齐 GraphReady v2 前的同目标下界、不可比诊断和换型基准准备口径。
    - 所属模块：证明与评测底座
    - 依赖：`long-run-tuning-evidence`
    - 状态：done
    - 对应 feature：`2026-06-29-graph-ready-v2-hardening`
    - 备注：已作为 GraphReady v2 的前置量尺落地并被 `graph-ready-v2-comparison-baseline-contract` 消费；只补量尺和诊断，不重复 item 3/5/7/8 已有 no-op、no-improvement、same-fingerprint、improved 合同；Jackson 单机抢占下界只在同目标同指标可声明时进入 gap，否则标 `not_comparable`；WTSDS / Cicirello / SDST 换型基准已定义装载、评分、脱敏和默认 stdout / ignored 输出口径，不下载 tracked 数据。

15. **graph-ready-v2-comparison-baseline-contract** — 建立 GraphReady v2 修改前的多算法同台比较基准，补齐算法名 / 版本 / seed 维度的 ratchet key。
    - 所属模块：证明与评测底座
    - 依赖：`benchmark-reference-diagnostics-baseline`
    - 状态：done
    - 对应 feature：`2026-06-29-graph-ready-v2-hardening`
    - 备注：已建立同一 case / seed / time budget / objective 下的多算法比较基准；ratchet key 至少包含 `case_group`、`case_slug`、`algorithm_profile`、`algorithm_version`、`seed`。`portfolio_all` 只作为事后上界行，必须标 `comparison_semantics=posthoc_upper_bound`，普通胜平负必须标 `not_comparable`，不能伪装成同预算算法。当前对比可在脏工作区以 `unbound_dirty_worktree` 运行，但不能包装成 clean proof。

16. **graph-ready-v2-objective-feature-contract** — 为 GraphReady v2 定义交期压力、松弛时间、可救批次、剩余工时、工时密度和长尾牺牲等目标感知特征。
    - 所属模块：工序图就绪优化层
    - 依赖：`graph-ready-v2-comparison-baseline-contract`
    - 状态：done
    - 对应 feature：`2026-06-29-graph-ready-v2-hardening`
    - 备注：已落地交期压力、松弛时间、可救性、剩余工时、工时密度和长尾牺牲等目标感知特征；空交期作为合法 no-due 特征并在交期型公式中后置，非空非法交期、缺必要特征、非法数字和 NaN/Inf 均 fail-loud；所有特征进入排序前做 rank/percentile 归一化，避免不同单位裸加。

17. **graph-ready-v2-bottleneck-resource-score** — 将瓶颈机器分升级为残余容量、分摊负荷、最小候选负荷、灵活性降权和交期门控的瓶颈资源分。
    - 所属模块：工序图就绪优化层
    - 依赖：`graph-ready-v2-objective-feature-contract`
    - 状态：done
    - 对应 feature：`2026-06-30-graph-ready-v2-production-capacity`
    - 备注：已在生产 GraphReady v2 特征中补齐残余容量口径，按交期窗口统计日历可用工时，扣除设备停机和冻结/执行态/已排片段占用；新增残余容量、候选机器数、有效候选机器数和瓶颈压力相关字段。交期不紧或不可救时，瓶颈分不会越过主交期信号。

18. **graph-ready-v2-candidate-portfolio** — 建立 GraphReady v2 候选家族，覆盖目标规则、图交期混合、瓶颈交期混合、长尾牺牲和小扰动候选。
    - 所属模块：工序图就绪优化层
    - 依赖：`graph-ready-v2-bottleneck-resource-score`
    - 状态：done
    - 对应 feature：`2026-06-30-graph-ready-v2-production-capacity`
    - 备注：已保留旧九组图权重作为 v1 对照，并生成 EDD、SPT、min_slack、critical_ratio、ATC-like、saveability、sacrifice_long、graph_due_hybrid、bottleneck_due_gated、micro_perturbation 等候选。候选仍通过正式 SGS 解码，不能绕过前后置、资源资格、冻结或执行态保护；默认 GraphReady 候选 profile 为 19 个，配置上限仍为 60。

19. **graph-ready-v2-elite-local-repair** — 对 GraphReady v2 前 K 个候选做轻量局部修补，修复接近好解但差一两步的排序。
    - 所属模块：工序图就绪优化层
    - 依赖：`graph-ready-v2-candidate-portfolio`
    - 状态：in_progress
    - 对应 feature：未完整落地
    - 备注：本项是剪枝策略包的第一个生产落点，不新增独立剪枝算法。benchmark 支撑里已有 adjacent swap 与 single insert 的确定性 repair 脚手架，并能区分 `graph_ready_v2_no_repair` / `graph_ready_v2_with_repair`；生产 core 仍未落地 top-K elite、邻域上限、时间预算、tardy boundary move、repair pruning report 和正式 SGS 接受链，因此保持 in_progress。后续完成标准是：只对已正式 SGS 解码的前 K 精英候选生成有限邻居，邻居重新走正式 SGS、CandidateFingerprint 和严格 score 比较；重复、超预算、不可行、same_fingerprint 必须分开统计。

20. **graph-ready-v2-portfolio-integration** — 把 GraphReady v2 作为候选来源接入统一候选池，与贪心、局部搜索、GRASP/IG、GraphReady v1 共同择优。
    - 所属模块：接入与展示边界层
    - 依赖：`graph-ready-v2-elite-local-repair`
    - 状态：in_progress
    - 对应 feature：未完整落地
    - 备注：GraphReady v2 no-repair 候选池已接入生产 GraphReady 正式 profile，不再依赖 benchmark 注入；生产路径经正式 SGS 和统一 candidate preference / output fingerprint 去重，胜出来源为 `graph_ready_v2_generated`。仍未完成“与 GRASP/IG、VNS/SA 同一生产候选池并行择优”和 `graph_ready_v2_repaired` 生产来源，因此保持 in_progress。`graph_ready_v2_repaired` 只能作为统一候选池里的一个 `candidate_origin`，不能包装成独立剪枝算法；`portfolio_all` 仍只能按事后上界 / `not_comparable` 口径报告。

21. **graph-ready-v2-comparative-ratchet-gate** — 建立 GraphReady v2 修改后的轻 / 中 / 长对比门禁，和当前基准及其他算法做胜平负统计。
    - 所属模块：长跑调参与门禁层
    - 依赖：`graph-ready-v2-portfolio-integration`
    - 状态：in_progress
    - 对应 feature：未完整落地
    - 备注：本项只做比较门禁和反假证明，不实现剪枝算法本体。已能输出 v2 对 `local_search`、`grasp_ig`、`graph_ready_v1` 的胜 / 平 / 负；`portfolio_all` 只能作为事后上界报告差距、来源和 `not_comparable`，不能纳入同预算普通胜负。当前证据仍是 dirty worktree / `unbound_dirty_worktree`，且长跑脚本仍是旧 graph_ready 长跑，未建立最新 HEAD clean comparative ratchet baseline，因此保持 in_progress；缺算法、缺指标、目标不可比、dirty proof 冒充 clean proof、预算未评估冒充 bound proof、same_fingerprint 冒充 improvement 时必须失败或标 `not_comparable`。

22. **alns-graph-ready-bridge-contract** — 定义工序图闭环产物如何喂给自适应大邻域拆修搜索。
   - 所属模块：自适应大邻域拆修搜索层
   - 依赖：`graph-ready-v2-comparative-ratchet-gate`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：桥接项只消费第 9-13 项和 GraphReady v2 已校验过的图摘要、目标感知 ready rank、瓶颈资源分、多算法 ratchet baseline 和脱敏 pruning summary，不重新跑另一套图主链；桥接结果只能影响 destroy scope / repair priority，不能直接写可变工序时间，也不能把 GraphReady 剪枝重新解释成数学证明。

23. **alns-partial-repair-contract** — 定义自适应大邻域拆修搜索的局部拆修 allowed-op、payload validation 和执行态保护复用合同。
   - 所属模块：SGS repair 适配层
   - 依赖：`alns-graph-ready-bridge-contract`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：局部 repair 结果必须复用正式排产守门链，不能只靠拆修搜索内部校验。剪枝只允许减少 repair request 的候选数量，不能减少 allowed-op、payload validation、执行态保护检查；被剪掉、被评估、被拒绝、因预算跳过的候选都必须进入 `OptimizationPruningReport`。

24. **alns-state-operators-core** — 建立自适应大邻域拆修搜索 state、destroy/repair operator 接口、operator reward 和权重更新。
    - 所属模块：自适应大邻域拆修搜索层
    - 依赖：`alns-partial-repair-contract`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：先做纯 Python 外壳，不引入 `alns` / `job-shop-lib` 包、NumPy/Matplotlib 或重依赖。`ALNSOperatorResult`、`ALNSPruningReport`、`PruningRuleDecision`、`PruningRuleTrace` 字段必须在本项启动时定稿，非法 score / repair 输出 / seed_results 必须 fail-loud。operator reward 只能影响后续选择概率，不能覆盖 objective score。

25. **alns-sgs-repair-adapter** — 把拆修搜索 repair 接到现有 SGS，确保 repair 后完整校验并返回候选结果。
    - 所属模块：SGS repair 适配层
    - 依赖：`alns-state-operators-core`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：`seed_results` 只能放保护/执行态固定片段，mutable operations 必须由 SGS 重新落位。ALNS 剪枝后留下的候选必须通过本项 SGS repair adapter 执行正式排产；adapter 必须把 evaluated / rejected 计数回填到 pruning report 和 search report，不能让 ALNS 外壳自行宣称评估成功。

26. **alns-domain-neighborhood-operators** — 定义 ALNS 领域邻域算子：联合机器-排序、关键块 N5 和移动瓶颈候选。
    - 所属模块：自适应大邻域拆修搜索层
    - 依赖：`alns-sgs-repair-adapter`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：本项承载领域剪枝规则，不新增独立剪枝算法。只生成资源 override、batch_order 或 repair request，不直接写工序时间；机器选择必须先确认业务资源资格真实可选，缺资格数据一律 rejected / fail-loud；关键块 N5、移动瓶颈、联合机器-排序、延期边界剪枝只作为 destroy scope、repair priority 或 operator 候选，仍复用正式 SGS 解码和 CandidateFingerprint。scope filter 只能标 `heuristic_scope_reduction`，不能标 `safe_exact` proof。

27. **alns-setup-aware-neighborhoods** — 在换型基准量尺到位后定义 setup-aware 拆修邻域。
    - 所属模块：自适应大邻域拆修搜索层
    - 依赖：`alns-domain-neighborhood-operators`、`benchmark-reference-diagnostics-baseline`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：等换型基准、不可比诊断和 ALNS repair 链到位后再做；只优化换型相关候选作用域和排序/资源决策，不把 setup 收益写成缺证据的 objective improvement；无 SDST / WTSDS 等可比样例时只能跳过或标 `not_comparable`。setup-aware pruning 只能在同目标评分口径到位后启用，否则只能标 `heuristic_scope_reduction` 或 `not_comparable`。

28. **alns-selection-acceptance-trace** — 实现拆修搜索 operator 选择、threshold / Record-to-Record Travel / SA acceptance、segment 权重更新和 trace 输出。
    - 所属模块：自适应大邻域拆修搜索层
    - 依赖：`alns-sgs-repair-adapter`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：operator reward 只影响后续选择概率，不能直接覆盖 objective score。本项承载 pruning trace、candidate rejection trace、reward update trace 和归因边界；posthoc portfolio best 只能写 `portfolio_all` / `posthoc_upper_bound` / `not_comparable`，不能偷归因给单个 operator。

**最小闭环**：第 1 条 `optimizer-proof-harness` 做完后，系统能在不改写 tracked evidence 的前提下，运行 tiny oracle / lower bound / 当前算法对比，并明确输出“是否证明最优、gap 绑定的是哪个目标和指标、是否只能参考”。

## 6. 排期思路：已落地基础 → 工序图 v1 闭环 → GraphReady v2 → 拆修搜索

本路线现在不再按旧“两段式”推进。前 13 项已经把证明底座、搜索报告、候选指纹、GRASP/IG、业务邻域、VNS/SA、GraphReady v1、统一自动选择和轻/中/长门禁打完。GraphReady v2 的前半段也已经推进到 item 18:前置量尺、修改前基准、目标感知特征、瓶颈资源分和候选家族已经落地。下一段仍不直接进入 ALNS,而是继续收口 item 19-21:生产级 elite repair、组合池接入和对比 ratchet 门禁。

### 第一段 · 已完成的基础能力（item 1-8）

已完成链路是：proof 底座 → public 边界修复 → 搜索可观测合同 → 候选 profile/指纹 → GRASP/IG 候选构造 → 业务邻域 → VNS/SA 局搜。

这些项的价值是把“试了什么、有没有真的变好、是否只是重复同一张表、有没有泄漏内部 id”先钉死。没有这层底座，后面的工序图权重和拆修搜索都会变成凭感觉调参。

### 第二段 · 已完成的工序图 v1 闭环（item 9-13）

v1 已完成链路是：

1. **工序图局部搜索合同（item 9）**：先规定图候选能动什么、不能动什么，尤其不能直接写可变工序时间。
2. **图权重多起点比较（item 10）**：围绕关键路径、后续影响、下游工时、瓶颈资源跑多组候选，避免只靠一组默认权重。
3. **统一自动选择一期（item 11）**：把 GRASP/IG、VNS/SA、工序图候选放进同一套比较链路，先选当前已存在算法里最好的。
4. **基准门禁（item 12）**：把 FJSP 工序图收益、SMTWT 持平、大资源池性能不退步纳入轻/中/长门禁。
5. **长跑证据（item 13）**：多 seed、多样例跑稳定性，证明图权重不是只在某一个样例上碰巧好。

这一段的价值是让图 ready 候选真正跑进生产 optimizer，并留下 ratchet 证据。它的已知缺口也要写清：v1 当前能证明赢贪心基线，但还不能证明赢 `local_search`、GRASP/IG 或 `portfolio_all`；v1 的 9 组图权重偏结构重要性，目标函数感知不足。

### 第三段 · GraphReady v2 目标感知候选与多算法对比（item 14-21）

当前先收口 v2，不直接进入 ALNS：

`benchmark-reference-diagnostics-baseline` 已作为 item 14 的前置量尺落地并被消费。原因很简单：已有 proof harness 和 search report 能说明“有没有改进”，但还缺更具体的同目标下界、不可比诊断和换型基准准备；这层已补后,后续才可以继续做 v2 的生产级收口,并且仍不能拿不可比数据证明收益。

1. **同目标参考量尺（item 14,done）**：已补同目标下界、不可比诊断和换型基准准备口径。
2. **多算法修改前基准（item 15,done）**：已建立同台比较量尺，补 `algorithm_profile` / `algorithm_version` / `seed` 维度的 ratchet key，记录当前基准。
3. **目标感知特征（item 16,done）**：已加入交期压力、松弛时间、可救批次、剩余工时、工时密度和长尾牺牲等特征，让 `min_overdue` 先懂“能不能多救一个批次”。
4. **瓶颈资源分 v2（item 17,done）**：已用残余容量、负荷分摊、最小候选负荷、灵活性降权和交期门控，替换“能跑瓶颈机就高分”的粗糙口径。
5. **候选家族（item 18,done）**：已新增目标规则、图交期混合、瓶颈交期混合、长尾牺牲和小扰动候选，不再只调旧 9 组图权重。
6. **轻量 elite 修补（item 19,in_progress）**：benchmark 支撑已有脚手架,生产 core 仍需补 top-K、邻域上限、时间预算、tardy boundary move、repair pruning report 和正式 SGS 接受链,并单独报告有无修补的收益。
7. **组合池接入（item 20,in_progress）**：v2 no-repair 已作为 GraphReady 正式 profile 接入;仍需完成与贪心、局部搜索、GRASP/IG、v1 的同一生产候选池择优,以及 repaired 生产来源。`graph_ready_v2_repaired` 只是统一候选池里的来源之一,不是独立剪枝算法。
8. **修改后对比门禁（item 21,in_progress）**：已有 dirty worktree 对比证据,但还缺最新 HEAD clean comparative ratchet baseline;后续仍要和 item 15 的“修改前”基准比较,并输出 v2 对 `local_search`、GRASP/IG、v1 的胜 / 平 / 负；`portfolio_all` 只作为事后上界报告差距和来源，不能参与同预算普通胜负；剪枝报告缺失、不可比下界冒充证明、预算未评估冒充 bound proof、same_fingerprint 冒充 improvement 都必须失败或标 `not_comparable`。

这一段的硬要求是“改完必须和现在的基准比，也必须和其他算法比”。不能只写“v2 赢 greedy”，不能拿 FJSP makespan 当 APS 业务目标最优证明，也不能把 dirty proof 包装成 clean proof。

### 第四段 · 自适应大邻域拆修搜索（item 22-28）

工序图闭环之后，再做自适应大邻域拆修搜索七项：

1. **工序图桥接合同（item 22）**：先规定拆修搜索只能消费第 9-13 项和 v2 沉淀出的图摘要、目标感知 ready rank、瓶颈资源分和多算法基准，不能重建图主链。
2. **局部拆修合同（item 23）**：锁住 allowed-op、payload 校验和执行态保护，防止拆修搜索绕开正式排产守门链。
3. **搜索状态和算子外壳（item 24）**：纯 Python 实现 state、destroy/repair operator、operator reward、权重更新和通用 pruning report，不引入重依赖。
4. **SGS repair 适配（item 25）**：被拆掉的工序必须交回现有 SGS 正式落位，不能由新算法直接写开始结束时间；剪枝后留下的候选也必须经由这个 adapter 真正解码。
5. **领域邻域算子（item 26）**：定义联合机器-排序、关键块 N5、移动瓶颈和延期边界候选,但仍只生成资源 override、batch_order 或 repair request；领域剪枝只能缩小候选范围，不能写成数学证明。
6. **换型感知邻域（item 27）**：换型基准量尺到位后再定义 setup-aware 拆修邻域,不可把 setup 收益写成缺证据的 objective improvement；没有可比换型基准时只能 skip 或 `not_comparable`。
7. **选择、接受和 trace（item 28）**：把算子选择、接受准则、权重更新、pruning trace、拒绝原因和归因边界归一到搜索报告里。

本轮新增的 ALNS 领域算子不前移到 GraphReady v2：`alns-domain-neighborhood-operators` 等 SGS repair 适配完成后，再定义联合机器-排序、关键块 N5 和移动瓶颈这类 operator 候选；`alns-setup-aware-neighborhoods` 还要等换型基准量尺到位，避免把缺证据的 setup 收益写成真实 objective 改进。

这七项仍然保留为 planned，并且排在 GraphReady v2 之后。这样路线图不会删除后续高级搜索，也不会把“剪枝算法”单独变成一条新主线；实际推进顺序会先把图候选自身做强、量尺做准，再让拆修搜索复用同一套图摘要、自动选择、剪枝报告和 benchmark 证据。

## 7. 观察项

- `.codestable/roadmap/networkx-scheduler-graph-introduction/` 已经完成图分析引入，本路线不能重复“再引入一套图主链”，只能消费已有工序图上下文、ready 队列和图评分摘要。
- `.codestable/roadmap/aps-three-gap-directions/` 当时明确“不重写排程算法”，那是面向方案解释和现场反馈的范围；本路线是新的算法搜索能力，不能塞进旧路线。**算法范围互不冲突，但契约面有真实重叠且须治理**：该路线已 completed 并定稿了 candidate-comparison（`CandidateCard`/`CandidateMetrics`、`diff=current-adopted`）、summary delta、`OverdueDiagnosisReport` 诊断、以及 program-field-vs-user-visible-text 的 public/id 边界。本路线模块 H（`diagnostic-public-id-boundary-fix`、`optimizer-integration-auto-selection`）会改到这四处共享契约——**这不是绿地，改动前必须回 aps-three-gap-directions 走它的 update gate（其 roadmap 明确“改字段/状态/路由/错误码前先回来 update”），不得单方面改动**。`diagnostic-public-id-boundary-fix` 因此是动他人已定稿契约的前置治理项，等级高于普通 issue（口径以那条 roadmap 文档为准：completed + 合同定稿 + update gate 存在；不等于已逐项核对所有相关代码面都已上线）。
- `schedule-delay-diagnosis` requirement 仍是 draft，但相关能力在多个路线里已有实现片段，后续可能需要单独 `cs-req update`。
- `candidate-comparison-business-view` 已是 current，但 `VISION.md` 中状态可能需要刷新。
- `diagnostic-public-id-boundary-fix` 更像 issue/安全边界修复；本路线把它列为新增 search report / diagnostics 的前置 feature，也可以单独走 `cs-issue` 先完成。
- 当前工作区已有未提交改动和 benchmark evidence 修改，任何 clean proof 都必须在最新 HEAD 与干净工作区上重新跑。
- 2026-07-01 审阅剪枝口径后确认：不新增独立“剪枝算法”路线，不引入分支定界生产主引擎或束搜索默认引擎。剪枝策略包作为现有 scheduler-global-optimizer 的补充合同存在，先服务 item 19 GraphReady v2 elite repair，再进入 item 24/26/28 的 ALNS state/operator、领域邻域和 trace，同时由 item 21 做反假证明门禁。核心边界是：剪枝只减少候选评估次数，不替代正式 SGS / Greedy 解码，不把预算未评估、不可比下界或重复 fingerprint 包装成改进证明。
- 2026-06-29 基准复核确认：工序图就绪队列派工的收益集中在有工序前后关系的场景。FJSP 默认 5 个样例里，平均总完工时长从批次顺序派工 262.60h、普通串行派工 236.20h，降到工序图就绪队列派工 206.60h；平均参考差距从 62.67% / 46.37% 降到 33.79%。但在 SMTWT 这类单工序样例上，普通串行派工和工序图就绪队列派工都是平均 gap 16.16、达最优 39/250；大资源池和碎片时间线也基本持平。归属：item 9-13 先做工序图局部搜索、权重比较、自动选择和门禁。
- 2026-06-29 Exa MCP 补强调研没有推翻当前主线，但补出三个路线图缺口：① FJSP/JSP 常见算法证据支持大邻域搜索、禁忌搜索、移动瓶颈法和图 / 优先级规则混合，但本仓库仍应先走纯 Python、SGS repair、无重依赖路线；② 拖期和换型目标必须有专门基准，不能用 FJSP makespan 参考结果替代；③ 启发式算法验收必须多样例、多 seed、报告均值和最差值，不能只展示单次最好结果。归属：item 12 / 13 的门禁矩阵和长跑证据格式。
- 2026-06-29 对抗审查后确认：GP 超启发式只适合作为研究候选，不进入当前主线 items。原因是两份路线图文件里没有现成接口、基准或 Win7 / Python 3.8 / 纯 Python 落地边界支撑；若未来重新评估，必须先证明它只生成可解释的规则 / 候选决策，并继续回 SGS 解码。
- 2026-06-29 对抗审查后确认：联合机器-排序邻域只有在业务机器资格真实可选时才成立。当前 roadmap 只能证明“资源 override / repair request 可以回 SGS 解码”，不能证明每个业务场景都有可替代机器；后续 `alns-domain-neighborhood-operators` 启动时必须先查资源资格数据，缺数据就拒绝候选，不能回退成“所有机器都可选”。
- 2026-06-26 经 proof-harness（item 1）实测发现：现有 `improve` 局部搜索在 SGS 派工模式下是**结构性 no-op**。其唯一邻域是 swap/insert/block 重排 `batch_order`（`core/services/scheduler/run/optimizer_local_search.py:15-61`），但 SGS 只把 `batch_order` 当 `build_dispatch_key` 末位平手决胜键（`core/algorithms/dispatch_rules.py:33-36`、`core/algorithms/greedy/dispatch/sgs.py:44-48,99,215`），slack/atc 近似连续几乎不平手，故批次顺序重排几乎总解出同一张表。证据：SMTWT 同起点重排批次顺序 300 次 overdue 零变化，而 `batch_order` 派工模式下 206/300 更好（34→28）；默认 `dispatch_mode=batch_order` 经多起点扩展后 sgs 起点总胜出、局搜继承胜出起点模式（`optimizer_local_search.py:253`），导致局搜恒 0 改进且空烧满 `time_budget`（budget 5/20s 结果一致）。
    - 治理归属：no-op 如实记 + 到预算止损归 **item 3 `optimizer-search-report-contract`**（§4.3 已明文要求 `candidate_rejected=noop_neighbor` 与 `stop_reason=time_budget`）；业务邻域的 no-op/fallback 可解释记录已由 **item 7 `business-neighborhood-registry`** 治理为 `neighborhood_summary`/`neighborhood_moves`；搜索状态机与非改进接受已由 **item 8 `vns-sa-local-search-upgrade`** 治理为 current/best 分离、VNS 邻域切换与真实 acceptance trace。item 9-13 已完成工序图 v1 闭环；后续真正补目标感知搜索空间，归 item 14-21 GraphReady v2，再归 item 22-28 拆修搜索。
- 2026-06-26 目标↔基准覆盖盘点（决定后续换目标时拿什么证明）：系统当前有 4 个目标（`core/models/objective.py:18-46`）——`min_overdue` / `min_tardiness` / `min_weighted_tardiness` / `min_changeover`，**没有 makespan 目标**（`makespan_hours` 仅作各目标 5 元组里的低位平手决胜键，从不是主优化项）。
    - **可比覆盖现状**：目前只有 `min_overdue` 的**首分量 `overdue_count`** 有同模型同指标的精确最优基准（SMTWT + Moore-Hodgson，`tests/_support/optimizer_benchmark_grading.py`），且当前只给 **greedy** 打分、未给 improve 打分；`min_overdue` 后 4 个 tie-break 分量、以及其余 3 个目标**都没有可比的已证明最优基准**。
    - **拖期/加权拖期缺口**：SMTWT 自带的 `wtopt` 是**自由权重（1–10）的加权拖期**最优，而 APS 加权拖期只有 3 档（critical/urgent/normal），两套权重不同**不可比**；无权重的 1‖ΣT_j 是 NP-hard、本仓库无 oracle。故 `min_tardiness` / `min_weighted_tardiness` 短期只能用下界 / best-known 做参考，做不了"精确最优"对照。
    - **换型缺口**：`min_changeover` 量的是换型次数，**SMTWT / JSP / RCPSP 一个都不涉及换型**；要证明它须另引**顺序相关换型时间（SDST）基准**（如 OR-Library SDST 集），目前未下。
    - **makespan 基准（JSP/RCPSP/FJSP）定位**：它们量 makespan，而系统无 makespan 目标，故只能当 `folded_not_comparable` 参考；**仅当将来真新增 makespan 族目标时才会翻成可打分基准**。本系统以交期 / 换型为导向，makespan 是否值得设为目标存疑——建议保持参考态，不为"凑基准"硬加目标。
    - 归属：本盘点是 **item 12 `benchmark-ratchet-quality-gate`** 的前置输入（每个目标要单独配齐"同目标同指标的量尺"才能纳入非劣化门禁，且应把 improve 也纳入打分）；属观察归档，本轮不改代码。

- 2026-06-28 经 item 3 review + Codex 对抗复审：确认 item 3 落地的 `distinct_candidates` 与 `improved` 是**过渡口径**，正确实现归 **item 5 `distinct-candidate-fingerprint-contract`**（其 description 即「候选指纹、去重计数、same-fingerprint 拒绝和 improved 判定合同」）。**已在 item 5（2026-06-28）修复**。
    - `distinct_candidates`：原 `candidate_report_fingerprint` 把 `order`/`origin` 编入指纹（旧 `core/services/scheduler/run/optimizer_search_report.py:36-51`），叠加本节已记的 SGS 解码塌缩（不同 batch_order 解出同一张表），会让 distinct 在 improve 默认模式下系统性虚高。item 5 已改为 `output_fingerprint` / `decoded_output` 口径去重，并在 public / minimal search_report 里保留 `distinct_fingerprint_scope` 与中文口径说明。
    - `improved`：原 `improved = best_fingerprint_changed` 是单条件隐式耦合。item 5 已显式输出 `improvement_conditions`，并仅在 `fingerprint_changed`、`score_strictly_better`、`acceptance_passed` 三条件同时成立时 `improved=True`；item 8 后 `acceptance_passed` 来自真实 best acceptance 事件，非改进候选被接受为 current 不会让 `improved=True`。
    - `same_as_parent` / `same_as_seen`：item 5 已把重复 decoded output 记为 `same_fingerprint` 拒绝，不再计入新的 distinct，也不计入 improvement。
    - 同轮清理本 item 引入的两处代码债（非 item 5 范围）：删除 `finalize` 中 best 非空但无 accept 记录时的兜底 `mark_candidate_accepted`（生产不可达 + 破坏 `accepted_distinct ≤ distinct` 不变式，连带删 `finalize` 的 best 形参）、删除 `_runtime_ms` 的 `except Exception` 静默兜底（改为 clock 异常 fail-loud）；补 `no_improvement` / `all_candidates_rejected` 两个 stop_reason 回归测试。

- 2026-06-28 item 5 review 收尾（OPUS 子代理定向+盲审 + Codex 对抗复审，实跑 48+352 测试全绿、质量门禁 17/17）：确认 distinct/improved/public 边界实质达标，无破坏正确性或泄漏内部 id 的 blocker；按裁决硬化 1 处脆弱代码并清理代码债——路线图无后续 item 覆盖的就地处理、已覆盖的留给对应 item。
    - **B1（指纹排序防御性硬化；真实数据流下不可达，非生产会触发的崩溃）**：`optimizer_candidate_fingerprint.py` 的 `_result_signature` 旧实现用类型不稳定的 `op_id` 作排序键首元素——旧 `_identity_value` 对正整数返回 `int`、对 `0`/`None`/≤0 返回 `str`，若一批 `results` 混入正整数与 `0`/`None` 的 op_id，`sorted` 会拿 `int` 与 `str` 比较而抛 `TypeError`。**经核实该输入在生产不可达**：`BatchOperations.id` 为 `INTEGER PRIMARY KEY AUTOINCREMENT`（`schema.sql:148`）必为正整数；排产工序全部经 `op_repo.list_by_batch`（`SELECT id FROM BatchOperations`）从库查（`schedule_input_collector.py:162`）；生产代码（`core/services` + `data`）无任何内存构造 `BatchOperation(...)`。故 `op.id` 必为正整数、`_build_internal_result` 的 `op.id or 0` 永不落 0，单元测试外不会出现混合 op_id。脆弱点的本质是 `_identity_value`「特意为非正整数留 `str` 兜底」与排序「假设同质可比」两个假设自相矛盾：兜底反而埋了崩溃点。修复删 `_identity_value`、签名内 `op_id` 统一 `str`，使排序键类型恒定、两个假设不再打架，焊死未来若引入「未入库工序参与排产」时的潜伏崩溃点；定性为防御性硬化，非修当前会触发的生产 bug。补 op_id 混合回归测试锁住该健壮性。**前轮 review（含 Codex）把它标为「偏 blocker、可达性高」是高估——当时停在「`id` 类型为 `Optional[int]` 故理论可能」，未闭合「主键自增 + 全量从库查」这一环。**
    - **死代码/兜底清理**：删 `_resource_override_payload` 三个无写入方 key 别名（O1）；删孤儿函数 `candidate_report_fingerprint`/`attempt_report_fingerprint`/`stable_report_fingerprint`（O3，dead-code 岛屿 358→355）；删 `mark_candidate_rejected`/`mark_optional_warmstart_failed` 的 dead `attempt` 形参 + 4 调用点（O4）；删 report 层与 `distinct_fingerprint_scope` 值重复的冗余 `fingerprint_scope` 字段（M2）。补候选缺 `results`/非有限 score/非法 `seed_result_count` 三条 fail-loud 测试。
    - **M1（已修复，item 8）**：`acceptance_passed = accepted_candidates>1` 这个间接代理已删除。当前 `OptimizationSearchReportState.best_acceptance_passed` 只在 best 通过真实 acceptance 事件更新时置真；`accepted_candidates` 可以包含 threshold/Record-to-Record Travel/simulated_annealing 接受的非改进 current 解，但这些不会让 `acceptance_passed=True`。O2（`_mutable_scope_payload` fallback）复查为测试可达的优雅降级，撤回不删；I1/I2（`_jsonable` 有损降级）仅影响 diagnostics、`output_fingerprint` 不经该分支，仅加注释。
    - **关于 batch_order/SGS 的 `op_id<=0` 处理差异（已评估，不单独立 issue）**：`batch_order` 落位（improve 默认重排）对 `op_id<=0` 无校验，SGS 经 `ready_queue` 对 `op_id<=0` fail-loud，二者写法不一致。但承上——主键自增必正整数、排产工序全从库查、生产无内存构造工序，两条路径在真实数据流下都遇不到 `op_id<=0`，该差异同样不可达，**不单独立 issue**。`_build_internal_result`（`core/algorithms/greedy/internal_operation.py:211`）的 `op.id or 0` 也是对不可达输入的防御，保留无害；真要消除可在引擎层把 `op.id` 收紧为 `parse_required_int` 统一 fail-loud，但优先级低、且属排产引擎范围，不在本 item。

## 8. 变更日志

- 2026-07-01：审阅并落档“剪枝策略包”路线图口径。明确不新增独立 `pruning-algorithm` item，不把分支定界 / 束搜索做成生产主线；新增 §2 剪枝策略包定位、§4.1.1 `OptimizationPruningReport` 合同，补模块 E/F 的剪枝职责、GraphReady v2 修补剪枝报告、多算法对比门禁、图桥接约束和 item 19-28 的剪枝 / repair / trace / 归因边界。items 状态不变：19-21 仍为 in_progress，22-28 仍为 planned。
- 2026-06-26：创建 roadmap。基于本地调用链、9 个只读 Sub Agent、Exa 深研和现有 CodeStable 路线整理；本阶段明确不引入 OR-Tools，主线为 proof harness + public 边界修复 + GRASP/IG + VNS/SA + ALNS with SGS repair。
- 2026-06-26：根据线上审阅补强 `APPROVE_WITH_CHANGES` 三项：optimizer 退出路径映射、SearchProfile configured/effective 报告、benchmark public/diagnostics 分层。
- 2026-06-26：吸收非 OR-Tools 深研报告审阅意见：新增 `distinct-candidate-fingerprint-contract`，收紧全局最优口径、第三方库依赖边界、Record-to-Record Travel 全称命名和 same-fingerprint 不得伪成功合同。
- 2026-06-26：完成 `optimizer-proof-harness` 最小闭环：新增 tiny exact oracle / objective_score 证明、makespan lower bound 参考字段、FJSP 折叠不可比引用口径和默认 stdout 的 check 脚本；默认不写 tracked evidence。
- 2026-06-26：经两轮深度 review + Codex 对抗核实后重构排期与契约口径。① 给 proof harness 补 `assert_oracle_decoder_matches_greedy` fail-loud 守卫，把 `same_model` 从字段声明改为每次运行由构造强制（oracle 解码须复现 greedy 实际所选排程，否则禁止声称证明）。② 排期改为 Phase A（item 1-6 贴主链、逐项增量集成）/ Phase B（item 7-15 由 harness 证据闸门解锁），item 2 标可并行，item 13 收敛为“统一自动选择”而非大爆炸集成。③ 当时的 `ALNSOperatorResult` 标注为前瞻接口占位（待后续拆修搜索定稿），`PartialRepairContract` 保持（属防御既有安全边界）。④ public/id 脱敏设为单一真相源，其余契约引用而非复述。⑤ OR-Tools 措辞精确化为“已有可选 warm-start 不升级为主引擎”。⑥ 把与已 completed 的 `aps-three-gap-directions` 的契约重叠升级为显式跨路线 update-gate 治理前置。
- 2026-06-26：完成 `diagnostic-public-id-boundary-fix`。public algo / graph / candidate / HTML / export / OperationLogs 统一走安全摘要投影；`attempts` 只允许 list 形态下的白名单字段，非 list 原始 dict 直接从 public 输出移除；第二轮定向复审与盲审均未发现 blocker。
- 2026-06-26：proof-harness 实测暴露现有 improve 局搜在 SGS 下结构性 no-op + 空烧 time_budget（证据见 §7 观察项）；确认机制治理归 item 3、搜索空间修复归 item 8，本轮只归档不改代码。
- 2026-06-26：补"目标↔基准覆盖盘点"（§7）：系统 4 目标无 makespan；仅 `min_overdue` 首分量 `overdue_count` 有精确可比基准且只测 greedy；拖期/加权拖期因权重口径不一致 + NP-hard 缺 oracle、换型缺 SDST 基准、JSP/RCPSP 属 makespan 休眠参考；当前重排后对应 item 12 前置输入。本轮只归档不改代码。
- 2026-06-27：完成 `optimizer-search-report-contract`。新增 `core/services/scheduler/run/optimizer_search_report.py`、`core/services/scheduler/run/optimizer_step_report_hooks.py` 和 `core/services/scheduler/summary/optimizer_public_search_report.py`，`OptimizationOutcome`、orchestrator、candidate plan、summary、summary size guard 最小摘要和 OperationLogs 小摘要均接入 search report；新增 `tests/algorithm/test_optimizer_search_report_contract.py` 并登记 test registry，同时收紧 size guard 回归测试。验证覆盖 report 基础字段、baseline fallback、multi-start 成功、optional warm-start failure、strict ValidationError fail-loud、non-strict candidate_rejected、local search time_budget / iteration_limit / skipped、public/diagnostics 分层、size guard 最小摘要保留 public search_report 和 OperationLogs 摘要；proof harness 回归仍通过。边界：本轮只做报告合同，不做 item 4 candidate profile、item 5 完整 CandidateFingerprint，不做 GRASP / IG / VNS / SA / ALNS。
- 2026-06-28：item 3 `optimizer-search-report-contract` 收尾 review（3 个只读 OPUS 子代理 + Codex 对抗复审，实跑 52 项相关测试全绿）。总裁定：无破坏正确性或泄漏内部 id 的硬 blocker。按裁决本轮清理本 item 代码债（删 `finalize` 兜底 + best 形参、删 `_runtime_ms` 静默兜底）、补 `no_improvement` / `all_candidates_rejected` stop_reason 测试；`distinct_candidates` / `improved` 过渡口径归 item 5，已在 §7 钉遗留，本轮不改其实现。
- 2026-06-28：完成 `optimizer-candidate-profile-contract`（item 4）。新增 `core/services/scheduler/run/optimizer_candidate_profile.py`（`CandidateProfile` 合同 + `build_candidate_profile` fail-loud 校验 + `derive_iteration_limits` 迭代上限单一真相源），接入 `OptimizationSearchReport.candidate_profile`，`algorithm_profile` 改由 profile 稳定派生并删除旧 `_algorithm_profile` 模糊串函数；`optimizer_local_search` 的内联迭代/重启公式改为共用 `derive_iteration_limits`（逐位等价、零行为变化）；summary 层新增 `profile_public`/`profile_diagnostics` 白名单分层投影，size guard 最小摘要保留 `profile_public`。新增 `tests/algorithm/test_optimizer_candidate_profile_contract.py`（23 用例）并登记 test registry。验证覆盖 configured/effective budget&iteration 区分、系统钳制 floor/ceiling 如实报告、未知 profile/repair/acceptance/neighborhood + 非法 budget fail-loud（与 strict 无关）、baseline 不升 OR-Tools 主引擎、seed version 派生标注、public 无内部 id 泄漏、四出口（页面/OperationLogs/size guard/algo summary）分层不破。执行者记录中含 4 层 OPUS 对抗审查摘要，但仓库当前未附独立审查产物；如需作为可复核 proof，应补原始审查记录或链接。质量门禁 17/17 步通过（`--allow-dirty-worktree`，dirty/unbound proof，非 clean proof）。当时只记录 item 4 初始边界：`baseline`/`multi_start_local_search`、`repair=sgs`、`acceptance=improve_only`、旧 `swap/insert/block` 邻域；当前生产能力已由后续 item 扩展，现状口径以上文 item 6/7/8 和 2026-06-29 口径校正为准。
- 2026-06-28：完成 `distinct-candidate-fingerprint-contract`（item 5）。新增 `core/services/scheduler/run/optimizer_candidate_fingerprint.py`，定义 `CandidateFingerprint`、decision/output 双指纹、decoded output 去重口径和 score 严格更优判定；`OptimizationSearchReportState` 改用 `output_fingerprint` 统计 `distinct_candidates` / `accepted_distinct_candidates`，public/minimal 摘要新增 distinct 口径说明，fingerprint hash 与事件留 diagnostics；`improved` 改为 fingerprint 改变 + score 严格更优 + acceptance 通过三条件，acceptance 对齐 item 4 `improve_only`；same-fingerprint 记 `same_fingerprint` 拒绝。新增 `tests/algorithm/test_optimizer_candidate_fingerprint_contract.py` 并登记 test registry；同步收紧 search_report、public boundary、size guard 与内部 id 脱敏测试。边界：未新增候选构造、未引入 GRASP / IG / VNS / SA / ALNS，未做业务邻域 registry。
- 2026-06-28：`distinct-candidate-fingerprint-contract`（item 5）review 收尾。B1 指纹排序防御性硬化（`op_id` 在签名内统一 `str`、删 `_identity_value`，消除「为非正整数留 str 兜底」与「排序假设同质可比」的自相矛盾）——经核实 op_id 来自自增主键（`schema.sql:148`）、排产工序全从库查（`schedule_input_collector.py:162`）、生产无内存构造 `BatchOperation`，该崩溃真实数据流不可达，属潜伏崩溃点的预防性焊死、非当前会触发的 bug（前轮含 Codex 标「偏 blocker」系高估）；清理死代码与兜底：删 `_resource_override_payload` 三个无写入方别名、删 3 个孤儿指纹函数（dead-code 岛屿 358→355）、删 `mark_candidate_rejected`/`mark_optional_warmstart_failed` 的 dead `attempt` 形参（含 4 调用点）、删 report 层冗余 `fingerprint_scope` 字段与 `FINGERPRINT_SCOPE` 常量；补缺 `results`/非有限 score/非法 `seed_result_count` 三条 fail-loud 测试 + op_id 混合回归。M1（`acceptance_passed` 间接代理）已加注释并归 item 8；I1/I2（`_jsonable` 有损降级，仅 diagnostics）仅加注释；O2（`_mutable_scope_payload` fallback）复查为测试可达的优雅降级，撤回不删。batch_order/SGS 对 `op_id<=0` 处理写法不一致，但同因 op_id 必正整数而不可达，已评估不单独立 issue。实跑 48+352 测试全绿、质量门禁 17/17 通过（`--allow-dirty-worktree`，dirty/unbound proof）。
- 2026-06-28：完成 `grasp-ig-candidate-construction`（item 6）。新增 `core/services/scheduler/run/optimizer_grasp_ig_specs.py` 与 `core/services/scheduler/run/optimizer_grasp_ig_candidates.py`，在多起点后、局搜前构造 GRASP / Iterated Greedy 候选起点；候选只改批次顺序并通过 `batch_order` 派工解码，正式排程仍调用现有 GreedyScheduler 解码链。`CandidateProfile` 默认 improve 扩展为 `grasp_ig`，新增 `candidate_strategy_families` 与 `candidate_construction`，configured/effective 的 GRASP restart / RCL size / IG restart / destruction size 如实报告；public 只投策略族安全摘要，构造预算只进 diagnostics。`OptimizationSearchReport` 接受 `best_origin=grasp/ig`，但没有真实 best acceptance event 时 `acceptance_passed=False` 且 `improved=False`；`CandidateFingerprint` 继续按 decision/output 双指纹工作，`distinct_candidates` 仍按 `decoded_output` 去重，same-fingerprint 不算 improvement。新增 `tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py` 并登记 test registry；验证覆盖 seed 确定性、batch_order 解码、ValidationError rejected/fail-loud、collapsed output 去重、best_origin、fingerprint split、public/OperationLogs/size guard 边界。边界：未做业务邻域 registry、VNS/SA acceptance、ALNS；不可达的 GRASP/IG `sgs` 候选分支已移除。
- 2026-06-28：完成 `business-neighborhood-registry`（item 7）。新增 `core/services/scheduler/run/optimizer_neighborhood_moves.py`、`optimizer_neighborhood_move_support.py`、`optimizer_neighborhood_registry.py`，注册 `critical_chain/tardy_window/bottleneck_machine/changeover_block/resource_alternative/time_window` 六个业务邻域，另注册 SGS 专用 `sgs_dispatch_rule`；旧 `swap/insert/block` 不在正式 registry 和 profile 白名单里。local search 通过 registry 生成 `NeighborhoodMove` 后仍调用现有正式解码链。`CandidateProfile.neighborhoods` 默认改为六个业务邻域，未知邻域继续 `ValidationError`；`OptimizationSearchReport` 新增 `neighborhood_moves` diagnostics 与 `neighborhood_summary` public 小摘要，no-op/fallback 如实计数，并把 configured/effective 邻域分开报告，避免 SGS 模式被误读成跑了六个业务邻域。新增 `tests/algorithm/test_optimizer_business_neighborhood_registry_contract.py` 并登记 test registry；验证覆盖白名单、fail-loud、no-op、fallback、decision/output fingerprint、解码接入、resource-only move、public/OperationLogs/size guard 边界。边界：未做 VNS/SA acceptance/current-best 状态机，未做 ALNS。
- 2026-06-28：完成 `vns-sa-local-search-upgrade`（item 8）。新增 `core/services/scheduler/run/optimizer_acceptance.py`、`optimizer_local_search_state.py`、`optimizer_vns.py`、`optimizer_local_search_report_hooks.py`，在 item 7 业务邻域之上实现 current/best 分离、VNS 邻域切换、`improve_only`/`threshold`/`record_to_record`/`simulated_annealing` acceptance 语义；非改进候选可被接受为 current，但 best 只在真实 acceptance 通过、score 严格更优、`output_fingerprint` 非 parent 且非 seen 时更新。`CandidateProfile` 默认 improve 扩展为 `vns_sa`，acceptance 白名单扩为四种且未知值 fail-loud；`OptimizationSearchReport` 新增 `current_accepted_candidates`、`best_improved_candidates`、`acceptance_events`/`acceptance_summary`、`vns_events`/`vns_summary`，并把 `acceptance_passed` 改为真实 best acceptance 事件，修复 item 5 review 记录的 M1 代理问题。public、OperationLogs、size guard 只投 acceptance/VNS 安全计数摘要，不展示 raw random draw、fingerprint hash、raw move 或内部 op/resource id。新增 `tests/algorithm/test_optimizer_vns_sa_local_search_contract.py` 并登记 test registry；验证覆盖 current/best 分离、非改进接受不制造 improved、best 真改善、SA 确定性、VNS 切换、public 边界。边界：未做 ALNS destroy/repair/selection/weight update。
- 2026-06-29：按基准复核和用户拍板重排后续路线：新增 `graph-ready-local-search-contract` 与 `graph-ready-priority-tuning`，把工序图就绪队列派工局部搜索、图权重比较、统一自动选择、基准门禁和长跑证据排在前面；原自适应大邻域拆修搜索四项继续保留为 planned，顺序排到工序图闭环之后。同步新增 4.6 `GraphReadyOptimizationProfile` 合同，并把 public/diagnostics 分层编号顺延为 4.9。
- 2026-06-29：路线图补强。吸收 4 个只读子代理审查和 Exa MCP 补强调研结论：① 4.6 补 `GraphReadyOptimizationProfile` 必填上下文字段、默认 9 组图权重表和统一自动选择规则；② 新增 4.10 基准门禁矩阵，明确轻 / 中 / 长门禁、ratchet snapshot 字段、FJSP makespan 仅作技术参考、SMTWT 只证明 `min_overdue.overdue_count`、换型目标需要 SDST 类基准；③ 新增 4.11 工序图到拆修搜索桥接合同；④ 子 feature 增加 `alns-graph-ready-bridge-contract`，原拆修搜索四项后移；⑤ 第 9-13 项备注补足字段校验、权重、自动选择、门禁阈值和长跑证据格式。
- 2026-06-29：按 GraphReady v1 未赢 GRASP/IG / `atc` 局搜的复盘结果，新增 GraphReady v2 阶段（item 14-21），并把 ALNS 后移到 item 22-28。v2 阶段要求先采集修改前多算法基准，再实现目标感知特征、瓶颈资源分、候选家族、elite 轻量修补和组合池接入；修改后必须和当前基准、`local_search`、GRASP/IG、GraphReady v1 做同 case / seed / time budget / objective 的胜平负对比；`portfolio_all` 只作为事后上界报告差距和来源，不能纳入同预算普通胜负。同步新增 4.6.1 v2 合同、4.10 多算法对比口径、修正文档中 9-13 的 done 状态，并落盘下一轮执行提示词 `drafts/graph-ready-v2-next-agent-prompt.md`。
- 2026-06-29：对“算法方向 -> roadmap 阶段归属”做 3 路子代理对抗审查后，只新增确认未被完整覆盖的项：`benchmark-reference-diagnostics-baseline` 作为 GraphReady v2 修改前基准的前置量尺，`alns-domain-neighborhood-operators` 作为 ALNS repair 链后的联合机器-排序 / 关键块 N5 / 移动瓶颈算子项，`alns-setup-aware-neighborhoods` 作为换型基准到位后的 setup-aware 邻域项。确认不新增泛化 no-op / 恒 0 改进诊断，因为 item 3/5/7/8 和 §7 已覆盖；GP 超启发式只进观察项，不进主线 items。
