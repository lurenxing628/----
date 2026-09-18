---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-07
nature: quality
severity: P1
confidence: high
suggested_action: cs-issue
status: withdrawn
---

# Finding 07：修补与 IG 的父方案不是精英本身（09-14 finding-10 扩大到工序序族、IG 与自动派工）

## 速答

`_parent_from_candidate` 用按开工时刻排堆的 `decoded_topological_order` 重建父顺序，不是 SGS 实际拣选序；`inherited` 只取 `repair_decision.resource_overrides`，档位候选为空，自动派工的机人选择不钉住。修补把优先键整体换成 `(rank, batch_rank)`、批次邻域只用 `(batch_rank,)`。结果"零移动"的恒等决策解出与父不同的排程，IG 从比现任更差的点起走。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_moves.py:22-40`；`optimizer_graph_ready_operation_neighbors.py:65-83`；`optimizer_graph_ready_repair_decisions.py:44-55`；`optimizer_graph_ready_repair_neighbors.py:81-84`；`optimizer_graph_ready_candidate_payload.py:57-74`。
- 实测（`/tmp/aps-audit-20260918/S3/probe_f10_multiop.py`、`probe_f10_ig_report.py`，质量矩阵真实 SGS + 日历）：`medium_shift_pool`（48 工序、自动派工）10 个精英的批次恒等决策 10/10、工序序恒等决策 10/10 输出指纹与父不同；IG 起点重解码现任 (9,1324.5) 得到 (9,1394)，`parent_order_consistent=false`；IG 报告 `improvements=2`，其中 1 次只是把父顺序重解码回来。`tiny` 批次恒等 5/7 不复现；SMTWT-40 单机单工序 9/9 恒等（09-14 单机反证不成立）。

## 影响

生产默认（图分析 on + 自动派工）下修补与 IG 的基座都不是精英，预算花在偏离点上；`same_fingerprint` 去重抓不到"同决策不同输出"。

## 修复方向

候选载荷记录 SGS 实际拣选序作为 `operation_order`（活动表性质保证按拣选序为优先级重解码逐步选到同一工序；检查点机制已有 `picked_op_ids`）；自动派工场景把解码出的 (机, 人) 钉为 `resource_overrides`；修补批次邻域以父拣选序为基座。

## 处理结果

2026-09-18 同日落地，随后按实测三次修正，最终结论是**复议撤回**：本发现描述的现象属实（恒等决策不复现父方案），但三种"让父方案身份精确"的修法在真实时钟基准上都没有收益或明显更差；漂移本身就是自动派工与批次重取序场景的搜索自由。

- (a) 取序基座：只带取序回调的检查点请求捕获 SGS 实际拣选序，修补的工序级/资源级邻域与 IG 以它为父顺序。集成后 medium_shift_pool（自动派工，10 秒真实时钟，两遍逐位确定）加权拖期 1128 → 1199.5（+6%）、拖期 849 → 885.5、min_weighted 1128 → 1149。先按代理文件组把 HEAD 覆盖成 HEAD+S1/S3/S4/S5 四棵树，只有 S3 组复现；再在集成树上对 S3 内 13 个因素逐个与组合开关，回到 HEAD 值 1128 的最小组合是"工序级邻域回到开工序 + 资源邻域回到显式决策序 + IG 回到开工序"，三者缺一不可（单独或两两关闭只回到 1144.5–1147）。端到端 20 例与冻结时钟黄金向量对该基座中性。已整体撤回：`sgs_checkpoint.py`、`optimizer_graph_ready.py`、候选载荷、`_repair_decisions.py`、`_operation_neighbors.py`、`_iterated_greedy_moves.py` 回到 HEAD；`optimizer_graph_ready_decode_capture.py` 只保留检查点捕获期失败的降级规则（finding-02）；`parent_identity` / `repair_parent_identity` / `free_resources` 上报与 `tests/algorithm/test_graph_ready_parent_identity_contract.py` 删除（登记表同步）。
- (b) 钉住解码出的 (机, 人) 为 `resource_overrides`：首版钉住后 medium_shift_pool 4 个目标全部变差——IG 400 次解码 0 改进（HEAD 179 次 7 改进）、档位/修补 28/32 变 13/47、加权拖期 1128 → 1255.5；已撤回。
- (c) 修补批次邻域按父取序整块搬移：真实时钟端到端 20 例对 HEAD 7 例变差（frozen_ready_external 4/4、shift_pool 3/4），逐因素开关中唯一能逐位回到 HEAD 的因素（frozen_ready_external/min_overdue 加权拖期 284 → 246）；已撤回，批次决策只带批次排名。

保留的只有与身份无关的改进：`parent_order_consistent` 按输出指纹判定（不只比分数）、参考捕获单独记账（finding-14）、检查点捕获期失败降级（finding-02）、同一精英每个特征基各自记录已消费前缀。09-14 finding-10 与本发现的"父方案不是精英本身"判定改记为 by-design：想再走"精确身份"路线，必须把漂移改成显式算子，并用真实时钟端到端 20 例 + 质量矩阵证明不劣。
