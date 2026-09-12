---
doc_type: refactor-apply-notes
refactor: 2026-09-12-graph-preparation-efficiency
---

# 图准备与评分优化执行记录

## 授权范围与方法

用户在算法全面研究后授权实施已研究优化。本记录覆盖 I：精确后继计数扩展性、同次候选对比中的权重无关投影复用、节点联合评分。遵循项目 cs-refactor 行为等价原则；采用 M-L4-01 Memoization、M-L4-02 Batching 和 M-L4-05 Index & Cache。没有改变目标函数、权重语义、派工顺序或错误降级合同。

修改前检查工作区并运行 symbol_locator 定位 build_node_metrics、prepare_schedule_graph_for_dispatch、build_graph_ready_context、build_graph_health_context、graph_priority_key_component、graph_score_bonus 和 build_available_graph_score_projection；另用当前源码 rg 核对调用方。整个任务有其他代理并行修改，以下验证均为当前工作区局部证据，不是 clean-worktree proof。

## 步骤 1：精确后继计数

- 新增 `core/services/scheduler/graph/impact_counts.py`，`metrics.py` 保留原私有调用入口。
- 若全图每个节点最多一个后继，反向动态规划精确计数，时间与空间为 O(N+E)，允许多条链汇合。
- 一般 DAG 按真实弱连通分量使用局部位下标和位集合去重，不按 batch 标签拆图，不将菱形后继简单累加。
- 不使用 Python 3.8 缺少的 `int.bit_count`，不把缺失后继计数回退为零。一般大型连通 DAG 仍有精确位集合的成本，未声称其为线性算法。
- 新测试：`tests/scheduler_graph/test_metrics_impact_components.py`。固定五节点拓扑序的 1,024 个 DAG 全部与 `nx.descendants` 对拍；6,000 节点短链确认不经过位集合；80 个独立菱形最大掩码宽度为 4；坏拓扑、自环、环及缺后继继续显式失败。

## 步骤 2：联合评分

- `scoring.py` 新增 `graph_score_components`：严格合法化一次，联合返回精确整数 bonus 和原浮点排序 key；原有 bonus/key API 保留。
- `schedule_graph_score_projection.py` 一次遍历待排节点填充两张结果映射，诊断样本使用同一个精确 bonus，避免从浮点 key 反推导致大整数丢精度。
- 每个候选仍重新验证指标和权重；非法类型、负值、缺字段继续报错。单独调用 `graph_score_bonus` 不被迫转 float，保持任意大整数的既有行为。

## 步骤 3：候选投影模板复用

- 新增 `schedule_graph_cached_projection.py`，由 `schedule_graph_report.py` 调用；复用既有 comparison-local core_cache 生命周期。
- 同次 comparison 的候选只替换 cfg，工序、批次、资源池、冻结和种子输入保持不变。缓存只用于这一既有作用域，不跨运行使用。
- 健康上下文、ready 邻接/排序/固定来源和首波资源最大匹配只构建一次；模式与 metrics_mode 都进入投影键，防止 report 与未评分 on 共用错误的 ready 状态。
- 私有模板在加入候选 score 前保存。每次返回复制 set、邻接 set、映射、健康列表以及资源匹配的嵌套诊断，避免先返回的候选改变后续候选。
- 匹配合同错误投影不缓存；未知异常继续上抛。单次排产不传缓存。
- 新测试：`tests/scheduler_graph/test_graph_preparation_efficiency.py`。40 个节点、38 个待排节点、5 档权重时，核心分析、健康、ready 和资源匹配各调用一次，指标合法化共 190 次（旧实现为 570 次）；5 档 key 不同。缓存/独立构建结果去除计时字段后逐字段一致。
- 测试还覆盖返回容器污染、report/basic 与 on/basic 模式区别、错误重试、缓存生命周期、缓存命中仍拒绝坏指标/权重，以及大整数精确 bonus。
- 本范围未修改 `core/services/workbench/run_compute_graph.py`；piece 接线由主线程统筹。

## 验证

- Python 3.8.10：`pytest tests/scheduler_graph --ignore=tests/scheduler_graph/test_graph_performance.py -q` → **380 passed in 2.17s**。
- 定点 Ruff 检查上述 6 个产品文件和 2 个新测试文件 → **All checks passed**。
- 限定改动 `git diff --check` 通过。
- 由已有子代理独立定向复核评分与投影缓存，未发现成立问题；对 HEAD 与当前 bonus/key API 的 950 组调用比较返回类型、值、异常类型和消息，全部一致，包含超大整数、负值、bool、float 和缺字段。
- 按主线程分工，没有运行完整质量门禁、没有提交、没有进行大型耗时基准。测试中的规模验证检查工作量路径和准确性，不宣称真实排产总耗时提升比例。
- 两个新测试文件需由主线程统一加入质量门禁注册。
