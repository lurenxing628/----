---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-08"
classification: NEEDS_FEATURE
nature: arch-drift
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 08：延期解释接现场事实和牵连影响面都放第二阶段

## 结论

延期解释的事实、线索、证据缺口已经有基础，但还没接现场事实事件，也没有可靠的牵连批次/订单影响面。设计稿要求“能判断就展示，不能判断就明说”，这需要新增服务能力或展示层保守说明。

## 证据

- 诊断服务能生成事实、线索、数据缺口、建议动作：`core/services/scheduler/schedule_delay_diagnosis_service.py:157`、`:169`、`:217`、`:312`。
- 展示层只保留简化字段：`core/services/report/delay_diagnosis_presentation.py:47`。
- 当前诊断仍会固定补“没有现场执行反馈”类数据缺口：`core/services/scheduler/schedule_delay_diagnosis_service.py:181`。
- 工序线索里的实际开始/实际结束仍为空：`core/services/scheduler/schedule_delay_diagnosis_service.py:285`。
- 现场事实服务已经存在：`core/services/scheduler/operation_execution_feedback_service.py:73`。
- 诊断模型没有牵连批次列表：`core/models/schedule_delay_diagnosis.py:112`。
- 测试明确不暴露 `critical_chain`：`tests/regression_scheduler_delay_diagnosis_contract.py:301`。

## 当前能直接做

- 把已有事实、线索、证据缺口按设计稿的五段式详情展示得更完整。
- 给“不能判断牵连批次”补保守中文说明。
- 把延期详情里的建议动作链接接到统一 WorkbenchLink。

## 必须新增的功能

- 把现场事实事件接入延期诊断，避免计划员已经录了现场情况，页面还说“没有现场事实”。
- 如果要展示牵连批次/订单，需要新增影响面聚合。
- 如果暂时不做影响面，要在页面明确写“当前只能解释本批次，暂不能证明影响到哪些批次/订单”。

## 阶段归属

- 第一版：把现有延期事实、线索、证据缺口做成更完整的五段式展示；对牵连影响面和现场事实不足给保守中文说明；建议动作使用统一 WorkbenchLink。
- 第二阶段：延期解释接现场事实；新增牵连批次/订单影响面聚合。
