---
doc_type: issue-fix
issue: 2026-06-29-scheduler-optimizer-actuator-misplacement
path: standard
fix_date: 2026-06-29
related: [scheduler-optimizer-actuator-misplacement-analysis.md, ../../audits/2026-06-29-scheduler-optimizer-actuator-misplacement/index.md]
tags: [scheduler, optimizer, local-search, sgs, graph-ready, benchmark]
---

# 排产优化器作用点错位修复记录

## 1. 实际采用方案

采用 analysis 里推荐的 A + C + B:

- A: 给 SGS 局搜增加专属邻域 `sgs_dispatch_rule`,不再让 SGS 局搜继续拧 `batch_order` 这个弱旋钮。候选会在 `slack`、`cr`、`atc` 等合法派工规则之间切换,并把候选规则真实传给 `GreedyScheduler.schedule`。
- C: 图 ready 路径不再承接旧批次顺序邻域。`graph_ready_context` 存在时,GRASP/IG 和 local search 都明确记录 `graph_ready_requires_graph_neighborhood` 跳过。
- B: GRASP/IG 的批次顺序候选改用 `batch_order` 解码,不再硬编码成 `sgs` 解码。

额外沿用本轮已完成的配套修复:

- threshold / record_to_record 对 `failed_ops` 变差零容忍。
- `positive_count` 不再裸吞所有异常。
- `resource_alternative` 没有真实 rank 变化时返回 noop。
- GRASP/IG candidate specs 在完整解码前先按决策去重。

## 2. 改动文件清单

- `core/services/scheduler/run/optimizer_neighborhood_moves.py`:新增 `SGS_DISPATCH_RULE`、`DEFAULT_SGS_DISPATCH_RULES` 和 `sgs_dispatch_rule_move`;`NeighborhoodMove` 可携带候选派工模式和派工规则。
- `core/services/scheduler/run/optimizer_neighborhood_registry.py`:注册 SGS 派工规则邻域,并把当前规则、合法规则列表传入 move 生成器。
- `core/services/scheduler/run/optimizer_local_search.py`:SGS 路径使用 `sgs_dispatch_rule`;候选解码时用 move 自带的派工模式/规则;图 ready 路径明确跳过旧局搜邻域;接受候选后刷新 current 的策略、参数和派工状态。
- `core/services/scheduler/run/optimizer_local_search_candidate_eval.py`:候选 mutable scope 记录派工模式/规则变更。
- `core/services/scheduler/run/optimizer_grasp_ig_candidates.py`:GRASP/IG 批次顺序候选改用 `batch_order` 解码;图 ready 路径跳过;候选去重指纹纳入 dispatch mode。
- `core/services/scheduler/run/schedule_optimizer.py`:总入口把 `batch_order_enabled`、`candidate_dispatch_mode` 和合法 dispatch rules 传入候选阶段/局搜阶段。
- `tests/algorithm/test_optimizer_business_neighborhood_registry_contract.py`:补 SGS 派工规则邻域合同和报告断言。
- `tests/algorithm/test_optimizer_vns_sa_local_search_contract.py`:补 SGS 真实 GreedyScheduler 局搜改善、batch_order 路径改善、图 ready 跳过测试。
- `tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py`:补 GRASP/IG 批次顺序解码、真实 GreedyScheduler 改善、图 ready 跳过测试。
- `tests/algorithm/test_optimizer_local_search_neighbor_dedup.py`:把原本关注批次顺序邻域的去重/拒绝测试显式限定到 `batch_order` 路径。
- `tests/_scripts_e2e/benchmark_smtwt_localsearch.py`:更新 Benchmark 描述和格式,反映 SGS 现在使用专属邻域。
- `.codestable/audits/2026-06-29-scheduler-optimizer-actuator-misplacement/index.md`:记录修复后 Benchmark 和状态。
- `.codestable/issues/2026-06-29-scheduler-optimizer-actuator-misplacement/scheduler-optimizer-actuator-misplacement-analysis.md`:状态改为 confirmed。

## 3. 验证结果

- 定向回归测试:
  - `python3 -m pytest tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py tests/algorithm/test_optimizer_business_neighborhood_registry_contract.py tests/algorithm/test_optimizer_vns_sa_local_search_contract.py tests/algorithm/test_optimizer_local_search_neighbor_dedup.py tests/algorithm/test_optimizer_candidate_fingerprint_contract.py tests/algorithm/test_optimizer_search_report_contract.py tests/algorithm/test_optimizer_candidate_profile_contract.py tests/algorithm/test_optimizer_build_order_once_per_strategy.py -q`
  - 结果: 98 passed。
- 代码检查:
  - `python3 -m ruff check ...`
  - 结果: passed。
- 空白检查:
  - `git diff --check ...`
  - 结果: passed。
- actuator 探针:
  - `python3 tests/_scripts_e2e/probe_localsearch_actuator.py`
  - 结果:仍确认原事实: `batch_order` 在 batch_order 派工下有效,在 SGS 下仍是死键。这说明本修复没有继续强拧错旋钮,而是改走 SGS 专属派工规则旋钮。
- Benchmark 全跑:
  - `python3 tests/_scripts_e2e/benchmark_optimizer_proof_harness.py`:passed,1 个 tiny oracle 用例 objective score 匹配。
  - `python3 tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py`:passed,报告写入 `evidence/Benchmark/sgs_large_resource_pool_report.md`。
  - `python3 tests/_scripts_e2e/benchmark_fjsp.py`:passed,15 runs / 15 valid,报告写入 `evidence/Benchmark/fjsp_benchmark_report.md`。
  - `python3 tests/_scripts_e2e/benchmark_smtwt_localsearch.py`:passed。修复后 SGS 合计 250 实例改进 209 个(83.6%),gap 16.16 -> 6.82,平均缩小 9.33;batch_order 合计 250 实例改进 165 个(66.0%),gap 15.40 -> 10.38,平均缩小 5.02。
- 质量门禁:
  - `.venv/bin/python scripts/run_quality_gate.py`
  - 结果:未形成 clean proof。门禁在启动阶段因当前 dirty worktree 阻塞,报错为 `dirty worktree ... untracked source files: tools/scan_import_cycles.py`。这是工作区状态限制,不是本次测试或 Benchmark 失败。

## 4. 遗留事项

- 本 issue 的 P0/P1/P5 blocker 已关闭。
- 图 ready 如果后续也要做局搜优化,需要另开图语义邻域需求,例如作用在图 ready 排序权重或关键路径节点优先级上,不要复用 `batch_order` 邻域。
- 当前工作区仍包含多组既有未提交/未跟踪文件,所以不能宣称 clean-worktree proof。
