---
doc_type: audit
slug: scheduler-optimizer-actuator-misplacement
scope: scheduler-global-optimizer roadmap item 6/7/8(GRASP/IG 候选构造、业务邻域注册表、VNS/acceptance 局搜)的算法有效性审计
summary: 三层搜索升级的"作用点错位"已修复——SGS 局搜改用派工规则邻域,GRASP/IG 批次顺序候选改回 batch_order 解码,图 ready 路径不再宣称旧 batch_order 邻域有效
status: fixed
created: 2026-06-29
last_reviewed: 2026-06-29
verified_by: 主代理 + 3 OPUS subagent 静态核查 + Codex 对抗审核(job task-mqxyjb0q-iy65ws,7 子代理 fan-out)+ 真跑实测(探针全排列 / SMTWT 250 / FJSP 新旧 / 修复后 Benchmark 全跑)
related_roadmap: scheduler-global-optimizer
tags: [scheduler, optimizer, local-search, grasp-ig, vns, benchmark, actuator-misplacement, audit]
---

# 排产优化器"作用点错位"审计(item 6/7/8,经 Codex 对抗 + 实测校准)

> 性质:**有效性发现清单 + 修复闭环记录**。历史问题证据保留在本文中,修复闭环见第 8 节和 issue fix-note。
> 可信度:**高**——结论同时有静态 file:line、真跑实测、Codex 独立对抗三方支撑;几处机制细节经 Codex 纠正后已更正。

## 0. 一句话结论

item 6/7/8 工程质量扎实(窄职责拆分、报告诚实、public/diagnostics 边界守住、seed 派生随机),但修复前三层搜索升级(GRASP/IG、业务邻域、VNS)的**搜索旋钮主要是 `batch_order`(批次顺序),而 `batch_order` 在 SGS 派工下是 `dispatch_key` 第 6 位 tie-break,实测几乎改不动结果**。

2026-06-29 已按推荐方案修复:

- SGS 局搜不再用旧批次顺序邻域,改用 `sgs_dispatch_rule` 派工规则切换邻域。
- GRASP/IG 的批次顺序候选不再强制用 SGS 解码,改用 `batch_order` 解码。
- 图 ready 路径遇到旧批次顺序邻域时明确跳过,不再把无效旋钮报告成有效。

修复后 SMTWT 250 实例 Benchmark:SGS 局搜从修复前 **0/250 改进**变成 **209/250 改进(83.6%)**,平均 gap 从 **16.16 降到 6.82**,平均缩小 **9.33**。

## 1. 背景与方法

- **审计对象**:最近三次 feature 提交 —— item 6 `grasp-ig-candidate-construction`、item 7 `business-neighborhood-registry`、item 8 `vns-sa-local-search-upgrade`(均 roadmap `scheduler-global-optimizer`,已标 `done`)。
- **三方验证**:
  1. 静态:主代理 + 3 个 OPUS subagent 读代码 + 调用链(`tools.symbol_locator`)。
  2. 实测:真跑探针(全排列枚举 sgs vs batch_order)、SMTWT 250 实例 vs Moore-Hodgson 精确最优、FJSP mk01–mk10 新旧对比。
  3. 对抗:Codex 7 子代理独立核验,挑出主代理 4 处夸大 + 1 处硬错误,已全部采纳更正(见 §5)。

## 2. 核心发现:作用点错位 + 分路径图景

候选/邻域的"决策变量"本质只有两个:`batch_order` 和极少量 `resource_pool`。6 个业务邻域里 **5 个**只改 `batch_order`(`_pull_batch_earlier` 把批次往前挪 2 格),只有 `resource_alternative` 改 `resource_pool.pair_rank`。而 `batch_order` 在不同派工模式下的"杠杆"天差地别:

| 路径 | 默认占比 | batch_order 是否有效 | 局搜/候选效果 |
|---|---|---|---|
| **batch_order 主派工 + 非图候选(baseline)** | 1/6 候选 | ✅ 是 `operation_sort_key` 首键 | **有效**(实测可改进) |
| **graph 候选(默认 on,最多 5 个)** | 最多 5/6 候选 | ❌ 强制 sgs,且图 ready 用图自己的 `sort_key_by_op_id` | 空烧 |
| **GRASP/IG 阶段** | improve 必跑 | ❌ 硬编码 sgs 解码,batch_order 第 6 位 tie-break | **真跑完整 SGS 解码后空烧**(撞 same_fingerprint) |
| **单机 sgs(如 SMTWT 类纯延期场景)** | 配置相关 | ❌ 死键 | 空烧 |

