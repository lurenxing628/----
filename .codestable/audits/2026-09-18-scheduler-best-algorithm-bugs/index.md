---
doc_type: audit-index
audit: 2026-09-18-scheduler-best-algorithm-bugs
scope: 当前生产最优排产算法（improve + 候选去重 + GraphReady v2 三阶段轮转 + SGS 加速解码）的 bug 与优化空间——core/algorithms、core/algorithm_runtime、core/algorithm_contracts、core/services/scheduler/run 的 optimizer_* / schedule_candidate_*、日历引擎与在制预留覆盖层；维度取正确性、报告口径、搜索质量、预算利用、性能
created: 2026-09-18
status: active
total_findings: 19
subagents_used: 5
verified_by: 主代理实测（端到端 20 例 / SMTWT 250 局搜 / 质量矩阵 8 例对 09-08 冻结基线 / tests/algorithm+candidate+scheduler_graph 串行 3123 passed）+ 5 个 Fable 5.1 只读子代理（S1 解码加速层差分 240 实例、S2 检查点续排与尾段复用 ~250 次续排、S3 图阶段轮转与 IG、S4 外层候选与局搜预算、S5 SGS 派工评分与目标）
---

# 当前最优算法 bug 与优化空间审计（2026-09-18）

## 范围

用户诉求"看一下当前的最优算法还有没有什么 bug 和优化空间"，随后明令"全修，按你的意见来办"。本审计是 HEAD `1c1ed23c`（09-14～09-16 落地的解码提速、检查点复用、ATC k 梯子、图阶段迭代贪心与三阶段轮转之后，且这批代码按用户要求未跑过全量门禁）上的发现清单；实施记录另见各 finding 的"处理结果"与 `.codestable/compound/2026-09-18-decision-*.md`。

## 本轮实测基线（HEAD 干净工作区，受同机并行探针的 CPU 争抢影响，仅作对照尺子）

| 尺子 | 结果 | 含义 |
|---|---|---|
| SMTWT 250 实例局搜（1s，vs Moore-Hodgson 最优） | sgs 模式 gap 16.16 → 4.13、改进 211/250；batch_order 15.40 → 10.78、161/250 | 与 09-14/09-16 记录逐位一致，无退化；batch_order 局搜仍在 0.2s 内撞 200 次迭代 |
| 端到端 20 例（1s/候选，5s run） | 20/20 passed；wide_parallel_chains 3 档去重为 1 次优化器 | 候选去重生效 |
| 质量矩阵 8 例对 09-08 冻结基线（10s） | 主目标 8/8 不劣、6/8 更好；tiny 耗时 48ms → 950ms、medium 4.1s → 10.0s | 轮转把剩余预算全部用掉，小实例搜索空间耗尽后仍烧预算 |
| 定向测试 | tests/algorithm + candidate + scheduler_graph 串行 3123 passed；xdist 下 74 个红全是"矩阵不得在 xdist 下跑"守卫 | HEAD 无红 |
| S1 差分 | 240 实例（12,256 工序）加速全开/全关/仅关见证/仅关备忘/09-13 基线树 payload 哈希全同；~250 次续排与尾段复用一致 | 加速层等价性成立 |

## 总评

