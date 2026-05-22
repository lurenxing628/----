---
doc_type: feature-acceptance
feature: 2026-05-22-gantt-adjustment-validate-simulate
status: accepted
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-adjustment-validate-simulate
tags: [scheduler, gantt, validation, simulation, acceptance]
---

# gantt-adjustment-validate-simulate acceptance

## 验收结论

已完成。

本阶段只做后端校验和内存试算。它能告诉后续模拟调整入口“这个拖动落点能不能放、为什么、会有什么风险”，但不会保存 Scenario，不会发布正式版本，也不会改变正式排产结果。

## 已完成内容

- 新增 `GanttAdjustmentValidationService`，读取 Draft 草稿和基准方案，在内存里叠加调整项。
- 新增 `gantt_adjustment_projection.py`，把基准排程行转换成校验用的轻量结构，集中处理资源重叠、前后工序倒挂、交期风险和结果状态。
- 新增 `POST /scheduler/gantt/adjustments/validate-simulate` 薄 route，只负责接收 JSON、调用服务、返回 JSON。
- `RequestServices` 暴露 `gantt_adjustment_validation_service`，保持页面请求侧服务入口一致。
- 回归测试覆盖 valid、warning、blocked、route 可调用、页面仍不开放入口、正式表不变和基准方案不回退。

## 边界确认

- 不写 `Schedule`。
- 不写 `ScheduleHistory`。
- 不写 `ScheduleVersionSeq`。
- 不写 `ScheduleCandidate` / `ScheduleCandidateRows` / `ScheduleCandidateSelection`。
- 不调用 `ScheduleService.run_schedule(simulate=True)`。
- 不保存 Scenario。
- 不发布 Official Version。
- 模板没有注入 `validate-simulate` 地址，也没有 `data-adjustment-url`，用户页面仍然不能点击进入真实模拟调整。

## 对抗性审核修复

- 修正 roadmap 中旧的校验接口口径，统一为 `POST /scheduler/gantt/adjustments/validate-simulate`。
- 补充架构现状，明确后端已有校验试算服务和 route，但页面入口仍未开放。
- 补齐本阶段 acceptance 和 checklist 状态，避免“代码已完成、文档仍像未完成”的口径漂移。
- 增加“基准候选方案消失时不能回退 adopted”的回归测试。
- 增加“目标时间越过工作日历班次窗口”的回归测试。
- 在 blocker 和 warning 路径也比对正式表快照，确认校验试算不写正式排产数据。
- 候选方案表快照从只比数量改成比全行，避免字段被误写时漏测。
- 缺失物料齐套状态时返回 `material_status_missing` warning，不默认当作已齐套。

## 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_adjustment_validate_simulate.py`：9 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_adjustment_validate_simulate.py tests/regression_gantt_adjustment_draft_model.py tests/regression_gantt_simulation_entry_shell.py tests/regression_request_services_contract.py tests/regression_request_services_lazy_construction.py tests/regression_request_services_failure_propagation.py tests/test_run_quality_gate.py tests/test_long_gate_manifest.py`：145 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/gantt_adjustment_projection.py core/services/scheduler/gantt_adjustment_validation_service.py web/routes/domains/scheduler/scheduler_gantt_adjustments.py tests/regression_gantt_adjustment_validate_simulate.py web/bootstrap/request_services.py core/services/scheduler/__init__.py web/routes/domains/scheduler/scheduler_route_registrar.py`：通过。

## 后续承接

下一阶段是 `gantt-draft-save-and-preview`：把校验通过的 Draft 保存为 Scenario 模拟方案，并让结果页按 Scenario 预览。下一阶段仍不能正式采用；正式采用必须等 `gantt-draft-publish-official-version` 单独实现二次确认、原因必填、重新校验和审计记录。
