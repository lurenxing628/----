---
doc_type: feature-acceptance
feature: graph-ready-elite-repair
status: accepted
summary: 最小生产 elite repair 已接入正式 phase，146 项局部测试通过；多 seed 有收益也有持平，不是 clean proof
tags: [scheduler, graph-ready, elite-repair, dirty-proof]
---

# 结论与范围

本轮授权的最小生产 repair 已实现，不再仅存在于 benchmark。默认生产 v2 使用 top3、每 elite 最多8个邻居；候选总预算沿用 max_candidate_profiles=60，并扣除已启动 profile 数。实际剩余时间与可选内部 time_budget_ms 取小值。SGS 前再次检查 deadline；构造已耗尽预算时不启动解码。已启动 SGS 不抢占，单次超时如实报告。

所有 repair 候选走 `evaluate_graph_ready_candidate -> schedule_fn/SGS -> compute_metrics -> objective_score -> CandidateFingerprint -> candidate_is_preferred + improve_only acceptance`。仅改变 batch priority 决策；不直接创建可变工序时间。固定 seed、前后置和资源参数原样交 SGS。拒绝、预算跳过和解码前去重分开；没有改进不冒充成功。

公开投影无需额外改文件：安全中文计数进入既有 `profile.message`；完整阶段报告同时进入 `candidate_profile.graph_ready_optimization.elite_repair` 和原有 `diagnostics.attempts`。测试实际调用 `project_search_report`，验证摘要保留且不泄漏内部 ID、指纹 hash 或 trace。

# 修改文件

以下路径均相对 `/Users/lurenxing/GitHub/----`：

- `core/services/scheduler/run/optimizer_graph_ready.py`：生产 profile 搜索尾部接 repair，复用一个正式 evaluator；原有 per-candidate runtime 修复保留。
- `core/services/scheduler/run/optimizer_graph_ready_candidates.py`：显式 repair order、来源校验、SGS 启动前预算回调；原有 metrics 调用兼容签名保留。
- `core/services/scheduler/run/optimizer_graph_ready_reporting.py`：安全中文摘要。
- 新 `optimizer_graph_ready_repair.py`：top-K、正式解码、真实输出去重、严格接受和阶段统计。
- 新 `optimizer_graph_ready_repair_contract.py`：最小内部预算与报告字段。
- 新 `optimizer_graph_ready_repair_neighbors.py`：确定性有限 swap/风险批次 insert/延期边界 move；仅优先级决策。
- 新 `tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py`、`test_optimizer_graph_ready_v2_elite_repair_neighbors.py`：新增边界和真实 SGS 合同。
- 新 `tests/_support/optimizer_graph_ready_repair_benchmark.py`：复用 tiny、SMTWT 既有数据/构造器，真实时钟配对比较。
- `tests/_support/optimizer_graph_ready_v2_benchmark.py`：删除原独立 repair 脚手架，no-repair/with-repair 都走生产 phase。
- `tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`：仅把两条旧 scope 断言改成 production_core，既有 dirty 保留。
- 本 feature 的 design/checklist/acceptance。

# 验证

环境：`.venv/bin/python --version` 为 **Python 3.8.10**。测试命令：

```bash
.venv/bin/python -m pytest -q \
  tests/algorithm/test_optimizer_graph_ready_candidate_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_long_run_contract.py \
  tests/algorithm/test_optimizer_graph_ready_runtime_tiebreak_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_neighbors.py \
  tests/algorithm/test_optimizer_candidate_profile_contract.py \
  tests/algorithm/test_graph_ready_v2_zero_quantity_features.py
```

最终结果：**146 passed in 4.42s**。覆盖 top-K/邻居/候选/time/global deadline、构造跨 deadline 不解码、重复 decision 不解码、同输出拒绝（含无可选 report state）、equal/worse 不接受、不可行拒绝、strict/non-strict 异常、真实 fixed seed/前后置保护、真正 strict improvement 的指纹和 acceptance event、实际公开投影边界。

- 对本轮全部 Python 修改运行 ruff check：通过；自动修正只涉及 import 排序。
- 六个修改/新增生产模块运行 `pyright --pythonversion 3.8`：0 errors / 0 warnings。
- 本轮 tracked 文件 `git diff --check`：通过；生产文件均低于500行。
- 未运行长时间全库门禁、未更新 registry/公共 baseline；本轮只能称局部 dirty 验证。

# 同预算实测

最终代码上顺序跑两组 paired comparison。每组 seed 为0..9；每个 seed 的 on/off 使用同数据、同目标 min_overdue、同60个 graph candidate 上限；时间是实际 `perf_counter` 而非模拟时钟。候选预算是上限，不保证双方消耗相同候选数。

