# graph ready ratchet bottleneck 修复记录

## 问题

- graph ready 九组权重里有 `bottleneck_machine`，但生产 `node_metrics` 没有生成 `bottleneck_machine_score`，候选评分读取时默认 0，导致瓶颈维度静默失效。
- 轻量 benchmark ratchet 只跑 tiny proof harness，没有真实跑 graph ready 候选搜索，`distinct_candidates` 等字段是硬编码，不能保护九组权重退化。
- ratchet baseline 比对只遍历 actual rows，不检查 baseline 用例是否缺失，也不拒绝空 actual cases。
- 长跑 benchmark 用自造 schedule stub，不是项目真实 SGS 解码。
- acceptance 文档把 SMTWT 局部搜索 209/250 归到 graph ready items 9-13，证据归因错误。

## 根因

- 图指标生产层和图权重消费层没有同一份字段合同。
- benchmark 只证明“脚本能跑”，没有把 graph ready 候选搜索的真实输出纳入门禁。
- baseline 比对缺少集合完整性检查，所以空结果和少跑用例会假绿。

## 修复

- `core/services/scheduler/graph/metrics.py` 生成 `bottleneck_machine_score`，多候选机器工序按工时分摊到候选机器，节点取最小候选机器负荷，并按候选机器数做灵活性降权。
- `core/services/scheduler/run/optimizer_graph_ready_context.py` 新增必填非负数读取；`optimizer_graph_ready_candidates.py` 缺 `bottleneck_machine_score` 时直接抛 `ValidationError`。
- `tests/_support/optimizer_graph_ready_benchmark.py` 新增真实 SGS graph ready 基准夹具，九组权重跑项目自己的 `GreedyScheduler`。
- `tests/_support/optimizer_benchmark_ratchet.py` 将真实 graph ready case 纳入 light snapshot，并收紧 baseline 比对：空 actual、缺 baseline case、多 actual case、case_count 不一致均失败。
- `tests/_scripts_e2e/benchmark_optimizer_long_run.py` 改为复用真实 SGS graph ready 基准，不再使用 stub，不再硬编码 passed。
- `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json` 更新为 3 个 case：tiny proof + real graph ready SGS + flexible machine bottleneck metric。
- acceptance 文档修正 SMTWT/FJSP 的证据边界，明确它们不是 graph ready 成效归因。

## 验证

- `.venv/bin/python -m pytest -q tests/scheduler_graph/test_metrics_impact.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py::test_on_dag_prepares_plain_graph_ready_context_before_optimizer tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py::test_on_dag_score_context_uses_single_full_metrics_pass`
  - 结果：33 passed
- `.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --check-baseline`
  - 结果：passed，failure_count=0，light baseline 当前 3 个 case
- `.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_long_run.py --seeds 10 --no-write`
  - 结果：passed，min_distinct_candidates=6，min_accepted_distinct_candidates=3
- `.venv/bin/python /tmp/verify_graph_ready.py`
  - 结果：按预期 fail-loud，因为脚本构造了缺 `bottleneck_machine_score` 的旧输入。

## 遗留边界

- 当前真实 graph ready 基准是轻量门禁用例，用来防退化；它不是 APS 全数据集的全局最优证明。
- 新增 flexible machine bottleneck metric case 是图指标小基准，用来防止多候选机器被折叠成最堵机器；它不是完整 FJSP 自动选机基准。
- 中门禁里的 SMTWT/FJSP 数字只能分别证明局部搜索和技术基准，不作为 graph ready 归因证据。
