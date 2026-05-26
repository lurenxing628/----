---
doc_type: feature-acceptance
feature: 2026-05-27-shared-plan-identity-evidence-contract
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: shared-plan-identity-evidence-contract
created: 2026-05-27
---

# 公共读取身份与证据协议验收

## 验收结论

已完成。

本阶段只把“正在看的排程结果到底是哪一套”讲清楚，并把后续诊断、对比、派工、反馈都会用到的证据格式定下来。不提前开放确认派工、开工、完工、异常反馈，也不把候选方案或模拟预览当成正式执行计划。

## 已落地范围

- 新增 `PlanIdentity`，统一记录版本、请求方案、实际读取方案、来源、候选编号、模拟预览编号、结果状态、是否正式方案、是否预览、是否当前可执行版本、是否被新版本替代、锁定状态、能否派工、能否写现场反馈等字段。
- 新增 `EvidenceLink`，支持行级证据、汇总证据、缺数据证据三类口径。
- 行级证据必须带真实来源和来源行；假来源表会直接报错，不能为了凑证据填假表名。
- 缺数据证据必须标成“当前数据不足”，不能伪装成已经确认的事实。
- 排程读取服务会在正式方案、代表候选方案、历史版本、缺明细回退和模拟预览解析后补上统一计划身份。
- 当前可派工、可写现场反馈只允许当前最新正式 adopted 方案；候选方案、模拟预览、历史正式版本、失败结果、模拟结果、缺明细回退都不会放开。
- `Schedule.lock_status` 只作为页面展示的锁定状态，不会阻止当前正式方案写现场反馈。
- 默认页面上下文也补了安全的计划身份默认值，避免空数据页面误放开派工或反馈。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_plan_identity_evidence_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_analysis_candidate_links_and_roles.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/models/schedule_plan_identity.py core/models/schedule_plan_resolution.py core/services/scheduler/schedule_plan_identity_builder.py core/services/scheduler/schedule_plan_query_service.py core/services/scheduler/schedule_result_view_context.py data/repositories/schedule_plan_query_repo.py tests/regression_scheduler_plan_identity_evidence_contract.py`

## 子代理复审

- 调查阶段 3 个子代理分别检查了公共计划解析链路、候选分析页展示链路、资源派工读取链路。
- 第一轮对抗审核 3 个子代理分别检查了证据字段、公开输出和派工护栏，发现并推动修复了失败/模拟结果、证据链接串计划、假来源表和缺数据证据等级问题。
- 修复后重新派 1 个子代理做同范围复审，确认本阶段没有阻塞项后再进入提交。

## 未做

- 不开放普通用户的确认派工或现场反馈按钮。
- 不新增延期诊断原因计算。
- 不新增候选方案推荐卡、三方案差值卡或钻取空状态。
- 不新增执行事件表写入流程。
