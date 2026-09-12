---
doc_type: feature-implementation
feature: 2026-09-12-optimizer-end-to-end-quality
status: implemented
summary: 完整候选入口基准与独立tiny oracle已实现，局部合同通过，正式20例和整仓门禁由主线程收口
tags: [optimizer, benchmark, exact-oracle, verification]
---

# 实施与局部验证

- 新增 `tests/_support/optimizer_end_to_end_cases.py`、`optimizer_end_to_end_schedule.py`、`optimizer_end_to_end_runner.py`、`optimizer_end_to_end_compare.py`、`optimizer_end_to_end_io.py`，分别负责夹具、输出审计、真实入口测量、快照比较和基线生命周期。
- 新增 `tests/_support/optimizer_exact_oracle.py`，独立枚举限定域并计算四目标完整向量；现有核心八例未改。
- 新增 `tests/_scripts_e2e/benchmark_optimizer_end_to_end.py`，提供 `run/check/compare/update-baseline`。
- 定点只读审查后补齐外协输出不得占用内部资源、候选全集与 `score_only` 最低分选择、macOS 大小写路径保护，并新增相应反例测试。
- 计数量尺与原生 SGS 复用接入后，移除对 `GreedyScheduler.schedule` 的 monkeypatch，默认读取每实例真实 `decoder_invocations`。新增 `native/uncounted` 显式模式；旧源对照不回填产品计数代码，未计数模式始终写 `null`，跨模式禁止性能比较。
- `wide_parallel_chains` 最终使用12条链各自独占的一组合格机器/人员，共24工序/12组资源；完整重建机器资格、人员资格和双向映射。通过真实实例私有诊断证明 SGS 复用有实际命中，计数总和与真实实例逐一相等，完整测量期间 `GreedyScheduler.schedule` 身份保持不变。共享及稀缺资源由另两个场景覆盖，不弱化其合同。

2026-09-12 局部验证：

| 命令/检查 | 结果 |
|---|---|
| `.venv/bin/python -m pytest tests/algorithm/test_optimizer_exact_oracle.py -q` | 31 passed，0.45s |
| `test_fixture_shapes_expand_coverage_without_claiming_piece_pipeline` 与 `test_native_counter_keeps_decoder_unpatched_and_allows_real_sgs_reuse` | 最终12组独占机人夹具：2 passed，1.37s；完整双向资格映射、真实原生计数、未patch、cache hit与固定资源审计 |
| 同模块其余用例（`-k 'not native_counter_keeps_decoder_unpatched_and_allows_real_sgs_reuse'`） | 27 passed，3.18s |
| `.venv/bin/python -m pytest tests/algorithm/test_optimizer_end_to_end_snapshot_contract.py -q` | 67 passed，10.74s |
| 新增代码 Ruff | 通过 |
| 新增代码 Python 3.8 AST 语法检查 | 通过 |
| CLI `run --scenario tiny_chain --objective min_overdue` 后 `check --snapshot` | native及uncounted各两步通过；两者均真实4个外层候选/4次优化入口，native=10次decode，uncounted=null；合法无改进 |

三个模块分项累计126项局部合同通过；最终12组独占机人夹具另完成表中两项定向复验，不把此前共享三资源夹具的耗时当作当前适用域性能证据。CLI smoke 保存于 `/private/tmp/aps-algorithm-implementation-20260912/g-entry-smoke.json`（native）和同目录 `g-entry-uncounted-smoke.json`，来源明确为 `unbound_dirty_worktree`。单次约48–49ms只用于证明真实入口和两模式输出验证接通，不能用作稳定提速比例或正式全覆盖基线；原先使用schedule wrapper的早期smoke已由原生量尺结果替代。

工作区同时包含其它算法实施改动。本分项没有提交、没有运行正式20例、没有提升基线、没有运行完整质量门禁；以上均为 dirty 工作区局部验证。三个新测试文件的必跑注册与真实计时模块串行分片由主线程统一处理，正式验证结果以主线程最终回执为准。
