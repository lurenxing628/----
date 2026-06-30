---
doc_type: decision
slug: graph-ready-v2-due-budget-window-basis
date: 2026-06-30
status: accepted
tags:
  - scheduler
  - optimizer
  - graph-ready
  - due-budget
  - benchmark
---

# 决策:GraphReady v2 `due_budget_hours` 采用「窗口产能(毛)」而非「残余产能(净)」

## 一句话结论

GraphReady v2 的追交预算 `due_budget_hours`,内制工序在有日历时**保持使用 `residual_capacity_window_hours`(窗口毛产能,未扣 downtime/seed 占用)**,**不改用** `residual_capacity_hours`(净残余产能)。代码不变,仅修正文档措辞。本决策由毛/净两轮基准对比数据支撑。

## 背景与问题

- 代码现状:`core/services/scheduler/run/optimizer_graph_ready_v2_features.py` 的 `_deadline_budget_hours`,内制 + 有日历时返回 `capacity["residual_capacity_window_hours"]`(毛窗口)。
- 文档(本特征 acceptance)曾写「使用**可用产能**小时」,语义上指 `residual_capacity_hours`(净 = 窗口 − downtime/seed 占用)。**代码用毛、文档说净,口径对不上。**
- 两者**只有在交期窗口内有 downtime 或 seed 占用时才不同**;无占用时相等。
- 争议点:净更贴「可用于追交的预算」字面语义(资源已被占用时不高估 slack);但争用本就另由 `residual_capacity_pressure`(→ `bottleneck_*`)表达,可能重复;且所有交期特征(slack/pressure/saveability/critical_ratio/sacrifice)进排序前都过 **rank01 排名归一化**,绝对口径未必影响结果。

不空谈,用数据定。

## 实验方法

不改生产代码,用 monkeypatch 在 `_deadline_budget_hours` 上切换毛/净两种返回值(跑完 `finally` 还原,断言 `is _ORIG`,重 import 确认源码仍返回毛,全局未污染),在**真实排产代码路径**(`run_graph_ready_candidates` + 真实 `GreedyScheduler` SGS,strict_mode=False,objective_aware_portfolio)上,对同一批场景毛/净各跑多 seed,量**逾期批次数 / 总拖期 / failed_ops**(`compute_metrics` + `objective_score`)。

脚本与数据见同目录 `scripts/`、`data/`、`baselines/`。当前归档脚本会按自身位置自动定位仓库根和 `baselines/fjsp/`,默认把新结果写回本目录 `data/`,不再依赖原会话临时目录。

## 阶段一:合成争用场景(小实例)

自建带班次日历 + downtime/seed 占用落在交期窗口内的场景,轻/中/重三档争用。自检确认净<毛有效(如 heavy_seed_choke 某批次毛 16h / 净 2h;rank_flip 某批次毛 80h / 净 32h)。

结果:**毛/净 delta 恒为 0**(逾期/拖期/failed_ops 全相等),与争用强度无关,10 seed 完全一致。

机制:v2 打分吃的是 `due_budget` 的 **rank01(排名)值,非绝对小时**。净=毛−占用,只有当占用把批次间**相对排名翻转**时才改打分;而实测即使排名翻转(选出的 best_order 不同),毛/净仍**收敛到同一目标分数**——净找到的是「不一样但一样好」的方案。胜出来源均为 `graph_ready_v2_generated`(信号确实进了真实 SGS),但影响不到逾期/拖期前沿。

→ 小实例上「毛 vs 净」被 rank 归一化结构性抹平。数据见 `data/experiment_result.json`、`data/selfcheck_result.json`、`data/experiment_mk01_overdue.json`。

## 阶段二:真实 FJSP 大/复杂实例

为验证「实例大、解空间大到 ~60 条候选排序穷举不完时,SGS 从毛/净两起点会否摸到不同方案」,拉真实 Brandimarte FJSP 实例(github `SchedulingLab/fjsp-instances`)做三档规模:

| 实例 | 规模 | 自检 net<gross |
|---|---|---|
| mk01 | 10 job / 6 机 / 55 工序 | 18/55(delta 到 −11.3h) |
| mk06 | 10 job / 10 机 / 150 工序,柔性高 | 150/150 |
| mk10 | 20 job / 15 机 / 240 工序 | 233/240 |

结果矩阵(净 − 毛,10 seed 平均;failed_ops 全程 0):

| 实例 | min_overdue 逾期/拖期 | min_tardiness 逾期/拖期 |
|---|---|---|
| mk01 | **−1.00** / +13 → 净优(逾期数) | −1.00 / +2.4 → 净优 |
| mk06 | **−0.70** / +24.8 → 净优(逾期数) | 0 / 0 → 无差别 |
| mk10 | 0 / **+444.5** → 净更差(拖期) | 0 / **−63** → 净略优 |

