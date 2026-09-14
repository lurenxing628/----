---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-08
nature: quality
severity: P1
confidence: high
suggested_action: cs-feat
status: open
---

# Finding 08：SGS 起点搜索空间只有 3 个离散派工规则，达最优率 17.6% 是结构上限

## 速答

`DispatchRule` 只有 SLACK / CR / ATC 三种，ATC 的 k 写死 2.0，没有任何连续旋钮暴露给搜索；SGS 起点下局搜就是在 3 个点之间切换。实测 SMTWT 250 实例 greedy 三规则各跑一次取最优 = 44/250（17.6%）、gap 6.82，与"修复后局搜"记录逐位相同，说明局搜全部收益等于"换成 ATC"。

## 关键证据

- `core/algorithm_contracts/dispatch_rules.py:19-22` —— 仅三种规则；`:80-82` `k = 2.0` 硬编码。
- `core/services/scheduler/run/optimizer_local_search.py:309` —— `_resolve_sgs_dispatch_rules` 池 = 3。
- `core/algorithms/greedy/dispatch/sgs_scoring.py:106-107` —— 图 on 时规则主键被压到图键之后，规则切换杠杆更小。
- 实测（S2）：slack-only 39/250 = 15.6% gap 16.16；best-of-3 44/250 = 17.6% gap 6.82；ATC 在 250/250 实例上都是最佳或并列最佳。主代理 SMTWT 复跑：SGS 局搜 209/250 改进、gap 16.16→6.82。

## 影响

SGS 是图候选与 sgs 配置的唯一解码器，其可搜索维度一个都没有；逼近最优只能靠改排序键（图 profile / 修补），规则层不贡献多样性。

## 修复方向

把 `DispatchInputs` 参数化（ATC k、slack/CR 混合权重、per-op 优先级偏移），让 `sgs_dispatch_rule` 邻域在连续参数上做步长搜索；或复用图路径的 per-op priority key 作为 SGS 起点的操作级旋钮。需用 SMTWT 250 实例证明达最优率与 gap 的改善。

## 建议动作

`cs-feat`，属于新增搜索维度，应挂到 `scheduler-global-optimizer` roadmap。
