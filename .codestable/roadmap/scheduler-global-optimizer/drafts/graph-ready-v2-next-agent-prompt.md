# 下一轮 Agent 提示词：GraphReady v2 前置量尺、目标感知候选与多算法对比

你是接手 `/Users/lurenxing/GitHub/----` 的下一轮实现 Agent。请默认使用简体中文，遵守仓库 `AGENTS.md` 和 CodeStable 工作流。你的任务是按 `.codestable/roadmap/scheduler-global-optimizer/` 里的最新路线图，推进 `benchmark-reference-diagnostics-baseline` 和 GraphReady v2。不要直接从算法公式开改，必须先补齐“同目标参考量尺 / 不可比诊断 / 换型基准准备”这个前置 item，再建立“修改前”多算法基准，再实现，再和基准及其他算法比较。

## 0. 启动必读

先读：

- `.codestable/attention.md`
- `.codestable/reference/system-overview.md`
- `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-roadmap.md`
- `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-items.yaml`
- `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json`

再看当前现场：

```bash
git status --short
```

当前工作区大概率已有大量未提交改动。不要回退、清理或覆盖用户已有改动。只改你本轮明确负责的文件。

路线图推进顺序以 `scheduler-global-optimizer-items.yaml` 的 `depends_on` 为准，不要只按旧编号记忆推进。当前 GraphReady v2 的多算法基准 item 已依赖 `benchmark-reference-diagnostics-baseline`。

## 1. 本轮目标

把 `graph_ready` 从“9 组固定图结构权重排序器”升级为“目标函数感知候选生成器”，但不要让它独立替代其他算法。最终目标是：

- 先完成 `benchmark-reference-diagnostics-baseline`，给 GraphReady v2 多算法比较补同目标参考量尺、不可比诊断和换型基准准备口径。
- v2 能生成目标感知候选。
- v2 能和 greedy、local_search、GRASP/IG、graph_ready v1、portfolio_all 同台比较。
- 修改完成后，必须明确回答：
  - 前置量尺里哪些 reference 可比，哪些 reference 不可比，原因是什么？
  - v2 比现在的基准提升多少？
  - v2 比 local_search 强多少？
  - v2 比 GRASP/IG 强多少？
  - v2 是否真的贡献了 portfolio_all 的最终最优？
  - 哪些 case 赢，哪些 case 输，哪些 case 只是持平？

## 1.1 执行纪律：追求更接近全局最优，不做最小演示

本轮不是“让一个小样本看起来赢一次”的最小实现。目标是把 `graph_ready` 的候选空间、目标函数特征、真实 SGS 解码择优、多算法对比和门禁证据一起做扎实，让它在当前 APS 约束下更接近全局最优。

这里的“全局最优”必须诚实：

- tiny case：能枚举或有 exact/oracle 的样例，要用同目标证明是否达到最优。
- 中大 case：不能承诺数学全局最优，只能在同一目标、同一数据、同一 seed、同一时间预算下报告 gap、胜 / 平 / 负、均值、最差退步和不劣化。
- 实现取向：宁可把候选生成、目标特征、瓶颈分和 benchmark 比较做完整，也不要只写一个刚好通过当前 4 工序样本的特殊规则。
- 不允许把 `portfolio_all`、local_search、GRASP/IG 的收益偷归因给 `graph_ready`；必须用 `best_origin` / `candidate_origin` 说清楚真正是谁赢。

## 1.2 执行纪律：不要过度防御、过度兜底、静默吞错

不要用“兜底成 0”“异常后继续当成功”“缺字段时退回旧逻辑”来制造假绿灯。合理做法是把问题暴露出来，让候选被拒绝、跳过或直接失败。

硬要求：

- 缺必要特征、非法权重、非法 score、非法候选、repair 失败：必须 `candidate_rejected`、`skipped` 或 fail-loud。
- 不能用 `.get(..., 0.0)` 这类默认值把生产缺字段变成“看似正常但特征失效”。
- 展示层、诊断层可以为了页面不崩做只读容错，但必须明确标注“不参与采纳 / 不参与证明 / 仅诊断”，不能混进正式择优链。
- 如果某个异常理论上不该发生，要么用合同测试锁住，要么 fail-loud；不要写大范围 `except Exception` 继续返回旧方案。
- 不要绕开正式 SGS，不要直接写 `ScheduleResult` 的开始 / 结束时间来伪造更优排程。

