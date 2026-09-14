---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-09
nature: quality
severity: P1
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 09：batch_order 局搜邻域确定性且每状态 ≤6 个，迭代上限按配置秒数派生，预算利用率 4%

## 速答

六个业务邻域里五个都是"某个批次往前挪 2 格"的同构小步，且都是确定性选靶，VNS 每轮只暴露 1 个邻域，同一状态最多 6 个不同邻居；迭代上限 200 由配置秒数 5 派生而不看实际分配到的候选预算，实测 0.2 秒用完 200 次迭代（168 次 noop）就停，剩下 4.8 秒白白放弃。

## 关键证据

- `core/services/scheduler/run/optimizer_neighborhood_moves.py:114-129,131-146,149-164,223-237,320-350` —— `out.insert(max(index-2,0))` 前挪 2 格；`:190-220` `resource_alternative` 只改 1 对 pair_rank。
- `core/services/scheduler/run/optimizer_vns.py:28-29`、`optimizer_neighborhood_registry.py:118` —— 每轮单邻域。
- `core/services/scheduler/run/optimizer_candidate_profile.py:79-89` —— `derive_iteration_limits(5)=(200,50)`；`optimizer_local_search.py:318` 用配置秒数。
- `core/services/scheduler/run/optimizer_local_search_round.py:221-237` —— 重复 decision_key 记 noop 仍计迭代与 no_improve。
- `core/services/scheduler/run/optimizer_local_search.py:32-46,232-233` —— restart shake 3～8 次常数幅度。
- 实测（S2）：wt40[0] batch_order 5s：`iterations=200 decodes=36 evaluated=33 rejected={'noop_neighbor':168} elapsed=0.20s`，overdue 6→6（最优 3）。

## 影响

局搜在 batch_order 起点上几乎不探索；预算利用率 4%，84% 迭代是重复 noop。

## 修复方向

迭代上限改按剩余时间自适应或直接用时间预算；noop 不计迭代、重复直接换邻域；扩成真正的邻域族（任意位置 insert、相邻/远程 swap、块移动、tardy-boundary），用 predecode 决策去重代替评估后指纹去重。

## 建议动作

`cs-refactor`（迭代/时间语义与去重）+ `cs-feat`（邻域族扩展，属 roadmap ALNS 段）。