解码加速层、检查点续排、尾段复用的等价性在 240 个随机与压力实例上全部成立，确定性与截止控制也对得上合同；问题集中在上层搜索与报告：IG 采纳新现任失败后留下过期 reference 会让整次排产崩溃（P1）；修补与 IG 的父方案不是精英本身，生产默认自动派工场景恒等决策 10/10 不复现（P1）；图档触达不到 ATC k 梯子、局搜迭代上限按配置秒数派生且小实例去重关闭（P1）；派工规则把日历小时和工作小时混着除、优先级权重在 slack/CR 下不起作用（P2）；有在制工序时整套认证加速失效、共享槽位在饱和资源上几乎不命中（P2）。共 19 条：bug/错报 6 条（P1 1 / P2 4 / P3 1）、搜索质量与预算 10 条（P1 3 / P2 6 / P3 1）、性能 3 条（P2 2 / P3 1）。

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 01 | bug | P1 | high | IG 采纳新现任失败后留下过期 reference，下一轮续排签名不一致崩掉整次排产 | [finding-01.md](finding-01.md) |
| 02 | bug | P2 | high | 检查点"输入不支持"不降级而是让整次候选对比失败 | [finding-02.md](finding-02.md) |
| 03 | bug（报告） | P2 | high | IG 启动时"预计父方案解码放不下"被报成 time_budget / skipped_by_budget | [finding-03.md](finding-03.md) |
| 04 | bug（报告） | P2 | high | batch_order 模式下 GRASP/IG 起点轮换派工规则并上报 adopted_dispatch_rule=cr/atc | [finding-04.md](finding-04.md) |
| 05 | bug（报告） | P2 | high | 交期构造起点被采用时 parent_order_* 写的是起点的值 | [finding-05.md](finding-05.md) |
| 06 | bug（报告） | P3 | high | 图档配置 batch_order 时实际以 sgs 解码，CandidatePlan.dispatch_mode 与持久化列仍记 batch_order | [finding-06.md](finding-06.md) |
| 07 | quality | P1 | high | 修补与 IG 的父方案不是精英本身（finding-10 扩大到工序序族、IG 与自动派工） | [finding-07.md](finding-07.md) |
| 08 | quality | P1 | high | 图档触达不到 ATC k 梯子，图阶段全部只用配置规则 | [finding-08.md](finding-08.md) |
| 09 | quality | P1 | high | 局搜迭代上限按配置秒数派生（finding-09 仍 open）且批次数 <10 时决策去重关闭 | [finding-09.md](finding-09.md) |
| 10 | quality | P2 | high | 派工规则把日历小时和工作小时混着除，跨周末错判紧急度，默认 k 下 ATC 退化成近 EDD | [finding-10.md](finding-10.md) |
| 11 | quality | P2 | high | slack/CR 规则下批次优先级基本不起作用 | [finding-11.md](finding-11.md) |
| 12 | quality | P2 | high | 候选预算反馈"上一档无改进→下一档减半"饿死中间档 | [finding-12.md](finding-12.md) |
| 13 | performance | P2 | high | 图档多起点对 3 条规则各解一次，无并列时必同输出 | [finding-13.md](finding-13.md) |
| 14 | performance | P2 | high | IG 起点/换起点/采纳现任都全量重解码已解码方案，并计成 same_fingerprint 拒绝 | [finding-14.md](finding-14.md) |
| 15 | quality | P3 | high | 退火接受名存实亡；自适应破坏规模单向漂移 | [finding-15.md](finding-15.md) |
| 16 | quality（by-design 复议） | P2 | high | 任一批次未完成时目标全分量置 float max，搜索失去信号 | [finding-16.md](finding-16.md) |
| 17 | performance | P2 | high | 有在制工序时整套认证加速全部失效 | [finding-17.md](finding-17.md) |
| 18 | performance | P2 | medium-high | 共享槽位只收录同一认证窗口内的估算，饱和资源上几乎不命中 | [finding-18.md](finding-18.md) |
| 19 | performance | P3 | medium | 全部输出恒等无停滞退出；图模式每步全量 sorted；小实例搜索耗尽仍烧满预算 | [finding-19.md](finding-19.md) |

## 与既有记录冲突（需要回写的地方）

1. `.codestable/features/2026-09-14-sgs-atc-k-ladder/` ff-note 称"图候选仍可通过换规则邻域到达梯子令牌"：`optimizer_local_search.py:304-306` 有图上下文直接跳过整个局搜，换规则邻域只住在局搜里，该说法不成立（finding-08）。
2. 09-14 审计 finding-10 只判定"批次邻域基座不是精英"且单机反例成立：本轮实测生产默认自动派工场景工序序恒等决策也 10/10 不复现，IG 起点同样受影响（finding-07）。
3. 09-15 决定第 5 项"不能把估算不足伪装成到达截止"：IG 启动路径仍报 `time_budget`（finding-03）。
4. 2026-09-08 incomplete-batch-objective 决定接受的"同 failed_ops 一律持平"边界：生产里一个批次缺资质就让整个 improve 预算失去信号，本轮修订（finding-16）。

## 09-14 审计遗留状态