## 1.3 执行纪律：接近门禁上限就拆，不要躲

本仓库有文件长度和复杂度门禁。不要为了躲门禁把逻辑压成难读的一团，也不要靠合并语句、嵌套条件、超长函数来“刚好过线”。

硬要求：

- 文件接近 500 行时，按职责拆模块。
- 函数复杂度接近 15 时，按判断分支拆小函数。
- 拆分优先按真实职责来：候选生成、特征计算、瓶颈资源分、SGS 解码、择优报告、benchmark 对比分开。
- 测试也跟着职责走，不要把所有 case 堆进一个巨型测试函数。
- 拆分不是为了“看起来架构高级”，而是为了让下一轮能看懂、能测、能继续改。

## 1.4 调研链要求：静态分析 + 动态验证闭环

动手前必须先把调用链和真实运行路径查清楚。只看一两个文件不够，必须同时做静态分析和动态验证。

静态分析至少跑：

```bash
python3 -m tools.symbol_locator whereis run_graph_ready_candidates
python3 -m tools.symbol_locator callers run_graph_ready_candidates --deep
python3 -m tools.symbol_locator callees run_graph_ready_candidates --deep
python3 -m tools.symbol_locator whereis graph_node_metrics_by_op_id
python3 -m tools.symbol_locator callers graph_node_metrics_by_op_id --deep
python3 -m tools.symbol_locator callees graph_node_metrics_by_op_id --deep
rg -n "bottleneck_machine_score|due_pressure|saveability|objective_score|candidate_origin|distinct_candidates" core tests
```

动态验证至少做到：

- 修改前先完成 `benchmark-reference-diagnostics-baseline`，再跑多算法基准，保存当前 `graph_ready v1`、local_search、GRASP/IG、portfolio_all 的同台结果。
- 修改后用同一批 case、同一 seed、同一时间预算复跑，直接和修改前表格比。
- 必须证明真实路径触发：可以用最小复现、计数、测试断言、benchmark 输出或诊断字段证明候选确实经过 `run_graph_ready_candidates -> 正式 SGS -> 统一择优`。
- 如果某个脚本或门禁不存在，本轮要补齐；不能因为脚本不存在就跳过多算法比较。
- 需要并行核查时可以调用 subagent，但子代理输出必须带 `file:line`；证据不足就写“证据不足”，不能把猜测写成结论。

## 2. 必须按路线图 item 顺序推进

### 前置 item：`benchmark-reference-diagnostics-baseline`

先做这个前置量尺。不要跳过它直接进入 `graph-ready-v2-comparison-baseline-contract`。

要求：

- 补同目标参考下界和诊断字段，让后续多算法比较能区分“真的没改进”和“拿了不可比 reference 硬比”。
- Jackson 单机抢占参考下界只在同目标、同指标、同数据口径可声明时进入 gap 计算；否则必须标成 `not_comparable`，不能拿它证明 APS 的 `min_overdue` 最优。
- 换型基准只做准备口径：定义 WTSDS / Cicirello / SDST 基准的装载、评分、脱敏、标准输出和 `ignored` 规则。不要在本轮下载、提交或伪造 tracked 数据。
- 不重复 item 3 / item 5 / item 7 / item 8 已有的 `noop`、`no_improvement`、`same_fingerprint`、`improved` 合同；本 item 的重点是“reference 是否可比”和“换型基准如何进入比较矩阵”。
- 输出必须能被 item 14 消费，至少包含：
  - `reference_type`
  - `bound_metric`
  - `objective_metric_keys`
  - `comparison_scope`
  - `not_comparable_reason`
  - `changeover_baseline_status`
  - `diagnostics_ref`

### item 14：`graph-ready-v2-comparison-baseline-contract`

前置量尺通过后，再做多算法同台比较基准。不要先改算法。

要求：

- 新增或扩展一个 compare 脚本，建议形态：

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py \
  --profiles greedy,local_search,grasp_ig,graph_ready_v1,portfolio_all \
  --seeds 10 \
  --no-write
