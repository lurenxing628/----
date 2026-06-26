---
doc_type: feature-ff-note
feature: optimizer-proof-harness
status: completed
summary: "为非 OR-Tools 全局优化路线建立 tiny oracle、BenchmarkReference 合同和默认不落盘的 proof check 脚本。"
tags: [scheduler, optimizer, benchmark, proof-harness, python38, win7]
roadmap: scheduler-global-optimizer
roadmap_item: optimizer-proof-harness
---

# optimizer-proof-harness fastforward note

## 背景

本轮执行 `scheduler-global-optimizer` roadmap 第 1 项：`optimizer-proof-harness`。

目标不是实现新搜索算法，而是先补“怎么证明更好”的地基：

- tiny case 用纯 Python exact oracle 穷举同模型可行顺序。
- 证明口径绑定 `objective_name`、`objective_metric_keys`、`bound_metric`、`bound_scope` 和 `bound_is_objective_comparable`。
- makespan 下界只作为 `makespan_lower_bound_*` 参考字段，不能拿来证明 `min_overdue` 等业务目标。
- FJSP 折叠样本明确标记为 `folded_not_comparable`，只能参考，不能证明 APS 多目标全局最优。
- 默认 check 只输出 stdout JSON，不改写 `evidence/Benchmark`；只有显式 `--write-report` 才写 tracked Markdown。

## 改动范围

- 新增 `core/services/scheduler/run/optimizer_proof_harness.py`
  - `BenchmarkReference` 合同校验。
  - tiny exact oracle。
  - makespan lower bound 参考计算。
  - FJSP folded reference 构造。
  - public payload 脱敏检查。
- 新增 `tests/_scripts_e2e/benchmark_optimizer_proof_harness.py`
  - 默认 stdout JSON。
  - `--write-report` 显式写报告。
- 新增 `tests/algorithm/test_optimizer_proof_harness_contract.py`
  - 锁 tiny oracle 引用合同。
  - 锁 FJSP folded 不可比口径。
  - 锁 public 输出不含内部 id。
  - 锁默认脚本不写 tracked evidence。
- 更新质量门禁注册表：
  - `tools/test_registry_data.py`
  - `tools/test_registry_groups_scheduler.py`
- 回写 roadmap：
  - `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-items.yaml`
  - `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-roadmap.md`

## 验证

- `.venv/bin/python -m pytest -q tests/algorithm/test_optimizer_proof_harness_contract.py`
- `.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_proof_harness.py`

## 后续补强：same-model 解码器等价守卫

初版只在字段层声明 `bound_scope="same_model"`，但 oracle 的 `_decode_sequence` 与生产 `GreedyScheduler` 是两份独立解码实现，仅在退化默认 case 上效果等价；一旦喂进非退化 case（多机资源空洞 / 真实日历 / unit·quantity / 多 seq），两解码器可能分叉，使 `proven_optimal` / `gap_to_oracle_pct==0` 变成两把尺子量出来的假相等。现有 `gap/match` 检查无法区分“greedy 次优”与“两把尺子”，反而会误判或放假阳。

补强：`optimizer_proof_oracle.assert_oracle_decoder_matches_greedy` 在 `build_tiny_case_reference` 跑 greedy 后立即执行 fail-loud 守卫——把 greedy 的结果**按 start_time 排序**重放给 `_decode_sequence`，要求逐 op `(start_time, end_time, machine_id, operator_id)` 完全一致，否则抛 `ValidationError(field="oracle_decoder_parity")`，禁止声称证明。

为什么按 start_time 排序而不是派工顺序：greedy/SGS 的派工顺序 ≠ 最终开始时间顺序（后派工序可经 `bisect.insort` 占用段 + 重叠才推迟的逻辑回填进更早空洞，见 `downtime.py:17`、`internal_slot.py:294/312`）。但 start_time 序是最终排程的一个**合法拓扑序**,水位线解码器按此序处理即可复现任何“各 op 起始=其约束水位线最大值”的排程，**与派工顺序、是否回填无关**；复现不出才说明两解码器是两把尺子。

口径要诚实，不要 overclaim：这是**对“所报告的 greedy 排程在 oracle 模型下可复现”的每次运行强制校验**，关掉了最可能的静默分叉（两解码器对同一条排程算出不同时间），与“下界≤实测”那条 fail-loud 对称。但它**不是完整的模型等价证明**——只认证 greedy 自身那条排程，未覆盖 oracle 枚举到的其它序列（尤其 oracle 认为最优的那条在 greedy 真实模型下是否更差）。完整等价仍须让 oracle 复用 greedy 解码器（见“明确未做”）。回归测试锁两端：退化 case 守卫为 no-op；篡改一条 result 即被拦截。

## 明确未做

- 未实现 GRASP / IG / VNS / SA / ALNS。
- 未给 optimizer 主链增加 `OptimizationSearchReport`；该项属于后续 `optimizer-search-report-contract`。
- 未修复现有诊断页 public/diagnostics 泄漏；该项属于下一轮 `diagnostic-public-id-boundary-fix`。
- 未让 oracle 复用 `estimate_internal_slot` 真正合一解码器；当前用 fail-loud 守卫兜住 same-model，等引入非退化 case 时再评估是否合并解码路径。