finding-09（本轮 finding-09 扩大）、10（本轮 finding-07 扩大）、11、12、13.2/13.3/13.4、14、15、16 在 HEAD 上状态未变；13.3 的 `run_time_budget_seconds` 只有 `ScheduleService` API 参数可达、web 无调用方。

## 已核对且未发现问题

见证缓存/机人对备忘/共享槽位证书/优先级剪枝/长快照证书的安全前提与 SGS 写集对得上；检查点身份覆盖工序/批次/派工令牌/日历证书/种子/在制释放；发布前完整核对确实执行；退火只影响行走，没有把更差解写进 best 的路径；轮转不会饿死；60 次上限只约束档位+修补、IG 独立 400；随机流只由 version 派生，步进时钟两遍逐项相同；真实时钟总墙钟超出 ≤40ms；三条派工规则公式与手算一致、极端输入无 NaN/Inf、`PYTHONHASHSEED` 无影响；原生类证书除 `__slotnames__` 外未发现其他 CPython 3.8 记账属性。

## 集成后归因与盲审复审（2026-09-18）

四组修复合并到主工作区后，真实时钟端到端 20 例对 HEAD 快照 1 好 12 平 7 差（frozen_ready_external 4/4、shift_pool 3/4），质量矩阵 medium_shift_pool 4 目标全差（加权拖期 1128 → 1199.5）。归因方法：先把 HEAD 分别覆盖成 HEAD+S1/S3/S4/S5 四棵树（用当前文件刷新），两项退化都只由 S3 组逐位复现；再在集成树上对 S3 内部因素逐个与组合开关（真实时钟每配置两遍、结果逐位确定）。端到端退化唯一指向修补的"批次整块搬移"；medium_shift_pool 退化指向"取序基座"（工序级邻域、资源邻域、IG 三处都回到开工序/显式决策序才恢复 1128）。两项连同同日的"钉住解码资源"一起撤回（finding-07 改记 withdrawn）：修补/IG 的邻域越贴近"精确身份"越差，漂移是搜索自由。

盲审（独立 Fable 5.1 子代理，只读，仓库未改动）复审集成后的全部改动，结论与处置：

| # | 判定 | 内容 | 处置 |
|---|---|---|---|
| 1 | major | 远交期（2099-12-31 一类哨兵）让工作小时前缀逐日游走到交期，超百年交期在评分热路径抛错 | 已修：工作小时只在排产视野内计，视野外按墙钟延续（finding-10 处理结果、派工决定第 2 条） |
| 2 | major（裁决级） | `failed_ops` 相同但未完成集合不同的候选按已完成子集比分，可能偏好"丢掉最糟批次" | 记为已知限制，不改行为（finding-16、未完成候选决定第 6 条） |
| 3 | minor | 局搜重启被预算守卫拒绝时记成"重复轮" | 已修：`RestartOutcome.duplicate` 只在扰动顺序已解码过时为真（`optimizer_local_search_restart.py`），合同测试补一条 |
| 4 | minor | 未认证原因的原始异常文本进入候选公开摘要 | 已修：公开字段只给 `uncertified` 代码，原因文本留在方案字段与日志（`schedule_candidate_summary.py`） |
| 5 | minor | 缺 `working_hours_between` 的日历静默退回墙钟 | 保持：连续日历协议，生产日历类型全部暴露该方法并有合同测试锁住 |

盲审同时核对无问题的项：覆盖层认证、共享槽位同效率窗口链、见证缓存挂起、IG 起点/准入/捕获降级、剖面停滞退出、局搜上限、预算反馈、`_required_candidate_setting` fail-loud、公开投影白名单、图档规则范围前提（键序 penalty → 图键 → 派工键）。

## 实施安排（用户已授权"全修，按你的意见来办"）

- 第一波（主工作区并行，文件按归属切分）：S1 修 17/18/19b；S3 修 1/2/3/5/7/14/15 与图阶段报告口径；S4 修 4/6/8/9/12/13 与外层上报。
- 第二波（隔离 worktree `fix/dispatch-semantics`）：S5 修 10/11/16，附两份决定文档与改前改后基准对照，之后合并。
- 各 finding 的"处理结果"在实施完成后回填。