```

- 同一 case、同一 seed、同一 time budget、同一 objective 下比较。
- compare 结果必须消费 `benchmark-reference-diagnostics-baseline` 的输出，明确哪些 reference 可比、哪些 `not_comparable`、换型基准当前是 `loaded`、`ignored` 还是 `not_available`。
- ratchet key 至少包含：
  - `case_group`
  - `case_slug`
  - `algorithm_profile`
  - `algorithm_version`
  - `seed`
- 当前只用 `case_group + case_slug` 的比较键不能承载多算法比较，必须修。
- 每行结果至少记录：
  - `objective_score`
  - `failed_ops`
  - `runtime_ms`
  - `evaluated_candidates`
  - `distinct_candidates`
  - `accepted_candidates`
  - `candidate_rejections`
  - `best_origin`
  - 安全的 `best_order` 或顺序摘要
  - `comparison_to_current_baseline`
  - `comparison_to_graph_ready_v1`
  - `comparison_to_portfolio_best`

注意：`.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json` 里有 `dirty_worktree=true`，只能当当前工作区参考快照，不能说成 clean proof。

### item 15：`graph-ready-v2-objective-feature-contract`

实现目标感知特征。`min_overdue` 的第一优先级是减少超期批次数，所以特征要能表达：

- 这个批次是否还救得回来。
- 提前它能不能少一个超期批次。
- 剩余工时短的批次是否更值得先救。
- 已经很难救的长尾批次是否应该后置。

正式比较必须使用完整 `objective_score` 字典序：

1. 超期批次数。
2. 加权拖期。
3. 总拖期。
4. makespan。
5. 换型。

GraphReady v2 的特征只能用于生成候选，不能绕过正式 SGS 解码，不能用 makespan 或单个启发式分数冒充 `min_overdue` 全目标。

至少实现：

- `due_pressure`
- `slack_hours`
- `remaining_work_hours`
- `saveability`
- `processing_time_rank`
- `sacrifice_penalty`

缺必要特征时不能静默退回 v1 成功，必须 `skipped`、`candidate_rejected` 或 strict fail-loud。

### item 16：`graph-ready-v2-bottleneck-resource-score`

重算瓶颈资源分，不要继续简单按“能跑瓶颈机”给高分。

要求实现或明确设计：

- 残余容量：考虑日历、停机、冻结、已排片段。
- 分摊负荷：柔性工序不要把全部负荷算到每台候选机器。
- 最小候选负荷：如果工序能去空闲机器，就不能因为它也能去瓶颈机而误判为瓶颈紧急。
- 灵活性降权：可选机器越多，瓶颈紧迫性越低。
- 交期门控：交期不紧或不可救时，瓶颈分只能作为 tie-break。
- 拆分 `bottleneck_on` 和 `bottleneck_release`。

### item 17：`graph-ready-v2-candidate-portfolio`

新增候选家族，不要只把旧 9 组图权重扩成更多组。

候选家族至少覆盖：

- 旧 9 组图权重，作为 v1 对照。
- EDD。
- SPT。
- 最小松弛时间。
- 关键比率。
- ATC-like。
- 可救批次优先。
- 长尾牺牲。
- 图 + 交期混合。
- 瓶颈 + 交期门控。
- 小扰动候选。

EDD、最小松弛时间、关键比率、ATC-like 不能只停留在名字。每个候选家族都必须写清楚：

- 输入字段。
- 计算公式。
- 同分规则。
- 缺字段时的 `skipped` / `candidate_rejected` 原因。
- 公式版本，并把版本写进 diagnostics，避免以后结果对不上。

不要写死当前 4 工序样本的 `[2,3,4,1]`。本质是“保护更多可准交批次，必要时牺牲长尾”，不是“永远中工时优先”。

### item 18：`graph-ready-v2-elite-local-repair`

只对前 K 个候选做轻量修补。

建议邻域：

- adjacent ready swap
- single insert
- tardy boundary move

硬限制：

- 只跑 top-K。
- 每个候选限制 `max_neighbors_per_elite`。
- 有 `time_budget_ms`。
- 只接受真实 SGS 解码后 objective 严格更优。
- 报告必须分清：
  - `graph_ready_v2_no_repair`
  - `graph_ready_v2_with_repair`

### item 19：`graph-ready-v2-portfolio-integration`

v2 只作为候选来源之一，不独立替代 GRASP/IG 或 VNS/SA。

最终统一比较：

```text
greedy
local_search
GRASP/IG
graph_ready_v1
graph_ready_v2_no_repair
graph_ready_v2_with_repair
portfolio_all
```

报告要区分：

- `graph_ready_generated_best`
- `graph_ready_repaired_best`
- `graph_ready_seeded_other_best`
- `graph_ready_not_in_best_path`

### item 20：`graph-ready-v2-comparative-ratchet-gate`

修改完成后必须跑对比，不只跑单测。

至少跑：

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --check-baseline
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_long_run.py --seeds 10 --no-write
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_medium_gate.py --run
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py \
  --profiles greedy,local_search,grasp_ig,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all \
  --seeds 10 \
  --check-baseline
```

