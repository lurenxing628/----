# grasp-ig-candidate-construction fast-forward note

日期：2026-06-28

Roadmap：`.codestable/roadmap/scheduler-global-optimizer/`

## 范围

- 本阶段只完成 item 6：`grasp-ig-candidate-construction`。
- 新增 GRASP / Iterated Greedy 候选起点构造。
- 候选只改变批次顺序和 SGS 派工规则。
- 正式排程仍走现有 `GreedyScheduler.schedule(..., dispatch_mode="sgs")`，不在候选构造层生成 `ScheduleResult`、start/end 或可变 seed 结果。
- 未实现 item 7 业务邻域 registry。
- 未实现 item 8 VNS / SA / threshold / Record-to-Record Travel acceptance。
- 未实现 ALNS destroy / repair / selection / weight update。

## 代码落点

- `core/services/scheduler/run/optimizer_grasp_ig_specs.py`
  - 负责根据 version 派生 seed，构造 GRASP / IG 候选规格。
  - GRASP 用 restricted candidate list 思路从 base order 中抽取批次顺序。
  - Iterated Greedy 基于当前 best order 做 destruction / reinsertion。
- `core/services/scheduler/run/optimizer_grasp_ig_candidates.py`
  - 负责把候选规格交给 SGS 正式解码、记录 attempts、trace 和 search report。
  - 非 strict 的 `ValidationError` 记录为 `candidate_rejected=validation_error`。
  - strict 模式继续 fail-loud。
- `core/services/scheduler/run/schedule_optimizer.py`
  - 在 multi-start 之后、local search 之前接入 GRASP/IG 阶段。
  - 仅默认 runtime 启用该阶段；测试替身未提供该 hook 时保持旧行为。
- `core/services/scheduler/run/optimizer_candidate_profile.py`
  - 默认 improve profile 扩展为 `grasp_ig`。
  - 新增 `candidate_strategy_families` 和 `candidate_construction`。
  - GRASP / IG configured/effective budget 从 time budget 派生并钳制。
- `core/services/scheduler/summary/optimizer_public_search_report.py`
  - public 只展示 `candidate_strategy_families`。
  - `candidate_construction` 只进入 diagnostics 的安全数字摘要。
- `core/services/scheduler/summary/optimizer_public_attempts.py`
  - 给 `grasp:` 和 `ig:` attempt tag 增加安全中文来源标签。

## 合同

- 随机性只来自 version 派生 seed 或显式 runtime `rng_factory`。
- GRASP/IG 只构造候选决策，不伪造排程结果。
- 所有候选都必须经 SGS 解码后才能进入 CandidateFingerprint。
- `distinct_candidates` 继续按 `output_fingerprint` / `decoded_output` 去重。
- 不同构造方式可改变 `decision_fingerprint`。
- 多个候选若 SGS 解出同一张表，`distinct_candidates` 不虚高。
- `improved` 仍服从 item 5 三条件：fingerprint changed + score strictly better + acceptance passed。
- same_as_parent / same_as_seen 只记 same_fingerprint，不算 improvement。
- public / OperationLogs / size guard 不展示候选原始顺序、fingerprint hash、内部 op/resource id、raw trace。
- 最终 `used_params` / `strategy_params` 不保留内部 `candidate_construction`，避免绕过 `search_report` public 投影进入结果摘要、接口返回或 OperationLogs。

## 测试

- 新增 `tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py`。
- 已登记：
  - `tools/test_registry_data.py`
  - `tools/test_registry_groups_scheduler.py`
  - `tests/gate_meta/test_quality_gate_registry_split_scope_contract.py`

覆盖点：

- GRASP/IG 构造预算由 profile 如实报告。
- 同 seed 同输入候选一致，不同 seed 可产生不同候选。
- GRASP/IG 候选强制用 `dispatch_mode="sgs"` 正式解码。
- 非 strict 解码 `ValidationError` 记录 rejected，strict 模式 fail-loud。
- 多个 GRASP/IG 候选解码成同一输出时，`distinct_candidates=1`。
- 真实改善时 `best_origin` 可标记为 `grasp`。
- 构造元数据能区分 decision fingerprint，但同输出仍合并 output fingerprint。
- public / OperationLogs / size guard 不泄漏 raw order、fingerprint hash、内部资源编号。
- 主入口会调用 GRASP/IG 阶段。
- IG 候选成为最优时 `best_origin=ig`。
- `candidate_construction` 不通过最终 `used_params` / `strategy_params` 旁路泄漏。

## 当前验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py tests/algorithm/test_optimizer_candidate_profile_contract.py tests/algorithm/test_optimizer_candidate_fingerprint_contract.py tests/algorithm/test_optimizer_search_report_contract.py tests/algorithm/test_optimizer_public_summary_projection_contract.py tests/schedule/summary/test_schedule_summary_size_guard_large_lists.py`
  - 64 passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_proof_harness.py --require-optimal`
  - passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/gate_meta/test_architecture_fitness.py::test_file_size_limit tests/gate_meta/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/gate_meta/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards`
  - 3 passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit ...`
  - 0 findings
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`
  - passed

## 已知 proof 边界

- 当前尚未提交，新增测试文件仍是 Git 未跟踪文件。
- 因此 `tests/gate_meta/test_full_test_debt_registry_contract.py::test_quality_gate_required_startup_and_full_debt_share_registry` 会要求新增 required 测试已出现在 `git ls-files` 中，提交前无法作为 clean proof 通过。
- 这不是源码逻辑失败，是未提交状态下的 registry proof 限制。
