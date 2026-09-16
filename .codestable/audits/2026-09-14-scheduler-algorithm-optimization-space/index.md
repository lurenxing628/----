---
doc_type: audit-index
audit: 2026-09-14-scheduler-algorithm-optimization-space
scope: 排产算法层可优化空间评估——core/algorithms、core/algorithm_runtime、core/algorithm_contracts、core/services/scheduler/run 的 optimizer_*、core/services/scheduler/graph、日历引擎热路径；维度取性能、解质量、可维护性、架构偏离（安全维度对单机离线排产算法不适用）
created: 2026-09-14
status: active
total_findings: 16
subagents_used: 5
verified_by: 主代理实测（SMTWT 250 / FJSP mk01-mk10 / 生产质量矩阵 8 例 / 端到端矩阵 20+2 例 / 1000 工序 cProfile / 棘轮与长跑基准）+ 5 个 Fable 5.1 只读子代理（S1 热路径、S2 搜索空间、S3 GraphReady、S4 目标与预算、S5 可维护性）
---

# 排产算法可优化空间审计（2026-09-14）

## 范围

用户诉求"看一下当前的排产算法有没有可优化的空间"，随后追加"有优化空间就去优化，压榨优化空间"。本审计是实施前的发现清单；实施记录另见 `.codestable/refactors/2026-09-14-*` 与 `.codestable/features/2026-09-14-*`。

扫描对象：

- 解码器：`core/algorithms/greedy/dispatch/{sgs,sgs_scoring,sgs_reuse,sgs_graph,batch_order}.py`、`core/algorithms/greedy/{scheduler,internal_operation,auto_assign}.py`、`core/algorithm_runtime/{internal_slot,busy_block_skip,downtime,owned_timeline,sgs_estimate_reuse,slot_overlap_reuse,resource_quality,run_state}.py`
- 日历：`core/services/scheduler/{calendar_engine,calendar_service,calendar_native_timing,calendar_sgs_certificate}.py`
- 优化器：`core/services/scheduler/run/optimizer_*.py`（54 文件）、`schedule_optimizer*.py`、`schedule_candidate_*.py`
- 图：`core/services/scheduler/graph/*.py`、`run/schedule_graph_*.py`
- 文档：`scheduler-global-optimizer` roadmap、2026-09-12 A–K 批次记录、2026-06-29 / 2026-07-20 两次算法审计、`service-scheduler.md`

## 本轮实测基线（当前工作区，dirty，仅作对照尺子）

| 尺子 | 结果 | 含义 |
|---|---|---|
| SMTWT 250 实例（vs Moore-Hodgson 精确最优，1s 预算） | SGS 局搜改进 209/250，gap 16.16→6.82；batch_order 局搜 161/250，gap 15.40→10.78 | 与 2026-06-29 记录逐位相同，9 月性能批次在此路径行为等价；局搜后平均仍比最优多 6.8 个延期批次 |
| FJSP mk01/04/06/08/10（BKS 参考，20s） | improve 对 greedy+图：46/51、78/83、88/90、532/532、277/277 | 20 秒搜索平均只多赢约 1%，mk08/mk10 一无所得 |
| 生产质量矩阵 8 例（48 工序） | improve 超期 12→8、加权拖期 2187→1189，耗时 0.11s→7.4s | 交期场景下搜索层有真实收益，代价 66 倍时间 |
| 端到端矿阵 20 例 + 5 档复验 2 例 | 工作台 3 档/5 档图权重候选分数向量在 20/20、2/2 用例里几乎全同 | 外层候选重复计算，见 finding-06 |
| 1000 工序单机密集 cProfile | 评分 285,150 次、时隙估算 289,150 次（与 09-12 记录的"旧代码"数字一字不差），84% 时间在时隙估算，每步平均评 95 个就绪工序 | 09-12 增量评分复用在该路径零命中，见 finding-05 |
| S1 真实日历 1000 工序 | 固定资源单次解码 5.1s；自动派工单次解码 **55.6s**（估算 576,549 次，每估算 42 次日历策略解析） | 5 秒默认预算下 improve 在千级工序上退化为一次解码 |

## 总评

