---
doc_type: feature-acceptance
feature: graph-ready-iterated-greedy
status: passed
date: 2026-09-14
completed_on: 2026-09-15
summary: 以接手源码快照为基线，核验三阶段轮转、IG上下文、检查点和有界交期起点。
tags: [scheduler, iterated-greedy, benchmark, python38]
---

## 结论

四项改进与额外交期起点已实现，SMTWT 250 例在 3 秒与 5 秒预算下、e2e 20 例均逐例无退化，原始数据与运行源码已核对；千工序真实 IG 搜索也完成了有界开关对照。通过的是本次约定的定向验收。本次不运行完整质量门禁，不构成 clean-worktree proof。基线是接手时已有未提交改动的源码快照，不能等同于干净 HEAD 或此前 Agent 的历史源码。

下文保留后续 5000 工序启用实验未通过的历史记录；2026-09-15 已另行修复首解与预算阻塞，最终通过容量项，最新结果见本文末尾的修复链接。历史实验没有被覆盖或追认。

## 完成的实现

| 范围 | 本次结果 | 主要代码 |
| --- | --- | --- |
| 阶段调度 | 三阶段优先取得可用的首次工作机会，随后按实际用时及最近 8 次任务的严格改进率排队；反馈优势有上限。IG 每次试解后可暂停，保留本轮状态。 | `optimizer_graph_ready_stage_scheduler.py`、`optimizer_graph_ready_stages.py`、`optimizer_graph_ready_iterated_greedy_iteration.py` |
| 精英修补 | 暂停/结束时保留正确的未探索尾部与计数；当前更好父解及时取得空位，过时改进不挤掉有效父解，不增加轮数或候选上限。 | `optimizer_graph_ready_repair.py`、`optimizer_graph_ready_repair_accounting.py`、`optimizer_graph_ready_repair_rotation.py` |
| 连贯邻域 | 时间窗、资源窗、迟到/随机生成器按结果调整规模；成功续用，拒绝/变差/中断缩小，原位扩大；停滞换起点时重置规模但保留累计统计。 | `optimizer_graph_ready_iterated_greedy_neighborhoods.py`、`optimizer_graph_ready_iterated_greedy_run.py` |
| 解池及接力 | 同步工序顺序、批次顺序、资源和 profile；换上下文清理不兼容缓存。启动选最好分数层，池选择与邻域随机流独立；退火只改变行走，不改变最终严格择优。 | `optimizer_graph_ready_iterated_greedy.py`、`optimizer_graph_ready_iterated_greedy_acceptance.py` |
| 安全续排 | SGS 状态检查点绑定全部排产输入及日历证书，禁止可变工序经 seed_results 注入时间。续排改进必须在预算内通过全排 score 和业务摘要核对，才可发布及占用已验证指纹。 | `sgs_checkpoint.py`、`sgs_checkpoint_inputs.py`、`checkpoint_calendar.py`、`calendar_checkpoint_certificate.py`、`optimizer_graph_ready_iterated_greedy_incumbent.py` |
| 额外交期起点 | 独立单工序、同一内部机人组合的 min_overdue 输入，增加有界 Moore/Hodgson 排序及探测。估算只提出完整顺序，正式 SGS 验算较差时继续保留原起点。可用 due_date_seed=false 关闭。 | `optimizer_graph_ready_iterated_greedy_seed.py`、`optimizer_graph_ready_iterated_greedy_start.py` |

轮转不承诺一次不可抢占解码用完预算后仍能启动全部阶段。原 60 候选限制用于 profiles + repair，IG 自有独立限制。构造探测、SGS 开始、检查点捕获前拒绝、全量验证与普通 trial 均分别计数。

修补回归曾令同一正式用例从 `[0,171,4,285.5,135,1]` 退为 `[0,171,4,308,112.5,1]`。本次按父解轮转根因修复，恢复原完整断言；保留 `repair-trace-baseline/current/fixed.json`，没有通过降低断言要求掩盖退化。

## 参考实现的准确范围

OR-Tools 源码为 v9.15，commit `551ad10d94835c99e5e1e684500d3db398c0e345`。三阶段用时反馈参考 `ortools/sat/subsolver.h`；规模控制参考 `ortools/util/adaptative_parameter_value.h`；起点、拆修与接受思路参考 `ortools/constraint_solver/routing_ils.cc`、`ortools/sat/synchronization.h` 与 `ortools/sat/cp_model_lns.cc`。本项目是针对 SGS 的实现，不冒称 OR-Tools 原算法的逐行移植；对仅找到定义/测试的 GetUCBScore，不宣称已证实它处于 OR-Tools 生产调用链。

