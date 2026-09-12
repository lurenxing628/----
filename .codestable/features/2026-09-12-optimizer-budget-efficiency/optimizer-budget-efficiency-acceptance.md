---
doc_type: feature-acceptance
feature: 2026-09-12-optimizer-budget-efficiency
status: accepted
summary: 总预算共享、阶段预留、边界停解码及原生多起点去重已实现并通过局部验证。
tags: [scheduler, optimizer, performance]
---

# 实际行为

- 候选比较使用一个 monotonic 总 deadline。以 `remaining / remaining_candidates` 为基准，已完成结果的实际改善反馈有界调整下一份额；每个未试方案至少保留半个基准份额。准备图也计入，未使用的时间自然留给后续方案。方案数量和 completed/failed/skipped 枚举不变。
- 优化入口使用传入的同一时钟和截止点，并受配置的单次优化上限约束。先取得正式基线，再按 25% / 35% 截止点结束多起点和可选 warm-start；非图构造在 65% 截止，后段留给局部搜索。图阶段保留原 repair 预留，并按已经完成 profile 的真实评价成本检查下一 profile 是否会挤掉实际 batch 动作家族代表机会。
- `now == deadline` 不启动下一次解码，构造排序完成后再次检查。已开始的真实 SGS 可以完成，超时如实留痕。准备耗尽 slice 的方案明确 skipped；未知异常继续抛出，不转成失败候选或可采用结果。
- phase slice 用完记录 `reserved_for_later_phases`，不冒充整个优化已超时。公共 `assigned_time_budget_ms`、中文说明及诊断的准备/实际优化/超时毫秒数区分配置预算和本方案分配值。
- 原生解码计数通过 `search_report.decoder_invocations` 返回；普通及基线返回都验证过，没有原生计数器的 stub 不报 0。该字段不进入公共投影。

# 去重证明与范围

只有原生 strict scheduler、规范完整 batch override、原生对象/容器及原生日历 SQLite 事务满足快路径。键包含输入值快照、有效派工方式/规则、起止范围、资源/seed/图和日历策略缓存、SQLite `total_changes` 与 `data_version`。完整 override 使排序策略不再进入 dispatch 决策，但每个策略仍执行生产参数校验及排序构造；不同规则不合并。只有真实完整成功解码才记 seen，失败候选不记。

类/实例方法被覆盖、非事务、自定义对象或日历不尝试去重。若 SQLite authorizer 拒绝可选 PRAGMA 缓存探针，只关闭该次缓存判断，真实排程仍按原入口执行；真实参数和解码异常没有被该探针捕获。WAL 双连接切换事务、同连接改动及输入/配置/资源/seed/图/策略缓存变化均有失效测试。

原生 SGS 与 graph SGS 两个独立小例中，4 种排序 × 3 条规则由 12 次真实解码降到 3 次，最佳分数和输出指纹集合相同。实际 workbench 通常锁定一种策略/规则，不能把这个 `12 → 3` 直接当作工作台节时比例。

# 实际改善反馈补齐

- 观测必须是 completed、同一规范目标、完整成功/完成性证据、目标 schema 全长且有限非负的规范分数、正有限实测耗时。计数维度必须是整数值；缺字段、不同目标、未完成、未知目标值、NaN、布尔分数或无有效计时均不产生奖励或惩罚。
- 首个有效样本建立比较基线；之后只有严格优于已观察最优分数才记一次改善事件。使用事件率 `1 / elapsed_seconds`，不把不同目标的小时和次数硬拼成虚构收益。下一份额系数为 `1 + equal_slice / (equal_slice + elapsed_seconds)`；已测且未改善用 0.5；始终给其他未试方案保留至少半个当前均分份额，末候选取得剩余。
- 对相同的 12 秒剩余、3 个未试候选，1 秒内取得严格改善对应 7.2 秒下一份额，4 秒取得同类严格改善对应 6 秒；均保留其他候选最低机会。这个测试仅证明已观测成本会改变分配，不证明下一方案收益。
- `optimizer_budget.allocation_feedback` 仅有固定数量的标量诊断：策略/原因、观测次数、事件率、实测耗时、候选序号、实际系数及保留毫秒数，无 raw score/history 对象。内层已报告的阶段比例保持，绝对预算随反馈改变。
- 补齐后预算及 candidate runner 小测试 **48 passed**（含新增 24 个反馈正反、成本差异、主链接线和保留份额用例）；Ruff、Pyright、Python 3.8 语法及官方复杂度/体量检查通过。

# 硬加载环修复

去重 helper 删除日历、引擎和仓库类的顶层导入，读取 C 在 CalendarService 初始化时登记的独立 certificate；保留 exact 类型/方法、同连接及逐个 DayPolicy 实例守卫。新增 6 个回归证明 helper 加载前已有方法覆盖不会被重新认证，第二个 policy 的实例覆盖亦拒绝。去重合同 **31 passed**，与 C 联合 **61 passed**；正式 `scan_import_cycles --fail-on-new-cycle --quiet-when-clean` exit 0，未修改循环基线。证据不扩大为任意早于 CalendarService 首次加载的覆盖顺序。

