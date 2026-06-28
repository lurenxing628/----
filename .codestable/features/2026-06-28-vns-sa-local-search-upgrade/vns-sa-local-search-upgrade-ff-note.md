# vns-sa-local-search-upgrade

日期：2026-06-28

## 范围

- 落地 roadmap item 8：在 item 7 的业务邻域 registry 之上升级 local search。
- 新增 current/best 分离状态，允许 threshold / record_to_record / simulated_annealing 接受非改进候选作为 current。
- best 更新仍必须同时满足：真实 acceptance 通过、score 严格更优、output_fingerprint 非 parent 且非 seen。
- 不做 ALNS destroy/repair/operator selection/weight update，不推进 item 9+。

## 实现

- `optimizer_acceptance.py`：定义四种 acceptance 白名单和可复现 acceptance decision trace。
- `optimizer_local_search_state.py`：维护 current solution 与 best solution 分离。
- `optimizer_vns.py`：记录 VNS 当前邻域、no-improve 计数、shake 次数和切换原因。
- `optimizer_local_search.py`：每轮从 current 解生成业务邻域候选，候选仍交给现有 SGS 解码；非改进接受只更新 current，best 改善才写 best。
- `optimizer_search_report.py`：新增 acceptance/VNS trace 与摘要；`acceptance_passed` 改为真实 best acceptance 事件来源。
- `optimizer_public_search_report.py` / `summary_size_guard_fields.py`：只投安全计数摘要，不暴露 raw random draw、fingerprint hash、raw move 或内部 op/resource id。

## 测试

- 新增 `tests/algorithm/test_optimizer_vns_sa_local_search_contract.py`。
- 覆盖 current/best 分离、非改进接受不制造 improved、best 真改善、SA 确定性、VNS 切换。
- 回归覆盖 CandidateProfile、CandidateFingerprint、SearchReport、public projection、summary size guard。

## 边界

- public 只展示 acceptance/VNS 类型和计数摘要。
- diagnostics 可保留 raw acceptance/VNS trace，但不会进入 public/OperationLogs。
- same_as_parent / same_as_seen output 不允许更新 best，也不允许制造 improvement。
