# 概念身份证 · plan_role(结果方案角色)

- **status**: current
- **owner_area**: scheduler_result_view
- **canonical module**: `core/models/schedule_plan_role.py`(已核验，python3.14 import 通过)

## 规范定义
用户查看排产结果时选择的方案角色，是内部 URL/查询参数，不是用户可见文案。

| 值 | 用户标签 | 取数源表 |
|---|---|---|
| `adopted` | 正式采用方案 | `schedule` |
| `baseline_best` | 原算法代表方案 | `candidate_rows` |
| `critical_best` | 重点工序优先代表方案 | `candidate_rows` |

## 行为合同
- 标签映射唯一来源：`PLAN_ROLE_LABELS` / `plan_role_label()`。
- 合法值集唯一来源：`VALID_PLAN_ROLES`。
- 比较判定：`is_comparison_role()` / `is_comparison_plan()`。
- 失败语义(实测)：模型层 `plan_role_label()` 对未知值返回“未知方案身份”(纯展示容忍)；缺失/空经 `_normalize_role` 回落 `adopted`；**严格校验在** `schedule_plan_query_service.resolve_plan_view`(`ValueError → ValidationError`)。
- 用户可见规则：页面/导出/报表标题/错误消息不得直接展示 plan_role/source_table/candidate_id/scenario_id(ARCHITECTURE.md:65)。

## 禁止含义(改这个概念前必读)
- ❌ **不要在 `core/services/scheduler/` 下新建第二个 plan_role 标签/解析模块**——那是审计反复警告的 **P5 第N套私有实现**。本概念已有单一收口点。
- ❌ 不要把 adopted 之外的角色当成可写现场记录入口(ARCHITECTURE.md:67；见审计 §90 LB-A 族 execution_review 只复盘 adopted)。

## 守卫
- `.codestable/semantics/tests/test_plan_role_properties.py`(hypothesis 性质)
- `.codestable/semantics/tests/__snapshots__/plan_role_labels.json`(中文标签快照)