tightness 敏感性(mk01/mk06,min_overdue,8 seed):

| 实例 | tightness | 净−毛 逾期/拖期 | 方向 |
|---|---|---|---|
| mk01 | 0.8 紧 | 0 / +4 | 净略差 |
| mk01 | 1.0 | −1 / +13 | 净优 |
| mk01 | 1.2 松 | 0 / −96.9 | 净优(拖期) |
| mk01 | 1.0 **uniform** 对照 | **+1** / −162 | 净更差(符号翻转) |
| mk06 | 0.8 | 0 / +120 | 净更差 |
| mk06 | 1.2 | +1.1 / +2.4 | 净更差 |

→ **大/复杂实例上毛≠净确有非零差别,但方向不统一**,随规模、tightness、目标函数、占用分布(differential 集中 vs uniform 均匀,直接把符号从 −1 翻成 +1)而变。证明是「交期窗口内占用的集中分布触发跨批次秩翻转 → 改优先级 → 改方案」。数据见 `data/experiment_fjsp_*.json`、`data/experiment__probe_mk*.json`、`data/run_fjsp_*.log`。

## 为什么选「保留毛 + 改文档」(选项 A)

1. **净不是稳定更优**:方向随规模/松紧/目标/占用乱翻;最大实例 mk10 净在 min_overdue 下拖期还多 444h(实打实回退风险)。
2. **差别多半是「启发式没搜到底」的噪声**:更大时间预算 / 更强局搜时两者都更接近最优、差别会收窄,非稳定质量信号。
3. **无任何证据说净在真实工单上更好**:贸然换可能在某些负载变好、某些变差,且 rank 归一化在常见(小)规模下让它无影响。
4. **争用已另有表达**:`residual_capacity_pressure` 单独承载占用信息,毛口径不丢这层。

因此稳妥、零回退风险、零额外代码改动的选择是:**保留毛窗口口径,改文档措辞讲清楚**。

## 落地动作

- 代码:不改(`_deadline_budget_hours` 继续返回 `residual_capacity_window_hours`)。
- 文档:`.codestable/features/2026-06-30-graph-ready-v2-production-capacity/graph-ready-v2-production-capacity-acceptance.md` 的 `due_budget_hours` 措辞从「可用产能」改为「窗口产能(毛)」并加口径说明 + 指回本决策。
- 同步修正 `.codestable/issues/2026-06-30-graph-ready-v2-review-fixes/graph-ready-v2-review-fixes-fix-note.md` 中同样的「可用产能」措辞(若有)。

## 重新打开本决策的条件

- 拿到**真实工单 + 真实停机/在制占用**数据,毛/净对比显示净**稳定**更优;或
- 未来若让交期特征的绝对量(而非纯 rank)进入打分(绕过 rank01 归一化),则毛/净差异会被放大,需重测。

## 可复现

```bash
# 脚本(已归档)
.codestable/compound/2026-06-30-due-budget-window-vs-residual/scripts/due_budget_experiment.py
.codestable/compound/2026-06-30-due-budget-window-vs-residual/scripts/fjsp_loader.py
# FJSP 基线(已归档)
.codestable/compound/2026-06-30-due-budget-window-vs-residual/baselines/fjsp/mk0{1,6,10}.{txt,json}
```

原实验最早在会话 job tmp 下独立运行、未动 core,monkeypatch 跑完还原;归档后脚本已改为从本目录自定位,默认读取 `baselines/fjsp/`。`data/` 下为各档原始 per-seed 结果 JSON 与运行日志,体量较大(~2.4MB),本文表格为其蒸馏结论；旧日志里的会话 tmp 路径只代表当时原始运行位置,不是复跑依赖。

## 诚实声明(实验局限)

- **FJSP→本模型降维**:本模型一道工序只有单一 `unit_hours`,「选哪台机器」不改工时;FJSP 原始每台可选机器工时不同,这里取可选机器**最小工时**作代表值,丢了「机器选择影响工时」这一柔性维度,只保留「机器选择=占用争用」维度。系统性低估工时,但毛/净是**同映射下相对比较**,方向不受此偏置影响。
- **交期为合成**:FJSP 本身是 makespan 问题无交期,交期按关键路径工时 × tightness(0.8/1.0/1.2)合成。
- **争用为注入**:downtime 按 differential/uniform 两种铺法 + seed 冻结片段,作方向性信号,不等同真实工单分布。
- **单一时间预算**:portfolio 默认 ~60 候选、improve_only。
