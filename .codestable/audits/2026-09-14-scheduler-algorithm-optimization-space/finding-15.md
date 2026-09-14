---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: maintainability-15
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 15：留痕/接受代码 4–5 份复制且语义漂移；54 个 optimizer_* 平铺压线；指纹五套；proof harness 住生产包；死旋钮

## 速答

五个可维护性子项合并记录（S5 M1–M5）：

1. **留痕与接受四份复制**：attempt/trace/rejected-attempt 构造在 `optimizer_step_report_hooks.py:15-56,174-257`、`optimizer_grasp_ig_candidates.py:113-228`、`optimizer_graph_ready_reporting.py:14-74`、`optimizer_attempt_records.py:21-84` 各一份；接受准则已漂移——ortools/multi_start 用裸 `score >= best`（`step_report_hooks.py:153,245`）无指纹去重与 runtime tie-break，其余阶段用 `candidate_is_preferred`。
2. **平铺与压线**：`run/` 95 文件 / 20,771 行，`optimizer_*` 54 文件 / 11,693 行；`optimizer_grasp_ig_candidates.py` 491、`optimizer_graph_ready.py` 467、`optimizer_graph_ready_candidates.py` 462、`optimizer_graph_ready_v2_capacity.py` 460、`optimizer_proof_contracts.py` 453 均在 500 行门禁的 90–98%；`optimizer_candidate_phases.py` 全文只做 kwargs 转发；`schedule_optimizer_steps.py:19-34` 再导出下划线私有名供 5 个测试 monkeypatch。
3. **指纹五套**：`_spec_decision_fingerprint`（grasp）、`MultiStartDecisionCache.decision_key`、局搜 `move_seen_key/should_skip_seen`、`LocalSearchFingerprintTracker` 与 `OptimizationSearchReportState.mark_candidate_evaluated` 两份 seen/best 簿记、`EliteRepairPool.seen_outputs` 第三份。
4. **proof harness 住生产包**：`optimizer_proof_{cases,contracts,harness,oracle}.py` 共 1139 行，core/web 零引用，15 个测试文件 import。
5. **残留与死旋钮**：`optimizer_graph_ready_v2_features.py:96 due_date_state` 赋值未读、`:290,302 strict_mode` 形参无效；`ready_weight`（`config_field_spec.py:130-137`）web 零引用、算法侧校验后丢弃（`schedule_params.py:289`、`sort_strategies.py:149`）；零调用公开函数 `seed_results_by_machine_id`、`candidate_fingerprint_for_comparison`、`registered_neighborhoods`；11 份数值校验、两种交期解析、11 处 deadline 判定。

## 影响

改一个 attempt 字段或接受规则要动 4–6 处；diagnostics 的 `distinct_candidates` 口径依赖各阶段自觉调用；新增一个阈值参数要改 6–8 个签名；Win7 离线包携带无生产调用者的代码。

## 修复方向

抽单一 `candidate_ledger` 与单一接受函数；升格 `run/optimizer/` 子包（graph_ready / local_search / reporting），用 frozen context dataclass 取代 kwargs 透传；一个 `FingerprintLedger` 注入所有阶段；proof harness 迁 `tests/_support/optimizer_proof/`；删残留形参、`ready_weight` 标 hidden 或移除。

## 建议动作

`cs-refactor`，分批做，每批跑对应合同测试。