排产算法工程上成熟（合同、报告、去重、预算、fail-loud 都在），但**产出质量被单次 SGS 解码成本卡死**：解码器每一步对全部就绪候选重做完整时隙估算，日历算术按天循环，认证与重复估算叠加，使千级工序一次解码要 5～55 秒；而生产默认 5 秒预算又被工作台外层 6 个候选六等分，其中 5 个图候选重复跑同一套 29 档内层组合，导致多起点、GRASP/IG、图候选池、精英修补、局搜在生产规模上一次都轮不到。搜索空间本身也窄：SGS 起点只有 3 个离散派工规则（达最优率 17.6% 是 best-of-3 的结构上限），batch_order 局搜每状态最多 6 个确定性邻居且 200 次迭代 0.2 秒用完。共 16 条发现：性能 7 条（P0 3 / P1 4）、质量 6 条（P1 5 / P2 1）、可维护性 1 条（P1，含 5 个子项）、架构偏离 1 条（P1，含 3 个子项）、并行机会 1 条。

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 01 | performance | P0 | high | SGS 每步对全部就绪候选全量重评分，无依赖失效 | [finding-01.md](finding-01.md) |
| 02 | performance | P0 | high | 日历算术按天循环并重复解析同一时刻策略，占解码 35–40% | [finding-02.md](finding-02.md) |
| 03 | performance | P1 | high | 忙段闭包"每跳认证税"是闭包收益的 10–16 倍，且对自动派工探测基本不生效 | [finding-03.md](finding-03.md) |
| 04 | performance | P1 | high | 自动派工同一状态下重复估算：胜出对复算 + 正式放置整套重跑 | [finding-04.md](finding-04.md) |
| 05 | performance | P1 | high | 2026-09-12 增量评分证书在生产输入类型下结构性不可达，命中 0 仍付开销 | [finding-05.md](finding-05.md) |
| 06 | performance / quality | P0 | high | 外层"1 基线 + N 图权重档"各起独立内层优化器，5 档输出重复，预算等分使内层搜索零机会 | [finding-06.md](finding-06.md) |
| 07 | quality | P1 | high | 候选对比 allowlist 收窄使多起点退化为 1 起点、SGS 规则邻域必 noop | [finding-07.md](finding-07.md) |
| 08 | quality | P1 | high | SGS 起点搜索空间只有 3 个离散派工规则，ATC k 写死，达最优率 17.6% 是结构上限 | [finding-08.md](finding-08.md) |
| 09 | quality | P1 | high | batch_order 局搜邻域确定性且每状态 ≤6 个，迭代上限按配置秒数派生，预算利用率 4% | [finding-09.md](finding-09.md) |
| 10 | quality | P1 | high | 精英修补批次邻域的基座不是精英本身，恒等决策解出不同排程 | [finding-10.md](finding-10.md) |
| 11 | quality | P1 | high | 图指标与"关键块"全部资源不感知，没有解码后析取图 | [finding-11.md](finding-11.md) |
| 12 | performance | P1 | medium | 图候选 29% 解码后才发现重复；邻域急切构造、指纹双算、容量无记忆化 | [finding-12.md](finding-12.md) |
| 13 | quality | P2 | high | GRASP/IG 名不副实；v2 键单特征字典序；run 级预算被单次预算封顶；balanced 选优容差残留 | [finding-13.md](finding-13.md) |
| 14 | performance | P1 | medium | 外层候选彼此独立、可进程级并行（机会项，受 Win7 打包与日历连接约束） | [finding-14.md](finding-14.md) |
| 15 | maintainability | P1 | high | 留痕/接受代码 4–5 份复制且语义漂移；54 个 optimizer_* 平铺压线；指纹五套；proof harness 住生产包；死旋钮 | [finding-15.md](finding-15.md) |
| 16 | arch-drift | P1 | high | run/ 深钻算法层内部而非 façade 且无 fitness 守卫；service-scheduler.md §4/§10 脱节；大小门禁不覆盖算法层 | [finding-16.md](finding-16.md) |

## 按维度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---|---|---|---|
| performance | 3 | 5 | 0 | 8（06 双计） |
| quality | 1 | 5 | 1 | 7（06 双计） |
| maintainability | 0 | 1 | 0 | 1 |
| arch-drift | 0 | 1 | 0 | 1 |
| **合计（去重）** | **3** | **11** | **1** | **16**（06 同时计入性能与质量） |

## 与既有记录冲突（需要回写的地方）

1. `.codestable/refactors/2026-09-12-sgs-incremental-scoring/` 的命中数据全部基于 `SimpleNamespace` 夹具；生产 `schedule()` 传入的是 `OpForScheduleAlgo`，不在 `sgs_reuse.py:34` 类型白名单里，实测命中 0（finding-05）。
2. `.codestable/audits/2026-06-29-scheduler-optimizer-actuator-misplacement/index.md` 称 SGS 局搜"已修、真实切换 slack/cr/atc"：只对绕过候选对比的直接调用成立；默认生产路径（图分析 on → 候选对比 → trial allowlist 收窄）该邻域候选集为空、必 noop（finding-07）。且 209/250、gap 6.82、17.6% 与"greedy 三规则取最优"逐位相同，"局搜改进"实为"换 ATC"（finding-08）。
3. roadmap `scheduler-global-optimizer-items.yaml` 里 `graph-ready-v2-elite-local-repair` 备注"生产 core 仍未落地 top-K/max_neighbors/…"、`graph-ready-v2-portfolio-integration` 备注"未完成 repaired 生产来源"均已过期，代码已落地；`graph-ready-v2-candidate-portfolio` 写"19 个 profile"，当前 29/31 个。
4. 本次任务简报把 A12 记为"2026-07-20 已修"，实际仍是语义立案未动代码（`core/models/objective.py:33-38` 仍 4 键）；A18 完成性哨兵的落地日期是 2026-09-08。
5. 记忆 `graph-ready-v2-empty-due-bydesign-degrade` 中"非严格模式下非空非法交期占位降级"与所有已提交版本不符：`optimizer_graph_ready_v2_features.py:302-317` 一律 fail-loud，文档 §4 是对的，记忆需更正。
6. `service-scheduler.md` §4 规模数字（36→54 个 optimizer 文件、73/17686→95/20771）、"scoring.py 引 ready_queue"（从未成立）、§10 5/17 个行号锚点漂移。

