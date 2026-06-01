---
doc_type: feature-acceptance
feature: 2026-06-01-resource-dispatch-execution-lane
requirement: shop-floor-execution-feedback
roadmap: aps-frontend-workbench
roadmap_item: resource-dispatch-execution-lane
status: accepted
accepted_at: 2026-06-01
summary: 资源派工页已把计划员查看排班、现场事实代录和计划实际复盘分清，并补齐任务卡与执行流水公开字段。
tags: [aps, resource-dispatch, workbench, frontend, shop-floor]
---

# resource-dispatch-execution-lane acceptance

## 验收结论

- 通过。第 6 项仍在现有 `/scheduler/resource-dispatch` 页面内完成，没有新增或复活 `/scheduler/resource-execution` 独立页面。
- 计划员查看区域保留任务明细、日历矩阵和甘特图；现场事实区域保留现场记录。
- 顶部“查看计划和实际”是只读复盘入口；卡片内动作是“查看现场记录”。
- 任务卡显示图号/物料、计划时间、实际时间和偏差；缺图号/物料时显示“未填写图号或物料”。
- 执行流水显示“正式排程现场记录”和记录落库时间；公开 payload 不泄露 `source_table`。
- 非正式方案、历史方案和模拟预览不输出 actual 写入 URL，不输出空的 `data-actual-*` 写入地址。

## 复审记录

- 本地 SubAgent 四路复审已完成并关闭：后端身份链、前端分层、测试与 CodeStable、维护性/兼容性。
- Claude Code delegate 复审已完成，使用 4 个 Claude Code SubAgent，角色为后端写入身份链路、前端分层与模板边界、测试与文档覆盖、独立页面规模合规；Claude 报告确认子代理均按 `model: "opus"` 派发。
- Claude Code 报告的两个阻塞覆盖缺口已修复：补了缺图号/物料兜底测试、前端真实渲染兜底测试，补了四个入口仍在且分组正确的模板测试。
- `review_round_2` 已按 SubAgent 技能补跑：定向复审核旧阻塞，盲审覆盖后端写入链、前端分层、测试文档闭环；本轮发现的手册旧实时动作口径已刷新为现场记录当前用法，并加了手册锁词测试。
- Claude delegate 因桥接脚本把 `claude.exe` 识别为非运行态，发送和读取结果使用 tmux fallback；复审结束后已退出 Claude，并关闭 delegate Terminal 窗口。`list-delegate-claude.sh` 已无存活 delegate。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_ui_range_feedback_contract.py::test_resource_dispatch_script_bundle_is_unconditional_and_ordered tests/regression_scheduler_dispatch_plan_identity_guardrails.py::test_history_comparison_and_scenario_plans_are_read_only_with_plain_reasons tests/regression_resource_dispatch_workbench_lane_contract.py tests/regression_resource_dispatch_site_records_frontend_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_resource_dispatch_actual_records.py tests/regression_resource_dispatch_actual_import.py tests/regression_config_manual_markdown.py`
  - 结果：60 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_workbench_lane_contract.py tests/regression_config_manual_markdown.py tests/regression_resource_dispatch_actual_import.py tests/regression_resource_dispatch_actual_records.py`
  - 结果：32 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/ -k "resource_dispatch or execution or workbench or manual"`
  - 沙箱内因 `regression_check_manual_layout_runtime_resolution.py` 需要绑定 `127.0.0.1` 临时端口被拒绝。
  - 提升权限重跑后结果：308 passed, 3532 deselected。

## 后续提醒

- 后端 `import/preview` 和 `import/confirm` 兼容路由仍存在，但普通资源派工页面不引用它们；如果后续要彻底移除，需要单独评估历史兼容。