**为什么 SGS 下 batch_order 失效**:SGS 每步靠 `min(dispatch_key)` 选工序,key 是 8 元组 `(score_penalty, primary, changeover_penalty, pr_rank, time_left_h, batch_order, seq, op_id)`,`batch_order` 排第 6 位,前面压着 `primary`/`time_left_h` 两个基于开工时间的连续浮点,真实排产几乎总能在前几位分出胜负 → 轮不到 `batch_order` 起作用。它**仍被消费**(`sgs.py:99` batch_ids 排序、`sgs_scoring.py:65` 进评分键),只是实测改不动最终结果。

## 3. 证据

### 3.1 静态(file:line)
- batch_order 第 6 位 tie-break:`core/algorithms/dispatch_rules.py:87-95`(7 元组)+ `core/algorithms/greedy/dispatch/sgs_scoring.py:71`(前置 `score_penalty`)。
- 5/6 邻域只改 batch_order:`core/services/scheduler/run/optimizer_neighborhood_moves.py:105,122,140,158,206,261`(`_pull_batch_earlier`);`resource_alternative` 改 pair_rank:`:181-188`。
- improve 下 `dispatch_modes()` 恒含 sgs → `sgs_enabled` 恒 True:`core/services/scheduler/run/optimizer_config.py:54-57` + `schedule_optimizer.py:162`。
- GRASP/IG 硬编码 sgs 解码:`core/services/scheduler/run/optimizer_grasp_ig_candidates.py:62-79`(`:74`);skip 条件是 `not sgs_enabled`(默认不触发):`:238-240`。
- 默认 graph on + 5 档:`core/services/scheduler/config/config_field_spec.py:331-386`;graph 候选强制 sgs:`schedule_optimizer.py:220-222`。
- 同输出指纹去重发生在完整解码**之后**:`optimizer_grasp_ig_candidates.py:292-328` + `optimizer_search_report.py:271-276`。

### 3.2 实测(真跑,可复现)
- **探针全排列**(`tests/_scripts_e2e/probe_localsearch_actuator.py`):单机交期实例枚举全部批次顺序,**SGS 三种规则(slack/cr/atc)distinct 结果恒=1(死键)**,batch_order 模式 distinct=7/4(有效)。已固化为 `tests/algorithm/test_localsearch_batch_order_actuator.py`(4 passed)。
- **SMTWT 250 实例 vs Moore-Hodgson 精确最优**(overdue_count):greedy(SGS/slack)合计 **达最优仅 39/250 = 15.6%,平均 gap 16.16,最大 44**。这是 improve 本该填、但 sgs 下 batch_order 旋钮填不了的差距。
- **FJSP mk01–mk10 新旧对比**:greedy 基线完全不变(对比有效);improve **不再空烧 time_budget**(基线 ~23s → 现 0.9–12.6s,迭代上限早停生效);质量有进有退,**mk10 287→275 改进且修复了"improve 反而比 greedy 差"的反常**(item 8 `candidate_can_update_best` 之功),小实例 mk01/mk04 因迭代数大减略退。FJSP 折叠成单机绑定走 batch_order 模式,故 improve 在 FJSP 上有效——印证"batch_order 模式有效 / sgs 死键"。
- **修复前 SMTWT 250 局搜实测(决定性,`tests/_scripts_e2e/benchmark_smtwt_localsearch.py`,真实 `run_local_search`)**:同一份局搜代码——**sgs 派工:250 实例改进 0/250(0.0%),gap 16.16→16.16 缩小 0.00**;**batch_order 派工:165/250(66.0%)改进,gap 15.40→10.38 平均缩小 5.02**。证明局搜本身有效(batch_order 下 66% 改进、gap 缩 1/3),sgs 下纯空转——差别只在派工模式,因 batch_order 旋钮在 sgs 是死键。
- **修复后 SMTWT 250 局搜实测(2026-06-29)**:`sgs` 派工路径改为 SGS 派工规则邻域后,**sgs 派工:250 实例改进 209/250(83.6%),gap 16.16→6.82,平均缩小 9.33**;`batch_order` 路径保持有效,**165/250(66.0%),gap 15.40→10.38,平均缩小 5.02**。

### 3.3 Codex 对抗校准(已采纳)
见 §5;核心方向被确认,机制细节 1 处硬错误 + 4 处夸大已更正。

## 4. 治理清单(按优先级)

> 每项含:严重度 / 问题 / 根因 file:line / 修复方向 / 验收标准。具体 step-by-step 执行指令见配套修复提示词。