## 下一步（用户已授权"压榨优化空间，按自己的想法来"，本轮直接实施）

- **第一梯队（解码提速，行为等价，可用 payload 哈希证明）**：finding-01 依赖失效重评分、finding-03 认证税上提、finding-04 胜出估算交接、finding-02 日历热路径；目标是把千级工序单次解码压到原来的三分之一以下。
- **第二梯队（预算与候选结构）**：finding-06 外层图候选共享内层解码结果 + 按候选族分配预算，让第一个图候选真正跑得起内层组合与修补。
- **第三梯队（搜索质量小修）**：finding-10 修补基座改父候选解码序、finding-12 首解码给 v2 profile / 惰性邻域 / 单次指纹。
- **暂不动、留给后续 cs-issue / cs-refactor**：finding-07（需先确认 PR7b 锁定 allowlist 的产品意图）、finding-08/09/11/13（属搜索空间设计，宜走 roadmap ALNS 段）、finding-14（需 Win7 实机验证 spawn）、finding-15/16（可维护性与文档，独立重构）。

## 实施记录（2026-09-14 同日）

- finding-01/04/06 已修，finding-05 被见证缓存取代；设计与证据见 `.codestable/refactors/2026-09-14-scheduler-decode-speed-and-candidate-dedup/`。
- 实测：固定机人解码 3.3 倍、自动派工 2.7 倍；1000 工序密集工作台画像 22.56s → 7.71s（候选载荷哈希不变）；端到端 5 场景中 3 个场景 6 次优化器降到 2 次，选中方案分数全部不变。
- 第二阶段（同日）：finding-02 已修——不是累计工时索引，而是解码内日历纯函数备忘（重复率测量 96.5%–99.6%）；finding-03 已修——每跳 `inspect.getattr_static` 换成逐项等价的快速静态读取，认证粒度不变；机人对试算加"扫描区间外新增忙块不影响结果"的再验证。实测 1000 工序自动派工一次解码 23.5s → 4.94s（缓存关 35.97s），固定机人 1.2s → 0.52s，密集画像 7.71s → 6.93s，质量矩阵 medium_shift_pool 改进阶段约 7s → 3.5s；结果哈希、候选载荷 sha、质量矩阵分数全部不变。
- finding-07 已修（2026-09-14 用户裁决：规则池属于优化器内部搜索维度，不属于候选可比性的锁）：候选试跑不再收窄 `VALID_DISPATCH_RULES`，采用规则如实上报；端到端 20 例选中方案 1 例更好、19 例相同、0 例更差。
- finding-08 已修（`.codestable/features/2026-09-14-sgs-atc-k-ladder/`）：ATC 的 k 变成优化器可搜的离散梯子（默认仍 2.0，配置页仍三规则），令牌 `atc:k=<值>` 贯通参数解析、SGS 评分、多起点（仅无图上下文）、换规则邻域与决策去重；SMTWT 250 实例真实局搜 gap 16.16 → 4.14（此前 6.82），端到端 20 例选中方案 1 例更好、19 例相同、0 例更差。接线时发现并修掉多起点决策缓存用枚举值作键会剪掉梯子令牌的缺陷。
- finding-13 第 1 项部分落地（`.codestable/features/2026-09-14-graph-ready-iterated-greedy/`）：图阶段修补后新增真正的迭代贪心（拆除→停放→按真实解码最优重插，以上一轮结果为父），来源 `graph_ready_v2_iterated_greedy`，默认只用修补剩余预算。SMTWT 250 实例经图阶段实测：从修补分时 30%/50% 分别 42 好/31 差、48 好/72 差（噪声底 4/1），切片内完成不到一轮；生产默认 5 秒预算、默认策略 54 好 / 196 平 / 0 差（gap 4.30 → 4.23）；步进时钟给足解码时 wt40[2] 逾期 5 → 3。短预算下受预算结构限制，预算切分留作单独裁决。finding-13 其余三项与 finding-10 未动。
- 未动：finding-09、10、11、12、14、15、16。
