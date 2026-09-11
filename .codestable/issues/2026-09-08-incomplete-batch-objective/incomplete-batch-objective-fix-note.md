---
doc_type: issue-fix
issue: 2026-09-08-incomplete-batch-objective
path: fast-track
fix_date: 2026-09-08
tags: [A18, evaluation, incomplete-batch, optimizer, objective]
---

# A18 未完成批次评分修复记录

## 授权与现场

- 用户已批准区分完成/部分排产，保留 `failed_ops` 第一比较键及 CR、四个既定目标、`improve_only` 语义；不提交，不改真实 DB，不启动子代理。
- 入场已读 `AGENTS.md`、attention、system-overview 和项目版 cs-issue-fix。已运行 symbol_locator 的 whereis/callers/callees，并以当前源码 `rg compute_metrics` 补齐过期 SCIP 索引漏掉的 GraphReady 调用。
- 工作区入场即有大量 dirty 修改；本轮不撤销或接管。`evaluation.py` 已有 A18 限制注释，本轮将其更新为已实现合同；VNS 测试已有 A01 reset 合同修改，完整保留。

## 根因

旧 `_collect_result_metric_state` 对每批取已排结果的最大 end_time，无法区分真实完成与后续工序失败后的截断结果。`failed_ops` 相同的候选会把少排工序当成拖期、工期或换型改善。summary 已按 failure_details 单独标记未完成风险，不能修正优化器目标比较。

## 精确合同

### 完成性证据

`compute_metrics(results, batches, *, expected_operations, seed_results, failure_details)`：

1. 预期集合为本次真实待排工序与固定种子的 `(batch_id, op_id)` 并集；待排工序支持 `.id`，tiny proof spec 支持 `.op_id`。同一工序的 seed/待排重叠只计一次；同一 ID 跨批次冲突报错。
2. 只有真实返回结果中存在有效起止时间且 `end_time >= start_time` 的对应身份，才满足一项预期。零工时合法。固定/报工已完成种子必须出现在真实输出，不补造结果，也不把已完成工序重新要求排一遍。
3. 外协 merged 只合并时间块，真实调度仍逐工序返回结果；每个成员 ID 都要满足，不能拿一个组成员代表整组。
4. 缺任何预期身份、整批无预期证据、出现预期外结果或有失败明细的批次均标记未完成。失败明细可用已知 op_id 反查批次；身份矛盾、无法归属的明细明确报错，不吞掉。
5. 缺工序不依赖 `summary.failed_ops` 是否漏计。该数仍原样做第一键，不猜造新的失败数或业务处罚。

### 指标与评分

- `overdue_count` / 总拖期 / 加权拖期只累计确认完成的批次；完成批次原有 due_exclusive 边界、优先级权重均不变。未完成批次不产生预测完工日期或估算拖期。
- 工期、资源使用、换型等仍描述真实已排结果。原 `unscheduled_batch_count` 仍指没有结果的批次；已有部分结果的批次另外计入 completion 的 partial 数量。
- `ScheduleMetrics.completion` 和 `to_dict()['completion']` 提供 `objective_defined`、预期/缺失/预期外工序数、完成/未完成/部分批次数、失败数量与批次样本；明确标注 `due_metrics_scope=completed_batches_only` 和 `resource_metrics_scope=scheduled_results_only`。字段中的 0 是已完成批次的小计，绝非未知批次的零拖期预测。
- 方案全部完成时，`objective_score` 按现有注册表原样返回。`min_weighted_tardiness` 仍是四项，不加 overdue_count；其他目标仍五项；前置 `failed_ops` 后长度仍分别为 5 / 6。
- 任一批次未完成时，每个目标分量统一为 `UNKNOWN_OBJECTIVE_VALUE=sys.float_info.max`，长度不变。它是排序用未知哨兵，不写入真实拖期/日期字段，不随时间窗、失败数、优先级或候选集合估算处罚。
- 证明边界：任意有限浮点分量都 <= `sys.float_info.max`，包含负数和最大合法量，因此全哨兵元组不可能严格优于任一完整有限元组；极限完整元组全等于哨兵时允许持平。完整分数含 NaN/Infinity 明确报错。当前仅四个已注册目标，不新增 max_utilization。
- **保守限制：同 failed_ops 的不同不完整候选，目标分量一律持平，即使未完成批次数、完成子集拖期或已排工期不同。** `improve_only` 不会因此认定目标改善。既有候选指纹、来源/耗时等同分规则没有改；目标持平不等于禁止一切同分候选替换。
- 历史两参数接口保留旧结果投影和完整 benchmark helper 的 API。生产优化器所有调用都显式传入预期集合；`expected_operations=[]` 不会退回旧行为。新接口传 seed/failure 却不提供 expected 时明确报错。

