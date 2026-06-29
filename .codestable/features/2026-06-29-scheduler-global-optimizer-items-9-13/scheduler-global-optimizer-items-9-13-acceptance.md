# scheduler-global-optimizer items 9-13 acceptance

## 范围

- 完成 roadmap `scheduler-global-optimizer` 第 9-13 项。
- 生产接入图 ready 候选搜索、九组图权重、统一候选择优、benchmark ratchet 轻/中/长门禁。
- 不接入 ALNS；ALNS 在后续 GraphReady v2 和基准补强之后继续。

## 代码落点

- 图 ready 候选入口：`core/services/scheduler/run/optimizer_graph_ready.py`
- 图权重定义：`core/services/scheduler/run/optimizer_graph_ready_profiles.py`
- 图上下文校验：`core/services/scheduler/run/optimizer_graph_ready_context.py`
- 图候选正式解码：`core/services/scheduler/run/optimizer_graph_ready_candidates.py`
- 图候选报告记录：`core/services/scheduler/run/optimizer_graph_ready_reporting.py`
- 图 ready 真实 SGS 基准夹具：`tests/_support/optimizer_graph_ready_benchmark.py`
- 图节点指标生产：`core/services/scheduler/graph/metrics.py`
- 候选比较顺序：`core/services/scheduler/run/optimizer_candidate_comparison.py`
- 候选阶段编排：`core/services/scheduler/run/optimizer_candidate_phases.py`
- 图评分投影拆分：`core/services/scheduler/run/schedule_graph_score_projection.py`
- 搜索报告拆分：`core/services/scheduler/run/optimizer_search_report.py` + `optimizer_search_report_helpers.py`
- SGS 图上下文硬校验：`core/algorithms/greedy/dispatch/sgs_graph.py`
- benchmark ratchet：`tests/_support/optimizer_benchmark_ratchet.py`
- FJSP 基准拆分：
  - `tests/_scripts_e2e/benchmark_fjsp.py` 只保留命令入口
  - `tests/_support/optimizer_fjsp_dataset.py` 负责数据镜像、解析和多机折叠
  - `tests/_support/optimizer_fjsp_fixture.py` 负责 APS 测试库装载
  - `tests/_support/optimizer_fjsp_runner.py` 负责单个基准用例执行
  - `tests/_support/optimizer_fjsp_report.py` 负责 Markdown 报告输出
- 轻/中/长 benchmark 命令：
  - `tests/_scripts_e2e/benchmark_optimizer_ratchet.py`
  - `tests/_scripts_e2e/benchmark_optimizer_medium_gate.py`
  - `tests/_scripts_e2e/benchmark_optimizer_long_run.py`

## 验收结果

- 图 ready 模式不再记录旧原因 `graph_ready_requires_graph_neighborhood`，改为先走专用 graph-ready candidate phase。
- 九组默认权重已落地：balanced、critical_path_first、successor_fanout_first、downstream_work_first、bottleneck_relief、critical_bottleneck、fanout_downstream、bottleneck_downstream、graph_neutral。
- `bottleneck_machine_score` 已由生产图指标生成；多候选机器工序按工时分摊、取最小候选机器负荷、再按候选机器数做灵活性降权；图 ready 权重评分缺该字段时直接 `ValidationError`，不再静默当作 0。该部分是从后续 GraphReady v2 瓶颈资源分里提前抽出的基础图指标；v2 仍未完成交期门控、残余容量、`bottleneck_on/release` 拆分等目标感知能力。
- 统一候选择优顺序已落地并复核覆盖 GraphReady、GRASP/IG、VNS/SA：failed_ops → objective_score → best_fingerprint_changed → runtime_ms → candidate_origin；失败候选仍走 `candidate_rejected` 或 strict fail-loud，不包装成正常方案。
- 重复正式输出指纹只记 `same_fingerprint`，不采纳为新 best。
- public 投影只显示小摘要；完整图上下文、指纹、内部 attempts 仍留 diagnostics，不进普通 public。
- benchmark 默认报告写 `evidence/QualityGate/long_gate/optimizer_benchmark/`，该目录被 `.gitignore` 忽略；轻门禁已加入真实图 ready SGS 用例和灵活候选机器指标用例，不再只跑 tiny proof harness。
- ratchet 比对会拒绝空 actual cases、少跑 baseline cases、actual 多出未登记 cases、case_count 和 cases 不一致等假绿灯。
- 文件体积不是靠删空行压线：新建/改动的图候选、图评分、搜索报告和 FJSP 基准职责已经按模块拆分；本轮复核后生产门禁范围无超过 500 行文件、无复杂度超过 15 的函数。继续拆分 benchmark ratchet、import-cycle 工具、本地搜索循环和优化入口兜底后，当前变更 Python 文件整体也无复杂度达到或超过 15 的函数，复杂度最大值为 13。

## 已跑验证

- `.venv/bin/python -m pytest -q tests/scheduler_graph/test_metrics_impact.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py::test_on_dag_prepares_plain_graph_ready_context_before_optimizer tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py::test_on_dag_score_context_uses_single_full_metrics_pass`
  - 结果：33 passed
