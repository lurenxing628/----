---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-08
nature: quality
severity: P1
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 08：图档触达不到 ATC k 梯子，图阶段全部只用配置规则

## 速答

有图上下文时多起点只用 3 条注册规则，代码注释说"靠换规则邻域到梯子"；但有图上下文时局搜整体被跳过，换规则邻域只住在局搜里；档位/修补/IG 所有解码都传 `dispatch_rule_cfg`。09-14 ff-note"图候选仍可通过换规则邻域到达梯子令牌"与代码不符。生产默认路径下只有基线候选能用梯子，而默认 batch_order 基线根本不消费规则。

## 关键证据

- `core/services/scheduler/run/optimizer_multi_start.py:33-34`；`optimizer_local_search.py:304-306`；`optimizer_neighborhood_moves.py:240-265`；`optimizer_graph_ready.py:245,304`、`optimizer_graph_ready_candidates.py:128-129`；全部 `optimizer_graph_ready*.py` 无 `dispatch_rule_search_pool` / `ATC_K_LADDER`。
- 实测（S4）：shift_pool 每档图上下文 16 组图键并列，同一档 slack/cr 同输出、atc 与 atc:k=16 各不同（规则在并列处确实起作用）；基线候选（sgs）局搜采用 `atc:k=16.0`，图档全部 `adopted slack`。梯子对图档是否有收益：证据不足。

## 影响

09-14 finding-08 的收益只落在非图路径；图档规则维度只有并列处的 3 个点。

## 修复方向

多起点先判断图优先键在可排工序上是否有并列：无并列只解配置规则，有并列展开注册规则 + 梯子（沿用切片截断）；图阶段沿用现任方案采用的规则；更正 ff-note。

## 处理结果

2026-09-18 同日落地：`optimizer_multi_start.graph_rule_search_scope` 按图上下文证明——`score_enabled`、键同长度有限、两两不同 → `configured_only`；有并列 → `registry_and_ladder`（注册表 + ATC k 梯子，近端先起）；证明不了 → 全池并写原因，`multi_start_efficiency.graph_rule_scope` 上报。`optimizer_candidate_phases.graph_phase_dispatch_rule` 让档位/修补/IG 用 sgs 现任采用的规则解码，来源写进 `candidate_profile.graph_phase_dispatch_rule(_source)`。ff-note 第 16 行与"已知边界"已更正。合同测试 `tests/algorithm/test_optimizer_graph_rule_scope_contract.py`。
