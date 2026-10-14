---
doc_type: roadmap-review
roadmap: scheduling-decision-workbench
status: completed
created: 2026-10-13
reviewer: independent-subagent
review_rounds: 1
open_findings: 0
---

# 整体方案独立审查与处理记录

## 结论

独立 subAgent 审查结论：主方案方向、完整范围和八阶段依赖成立；补齐两项 P2 契约后可作为实施依据。主代理已逐项核对源码并修订正文，两项均已处理。

审查对象为 [主方案](scheduling-decision-workbench-roadmap.md) 与 [实施条目](scheduling-decision-workbench-items.yaml)。审查覆盖多方案横向比较、推荐与代价、交付和资源指标、准备/执行/冻结/分件、过程历史、既有采用规则以及验证规模。

## 独立发现与修订

| 编号 | 级别 | 发现与影响 | 修订决定 | 状态 |
| --- | --- | --- | --- | --- |
| R01 | P2 | `9999-12-31` 在正式计划与试调中分别得到 `unknown/null` 和 `due_unspecified/0`；统一接入时会使同一方案的交期汇总变化。 | 主方案 4.2 固定 `due_state`、交期评价集合、排除数量与全部无交期时的 `not_applicable`；第二阶段统一所有消费方，A04/A14 覆盖。 | resolved |
| R02 | P2 | balanced 交期容差对照 `raw_score_best`，关键链 health 对照算法 baseline；用户查看基准可切换，混用会改变历史选择解释。 | 主方案 5.1/8.2 分别保存 `raw_score_best_candidate_ref`、`health_reference_candidate_ref` 与用户 `DecisionScope.reference`；A11 增加第三候选基准切换。 | resolved |

R01 证据：`core/services/workbench/plan/delivery_projection.py:32-39,92-99`、`core/services/workbench/trial/projection.py:120-138`、`core/services/common/overdue_calculations.py:20`。审查代理执行纯函数核验，确认同一完整批次的两种投影结果存在上述差异。

R02 证据：`core/services/scheduler/run/schedule_candidate_selection.py:158-172` 与 `core/services/scheduler/run/schedule_candidate_health.py:64-94`。选择结果中的原始候选键可用于固定映射，字段见 `schedule_candidate_selection.py:30-41`。

## 审查期间一并明确的实施细节

- 完整性分搜索覆盖、应排工序覆盖、业务交付覆盖；合法待料暂缓使用“本次可排范围推荐”。
- 资源高压力固定为窗口内日峰值 ≥90%，设备/人员各计一次；均衡采用容量加权变异系数，并定义零需求和缺容量状态。
- 准备需求由实际排槽输入生成，原样保留和执行种子另列；运行共用需求账保存一份。
- 每个候选过程曲线保留最多 200 点，固定保留首次有效、首次全部应排完成、最终结果，余量使用时间桶；代表尝试与评估总量分别显示。
- 接口 query、明细分页、资源视角和 XLSX/CSV 分区约定写入主方案 8.3。
- 资源逐日计算按预算分块，整窗指标保持完整范围。

## 本轮验证

- 主方案 frontmatter 与实施条目 YAML 通过项目校验器。
- 八条实施项的引用、状态、唯一最小闭环和无环依赖检查通过。
- 主代理复核 R01/R02 对应代码和修订后的协议，正文与清单一致。
- 交付为方案文档；八个产品实施条目均保持 `planned`。