# 验证证据

- 新增：`test_optimizer_shared_budget.py`、`test_optimizer_multi_start_budget_integration.py`、`test_optimizer_multi_start_decision_dedup.py`；原 39 个参数化用例，反馈补齐和原生证书回归再新增 30 个。
- 新用例覆盖真实 SGS 的基线、graph 与 repair 获得份额；一次真实解码在 4 秒预算后于 4.5 秒完成时只有 1 次调用，下一次未启动且记录 500ms 超时；这些时间为受控时钟测试值，不是性能实测。
- 与既有 candidate runner、multi-start、search report/profile、GRASP 构造、完整批次、OR-Tools 预算、配置/派工组合、graph-on 合同合跑：170 passed。后续纯职责拆分又独立复跑受影响合同。
- 本项 9 个生产文件及 3 个新测试 Pyright 0 errors；本项生产/测试 Ruff 通过。9 个生产文件通过 Python 3.8 grammar 检查。
- 官方 `scan_complexity_entries`、`scan_oversize_entries` 对本项生产文件返回空列表；不是调整阈值或加豁免。原入口保留类型/函数 alias，multi-start 和结果包装分别拆到窄模块。
- 现有测试中直接通过 `sys.modules` 兼容入口访问模块属性的 test-wide Pyright 仍有静态识别问题；本项没有把其全文件静态检查宣称为通过。实际 pytest 合同已运行并通过。

# 验证边界

本项未执行全质量门禁、未提交、未写业务数据库。只在并行实施工作区做局部验证，不构成最终 HEAD clean-worktree proof。阶段保留及有界实际反馈是实施策略，不代表已证明最优分配或下一候选收益；大规模时间与质量对比由独立端到端量尺汇总，不能由小例推断真实节时比例。

# 限时覆盖回退的后续闭环

`shift_pool` 的旧获胜 `tardy_boundary_move` 已在新 decoder 中按真实原 decision 单独重放，完整 payload 与旧正式 D 结果相同，排除了资源解码把同一决策变坏。只把动作代表前置仍不够：当一秒内只够两次 repair 时第三家族仍没有机会。将代表前缀与上述实际成本准入组合后，限定同 1 秒单方案 / 5 秒总比较的诊断探针恢复了原 MO/MC 覆盖；MT 还依赖 E 维护的明确基础特征排序与 A 的同语义 repair 接线。

已注册的 `test_optimizer_profile_budget.py` 覆盖成本均值、真实家族数、邻居/候选/显式局部时间上限、无 elite/repair 禁用、零与非法耗时；`test_optimizer_profile_predecode_dedup.py` 锁住缓存命中不加入成本样本。控制时钟的真实 SGS 用例里，每次评价消耗 0.2 秒时先完成两个 profile，然后在原 1 秒截止前启动三个 repair；没有扩大时间或候选上限。该控制时钟数据是合同，不是性能结果。

当前集成的限定真时钟探针为 `a-shift-integrated-{min_overdue,min_tardiness,min_changeover}-i-trace.json` 与 `a-frozen-integrated-i-trace.json`（目录 `/private/tmp/aps-algorithm-implementation-20260912/`）。MO 完整向量 `(0,10,2297,1474,269.5,0)` 优于旧 D；MT 为 `(0,1423.5,12,3058.5,294.5,0)`，MC 为 `(0,0,10,1571.5,2469,295.5)`，均恢复旧 D；frozen/minT 保持 `(0,171,4,285.5,135,1)`。这些含 trace 的局部运行不代替主线程的独占、无探针完整矩阵验收。

当前 A 接线与 E 基础/增强候选集成后，八个受影响的既有模块合跑 **160 passed in 13.05s**（`a-coverage-cost-i-tests.log`）；四产品及两个预算/多轮测试 Pyright 0 errors，四产品与四个改动测试 Ruff 通过。官方 `scan_complexity_entries`、`scan_oversize_entries` 对上述八个 Python 文件均返回空列表，回执 `a-coverage-cost-i-structure-final.json`。独立定向静态复核未找到新的阻断；不新增测试模块、不修改注册表、阈值或质量基线。

resume1 后的 tiny 次级分数回归由同父排程的 basis 变体重复占用 top_k 名额引起。后续在原 top_k 内按不同 parent 计槽，同 slot 的所有 basis 变体合计每次仍最多 8 项；所有真实未耗尽尾部继续有限轮，原 60/轮数/deadline 不改。六个受影响模块 **156 passed in 15.94s**，原 SMTWT 多轮严格改善与硬上限合同保留。真 tiny 恢复 `(0,4,2,12,12,26)`，限定 shift_pool 三目标和 frozen/minT 也保持达标；详细因果、共享 slot 与跨 basis 决策去重范围见 `graph-search-neighborhoods-ff-note.md` 的 resume2 记录。
