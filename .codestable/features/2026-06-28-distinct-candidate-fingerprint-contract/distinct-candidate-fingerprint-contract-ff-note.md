---
doc_type: feature-ff-note
feature: distinct-candidate-fingerprint-contract
date: 2026-06-28
status: done
tags: [scheduler, optimizer, candidate-fingerprint, search-report, public-boundary, python38]
---

# distinct-candidate-fingerprint-contract fast-forward note

## 本轮目标

执行 roadmap item 5：`distinct-candidate-fingerprint-contract`。

本轮只定义“什么算同一个候选、什么算真的探索到不同方案、什么才算真的变好”。不新增搜索算法，不新增 GRASP / IG / VNS / SA / ALNS，不做业务邻域 registry。

## 落地内容

- 新增 `core/services/scheduler/run/optimizer_candidate_fingerprint.py`：
  - `CandidateFingerprint` 合同字段：`schema_version`、`fingerprint_scope`、`objective_name`、`decision_fingerprint`、`output_fingerprint`、`parent_fingerprint`、`same_as_parent`、`same_as_seen`、`fingerprint_changed`。
  - `decision_fingerprint` 覆盖 objective、strategy/params、dispatch mode/rule、batch_order、resource、locked seed、mutable scope。
  - `output_fingerprint` 覆盖正式解码结果数量、工序-资源-时间签名、summary 和当前 objective score。
- `optimizer_search_report.py`：
  - `distinct_candidates` / `accepted_distinct_candidates` 改为按 `decoded_output` 去重。
  - public/minimal report 增加 `distinct_fingerprint_scope` 和中文口径说明。
  - `improved` 改为三条件：fingerprint 改变 + score 严格更优 + 通过 `improve_only` acceptance。
  - `same_as_parent` / `same_as_seen` 记 `same_fingerprint` 拒绝，不算 improvement。
- public / diagnostics：
  - public 只展示计数、布尔值和口径说明。
  - `decision_fingerprint` / `output_fingerprint` hash、fingerprint event 和三条件明细只进 diagnostics。
  - `public_identifier_redaction.py` 禁用 key 并集补 `decision_fingerprint` / `output_fingerprint` / `parent_fingerprint`。
- 新增 `tests/algorithm/test_optimizer_candidate_fingerprint_contract.py` 并登记 test registry。

## 改了哪些

- `core/services/scheduler/run/optimizer_candidate_fingerprint.py` — 新增 CandidateFingerprint 合同和稳定 hash 生成。
- `core/services/scheduler/run/optimizer_search_report.py` — 接入 output 去重、same-fingerprint 拒绝和 improved 三条件。
- `core/services/scheduler/run/schedule_optimizer.py`、`schedule_optimizer_steps.py`、`optimizer_local_search.py` — 候选 dict 补 resource / seed / mutable scope 内部决策输入。
- `core/services/scheduler/summary/optimizer_public_search_report.py`、`summary_size_guard_fields.py`、`schedule_candidate_persistence_models.py` 间接出口 — 保留 public 口径说明，hash 仍只在 diagnostics。
- `core/models/public_identifier_redaction.py` — 新 fingerprint 字段名加入内部禁用 key 并集。
- `tests/algorithm/test_optimizer_candidate_fingerprint_contract.py`、相关旧测试和 registry — 锁 distinct/output、三条件、same-fingerprint、public 边界和 size guard。

## 怎么验证的

- `tests/algorithm/test_optimizer_candidate_fingerprint_contract.py` 覆盖确定性、decision/output 区分、同解码输出去重、same-fingerprint 拒绝、improved 三条件、public/OperationLogs/size guard 不泄漏。
- item 1/2/3/4 回归已跑：search_report、candidate_profile、public summary、proof harness、local search neighbor dedup、multi-start build_order、内部 id 脱敏、size guard。
- registry 和架构门禁已跑到 `189 passed`；pyright gate/tools 均 0 errors。

## 边界说明

- 没有新增候选构造、搜索算法或业务邻域。
- 没有把 OR-Tools 升为主引擎。
- output fingerprint 的内部 id 只参与 hash，不进入 public、OperationLogs 或 size guard 最小摘要。
- clean-worktree proof 仍需在本轮改动提交到 HEAD 且工作区干净后运行 `scripts/run_quality_gate.py --require-clean-worktree`。

