---
doc_type: feature-design
feature: 2026-09-12-optimizer-budget-efficiency
status: approved
summary: 统一候选比较与优化阶段的预算，并在可证明的原生输入范围内减少重复多起点解码。
tags: [scheduler, optimizer, performance]
---

# 目标与授权

用户已授权实施算法研究提出的改进。本项处理外层候选、内层优化阶段预算、multi-start 决策等价去重，以及图搜索中实际解码成本与有限邻域覆盖的分配；不改变排程硬约束、评分、持久化或外层候选方案数量。

# 方案

- 外层使用 `time.monotonic`，建立一个总 deadline。以 `剩余时间 / 剩余方案数` 为基准份额，再按已完成方案的实际严格改善及实测耗时给下一方案有界反馈；每个尚未尝试方案至少保留半个基准份额。提前结束的时间回到后续方案池，图准备也计入 slice。
- `SearchBudget` 把同一个 clock、assigned deadline、outer deadline 下传 `optimize_schedule`。已有执行中的一次 SGS 可以完成；到达 deadline（含相等）后不启动下一次解码。未开始解码就耗尽预算的方案明确标为 skipped，不能伪造 completed。
- 内层先跑正式多起点基线，再让早期多起点/可选 warm-start 使用有限份额，保留图候选及现有 repair、非图局部搜索的时间。阶段预留和真正总预算耗尽分别留痕。
- `assigned_time_budget_ms` 公开准确的方案分配值；配置秒数保留用户输入语义，诊断另记准备时间、有效优化时间和不可抢占的单次解码超时。
- 多起点只缓存一次运行中已成功完成的原生调度决策。必须保留每种策略参数和排序输入的生产校验，并证明完整批次 override 后策略不再影响排程。非原生、可变回调/日历和不满足证明条件的输入继续完整解码。
- 实际 workbench 的 `_CandidateTrialConfigService` 常把策略、模式、规则各锁成一种，因此外层预算修复直接覆盖它；`4 × 3` 多起点去重主要覆盖直接 optimizer 默认 allowlist 路径，不能混写覆盖范围。

# 接口与验收

- 新增 `optimizer_search_budget.SearchBudget`；`optimize_schedule(..., search_budget=...)` 使用该预算的时钟和截止点。
- 外层全部广告方案保留 completed/failed/skipped 真状态与原选择规则。
- 测试锁定：总预算跨方案共享、准备耗时计入、边界 `now == deadline` 不启动、单次解码超时只完成当前解、基线保留、图阶段获得机会、阶段停下不冒充全局超时。
- 测试锁定：等价多起点减少实际解码且最佳分数/结果不变；派工规则、资源、seed、图和输入变化不能被错误合并；无效参数及意外异常仍按原合同暴露。
- Python 3.8 / Win7 兼容，无新依赖。只运行局部验证，本项不宣称最终 HEAD clean-worktree proof。

# 文件边界

现有文件限于 `schedule_optimizer.py`、`schedule_optimizer_steps.py`、`schedule_candidate_runner.py`、`schedule_candidate_runtime_helpers.py`、`optimizer_step_report_hooks.py`；新增预算、去重窄职责 helper 和对应测试。必要拆分保持原函数导入入口可用。实现时将 multi-start 枚举/执行拆到 `optimizer_multi_start.py`，结果类型/基线包装/测量拆到 `optimizer_outcome.py`，避免原文件跨 500 行门禁。公共字段投影由主代理协调。

测量补充：原生 `GreedyScheduler` 由并行实施增加实例 `_decode_invocations`，本项只在普通及基线结果的 raw `search_report.decoder_invocations` 投影真实整数计数；没有该原生计数器的 stub 不报伪零。量尺无需 patch `schedule`，不会因为观测而关闭原生优化。

收益反馈补充：`CandidateBudgetFeedback` 只观察 completed、同目标、完整成功证据、规范全长分数和正有限耗时。首个可比较结果只建立基线；后续严格优于已观察最优分数时，事件率为 `1 / elapsed_seconds`，下一份额系数为 `1 + equal_slice / (equal_slice + elapsed_seconds)`，并受其他方案的最低保留份额约束。已测但未改善时系数为 0.5；缺证据/零耗时/不完整分数保持中性，最后一个候选取得剩余时间。这是有界反馈启发式，不预测下一方案必然改善。内层 25/35/65 截止比例继续作为既定阶段保留，所用绝对秒数随外层分配改变。

加载边界补充：去重 helper 不再硬导入 scheduler 日历/引擎模块。CalendarService 初始化时由 C 登记独立原生证书，consumer 通过纯 runtime getter 读取；原生方法身份不会在 helper 首次使用时重新捕获，硬加载目录环不通过改债务基线掩盖。

# 图候选成本与有限动作覆盖

完整入口的 `shift_pool` 反例证实：外层方案 completed 并不表示内部搜索完成。1 秒内部预算可能只留下两次 repair 解码，新增动作交错也会把原 batch 家族的首代表推到截止之后。原固定 25% repair 时间预留继续保留，并叠加依据已观测成本的准入判断；不延长总截止，也不调整正式质量比较。

只统计已经完成并返回候选的 profile 评价正耗时，范围为该 profile 的构造、真实 SGS 与正式指标计算。缓存命中、构造拒绝、抛错及零时钟样本不冒充正耗时解码样本。以样本累计秒数除以样本数得均值 `c`；当前最佳可修补 elite 的实际 batch 家族代表数受每轮邻居上限、原 repair 候选预留和下一次 profile 后的剩余候选数共同限制，记作 `k`。预留预计秒数 `r = min(k*c, 图阶段初始剩余时间, 显式 repair 时间上限)`。若下一次 profile 的预计成本 `c` 加 `r` 超过当前剩余时间，就提前转向 repair。没有 elite、repair 禁用或没有正耗时样本时不启用该判断。

这是实测成本支持的机会分配启发式，不承诺下一次解码时长等于均值，也不承诺候选改善。真正的 deadline、60 总候选、每轮 8 项和 top_k 检查仍是最终边界；未开始的解码不能因估计而越界。raw `profile_efficiency` 记录样本数、均值、家族代表数、估计成本、受上限约束后的预留与明确停止原因。具体家族前缀与基础/增强语义池的合同见同轮 `graph-search-neighborhoods-ff-note.md`。