### Proof

- actual 和 exact oracle 均使用 tiny case 的全部 operations 评分。
- 解码一致性检查先要求实际工序身份与预期集合严格一一对应，缺失、重复或额外工序不能蒙混通过；actual 有失败数/失败证据或 oracle 输出不完整时，不发布最优证书。
- 不把有限未知哨兵拿去计算最优性 gap，拒绝不完整 proof。完整 tiny reference 的原分数、长度、最优值及 gap 不变。

## 文件范围

- `core/algorithms/evaluation.py`
- `core/algorithms/evaluation_completion.py`（新增，完成性证据与有限哨兵）
- `core/services/scheduler/run/optimizer_local_search_candidate_eval.py`
- `core/services/scheduler/run/optimizer_grasp_ig_candidates.py`
- `core/services/scheduler/run/schedule_optimizer.py`
- `core/services/scheduler/run/schedule_optimizer_steps.py`（multi-start 与 OR-Tools）
- `core/services/scheduler/run/optimizer_proof_harness.py`
- `core/services/scheduler/run/optimizer_proof_oracle.py`
- `tests/algorithm/test_incomplete_batch_metrics_contract.py`（新增）
- `tests/algorithm/test_incomplete_batch_optimizer_contract.py`（新增）
- `tests/algorithm/test_optimizer_vns_sa_local_search_contract.py`（仅补 fixture expected/batches，保持候选工序 ID）
- `tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py`（仅补整场景稳定 ID map 与 expected；任意自定义场景显式提供 map，不依候选顺序/subset 重编 ID）
- `tests/algorithm/test_optimizer_build_order_once_per_strategy.py`（获追加授权，仅将两处无 ID object dummy 换成有身份的工序）
- 本记录与专项测试证据。

禁止编辑的 `optimizer_graph_ready_candidates.py` 由主代理协调所有者接入三个 keyword，本轮没有编辑；新增 AST 合同测试检查全部 8 个产品 compute_metrics 调用。没有编辑 `optimizer_graph_ready.py`、前端、启动打包、台账或注册表。

## 验证与限制

- 初轮旧完整评分/交期/proof/搜索回归 60 项中 56 通过；4 失败来自 fixture 空 expected 却返回工序，不是 non-finite 校验造成。获授权后仅修 fixture，无目标断言修改，原失败项已通过。
- 最终专项回归 **175 passed / 0 failures / 0 errors / 0 skipped**，用时 0.98 秒。`targeted-tests.xml` 记录本次 17 个测试文件的所有节点，时间为 2026-09-08 15:38:24 +08:00；其中两份新文件 71 项，三份定点修 fixture 的文件全通过，原断言未改。
- 175 项包含原 `test_compute_metrics_contract`、priority weight、due_exclusive、horizon、objective projection、tiny proof、局部搜索/GRASP/IG、warmstart、summary incomplete 风险和 invalid due/unscheduled 回归。完整评分 API 和 non-finite fail-loud 变更无遗留专项失败。
- 本轮 13 个 Python 文件 Ruff 通过；8 个产品文件 Pyright 1.1.406 为 0 errors / 0 warnings。使用项目 `scan_complexity_entries`、`scan_oversize_entries` 检查产品文件：复杂度阈值 15、文件阈值 500 行，结果均为空；`git diff --check` 通过。
- 并发现场曾全跑 `tests/algorithm`：996 passed / 28 failed。包含其他代理 GraphReady 预算/预去重、SGS、日历等临时失败及本轮发现的无身份 fixture；这不是最终全量结论。用户要求停止继续全算法目录扫描，最终全量由主代理冻结后统一跑。
- `scripts/run_quality_gate.py --fast-precheck` 在其他并发文件的 16 个 Ruff 问题处失败，本轮文件 Ruff 独立通过。未跑整仓 full gate，不能宣称 clean-worktree proof。
- 全程使用仓库 `.venv/bin/python`（实测 Python 3.8.10）；测试使用内存对象/真实算法与测试临时数据，不读写真实业务 DB。

