---
doc_type: feature-acceptance
feature: 2026-05-27-dispatch-plan-identity-guardrails
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: dispatch-plan-identity-guardrails
created: 2026-05-27
---

# 资源派工计划身份护栏验收

## 验收结论

已完成。

本阶段把资源派工页和导出里的“当前看的到底是哪套计划”讲清楚：当前最新正式采用方案可以用于派工和现场反馈；历史正式方案、对比参考方案、模拟预览都只能查看，不能提交派工或写现场反馈。本阶段没有新增确认派工写入，也没有新增确认派工表。

## 已落地范围

- 资源派工 ViewModel 增加公开版 `plan_identity`，给页面和 data 接口提供中文计划身份、中文可写说明和护栏提示。
- 页面版本摘要区新增“计划身份”和“派工反馈”，并在摘要下方显示中文护栏提示。
- 资源派工 Excel 查询摘要新增“计划身份”和“派工反馈说明”。
- 公共筛选 payload 继续隐藏计划来源、候选编号、模拟预览编号等内部字段。
- `plan_role_filter_fields()` 修正布尔值合并规则，底层计划身份明确给出 false 时不会被外层旧字段覆盖。
- 新增回归测试覆盖当前正式、历史正式、对比参考、模拟预览、导出脱敏、无确认派工副作用和确认派工路由缺失。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_dispatch_plan_identity_guardrails.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_frontend_offline_static_assets.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_resource_dispatch.py core/services/scheduler/resource_dispatch_excel.py core/services/scheduler/schedule_result_view_context.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py`

## 子代理复审

- 调查阶段使用 5 个子代理，分别检查资源派工页面/data/service/viewmodel/template/JS 链路、导出链路、PlanIdentity 写入权限、测试覆盖、CodeStable 和提交隔离。
- 实现后第一轮使用 5 个子代理做对抗性审核，分别检查页面和离线资源、路由和副作用、Excel/export、CodeStable 回写、ViewModel/PlanIdentity 合并规则。
- 第一轮复审发现的阻塞点已经修复：补 CodeStable 回写，补确认派工表和无副作用测试，修正 plan_identity 布尔值被外层字段覆盖的问题，并白名单隔离第 8 项草稿。
- 第二轮复审使用 4 个子代理，分别复查计划身份布尔值、路由副作用、导出脱敏、CodeStable 状态和提交隔离；复审结论均为 OK，无阻塞项。

## 未做

- 不新增真正的确认派工写入。
- 不新增 `POST /scheduler/resource-dispatch/confirm`。
- 不新增确认派工表。
- 不开放开工、完工、暂停、继续生产或报异常按钮。
- 不改排程算法。
- 不改数据库 schema 或迁移。
