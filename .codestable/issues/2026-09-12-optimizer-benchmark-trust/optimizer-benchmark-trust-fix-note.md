---
doc_type: issue-fix
issue: optimizer-benchmark-trust
status: implemented
fix_date: 2026-09-12
tags: [optimizer, benchmark, wall-clock, baseline, serial-tests, python38]
---

# 优化器基准计时与基线信任修复

## 结论与范围

本轮用户已授权实施算法研究列出的改进；本专项修复评测框架，不改业务数据库、不提交代码、不把工作区修改后的输出冒充 clean proof。当前代码仍在主线程的集成修改中，最终统一性能实验和全门禁由主线程执行。

## 根因和实现

- 旧算法对比混用模拟时钟、真实时钟和获胜候选耗时。GraphReady、SMTWT、普通局搜和 GRASP 的新报告统一用 `time.perf_counter`，计时及预算从各算法初始方案排产前开始，直到全部搜索及正式 repair 完成；即使最终返回初始方案，也保留全部搜索时间。单个 candidate 的 `runtime_ms` 不再用来填算法总耗时。
- SMTWT 每个算法重新构建相同输入的独立 scheduler/baseline，避免复用前一个算法已经预热的状态。删除阶段外没有预算的私有 repair，只调用生产 `run_graph_ready_candidates` 内部正式 elite repair；GraphReady v1/v2 和局搜/GRASP 使用同一真实截止时间口径。
- 对比和长跑默认且仅接受一个 worker，报告明确 `serial_single_worker`。显式注入的测试时钟只用于合同测试，helper 输出标注 `test_injected_clock`，不能当作性能证据。
- 多算法比较升为 schema 2，记录 machine、运行前后 HEAD/工作区/源码摘要，以及时间测量范围。比较拒绝旧 schema、模拟时钟、未知/零耗时、运行期间相关源码变化、机器不一致和完整目标向量退化。默认耗时退化警报仍为 `actual > baseline * 3 + 250ms`，这是宽容的回退门槛，不是性能收益结论。
- 两个比较 CLI 的正式基线检查/更新互斥；正式提升禁止 `--allow-dirty-proof`，要求运行前后完整 clean receipt 相同、当前真实源码/机器匹配、既有 schema 2 基线非退化，并使用原子替换。旧/缺失/损坏基线先预检拒绝，不先消耗搜索预算。
- 旧 light ratchet 和旧 GraphReady 长跑同步真实计时；tiny greedy+oracle 只承担可行性/最优参照功能，不冒充完整优化器。light 自有测量协议独立于多算法行格式。
- 将 `test_optimizer_quality_matrix*.py`、`test_optimizer_end_to_end*.py` 和真实算法比较/长跑/ratchet/timing 测试整文件纳入 serial 分片。原来同一矩阵文件因测试名中是否含 `runtime` 而拆进 serial/parallel、重复构建 module fixture 的路径已锁住。
- 原 695 行 `optimizer_compare_algorithms.py` 按候选行/比较展示职责拆到 `optimizer_compare_algorithms_rows.py`；源码回执与正式 IO 同样分工，避免把新增合同堆回大文件。

## 验证

- Python 3.8.10：比较/SMTWT 现有合同、新生命周期、新计时、分片和 light ratchet 合并专项最终 **173 passed, 1 deselected in 7.08s**。排除的是既有真实十 seed 长跑 CLI smoke，保留该测试供主线程最终统一门禁执行，没有删除覆盖。
- 受控时钟测试验证 baseline 250ms + 全搜索 500ms 的累计边界，故意设置 candidate runtime=99999，保证报告不会读取错误字段；这些数字是测试输入，不是加速证据。真实四工序烟测验证正式调度路径可运行。
- 全部 29 个变更/新增 Python 文件通过 Python 3.8 AST 语法校验、Ruff 和指定 pathspec 的 `git diff --check`。未运行完整多 seed 性能长跑或全仓门禁，最终统一实验/门禁结果以主线程收口记录为准。
- 已实际执行 `benchmark_optimizer_compare_algorithms.py --check-baseline --no-write`：退出 1、`baseline_migration_required`；`benchmark_optimizer_graph_ready_v2_long_run.py --check-baseline --no-write`：退出 1、`missing_baseline`。预检阶段未启动搜索。
- light `benchmark_optimizer_ratchet.py --check-baseline` 同样实跑退出 1、`baseline_migration_required`；更新入口对旧 schema 也前置拒绝，没有重建或覆盖旧基线。所有普通比较/SMTWT CLI 不再给缺失 schema/source 的旧 payload 提供“已通过”兼容分支。