| 数据 | 每侧时间上限 | repair 胜/平/负 | 未开/开启平均总耗时 | 未开/开启 graph 解码数 |
| --- | --- | --- | --- | --- |
| 既有4工序 tiny | 1秒 | 0/10/0 | 21.6 / 38.1 ms | 19 / 31或35 |
| 既有 SMTWT wt40_1，40工序 | 2秒 | 10/0/0 | 858.1 / 1705.1 ms | 19 / 43 |

tiny 每个 seed 的完整 score 均为 `(0, 1, 8, 8, 24, 0)`。新增12或16次 repair 解码无收益；生成24个邻居，8或12个 decision 重复在解码前剪掉。预算跳过29或39个邻居，不能理解为已证明无改进。

wt40_1 每个 seed 从 `(0, 6, 12384, 12384, 49560, 0)` 改到 `(0, 5, 22848, 22848, 49560, 0)`。score 顺序是 failed_ops、超期批次数、加权拖期、总拖期、makespan、换型。**超期批次6→5，但拖期小时12384→22848变差**；这是当前 min_overdue 字典序优先减少超期批次的严格改进，不是所有指标都改善。每个 seed 评估24个 repair 邻居，272个预算跳过（含 top-K 未选择精英的邻居）；没有 bound/dominance 剪枝。

最后一次 wt40_1 各 seed 总耗时（关闭/开启，ms）：0=1198/1932，1=839/1679，2=819/1692，3=815/1671，4=819/1692，5=816/1665，6=816/1676，7=823/1681，8=816/1683，9=820/1680。均未越过2秒；环境负载会影响耗时和短预算下能评估的邻居数。

复跑入口：

```python
from tests._support.optimizer_graph_ready_repair_benchmark import repair_comparison, smtwt_repair_context
print(repair_comparison(seeds=10))
print(repair_comparison(seeds=10, case=smtwt_repair_context(), time_budget_seconds=2))
```

另调用既有 `build_graph_ready_v2_long_run(seeds=10, profiles=(greedy, local_search, grasp_ig, graph_ready_v1, graph_ready_v2_no_repair, graph_ready_v2_with_repair, portfolio_all), workers=1)`：status=passed、proof=unbound_dirty_worktree。v2 对 greedy/local_search/v1 是10胜，对 grasp_ig 是5胜5平；这些是既有 tiny 比较量尺，不是本次 repair 新增收益。portfolio_all 保持 posthoc_upper_bound / not_comparable。**其他旧算法行仍使用 BenchmarkClock，故不能把该全矩阵升级成严格真实墙钟同预算性能证明**；本轮真实时钟公平对比只由上表 on/off 两组承担。

# 证明边界与交接

- SMTWT 是单机、无图前后置的标准形状样例；tiny 是既有小样例。不是用户真实业务库，不构成 APS 多机/完整图模型最优性或普遍收益证明。没有写公共比较 baseline。
- 理论邻居数按启用的有限 move descriptor 计数（可能重复）；candidate_space_total 只算已选择 top-K，skipped_neighbors_by_top_k 单独列出，被计入 skipped_by_budget。因此 skipped_by_budget 可以大于 top-K 的 candidate_space_total，不是假 bound proof。
- 保留所有进入本轮前的 dirty；没有编辑主代理的 evaluation.py、schedule_optimizer.py/steps、optimizer_local_search*.py 或保守比较/接受规则。未运行 git add/commit/push。
- A18 评价接线仍留给主代理：当前只用 `compute_metrics(res, batches)`，正式 evaluator 位于 `optimizer_graph_ready_candidates.py`。如果主代理引入完整工序范围参数，应在这一处接入，全部新增候选会统一继承。
- 新测试未登记公共 registry，按写集要求由主代理决定后续登记和本地提交。公共 roadmap 的 item done 状态与整个后端整合门禁也由主代理统一收口。

# 验收核对

| 核对项 | 结论 |
| --- | --- |
| 接口契约 | 通过；repair 来源与显式优先决策一致，正式 evaluator 保持 compute_metrics 兼容调用 |
| 行为与决策 | 通过；严格 score/指纹/接受三条件；移除 phase 的 repair 调用即停止新候选，移除 priority override 则无法实现此邻域，移除报告挂载则失去可观察性，三处挂载已核对 |
| 场景 | 通过上述146项局部测试；前端明确延期，不适用浏览器验收 |
| 术语 | 沿既有 graph_ready_v2_repaired origin 与 roadmap repair/pruning 口径，不新增独立算法名称 |
| 架构归并 | 新职责在现有 GraphReady 命名族内；公共架构文档不在写集，交主代理统一归并 |
| requirement | 无本轮新 req，按用户写集不扩写公共需求档案 |
| roadmap | 未回写，明确由主代理持有；本报告不等于公共 items 已 done |
| attention 候选 | 无新增项目级运行前提，不修改 attention |
| 遗留 | A18 统一评价接线、registry 和整合提交由主代理完成；没有声称全库或 clean-worktree proof |