额外交期起点参考 [Moore (1968)](https://pubsonline.informs.org/doi/10.1287/mnsc.15.1.102)，属于另外的经典构造启发。实际 APS 的日历、个别释放时间、权重、资源变化仍由正式 SGS 决定，不宣称一般最优性。代码不根据 benchmark 名称、实例编号或已知答案选择顺序。

## 基线与比较协议

已找回旧 `ig_probe.py`、`e2e_snapshot.py`、20 例端到端原始数据和若干 SMTWT 文本回执。旧 3 秒回执为 8 好 / 238 平 / 4 差，旧 5 秒回执为 54 好 / 196 平 / 0 差。未找到该历史 SMTWT 的全部 250 行原始数据和完整 dirty 源码，不能将这些摘要作为本次验收基线。

本次基线为 `baseline/` 的 5632 文件快照，记录原 HEAD `7034b87303ec10e5d2f40ea704aee0b98770cf9c` 及每个文件 SHA-256。新版 `candidate-v3/` 为 5650 文件快照。两者都保留当时的未提交状态；研究运行目录无 `.git` 时，回执里的 HEAD 为 null，没有伪造提交元数据。

- SMTWT 使用相同 fixture：wt40、wt50 各 125 例，分别 3 秒、5 秒，seed 0、原有候选限制。6 个测量 lane，每 lane 两个隔离进程轮流工作；逐例交替左右先后，计时包含阶段内 baseline、全部试解和验证。
- 此 fixture 将 OR-Library 数据映射为 APS 的 min_overdue，并使用普通优先级；不是对原始任意权重 total weighted tardiness 最优解的认证。
- 胜平负比较正式完整 score 字典序，即 failed_ops 加 objective_metric_keys 定义的指标：SMTWT 为 6 项，e2e 的 min_weighted_tardiness 为 5 项，其余目标为 6 项；无容差或阈值变更。“无一变差”指每个完整目标向量不劣，并不表示所有低优先级指标都逐项不增。
- e2e 使用原 build_end_to_end_matrix 的 5 个场景 × 4 个目标，串行执行；每次 optimizer budget 1 秒、run budget 5 秒，保留排程审计和 tiny oracle。
- 每例保留输入摘要、完整 score、排程摘要、实际 SGS 次数/picks、阶段报告、执行顺序和失败。运行前后及各 worker 起止时复核源码 hash；未比较的失败例不得当平局。
- 研究源码聚合范围为 core/data/tests/_support 的 Python/SQL、vendored benchmark 数据与 schema.sql；整份快照的逐文件 manifest 另存，两种 hash 口径不混用。

## 完整质量对照

| 版本与范围 | 改善 | 相同 | 变差 | 结论 |
| --- | ---: | ---: | ---: | --- |
| candidate-v1，3 秒 × 250 | 44 | 156 | 50 | 未通过，原始失败例保留 |
| candidate-v1，5 秒 × 250 | 61 | 136 | 53 | 未通过，原始失败例保留 |
| candidate-v2，4 组 smoke | 2 | 1 | 1 | 未通过；不是完整矩阵 |
| candidate-v3，3 秒 × 250 | 208 | 42 | 0 | 完整数据与源码审计通过 |
| candidate-v3，5 秒 × 250 | 207 | 43 | 0 | 完整数据与源码审计通过 |
| candidate-v3，e2e × 20 | 2 | 18 | 0 | 完整数据与源码审计通过 |

v1 的全池均匀起点抽样在短预算内经常选到显著更差的父方案，并消耗了邻域随机流；v2 改成最好分数层和独立随机流后，5 秒 smoke 仍有退化。v3 增加通用条件下的确定性交期起点，保留正式 SGS 验证和所有失败回执。未以重跑相同失败版本挑好成绩作为修复。

完整 SMTWT 两组共 500 pairs，全部实际 SGS 计数与报告一致，0 个不可比较样本；e2e 为 20 pairs，同样完整。运行源码聚合 hash：baseline 为 `1d0cd680bdb64f42f2a0a3154f192c1681093dff4f6b9fe8b50f0518e37850cd`，candidate-v3 为 `471b683de06578ee849913ba546508869a3b253681dd1339d40cbe411aff5323`。

额外起点探针对全部 250 例正式 SGS 验算，参照此前 baseline 在 3/5 秒记录中较好的完整分数，结果 207 好 / 43 平 / 0 差。该探针在初始化结束后停止，不是完整 IG 搜索，也不能充当 3/5 秒计时矩阵。

e2e 最终改善发生在 shift_pool 的 min_overdue 与 min_changeover，完整分数的后续分量得到改善。两臂平均 wall time 为 1927.0 / 1984.7 ms；这是限时组合搜索耗时，不是纯解码速度测量。

## 千工序前缀性能

使用正式模型及 CalendarService，100 批 × 10 工序，一组固定机人资源；四档前缀，原顺序和合法后缀交换，重复 3 次，共 51 组配对、102 次正式解码。捕获结果、全排/续排及两份源码的业务输出均等价。

| 固定前缀工序数 | 新版全排均值 ms | 新版续排均值 ms | 全排/续排 | 实际重新派工数 |
| --- | ---: | ---: | ---: | ---: |
| 250 | 2826.6 | 2205.0 | 1.28 | 750 |
| 500 | 2850.2 | 1480.7 | 1.92 | 500 |
| 750 | 2856.2 | 720.2 | 3.97 | 250 |
| 900 | 2848.6 | 238.6 | 11.94 | 100 |

每次捕获四个检查点再续排八次，新版含捕获总耗时均值约 12.207 秒，对应八次全排约 22.763 秒，约 1.86 倍。这是“复用相对全排”的测量：接手版本来已有检查点能力，其对应总耗时约 11.733 秒；新版输入/日历安全核对增加约 4.0% 成本，不能把 1.86 倍称为新版相对旧版的加速。

该 probe 使用 candidate-v1；已经逐文件核对，v1 到 v3 的研究源码只改变 IG 主线、配置和两个起点文件，相关解码模块完全相同，证据见 final-verification.json。固定次数续排不能替代完整 IG 迭代吞吐，另行保留实际搜索探针及边界。

真实 IG 探针为同一 candidate-v3、同一千工序输入、seed 0，两臂各 30 秒，串行先关后开 checkpoint。事先声明只启用原生时间窗生成器、窗口选在末尾 100 个位置；产品正式 IG 拆修、SGS、验证及接受流程仍全部执行，不删除前 900 道工序。

| 真实搜索指标 | 关闭检查点 | 开启检查点 |
| --- | ---: | ---: |
| 30 秒内完整迭代 | 0 | 3 |
| 非 idle 完整迭代 | 0 | 2 |
| 实际开始 SGS / 总 picks | 10 / 10000 | 76 / 11103 |
| 其中续排 SGS | 0 | 73 |
| 捕获 SGS（与验证可重合） | 0 | 3 |
| 全量验证 SGS | 0 | 2 |
| 含捕获、验证的 IG wall time ms | 28624.0 | 29834.1 |
| deadline 超出 ms | 0 | 0 |

两臂最终完整 score 均为 `[0,0,0,0,3,0]`，完整覆盖与资源/前置审计通过。关闭臂未完成一轮，迭代比值没有定义，不能报“无穷倍”或“3 倍”。这是一个固定输入、固定 seed 和声明局部窗口的真实搜索进展证据，不能外推为默认全局搜索或一般提速结论；所有捕获和验证开销已经计入。

## 定向验证与交付边界

- Python 3.8.10 下，12 个相关合同测试文件合计 **265 passed in 41.99s**。覆盖阶段公平/预算、repair 尾部、生成器/退火、完整上下文切换、拒绝去重、正式起点边界、检查点输入/日历变化与全排等价。原始 JUnit 见 focused-final-v3.xml。
- 起点纯构造合同 46 例及真实 SGS 接入合同 4 例包含在上述 265 例中，不重复累计。
- 研究 runner 的失败路径另有 13 个模拟测试；worker 启动、崩溃、传输中断等会保留不完整双臂回执，不以缺失记录算成功。已完成的 v1 runner 副本和结果未被后来的 runner 修正覆盖。
- 最终 44 个修改 Python 文件的 3.8 编译与 Ruff 检查通过；28 个产品文件最大 483 行，最大复杂度 15，无超限；定向 git diff --check 通过。按用户明确要求，不运行完整质量门禁。
- 最后结构检查将 IteratedGreedyRun.finish 的状态判定块拆为私有辅助方法，并修正两个测试文件的导入排版。完整计时矩阵仍绑定原 candidate-v3，未冒称和交付源码逐字节相同：辅助方法内联后，整个 run 模块 Python 3.8 AST 与计时版本完全一致，两份测试的 AST 也完全一致；额外 **128 passed in 26.08s** 定向回归验证该收尾拆分。这 128 例与前述测试重叠，不累计成 393 个独立测试。
- 交付研究源码 hash 为 `a07281f6ff8d2becef7f57ccfd30569552d071fe650110963fb0f883fa60e3f3`；与计时源码唯一产品差异为上述收尾提取，搜索逻辑和时钟调用顺序不变。源码差异、AST 检查脚本和两个版本文件同时归档，回执见 delivery-source-receipt.json 与 final-verification.json。
- 没有增加 NumPy、OR-Tools 或其他产品依赖，没有换语言。目标仍是 Win7 x64 / Python 3.8 离线交付；本次实测机器为 macOS arm64，未声称已经完成 Win7 实机或打包验证。
- 工作区原有大量 UI/工作台和算法未提交改动已保留，本次也未提交。不能将本轮定向通过表述为整个工作区通过门禁。

## 方案一致性与文档联动

四项主线均按已授权技术决定实施；额外交期起点是为解决实际短预算质量退化而加入的有界构造，没有改变目标函数或数据约束。未增加页面、持久化数据结构或外部服务，因此本轮不新增 UI/数据迁移验收；Win7 实机和打包验证未执行。架构 §10.6、技术决定和本功能 checklist 已同步，旧 ff-note 只加历史指针与指标勘误，不覆盖原始测量。

本功能不是从 roadmap 的单一条目启动，因此不将整条路线图改成 done；仅在现有图修补与 ALNS 桥接 notes 中回填本次结果。通用 ALNS operator/reward、其他算法融合与更广的公平比较仍保持原状态。全门禁按用户明确指令排除，不能把它写成已通过。

## 证据位置

临时工作目录为 `/private/tmp/aps-ig-takeover-20260914-s56y00fj`。持久归档位于 `evidence/Benchmarks/2026-09-14-graph-ready-ig-takeover/`：README 给出复现入口，原始行、runner 副本、输入/源码 manifest、历史回执、测试以及各版本源码归档均保留；archive-verification.json 逐文件验证源码归档，bundle-files-sha256.json 记录交付文件 hash。该 evidence 目录按仓库既有规则被 Git 忽略；本轮未自动提交任何文件。

## 2026-09-15 补测：5000 工序 × 4 方案、180 秒容量验收

用户进一步要求重跑原容量项。当前完整工作区另行冻结为 4163 个代码、测试和本地资源文件，沿用原 CLI、100 批 × 50 工序夹具、四候选、HTTP/落库/重启检查及 180 秒上限，单次测得受理到完整终态 **91.429413333 秒**，引擎 **88.238972417 秒**，容量验收通过。四套各 5000 工序、合计 20000 条任务落库；72 张非运行业务表保持不变，重启保留、GET 零写入、完整性及外键检查均通过。四套完整排程 payload 与之前两次约 89 秒容量记录全部相同。

相比历史 89.381380042 / 89.475103292 秒的平均值 89.428241667 秒，本次多 2.0012 秒（约 +2.24%），**没有测出提速**。这是当前单次和历史两次的比较，不据此宣称稳定性能回退；没有因正常背景负载自动反复重跑。

该夹具仍为 `algo_mode=greedy`，并未启动 IG。旧版三个图方案各跑一次 slack，新版第一图方案比较 slack/cr/atc 三次 SGS、另外两个复用其结果：非复用候选的原生解码数两边都是基础 1 次 + 图 3 次。新版第一图方案耗时 85.2522 秒，后两组各约 0.004 秒，当前工作量分布发生变化；不能将本次计时用于宣称 IG 收益，也不能将复制到复用候选里的 report 再累计成新解码。未改产品代码、夹具、阈值或全门禁范围。

完整回执、规则与解码对照、冻结源码和整个私有运行目录归档于 `evidence/Benchmarks/2026-09-15-formal-capacity-5000/`；三个归档均逐文件解包读取核验。两个测试服务已正常退出，原用户应用未停止，原业务库不参与测量；Win7 实机和完整门禁仍未执行。

## 2026-09-15 追问：生产默认与精细计算启用实验

只读核对：源码出厂默认 `algo_mode=improve`、预算5秒、工序图on，图ready v2的IG默认跟随精英修补开启；本机现有 `db/aps.db` 实际保存 `algo_mode=greedy`、预算20秒、图分析off。工作台的一次运行副本会强制图分析on，但不改已保存的algo_mode，因此这份当前全局配置不会启动图IG。本轮没有修改生产配置；外部Win7部署版本及其实际设置未检查。

用户要求试启用后，复制上一轮相同产品源码，仅在私有测试夹具把greedy改为improve，保留原内部600秒预算和外部180秒上限，并增加原IG方法的生命周期观察。**180秒内四套方案未完成，最后进度为1/4；IG只有enabled=true的配置事件，0次start_attempt、0次解码。** 因此没有得到实际IG性能对照，不能将超时归因于IG本体；前置搜索与整个improve模式的预算行为仍待处理。此配置也不同于出厂5秒或本机20秒，不外推为这两种预算的实测结果。

原退出流程额外等待180秒仍未结束，测试脚本强制停止其自有服务，driver总计371.267654791秒。私有样例库完整性ok、外键违规0，但没有完成回执、持久化候选或候选任务；四套落库和重启验证未完成。父进程观察的产品输入hash前后一致，子服务因强停缺少最终来源及正常退出回执，不能标成完整通过。

失败回执、私有样例库、精确实验源码、测试侧改动及配置只读记录完整归档于 `evidence/Benchmarks/2026-09-15-capacity-improve-enabled/`。保留本节实验失败和上一节greedy容量通过两个独立结果；未改阈值、未改产品代码、未跑全门禁、未自动重试或启用生产库。

## 2026-09-15 本机实际启用与 20 秒容量跟进

已通过现有配置服务将本机保存值 greedy 切为 improve，保留 20 秒预算并重启最新源码；补齐四个缺失的注册配置项，原有配置行与业务数据保留，实际库严格配置读取和健康检查通过。其他 Win7 部署包没有更新。

原 5000 工序/四候选/180 秒验收，以 improve + 20 秒运行后在 37.1832 秒返回 partial，只完成 2/4 套，因此容量仍未通过，不能算作比 91.4294 秒更快。首个图方案解码 28.8022 秒，图 IG 0 次启动。独立 40 工序的相同模式/预算验证完成四套，图 IG 实际 400 次解码、21 轮迭代；它只证明启用链路，不能替换大实例失败。

详见 `../../issues/2026-09-15-optimizer-production-activation/optimizer-production-activation-fix-note.md` 及 `evidence/Benchmarks/2026-09-15-capacity-improve-20s/README.md`。本次未跑全门禁、未修改产品源码、未提交；前文通过范围保持原样。


## 2026-09-15 首解与预算阻塞修复完成

后续修复在本轮修复前快照上做对照：5000 工序首轮 SGS 从 27.3811 秒降到 7.1204 秒，最终四方案在 22.2549 秒全部完成；IG 完成了两次后缀试算，尚未完成整轮。3 秒与 5 秒 SMTWT 各 250 例均为 163 好 / 87 平 / 0 差，端到端 20 例全部相同。该基线与本文最初接手时的基线不同，不能累计百分比。

## 2026-09-15 局部任务和尾段复用补充验收

在上述交付版本之上继续优化后，同条件 5000 工序 × 四方案、内部 20 秒、外部 180 秒测试完成 5 轮有界小邻域，正式续排试算 2 → 5 次，四份 validated payload 相同；受理至完整终态 22.3105 → 21.2617 秒。每轮本次实际拆一道工序，五次均保留原位置，不能按旧版三道工序、多位置全扫的工作量折算迭代倍数。

相同 5000 工序调整动作的续排平均 1.34314 → 0.38495 秒，约快 3.49 倍；该计时不包含独立完整验证。SMTWT 3 秒 250 平 / 0 差，5 秒 1 好 / 249 平 / 0 差；原端到端 20 例和新增 192 工序 8 例全部同分。收益主要是解码和搜索量，未观察到大例业务分数提升。生产已重启加载，保存配置仍为 improve / 20 秒。完整边界、源码证明和数据保留见 [修复记录](../../issues/2026-09-15-ig-local-search/ig-local-search-fix-note.md)，不累加此前不同基线的百分比。

本机 production 已重启加载修复并保持 improve / 20 秒。大实例最后的后缀成本类与小例矩阵源码之间的适用范围、AST 等价证明、1204 通过和 18 个已复现旧失败，以及数据保留、Win7/全门禁限制，统一见 [修复记录](../../issues/2026-09-15-sgs-startup-budget/sgs-startup-budget-fix-note.md) 和 `evidence/Benchmarks/2026-09-15-sgs-startup-budget/`。
