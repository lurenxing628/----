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

## 2026-05-27 回溯补充验证

- 本轮第 4-9 项回溯总审查重新覆盖第 7 项资源派工计划身份护栏，覆盖正式方案、历史正式方案、对比参考方案、模拟预览、公开 data、页面文案和导出脱敏。
- 回溯修复了测试 helper 缺少 `/scheduler/resource-dispatch/execution/data` 端点的问题，让资源派工页面在新增现场反馈 data URL 后仍能完整跑页面级护栏测试。
- 回溯第一轮使用 5 个子代理：
  - `019e68cc-65e2-74a0-a4e0-00b631f653c8`：检查页面、普通 data、JS、service、ViewModel、模板和前端测试，结论 OK，无阻塞。
  - `019e68cc-b465-7be0-a778-118df192422e`：检查导出、Excel 文件名、导出审计和用户可见字段，结论 OK，无阻塞。
  - `019e68cd-5775-75c2-8d8f-647fbbd25851`：检查 PlanIdentity、写入开关、历史方案、候选方案、模拟预览和后端拒绝链路，结论 OK，无阻塞。
  - `019e68cd-ac0e-7522-bce2-593bc4e3d2ea`：检查只读副作用、确认派工边界、schema 只读性和现场反馈按钮边界，结论 OK，无阻塞。
  - `019e68cd-fba3-7972-a12c-3ab7dd80d421`：检查 CodeStable 回写、items.yaml、测试命令、禁改路径和提交隔离，结论为当前工作区混有后续阶段改动，不能当成第 7 项的干净工作区证明；这不是第 7 项代码行为阻塞，但不能宣称 clean-worktree proof。
- 回溯第二轮使用 5 个子代理：
  - `019e68d6-dbc0-7dc2-bc31-14712591c8be`：检查页面、普通 data、PlanIdentity、service、ViewModel、模板、JS 和测试，结论 OK，无阻塞。
  - `019e68d6-dc9d-7980-8c8b-63c62dd38efa`：检查 PlanIdentity、service、route、ViewModel、Excel、现场反馈 data 和后端拒绝链路，结论 OK，无阻塞。
  - `019e68d6-dd33-71a1-a0a8-0234d884be8c`：检查导出、Excel 文件名、工作簿摘要、导出审计和页面文案，发现阻塞：对比参考方案回退读取正式排程表时，页面“查看方案”、Excel “查看方案”和文件名可能显示成“正式采用方案”。
  - `019e68d6-de21-7a11-83dd-e2bc6af64e64`：检查只读副作用、确认派工 route/table、OperationLogs 例外和测试锁定，结论 OK，无阻塞。
  - `019e68d6-e00c-7a41-9a26-dbc907729ef2`：检查 CodeStable 产物、items.yaml、测试、Python 3.8、离线资源、禁改路径和 git 边界，发现阻塞：设计文档未纳入版本边界、验收测试数量记录不准、当前工作区混有后续项 schema/迁移/执行事件改动，不能宣称第 7 项 clean-worktree proof。
- 已修复第二轮行为阻塞：新增 `plan_view_label` 作为用户可见方案名，页面“方案/查看方案”、Excel “查看方案”和导出文件名都优先使用公开计划身份；当请求“重点工序优先代表方案”但明细回退读取正式排程表时，现在显示“对比参考方案-重点工序优先代表方案”，不会显示成可反馈的“正式采用方案”。
- 已修正验收记录中的测试数量：扩展组合当前真实结果是 `15 passed`，路线图精准组合是 `14 passed`。
- 当前工作区已经包含第 8 项以后 schema、迁移、执行事件和现场反馈改动；本条只能证明第 7 项允许路径内的行为与文档，不能宣称 clean-worktree proof。
- 修复后第三轮使用 5 个子代理做整项复审：
  - `019e68e7-7f68-7060-aedd-d9ae14c53e7a`：检查页面、普通 data、前端、模板、调用链和 git 边界，结论 OK，无阻塞。
  - `019e68e7-7ffc-7ec2-af5a-19332f77fee5`：检查 PlanIdentity、service、ViewModel、页面、Excel 和后端拒绝链路，结论 OK，无阻塞。
  - `019e68e7-80c0-7d11-b12f-54b4f03d0e39`：检查导出、Excel 文件名、工作簿内容、导出审计和内部字段边界，结论 OK，无阻塞。
  - `019e68e7-81b9-7d51-92b8-a7dd27bf28bd`：检查只读副作用、确认派工 route/table、schema 禁改边界、OperationLogs 审计例外和测试锁定，结论 OK，无阻塞。
  - `019e68e7-83e0-7021-b698-c5c898033536`：检查 CodeStable 产物、items.yaml、测试、Python 3.8、离线资源、forbidden_paths、staged 和 dirty 边界，结论 OK，无阻塞。
- 第三轮复审确认第二轮阻塞项已归零：设计文档已纳入版本边界，测试数量已更正，对比参考方案回退显示已修复，`schema.sql` 等后续项 dirty 仍只作为“不能宣称 clean-worktree proof”的非阻塞风险记录。
- 两个子代理都提到 `/scheduler/resource-dispatch/execution/data` 会把给程序校验用的 `plan_identity` 字段传给前端脚本。按 roadmap 第 5.0 节，URL、隐藏字段、前端请求体和服务端响应可以保留稳定程序字段，前提是页面、导出、按钮、弹窗和错误提示不能直接显示这些字段；本阶段验收口径仍以普通 `/resource-dispatch/data`、页面和 Excel 脱敏为准。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_frontend_offline_static_assets.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`
  - 结果：`15 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_frontend_offline_static_assets.py`
  - 结果：`14 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_public_output_contract.py tests/regression_resource_dispatch_viewmodel_public_output_contract.py tests/test_resource_dispatch_viewmodel.py tests/test_scheduler_resource_dispatch_smoke.py`
  - 结果：`20 passed`
- 第 4-9 项整段回归组合结果：`104 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-27-dispatch-plan-identity-guardrails --require doc_type --require status`
  - 结果：`3 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/viewmodels/scheduler_resource_dispatch.py core/services/scheduler/resource_dispatch_excel.py web/routes/domains/scheduler/scheduler_resource_dispatch.py tests/regression_scheduler_dispatch_plan_identity_guardrails.py`
  - 结果：未发现 Python 3.8 语法风险。
- `git diff --check`
  - 结果：无空白格式问题。

## 未做

- 不新增真正的确认派工写入。
- 不新增 `POST /scheduler/resource-dispatch/confirm`。
- 不新增确认派工表。
- 不开放开工、完工、暂停、继续生产或报异常按钮。
- 不改排程算法。
- 不改数据库 schema 或迁移。