- `.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --check-baseline`
  - 结果：passed，failure_count=0；当前 snapshot 标记 `dirty_worktree=true`，只能证明相对 dirty baseline 未退化，不能当作 clean proof。
  - 当前 light baseline 含 3 个 case：`tiny-sgs-single-machine`、`graph-ready-weight-grid-real-sgs`、`graph-ready-flexible-machine-bottleneck-metric`
  - 真实图 ready SGS case：9 个 profile 全部评估，10 个候选计数含 baseline，6 个不同输出指纹，3 个 accepted distinct candidates，best_origin=`graph_ready_weight_grid`
  - 图 ready 目标分从 `[0.0, 3.0, 18.0, 18.0, 24.0, 0.0]` 改善到 `[0.0, 2.0, 8.0, 8.0, 24.0, 0.0]`
  - 灵活候选机器指标 case：`busy=2.5`、`light=1.0`、`flex=0.707107`，并要求 `flex < light < busy`
- `.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_long_run.py --seeds 10 --no-write`
  - 结果：passed
  - 输出：10 seed，mean_failed_ops=0，worst_failed_ops=0，min_distinct_candidates=6，min_accepted_distinct_candidates=3，mean_duplicate_candidate_rate=0.4，mean_candidate_rejection_rate=0.4
- `.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_medium_gate.py --run`
  - 结果：passed
  - 覆盖：FJSP graph ready smoke、SMTWT 250 实例 sgs/batch_order 局搜、SGS 大资源池。
  - 关键输出：FJSP `runs=3 valid=3`；SMTWT sgs 模式 250 实例中 209 个局搜改进；SGS 大资源池报告写入 ignored long_gate。
- `.venv/bin/python -m pytest -q tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py tests/algorithm/test_optimizer_vns_sa_local_search_contract.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py`
  - 结果：47 passed
  - 覆盖：GRASP/IG、VNS/SA、GraphReady 共用候选择优顺序；ratchet 假绿灯拒绝。
- `.venv/bin/python -m pytest -q tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py::test_on_dag_prepares_plain_graph_ready_context_before_optimizer tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py::test_on_dag_score_context_uses_single_full_metrics_pass tests/algorithm/test_optimizer_grasp_ig_candidate_construction_contract.py tests/algorithm/test_optimizer_vns_sa_local_search_contract.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py`
  - 结果：40 passed
  - 覆盖：图上下文 bottleneck 指标、统一候选择优、benchmark ratchet 回归。
- `.venv/bin/python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean`
  - 结果：passed，无新增硬加载期循环依赖输出。
- `.venv/bin/python - <<'PY' ... scan_oversize_entries / scan_complexity_entries ... PY`
  - 结果：生产门禁范围 `oversize=[]`、`complexity_over_threshold=[]`；当前变更 Python 文件整体 `complexity_over_threshold=[]`。
- `.venv/bin/python /tmp/verify_graph_ready.py`
  - 结果：按预期 fail-loud
  - 原因：脚本第一层故意构造缺 `bottleneck_machine_score` 的指标；修复后不再默认 0，而是报 `图指标缺少 bottleneck_machine_score`

## 归因澄清

- `SMTWT` 的 209/250 局部搜索改进来自既有 `_run_local_search` 链路，不是本轮 graph ready 候选搜索成效。
- FJSP benchmark 仍是 `benchmark_fjsp.py` 的技术基准，不能单独证明 graph ready 在 APS 业务目标上全局最优。
- 本轮 graph ready 的直接证据以上述 `graph-ready-weight-grid-real-sgs` 真实 SGS case、ratchet baseline 和 graph-ready candidate contract 测试为准。

## 子代理复审吸收

- SGS 链路复审指出缺少显式环校验、固定来源核对、多余 key 拦截；本轮已在 SGS 和 graph-ready 候选校验层补齐。
- 候选比较复审指出缺少统一排序和 graph-ready 专用候选；本轮已新增 candidate comparison 与 graph-ready phase。
- public 边界复审指出新增 graph-ready/benchmark 输出容易泄漏内部字段；本轮已扩展 public/profile diagnostics 白名单并新增脱敏测试。
- benchmark 复审指出缺少 ratchet baseline、普通门禁不能直接塞重 benchmark、默认 tracked evidence 有风险；本轮已新增 ratchet baseline、轻/中/长命令，并把默认报告改到 ignored long_gate。
- 本轮 review 复审指出 GRASP/IG、VNS/SA 未共用 `candidate_is_preferred`，以及 benchmark ratchet 比对 helper 复杂度超过 15；已接入统一候选比较并拆分 ratchet / import-cycle helper，补充回归测试后复杂度超限清零。

## 剩余边界

- FJSP makespan 仍只是技术参考，不能证明 APS 业务目标全局最优。
- SMTWT 当前只证明局部搜索相关能力，不作为 graph ready 归因证据。
- GraphReady v2 的部分瓶颈资源分基础指标已提前进入 `bottleneck_machine_score`，后续 v2 不应重复实现这部分；仍需继续做目标感知特征、交期门控、残余容量和候选组合。
- ALNS 尚未接入；后续 ALNS 必须复用本轮候选比较和 benchmark ratchet。