## review 收尾清理（2026-06-28）

对 item 5 做对抗 review（OPUS 子代理定向+盲审 + Codex 复审）后，处理发现的缺陷与代码债。判断规则：路线图后续 item 无覆盖的就地处理，已覆盖的留给对应 item。

- **B1 指纹排序防御性硬化（真实数据流不可达，非生产崩溃 bug）**：`_result_signature` 旧实现的排序键首元素用了类型漂移的 `op_id`（旧 `_identity_value`：正整数→`int`、`0`/`None`/≤0→`str`），一批 `results` 混入正整数与 `0`/`None` 时 `sorted` 拿 int 与 str 比较抛 `TypeError`。**经核实生产不可达**：`BatchOperations.id` 是 `INTEGER PRIMARY KEY AUTOINCREMENT`（`schema.sql:148`）必正整数、排产工序全经 `op_repo.list_by_batch` 从库查（`schedule_input_collector.py:162`）、生产代码无内存构造 `BatchOperation`，故 op_id 必正整数、混合不会出现。脆弱本质：`_identity_value`「为非正整数留 str 兜底」与排序「假设同质可比」两个假设自相矛盾，兜底反而埋了崩溃点。已删 `_identity_value`、签名内 `op_id` 统一 `str` 使排序键类型恒定，焊死未来若引入「未入库工序参与排产」时的潜伏崩溃点。前轮含 Codex 标「偏 blocker」系高估（未闭合「主键自增 + 全量从库查」这一环）。
- **O1**：删 `_resource_override_payload` 三个无写入方的 key 别名（`resource_override`/`resource_overrides`/`resource_pool_override`），只留 `resource_pool`。
- **O3**：删孤儿函数 `candidate_report_fingerprint`/`attempt_report_fingerprint`/`stable_report_fingerprint` 及连带 import 与 `__all__`（dead-code 岛屿 358→355）。
- **O4**：删 `mark_candidate_rejected`/`mark_optional_warmstart_failed` 的 dead `attempt` 形参，同步 `optimizer_attempt_records`(×2)/`optimizer_local_search`/`optimizer_step_report_hooks` 四个调用点。
- **M2**：删 report 层与 `distinct_fingerprint_scope` 值重复的冗余 `fingerprint_scope` 字段与 `FINGERPRINT_SCOPE` 常量（保留 `CandidateFingerprint.fingerprint_scope` dataclass 字段）；同步 public 投影、size guard、3 个测试。
- **补测试**：候选缺 `results`、非有限 score、非法 `seed_result_count` 三条 `ValidationError` fail-loud + op_id 混合回归（此前新合同 fail-loud 路径无测试锁）。
- **M1（仅注释）**：`acceptance_passed = accepted_candidates>1` 是 improve_only 专用代理，item 8 引入非贪心 acceptance 后须改为依据真实 acceptance 判定，已加注释钉住。
- **I1/I2（仅注释）**：`_jsonable` 未知对象的 `{"type":类名}` 有损降级仅影响 `decision_fingerprint` 与 skipped 诊断 extra；`output_fingerprint`（去重/improved 判定用）全纯量、不经该分支，正确性无影响。
- **O2（撤回）**：`_mutable_scope_payload` 的 fallback 经复查是测试可达的优雅降级（测试候选不带 `mutable_scope`），非生产死分支，不删。
- **batch_order/SGS 的 `op_id<=0` 差异（已评估，不立 issue）**：`batch_order` 落位对 `op_id<=0` 无校验、SGS 经 `ready_queue` fail-loud，写法不一致；但同因 op_id 必正整数（自增主键 + 全量从库查 + 无内存构造），两条路径都遇不到 `op_id<=0`，该差异不可达，**不单独立 issue**。`_build_internal_result`（`internal_operation.py:211`）的 `op.id or 0` 也是对不可达输入的防御，保留无害。

验证：48 项针对性 + 352 项算法/registry 测试全绿；质量门禁 17/17 通过（`--allow-dirty-worktree`，dirty/unbound proof）。