专项复跑命令（仓库根目录）：

```bash
.venv/bin/python -m pytest -q \
  tests/algorithm/test_incomplete_batch_metrics_contract.py \
  tests/algorithm/test_incomplete_batch_optimizer_contract.py \
  tests/algorithm/test_optimizer_vns_sa_local_search_contract.py \
  tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py \
  tests/algorithm/test_optimizer_build_order_once_per_strategy.py \
  tests/algorithm/test_compute_metrics_contract.py \
  tests/algorithm/test_priority_weight_case_insensitive.py \
  tests/algorithm/test_due_exclusive_consistency.py \
  tests/algorithm/test_metrics_horizon_contract.py \
  tests/algorithm/test_optimizer_proof_harness_contract.py \
  tests/algorithm/test_objective_projection_contract.py \
  tests/algorithm/test_optimizer_business_neighborhood_registry_contract.py \
  tests/algorithm/test_optimizer_local_search_restart_alignment.py \
  tests/algorithm/test_localsearch_batch_order_actuator.py \
  tests/algorithm/test_warmstart_failure_surfaces_degradation.py \
  tests/schedule/summary/test_schedule_summary_incomplete_batches_risk.py \
  tests/schedule/summary/test_schedule_summary_invalid_due_and_unscheduled_counts.py \
  --junitxml=.codestable/issues/2026-09-08-incomplete-batch-objective/targeted-tests.xml
```

## 集成边界

- 用户确认公开投影是 A18 必须完成的集成，**主线程已接管** `core/services/scheduler/contracts/optimizer_public_safety.py` 及对应投影测试；不是可选后续工作。原因是原 `project_public_metrics` 只保留顶层数值，`project_attempt_metrics` 只保留既有目标键，会丢弃嵌套 completion 旗标/计数。本代理收尾不修改这部分、不将主线程尚未提供的验证算成本轮证据。
- 已向主线程交付并冻结安全投影字段：`objective_defined`（严格 bool）；7 个非负整数 `expected_operation_count` / `missing_operation_count` / `unexpected_result_count` / `complete_batch_count` / `incomplete_batch_count` / `partial_batch_count` / `failure_detail_count`。
- 安全枚举：`contract` 仅 `expected_operations_complete_only_v1`；`objective_score_policy` 仅 `original` 或 `unknown_all_components`；`due_metrics_scope` 仅 `completed_batches_only`；`resource_metrics_scope` 仅 `scheduled_results_only`。
- `unknown_objective_value`、`incomplete_batch_ids_sample`、`partial_batch_ids_sample`、`failure_batch_ids_sample` 仅供内部诊断，不公开。
- 旧两参数调用没有预期集合，不能提供新的完成性保证；保持其完整 benchmark 兼容是用户明确选择，不将它当成 completion-aware 证明。
- 不完整候选的同失败数目标持平，是本次明确接受的保守边界，未引入预测模型、欠排惩罚系数或其他业务偏好。

## 主线程最终集成

- `optimizer_public_safety.py` 已在摘要、候选和尝试 metrics 投影中保留上述安全 completion 字段；样本 ID 与内部哨兵不公开。
- 新增 `tests/algorithm/test_incomplete_metrics_public_projection.py`；公开投影及相邻摘要 17 项通过。
- 独立只读复核额外对照 200 组完整方案，四目标原评分均一致；未发现可复现的 A18/R40 回归。
- 最终全仓 5937 项通过，记录见 `evidence/QualityGate/long_gate/backend-2026-09-08/final-pytest.xml`。完整项目门禁仍受既有依赖基线差异阻塞，不是 clean-worktree proof。