### P0 · 作用点错位(根因) —— 已修复
- **严重度**:高(决定 item 6/7/8 在默认配置下的实际收益)。
- **问题**:GRASP/IG 与业务邻域主要靠 `batch_order` 撬动,而默认多数路径走 sgs,batch_order 在 sgs 下是末位 tie-break → 大量算力空烧、0 改进。
- **根因**:`optimizer_grasp_ig_candidates.py:74`(硬编码 sgs)、`optimizer_neighborhood_moves.py`(5/6 邻域只产 batch_order)、`dispatch_rules.py:87-95`(batch_order 第 6 位)。
- **修复方向**:让搜索作用在**真正驱动 sgs 的维度**——dispatch_rule 组合、primary 规则参数、或 sgs ready-queue/资源选择扰动;或明确"业务邻域只服务 batch_order 派工"并据此收敛 GRASP/IG 的解码模式(别在 sgs 下硬编码空烧)。
- **修复结果**:`optimizer_local_search.py` 在 SGS 当前解码模式下使用 `SGS_DISPATCH_RULE` 专属邻域,`NeighborhoodMove` 可携带候选 `dispatch_mode/dispatch_rule`,调度器实际按候选规则解码。
- **验收**:已补真实 GreedyScheduler 端到端断言,并用 SMTWT 250 Benchmark 验证 SGS 路径 209/250 个实例改进。

### P1 · 缺真实有效性测试 —— 已修复
- **严重度**:高(无防线 → no-op 回归无法察觉)。
- **问题**:item 6/7/8 三套测试全 stub 掉真实 `GreedyScheduler.schedule`,改善是假 `schedule_fn` 喂的;测试覆盖了合同/状态机,但**无一断言真实解码后 objective 严格下降**。
- **根因**:`tests/algorithm/test_optimizer_{grasp_ig_candidate_construction,business_neighborhood_registry,vns_sa_local_search}_contract.py`。
- **修复方向**:为 GRASP/IG、邻域、VNS 各补真实 GreedyScheduler 端到端用例(已起头 `test_localsearch_batch_order_actuator.py`)。
- **修复结果**:已补业务邻域、VNS/局搜、GRASP/IG 三条真实 GreedyScheduler 端到端改善测试。
- **验收**:定向回归测试 98 passed。

### P2 · acceptance 尺度错配(threshold / record_to_record)
- **严重度**:中(默认路径不触发,潜在缺陷)。
- **问题**:`DEFAULT_THRESHOLD=1.0` 直接与 `_score_delta` 比,而 score 首分量是 `failed_ops`(硬约束整数);显式选 threshold/RTR 时早期会把"多失败 1 道工序"的更差解接受为 current。默认 `improve_only` **不触发**。
- **根因**:`core/services/scheduler/run/optimizer_acceptance.py:24,78-112,197-206`;score 首位 `optimizer_local_search_candidate_eval.py:66`。
- **修复方向**:`failed_ops` 维度零容差(阈值只作用于目标分量,失败工序数变差一律不接受)。
- **验收**:threshold/RTR 下,候选 `failed_ops` 比 current 大时必被拒,测试锁住。

### P3 · positive_count 裸吞异常
- **严重度**:低(只进诊断字段 chain_node_count,不影响排产选择)。
- **问题**:`except Exception: return 0` 吞掉一切异常算诊断数。
- **根因**:`core/services/scheduler/run/optimizer_neighborhood_move_support.py:31-35`。
- **修复方向**:去掉裸 try 或只接 `TypeError`,让上游类型错误 fail-loud。
- **验收**:非预期异常不再被静默吞成 0。

### P4 · resource_alternative 虚假有效移动
- **严重度**:中(诊断失真 + 无效候选耗解码)。
- **问题**:旧 `pair_rank ≤ -1` 时 `min(old, -1)` 无真实变化,却仍报 `changed_decision_count=1`;且即便改了 rank,auto_assign 先比结束时间/换型/负载,pair_rank 只是末位 tie-break,常被吸收。
- **根因**:`core/services/scheduler/run/optimizer_neighborhood_moves.py:181-200`;auto_assign 排序 `core/algorithms/greedy/auto_assign.py:338-345,387`。
- **修复方向**:仅在 pair_rank 真实改变时报有效移动;评估 pair_rank 作用点是否够强。
- **验收**:无真实变化时 move 标 noop / changed=0。

### P5 · 图 ready 路径不走候选 batch_order —— 已修复
- **严重度**:中(进一步架空批次顺序邻域)。
- **问题**:图 ready 路径排序用图上下文自己的 `sort_key_by_op_id`,根本不消费优化候选生成的 batch_order。
- **根因**:`core/services/scheduler/run/schedule_graph_dispatch_context.py:193-202`、`core/algorithms/greedy/dispatch/sgs_graph.py:267-268`。
- **修复方向**:与 P0 一并考虑——图路径下批次顺序邻域基本无意义,应改作用点。
- **修复结果**:`graph_ready_context` 存在时,GRASP/IG 和 local search 都以 `graph_ready_requires_graph_neighborhood` 明确跳过旧批次顺序候选。
- **验收**:已补 local search / GRASP-IG 图 ready 跳过测试。

