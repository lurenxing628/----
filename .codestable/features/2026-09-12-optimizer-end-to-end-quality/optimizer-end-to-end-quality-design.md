---
doc_type: feature-design
feature: 2026-09-12-optimizer-end-to-end-quality
requirement:
status: implemented
summary: 给完整候选比较与优化入口增加可审计质量及耗时基准，并以独立小规模枚举校验四目标完整向量
tags: [optimizer, benchmark, quality, exact-oracle, offline]
---

# 完整优化入口质量与耗时基准

## 问题与范围

原有 `optimizer_quality_matrix` 的八例直接调用 SGS 与 GraphReady repair，能验证核心可行性和同轮不退化，但没有经过完整 `optimize_schedule` 或外层方案比较。原八例及其基线格式保持兼容；新增基准单独记录从已准备好算法输入开始的一次完整候选比较。

用户本轮授权实施算法研究发现的全部优化及验证建设。本项仅新增测试工具与文档，不改产品代码，不引入依赖，不提交或提升基线。

## 实际入口和计时口径

- 使用真实 `run_candidate_comparison`、默认生产图准备器与真实 `optimize_schedule`，覆盖其实际启用的多起点、GraphReady、局部搜索和外层候选选择。OR-Tools 按 Win7 离线主线配置关闭。
- 用 `time.perf_counter` 包围整个候选比较，包含图准备、所有优化阶段及外层选择。排除 SQLite 夹具初始化、结果审计和源码回执散列。
- 默认从每次真实优化入口的 raw `outcome.search_report["decoder_invocations"]` 读取原生 `GreedyScheduler` 实例累计计数；绝不 patch `GreedyScheduler.schedule`，避免破坏 SGS 原生复用认证。仅观察 `OptimizationSearchReportState.mark_candidate_accepted` 已有目标分数，不替换解码器、评分器或时钟，不在计时内额外重算目标。
- `first_improvement_ms` 表示相对本次第一个生产接受方案，首次接受严格更优目标元组的时刻；没有改进时为 `null`。同分接受不算改进。
- 明确采用生产支持的 `score_only` 选择策略，以锁住所选目标的词典序合同；此基准不宣称覆盖默认 `balanced` 的图健康容差选择。
- 耗时是单次诊断样本；默认跨快照守卫 `旧耗时 × 3 + 250ms` 用于识别大幅退化，不能把单次比值当稳定提速比例。正式提速结论应在独占机器同预算下重复运行并报告分布。

## 代表场景

每个场景均覆盖四个正式目标：`min_overdue`、`min_tardiness`、`min_weighted_tardiness`、`min_changeover`。

| 场景 | 工序数 | 有效约束与证据边界 |
|---|---:|---|
| tiny_improving | 4 | 固定单资源、不同交期/优先级/族；存在可严格改进的初始顺序，有独立精确最优值 |
| tiny_chain | 4 | 单批严格链、单资源；合法没有改进，四目标精确最优 |
| shift_pool | 48 | 8小时班次、两段停机、共享人员、TYPE1仅一台合资格机器 |
| wide_parallel_chains | 24 | 12条可并行批内链，图宽度12，每条链独占一组合格固定机器/人员，共12组；班次和停机，真实原生SGS复用命中 |
| frozen_ready_external | 16 | 已冻结工序种子不可改、未齐套但有未来齐套日、外协自然日周期、班次/停机/资源资格 |

全部使用纯合成数据和内存 SQLite。宽图是当前正式入口支持的并行线性批内链，不冒充任意跨批 fork/join DAG。冻结是已经准备好的固定 seed 约束，不代表完成业务冻结识别的端到端验证。

原生 SGS 复用仅在 ready 集中的固定候选机器和人员互相独占时启用，因此宽图用12组独立资源验证有收益的适用域；共享与稀缺资源继续由 `shift_pool` 和 `frozen_ready_external` 验证完整评分路径，不给宽图保留不成立的共享/稀缺标签。

本基准从准备后的算法输入开始，不包含数据库采集、工艺展开/拆件、执行事实采集或结果持久化；不将普通工序加上 piece 字段冒充拆件流水线覆盖。这些业务入口继续由对应服务测试约束。

## 独立精确 oracle

`optimizer_exact_oracle.py` 不导入生产解码、生产 metrics 或 objective_score。独立核验工序完整性、身份、资源资格、前序、加工时长和单资源不重叠，再从输出计算四个目标的完整向量（含 failed_ops 前缀）。优先级权重按当前契约 3/2/1，交期恰好等于 exclusive due 时计超期但拖期为零。

