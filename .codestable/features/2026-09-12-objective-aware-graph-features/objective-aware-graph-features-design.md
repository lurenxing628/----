---
doc_type: feature-design
slug: objective-aware-graph-features
date: 2026-09-12
status: implemented
tags: [scheduler, graph-ready, objective, due-budget]
---

# 正式目标候选与工序交期压力校准

## 范围与授权

用户已授权实施算法优化。本切片只负责 graph profile/feature/candidate 的目标传播、有限候选和多工序交期信号。主线程统一质量矩阵与整仓门禁；修补邻域由并行切片实施。没有提交、发布、依赖升级或生产数据修改。

## 原问题与合同

- `objective_aware_portfolio` 原来不接收正式目标，各目标使用相同的 19 组候选。
- 原特征先将同批所有待排工时求和，再给后道扣除前道的 ready offset。两道 4 小时、毛窗口 8 小时时，后道会同时承担 8 小时总负担和只剩 4 小时的窗口。
- 原按批次序号累加 offset，会把真实 DAG 中可并行的 piece 分支串行相加；批次数量直接用于 piece 工序，与 runtime `operation_batch` 的单件数量不同。
- 合并外协的工作桶必须采用 `(batch_id, piece_id, ext_group_id)` 的实际身份；同一 piece 内组内成员只计一次，不同 piece 不合并。

## 实现

1. `resolve_graph_ready_profiles_and_metrics` 新增有默认值的 `objective_name`、`graph_ready_context`，传至 profile 与 feature 层；旧普通调用保持可用。`before_metrics` 在 profile 配置验证后调用，供主链阻止已耗尽预算下的全量特征构造。未知目标沿正式 `normalize_objective_name` 口径处理。
2. 明确保留两类排序特征：既有 10 个 v2 slug 使用 `feature_basis=batch_workload_v1` 的整批工时排序启发；增强候选使用 `v2_successor_*` slug、`feature_basis=operation_successor_v1` 和独立公式版本。9 个 v1 权重配置与相对顺序保留。固定前缀为 balanced、基础 micro、基础 EDD，随后增强候选/v1/其余基础候选轮转；增强序列按目标将 SPT/min-slack/EDD/ATC、weighted-SPT/ATC 或类型正反分组提前。完整候选池为 29 或 31，上限参数仍由原 `max_candidate_profiles`、解码预算和截止时间约束，没有放宽 1 秒/5 秒/60。
3. 权重与正式评价共用 `PRIORITY_WEIGHT`；换型分组使用正式换型指标的 `op_type_name`。新公式只要求自身字段，旧公式及共用 rank cache 保持可用。缺少新公式需要的字段明确拒绝。
4. `optimizer_graph_ready_workload.py` 按真实 DAG 计算：当前工序及所有可达后继的唯一工作桶之和；ready offset 为前置完成的最长路径。合并桶间先拓扑排序；输入图越界、自环、环与不一致的合并组工时明确拒绝。后继集合使用整数位集，单后继链直接复用子节点负担。
5. 工序工时复用 runtime `operation_batch` 处理 piece 数量。前置释放使用 `ready_date`、seed 完工和毛日历工作时间；不扣机器停机和 seed 资源占用。固定前置有 seed 完工证据时采用该时间，没有未完成证据的 fixed 节点按现行图调度的已完成合同处理。无显式图时仅普通批次按原序号建立线性前置；piece 缺图拒绝，不能猜成串行。
6. `due_deadline_hours` 仍是从排程起点到批次交期；追交预算从本工序预计释放点到交期。内制且有日历时继续使用 `residual_capacity_window_hours` 毛窗口；净残余仍只在资源争用特征中使用。遵守 `.codestable/compound/2026-06-30-due-budget-window-vs-residual/decision.md`。
7. 新 `repair_decision` 在原 evaluator 中调用修补切片提供的 helper，真实 SGS 使用工序副本，正式 `compute_metrics` 仍依据原输入 IDs/工时。输出保留 JSON-safe 决策，工序序与资源选择纳入 mutable scope。结果封装拆到独立模块，避免超过 500 行门禁。
8. 顶层 feature rows 继续保存正确的 successor/calendar 量纲；基础启发另存 `graph_ready_baseline_ordering`，包含自己的 workload version、整批负担和按批序工时累计的 offset。基础工时仍采用当前 piece 数量及外协组身份合同，不恢复错误数量。缺少基础子行时拒绝基础 profile，不能把增强值冒充基础值；rank cache 用独立前缀隔离。修补池也按该 profile 的 feature basis 选择 saveability/sacrifice 等信号；并行 A 切片在原 top_k 内保留各 basis 最佳代表，使更好的增强父解不会抹掉基础父解的邻域机会。

## 边界

- 剩余负担是唯一后继工作量之和；ready offset 是忽略竞争的毛日历前置估计。两者不是完整可行排程或最优完工时间；分支可以并行，跨资源与内外制组合仍须交给真实 SGS 验证。
- 静态类型分组不代表全局最优换型；交期压力和 weighted-SPT/ATC 仅生成候选。真实解码、失败工序数、正式 `objective_score`、解码前去重和采纳规则保持最终裁决权。
- 基础整批工时仅作为保留的排序启发，不声称它是本工序的实际剩余工作量或可行释放时刻。增强特征继续用于新的候选，真实 SGS 决定可行性与质量。
- 组合版本为 `baseline_and_successor_portfolio_v1`；基础公式保留 `graph_ready_v2_objective_features_v2` 标识并明确 batch basis，增强公式使用 `graph_ready_v2_operation_successor_v1`。公开 profile payload 记录 feature basis，不再以同一 slug 静默替换旧排序。
- 新候选可改变受限预算下的探索分配，质量向量不退化结论由主线程相同预算矩阵确认，本切片不将定向测试冒充完整证明。

## 验收场景

- 两道 4 小时后道剩余负担 4 小时、毛窗口 4 小时、critical ratio 为 1；停机使净窗口为 2 时毛预算仍为 4。
- piece 菱形 DAG：共有前道计批数量，piece 计单件，分支不串行累加、汇合后继不重复计量。
- 相同外协组跨 piece 独立、同 piece 组内只计一次；fixed seed 只影响释放不计入待排负担。
- 图环、未知/布尔前置、piece 缺图、坏交期、新公式缺字段均明确拒绝。
- 四目标 profile/feature 元数据贯通，真实 SGS 输出完整，score 精确等于正式 objective_score。
- 加权候选将同长高权重工序前移，类型候选在真实 SGS 小实例把 3 次换型降为 1；这些只证明具体用例。
- 既有 graph 候选、零数量、解码前去重与预算测试回归通过。
- 同一真实 shift_pool 输入和当前 decoder：基础 EDD 父解完整目标向量为 `(0,1536.5,12,3588.5,289.5,0)`，其 `tardy_boundary_move` 仍生成 `(0,1423.5,12,3058.5,294.5,0)`；增强 micro 实际解码为 `(0,1460.5,11,2028,268.5,0)`。这些数值仅锁定已发现的回归路径；产品没有 fixture 分支。