### P6 · 解码后去重不挡空烧
- **严重度**:低(性能,非正确性)。
- **问题**:same_fingerprint 去重发生在完整 SGS 解码之后,挡不住重复候选的解码成本。
- **根因**:`optimizer_grasp_ig_candidates.py:292-328`。
- **修复方向**:解码前先按 `decision_fingerprint` 去重 specs。
- **验收**:重复 decision 候选不再各付一次完整解码。

## 5. Codex 对抗校准记录(已更正的主代理偏差)

| 项 | 主代理原说法 | Codex 纠正 / 现状 |
|---|---|---|
| GRASP/IG 触发(硬错误) | "batch_order 模式下整个阶段被跳过" | 错。看 `not sgs_enabled`,improve 下恒含 sgs → **默认必跑、强制 sgs 解码空烧**(比跳过更费算力) |
| 默认候选数 | "一定跑满 1+5" | 预算到期会跳过后续候选(`schedule_candidate_runner.py:181-184`) |
| 测试 | "只验证字段/计数" | 也验证了 SGS 模式/候选顺序/指纹去重/状态机,只是缺真实有效性 |
| acceptance | "默认会接受多失败 1 道工序" | 默认 `improve_only` 不触发,仅显式 threshold/RTR 才是潜在缺陷 |
| 历史实测 | 引用"300 次 SMTWT 实测" | 那是 roadmap 静态记录、不可复现;已用真跑 SMTWT 250 实例替代 |

Codex 额外发现的风险已并入治理清单 P4 / P5 / P6。

## 6. 产物与待办

- **已交付**:
  - `tests/_scripts_e2e/probe_localsearch_actuator.py`(全排列探针)
  - `tests/algorithm/test_localsearch_batch_order_actuator.py`(4 passed,锁 sgs 死键/batch_order 有效/有害vs无害空转)
  - `tests/_scripts_e2e/benchmark_smtwt_localsearch.py`(SMTWT 250 局搜 sgs vs batch_order 实测:修复前 sgs 0% 改进;修复后 sgs 83.6% 改进,batch_order 66.0% 改进)
- **2026-06-29 修复进度**:
  - P2 已修:threshold / record_to_record 现在会拒绝 `failed_ops` 变多的候选,并补回归测试。
  - P3 已修:`positive_count` 不再裸吞所有异常,非预期异常会暴露。
  - P4 已修:`resource_alternative` 在 `pair_rank` 没有真实变化时返回 noop,不再伪装成有效移动。
  - P6 已修:GRASP/IG candidate specs 在完整解码前按候选决策去重,避免重复候选各跑一次解码。
  - P0 已修:SGS 局搜改用 `sgs_dispatch_rule` 专属邻域,候选会真实切换 `slack/cr/atc` 派工规则。
  - P1 已修:已补业务邻域、VNS/局搜、GRASP/IG 的真实 `GreedyScheduler` 端到端改善测试。
  - P5 已修:图 ready 路径明确跳过旧批次顺序候选,不再报告伪有效。
  - GRASP/IG 对齐已修:批次顺序候选改用 `batch_order` 解码,图 ready 下跳过。
- **遗留**:无本审计内剩余 blocker。后续若要让图 ready 自身也能被局搜优化,应另开图语义邻域需求,不要复用批次顺序邻域。

## 8. 修复后 Benchmark 与门禁

- `python3 tests/_scripts_e2e/benchmark_optimizer_proof_harness.py`:passed,1 个 tiny oracle 用例 objective score 匹配。
- `python3 tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py`:passed,已生成 `evidence/Benchmark/sgs_large_resource_pool_report.md`。
- `python3 tests/_scripts_e2e/benchmark_fjsp.py`:passed,15 runs / 15 valid,已生成 `evidence/Benchmark/fjsp_benchmark_report.md`。
- `python3 tests/_scripts_e2e/benchmark_smtwt_localsearch.py`:passed。SGS 合计 250 实例改进 209 个(83.6%),gap 16.16→6.82;batch_order 合计 250 实例改进 165 个(66.0%),gap 15.40→10.38。
- 定向测试:`python3 -m pytest ...` 98 passed。
- 代码检查:`python3 -m ruff check ...` passed;`git diff --check ...` passed。
- 质量门禁:`.venv/bin/python scripts/run_quality_gate.py` 未形成 clean proof,因为当前工作区不是干净状态,门禁报 `dirty worktree ... untracked source files: tools/scan_import_cycles.py`。这是工作区状态阻塞,不是本次修复测试失败。

## 7. 相关文档
- roadmap:`.codestable/roadmap/scheduler-global-optimizer/`
- 记忆:`scheduler-item678-actuator-misplacement-2026-06`、`scheduler-sgs-localsearch-noop-2026-06`