精确性严格限于 1–6 工序、零释放时间、固定同一台机器及同一人员、24小时连续可用、不随顺序改变加工时间的场景。枚举全部拓扑顺序并从零时刻无空闲执行；任意可行排程都能删除空闲而不增加任何目标分量，故该域内最优完整向量由枚举覆盖。非零释放时间明确拒绝，避免因 makespan 的 `max(end)-min(start)` 定义而夸大最优性。

仅 tiny 两例给出独立最优向量与词典序差距：首个不同维度及其差值、是否达到该目标最优。其它场景明确标记不适用，不给伪下界或泛化最优保证。对某个目标最优不意味着同时达到另外三个目标最优。

## 输出与历史基线

- 每个候选保存真实状态、耗时、优化入口调用计数、SGS decode 数、当前目标 score，以及四个目标的完整向量。
- baseline 和 selected 均保存完整排程；读取快照时重建夹具并重算目标，检查遗漏/重复工序、身份、固定种子、前序、资源资格/冲突、停机、工作日历、齐套下界和外协工时。
- 快照绑定配置、覆盖集合、夹具散列、机器/Python/SQLite/NetworkX信息，以及运行前后的 HEAD、工作区状态和相关源码 SHA-256。新散列范围覆盖完整 core/data/schema 和新旧基准支持模块、oracle、CLI及新测试。
- `decoder_count_mode=native` 的测量元数据标明 `decoder_count_source=native_scheduler_counter`，只接受真实原生正整数计数。旧源码没有该计数接口时必须显式使用 `uncounted`；元数据标明 `unmeasured`，全部总计和候选decode字段为 `null`，不以已评估候选数量充当decode数量。
- 原生计数与未计数模式不能直接作性能比较。旧/新源码都用 `uncounted` 时，两边均保持真实未patch入口且测量模式相同，可以完整比较质量和耗时；新源码另跑 native 模式保留真实调用数。不给旧源码回填计数产品补丁。
- 运行中 HEAD 或被测源码变化的快照仅作诊断，不能比较或提升。运行前后稳定的 dirty 快照可与历史 clean 快照作诊断对照；对照通过仍不构成 clean proof。
- 正式提升只允许 native 模式、全部五场景×四目标的通过快照，要求本机、当前 clean HEAD、源码回执与测量结束时一致；已有基线不得通过提升操作掩盖质量/耗时退化。
- 质量比较按各行实际配置目标的完整词典序向量判断；其它目标保留完整诊断值，不误把合法目标权衡当作所有目标同时不退化的要求。

## CLI

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_end_to_end.py run --output /tmp/aps-e2e-current.json
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_end_to_end.py check --snapshot /tmp/aps-e2e-current.json
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_end_to_end.py compare --baseline /tmp/aps-e2e-old.json --actual /tmp/aps-e2e-current.json
```

跨旧/新源码做耗时对照时，两边同用：

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_end_to_end.py run --decoder-count-mode uncounted --output /tmp/aps-e2e-uncounted.json
```

`run` 支持重复 `--scenario` 和 `--objective` 做窄范围诊断；子集不能提升完整正式基线。`update-baseline --snapshot … --baseline …` 是独立显式操作，基线文件名需符合工具保留前缀；本轮没有执行提升。

旧 clean 版本对照应在主线程准备的 `/private/tmp/aps-algorithm-implementation-20260912/base-source` 中使用同一基准夹具与预算运行，并完整保留其真实 HEAD/dirty 状态；复制新工具到旧树会产生 dirty 工具覆盖，不能把它标成原始 clean 版本实测。已有冻结 clean 快照可直接用于新 dirty 诊断对照。

## 验证与接入

- `test_optimizer_exact_oracle.py`：独立显式预期向量、交期边界、4/6节点枚举、合法无改进、非法资格/前序/资源。
- `test_optimizer_end_to_end_matrix_contract.py`：真实完整入口 tiny 四目标、合法无改进链、有效冻结/齐套/外协以及排程序列化故障注入。
- `test_optimizer_end_to_end_snapshot_contract.py`：格式、配置、来源、机器、历史比较、基线生命周期和诊断隔离。

真实计时模块统一登记串行分片，避免模块 fixture 被重复建立和并行 CPU 争用；必跑注册由主线程统一修改，避免并发编辑注册文件。完整20例和正式质量门禁由主线程在产品修改稳定后串行运行，结果以主线程回执为准。
