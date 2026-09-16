---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-08
nature: quality
severity: P1
confidence: high
suggested_action: cs-feat
status: fixed
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

## 处理结果

2026-09-14 落地（记录见 `.codestable/features/2026-09-14-sgs-atc-k-ladder/`）：ATC 的 k 从写死 2.0 变成优化器可搜的离散梯子（0.5、1、2、4、8、16，默认仍 2.0），规则以 `atc:k=<值>` 令牌贯通参数解析、SGS 评分、多起点、换规则邻域与决策去重，采用的令牌如实上报为 `adopted_dispatch_rule`。用户配置页仍只在三条规则之间选。SMTWT 250 实例：单值扫描 k=6 达最优 50/250（k=2 为 44），每实例取梯子最优 57/250、gap 4.50；真实局搜基准 gap 16.16 → 4.14（此前 6.82）。端到端 20 例选中方案 1 例更好、19 例相同、0 例更差。接线时发现多起点决策缓存把 `atc:k=16.0` 与 `atc` 当同一决策剪掉，已改用规范令牌作键。图候选的多起点不展开梯子（图键在规则键之前，梯子起点多为重复决策），只靠换规则邻域触达。