## 旧基线保护和迁移

以下两份 tracked 文件均保持与本轮起始 HEAD 逐字节一致，未改成 clean、未刷新数值：

| 文件 | SHA-256 |
| --- | --- |
| `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json` | `0297feff58ee64f6477313e3e25a53fe4a674952cc266c01c2ecbe01342f83ff` |
| `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json` | `bff3351b5ee78e9edab0f67364335700cfa67921bfe22159342c85c1c2e74c2f` |

旧基线来自 2026-06-30，包含模拟/获胜候选计时且工作区标为 dirty，不能与新真实总耗时直接比较。新协议遇到它们明确返回 `baseline_migration_required`，`--allow-dirty-proof` 不能绕过。新正式基线应由最终 clean HEAD 在统一单机串行实验后，用新 schema 2 路径建立；不能只修改旧 JSON 的 schema/dirty 标签。旧数据保留为历史诊断来源。

## 正式历史质量比较接入

本轮实际历史非退化门禁接入核心八例矩阵：`test_real_matrix_does_not_regress_against_formal_historical_baseline` 直接复用现有 module-scoped `matrix` fixture，读取 `tests/fixtures/optimizer_quality_matrix_baseline.json`，检查基线来自 clean measured run，并调用 `compare_quality_only`。一般 pytest 始终验证两份快照自身的完整元数据、相同 fixture/config/measurement，以及 baseline/improved 两份排程按该目标定义的完整 `objective_score` 字典序；不同主机也必须执行质量检查，不改机器字段、不跳过。字典序允许更高优先级指标改善时次级指标有取舍，不要求每个分量逐项非退化。

真实耗时验收继续由显式 CLI `compare` 调用原 `compare_quality_matrices`：在共用上述质量校验后，仍要求 machine 字典逐字段相同并检查 baseline/improve/total 三段耗时，默认 `3×+250ms` 不变；跨机器完整比较仍失败。`update-baseline` 继续使用完整比较，不能用 quality-only 绕过正式基线耗时门槛。一般 pytest 的历史质量通过不代表历史耗时通过；同机显式 CLI 结果由主线程单独记录。没有重复创建矩阵 fixture，缺基线、dirty 基线或质量比较失败均直接使测试失败。

独立轻量合同 `test_optimizer_quality_matrix_quality_contract.py` 已 **12 passed in 3.08s**：只读取保存的正式快照，测试期间禁止 `GreedyScheduler.schedule`，没有新增 SGS 解码。覆盖异机同质量可比/完整比较拒绝、四目标真实排程延期导致质量退化、同机三段 runtime 恶化仍被完整比较拒绝、fixture/config/来源/机器元数据守卫，以及真实 tiny 排程“逾期数量更少但加权拖期更高”的合法字典序取舍。三个相关 Python 文件 Ruff、Python 3.8 AST、指定 diff 检查通过；完整矩阵和显式 CLI 历史耗时比较由主线程执行。

该基线由主线程从未修改的 `afc0551e` 独立 clean 参考 checkout 重新运行原核心八例，并通过那个版本的原 CLI 合法提升后复制；SHA-256 为 `120f75c3fcb1a0938677c19f95644bdbd42b5822e0251fecefa11cd049fcf857`，本专项已只读核对文件摘要。它代表修改前的历史参考；当前工作区的 dirty 结果不会被提升为正式参考。基线生成/复制、首次完整对比和最终全门禁回执由主线程记录；本专项没有修改该 JSON 或启动额外矩阵测量。

这项实际历史检查与旧 light/多算法比较入口的迁移状态分开：那些旧 schema 基线仍明确返回 `baseline_migration_required`，缺失的 schema 2 基线仍返回 `missing_baseline`，不能宣称这些旧入口已通过。核心矩阵比较通过也不等于完整入口全局最优或整仓 clean proof。