如果某脚本还不存在，要在本轮实现。

报告必须给表格：

| 算法 | case 数 | 赢 | 平 | 输 | 平均 objective 变化 | 最差退步 | runtime | 备注 |
|---|---:|---:|---:|---:|---:|---:|---:|---|

尤其要单列：

- v2 vs 当前基准
- v2 vs graph_ready_v1
- v2 vs local_search
- v2 vs GRASP/IG
- v2 vs portfolio_all

## 3. 验收红线

- 不能跳过 `benchmark-reference-diagnostics-baseline` 直接做 item 14。
- 不能把不可比下界或换型基准准备项说成“已经证明目标最优”。
- 不能只说“赢 greedy”。
- 不能拿 FJSP makespan 证明 APS 的 `min_overdue` 全目标最优。
- 不能把 dirty worktree 结果说成 clean proof。
- 不能把同一 output fingerprint 的重复候选算成多个 distinct。
- 不能把 `portfolio_all` 的收益全部归功给 graph_ready。
- 不能静默吞掉缺字段、非法特征、非法权重或 repair 失败。
- 不能引入不兼容 Python 3.8 / Win7 离线交付的依赖。
- 不能在本轮顺手实现自适应大邻域搜索（ALNS）、N5 关键块、移动瓶颈、setup-aware 邻域或 GP 超启发式；这些已经在路线图里后置或只列为观察项。

## 4. 推荐先读的代码入口

先用定位工具：

```bash
python3 -m tools.symbol_locator whereis run_graph_ready_candidates
python3 -m tools.symbol_locator callers run_graph_ready_candidates --deep
python3 -m tools.symbol_locator callees run_graph_ready_candidates --deep
python3 -m tools.symbol_locator whereis graph_node_metrics_by_op_id
python3 -m tools.symbol_locator callers graph_node_metrics_by_op_id --deep
python3 -m tools.symbol_locator callees graph_node_metrics_by_op_id --deep
rg -n "bottleneck_machine_score|due_pressure|saveability|objective_score|candidate_origin|distinct_candidates" core tests
rg -n "BenchmarkReference|not_comparable|changeover|same_fingerprint|no_improvement|benchmark-reference-diagnostics-baseline" .codestable core tests
```

再重点看：

- `core/services/scheduler/run/optimizer_graph_ready.py`
- `core/services/scheduler/run/optimizer_graph_ready_candidates.py`
- `core/services/scheduler/run/optimizer_graph_ready_profiles.py`
- `core/services/scheduler/run/optimizer_graph_ready_context.py`
- `core/services/scheduler/run/schedule_graph_score_projection.py`
- `core/services/scheduler/graph/metrics.py`
- `core/services/scheduler/run/optimizer_grasp_ig_candidates.py`
- `core/services/scheduler/run/optimizer_local_search.py`
- `tests/_support/optimizer_graph_ready_benchmark.py`
- `tests/_support/optimizer_benchmark_ratchet.py`
- `tests/_scripts_e2e/benchmark_optimizer_ratchet.py`
- `tests/_scripts_e2e/benchmark_optimizer_medium_gate.py`
- `tests/_scripts_e2e/benchmark_optimizer_long_run.py`

## 5. 最终交付

最终答复要包含：

- 改了哪些文件。
- `benchmark-reference-diagnostics-baseline` 的输出是什么。
- 哪些 reference 可比，哪些 reference 不可比，原因是什么。
- 换型基准准备状态是什么，是否产生 tracked evidence；默认不应写 tracked 外部数据。
- item 14 是否已经消费前置量尺输出。
- 新增了哪些候选特征和候选家族。
- 修改前基准是什么。
- 修改后和当前基准比提升多少。
- 和 `local_search`、GRASP/IG、v1、`portfolio_all` 各自比强多少。
- 哪些 case 退步，为什么可接受或需要继续修。
- 跑了哪些测试和 benchmark。
- 如果没法跑完整门禁，明确写原因，不要包装成已完成。
