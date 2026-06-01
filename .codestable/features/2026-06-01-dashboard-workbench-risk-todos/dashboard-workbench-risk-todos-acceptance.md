---
doc_type: feature-acceptance
feature: 2026-06-01-dashboard-workbench-risk-todos
status: accepted
summary: 首页值班台和今日待处理已落地，计划员可以从首页看到最新计划、风险卡、今日待处理和继续处理入口。
tags: [aps, workbench, dashboard, todos, frontend]
roadmap: aps-frontend-workbench
roadmap_item: dashboard-workbench-risk-todos
---

# dashboard-workbench-risk-todos acceptance

## 1. 接口契约核对

- 已新增 `web/viewmodels/dashboard_workbench.py`，统一生成首页值班台摘要；风险卡和快捷入口拆到 `web/viewmodels/dashboard_workbench_cards.py`，避免主 ViewModel 超过 500 行。
- `build_dashboard_workbench_summary()` 输出 `generated_at_label`、`realtime_note`、`latest_plan`、`risk_cards`、`todo_items`、`quick_links` 和 `empty_state`。
- 每条待处理包含 `kind`、`severity`、`title`、`impact_text`、`evidence_text`、`handling_state_label`、`primary_action` 和 `secondary_action`。
- 风险卡包含 `kind`、`label`、`value`、`helper_text`、`severity` 和 `link`。
- 待处理动作和快捷入口都复用第 1 阶段的 `WorkbenchLink`，模板没有手写跨页 URL。
- `web/routes/dashboard.py` 继续负责取首页所需数据，并补充最新正式计划范围、今日正式计划任务和现场事实。
- `templates/dashboard.html` 与 `web_new_test/templates/dashboard.html` 保持同步，页面只展示 ViewModel 给出的中文字段。

## 2. 行为与决策核对

- 首页顶部新增“计划员值班台”和“今日待处理”区域，旧统计卡、最近排产和常用工作区继续保留。
- 今日待处理最多展示 6 条，按 `danger > warning > notice` 排序。
- 待处理类型覆盖超期批次、方案需要确认、资源负荷偏高、现场情况待确认、基础数据缺口。
- 同一类型只展示一条，数量写进影响说明，不在首页铺开明细。
- 现场情况待确认只统计正式采用方案、当天范围内、计划开始时间已经到达、并且现场事实还不能说明进展的任务；未来任务不统计。
- 资源负荷使用 `machine_util_avg`，`>= 75%` 为提醒，`>= 90%` 为危险；拿不到利用率时显示“数据不足”，不把缺口写成 `0%`。
- 页面明确写出“待处理项根据当前数据实时生成，暂不保存已处理状态。”，不让用户误以为系统会记住处理进度。
- 页面文案使用“现场情况待确认”“暂未收到”“录入现场情况”等说法，不写“必须补录”。
- 反馈人为空不进入首页风险判断，也不阻断报表或现场记录流程。
- 本阶段没有新增 dashboard 路由、数据库表、算法逻辑、外链资源、新前端框架或 Python 3.10+ 语法。
- 挂载点反向核对已完成：本 feature 的运行时代码和测试落在 design 第 2.3 节列出的文件内。

## 3. 验收场景核对

- 没有排产历史时：首页仍显示值班台区域，并给出基础数据缺口和中文说明：`tests/regression_dashboard_workbench_contract.py` 覆盖。
- 有最新正式计划、超期摘要和候选方案对比时：首页出现超期批次和方案需要确认提醒：ViewModel 合同测试覆盖。
- `machine_util_avg >= 0.75` 和 `>= 0.90` 的提醒等级、无利用率时“数据不足”均由 ViewModel 合同测试覆盖。
- 当天已到计划开始时间且现场事实仍不能说明进展时，首页出现现场情况待确认；未来任务不计入：ViewModel 合同测试覆盖。
- 每条待处理都有默认动作和备用动作，并且动作来源是 `WorkbenchLink`：ViewModel 合同测试覆盖。
- 首页跳排产分析、设备甘特、资源派工、计划和现场实际时保留版本、正式采用方案、日期范围和视角参数：`tests/regression_aps_workbench_first_round_flow_contract.py` 覆盖。
- 页面不显示 `scenario_id`、`source_table`、`candidate_id`、`op_id`、`schedule_id` 等内部字段；`plan_role` 只作为 URL 参数传递，页面显示中文计划身份。
- V1/V2 dashboard 模板字节级同步，旧镜像同步测试保持通过。
- 浏览器验证已用本地临时服务打开首页，桌面和窄屏都能看到值班台、风险卡、今日待处理、实时生成说明和快捷入口，未发现按钮文字溢出或内容重叠。
- Claude Code 同步对抗复审：新开 delegate 会话并要求 Claude Code 自行调用 `model="opus"` 子代理；SubAgent A（`ab5435c6cdfae2c44`，定向复审）和 SubAgent B（`a68a5b9dc066a860c`，盲审）均成功创建且结论为 OK。
- 本地 Codex SubAgent 复审：定向复审和盲审均无阻塞；结果消费后已关闭。本次用户追问后再次尝试关闭两个本地 agent id，工具返回 `not found`，确认没有活跃本地句柄残留。

## 4. 术语一致性

- 方案第 0 节术语已落地：页面使用“首页值班台”“今日待处理”“工作台风险卡”“工作台链接”等说法。
- 用户可见位置使用中文业务话：正式采用方案、设备甘特图、资源派工、计划和现场实际、数据不足、暂未收到现场进展。
- 内部字段名 grep 和测试均通过：用户可见文案不展示 `scenario_id`、`source_table`、`candidate_id`、`op_id`、`schedule_id`。
- “计划和现场实际”仍是只读复盘入口，没有被首页写成现场记录保存入口。

## 5. 架构归并

- 已更新 `.codestable/architecture/ARCHITECTURE.md`：
  - 记录首页值班台由 `web/viewmodels/dashboard_workbench.py` 和 `web/viewmodels/dashboard_workbench_cards.py` 生成。
  - 明确首页只展示实时生成的待处理，不保存已处理状态。
  - 明确首页跨页入口继续使用 `WorkbenchLink`，不在模板手写 URL。
  - 明确值班台不新增数据库、不改算法、不输出现场记录写入入口。

## 6. requirement 回写

- 已 backfill `.codestable/requirements/scheduler-daily-workbench.md`，状态为 `current`。
- 已更新 `.codestable/requirements/VISION.md`，把“每天先看计划工作台处理风险”加入当前有效能力。
- 本 requirement 只描述用户能力，不写 ViewModel、路由、模板等实现细节。

## 7. roadmap 回写

- 已把 `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml` 中 `dashboard-workbench-risk-todos` 标记为 `done`。
- 已把 roadmap 主文档第 6 节子 feature 清单第 3 条状态改为 `done`。
- 已在 roadmap 变更日志记录本阶段结果，并说明第一轮最小闭环已经形成。

## 8. attention.md 候选盘点

- 本 feature 未暴露需要补入 `attention.md` 的通用启动注意事项。

## 9. 遗留

- Claude Code 提到的非阻塞观察项：
  - 真实 `machine_util_avg=0.0` 时会显示 `0.0%`，这表示“算得出且确实为 0”，不是“数据不足”。如后续产品口径要求所有 0 都隐藏，可另起小优化。
  - 没有任何版本时，基础数据缺口的默认动作会因缺版本被禁用，但备用动作仍可点击。若想更顺手，可后续把默认动作换成不依赖版本的入口。
- 文件大小门禁发现主 ViewModel 超过 500 行后，已把风险卡和快捷入口拆到 `dashboard_workbench_cards.py`，并复用已计算的现场缺口数量。
- 后续接力：第 4 阶段 `analysis-action-hub-layout` 继续调整排产分析页，让方案推荐和诊断行动出现在技术过程之前。

## 验证附录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/viewmodels/dashboard_workbench.py web/viewmodels/dashboard_workbench_cards.py web/routes/dashboard.py tests/regression_dashboard_workbench_contract.py tests/regression_aps_workbench_first_round_flow_contract.py`：All checks passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_dashboard_workbench_contract.py tests/regression_aps_workbench_first_round_flow_contract.py`：5 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_dashboard_workbench_contract.py tests/regression_aps_workbench_first_round_flow_contract.py tests/regression_frontend_ui_language_polish.py tests/regression_manual_entry_scope.py`：30 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_dashboard_workbench_contract.py tests/regression_aps_workbench_first_round_flow_contract.py tests/regression_frontend_ui_language_polish.py tests/regression_manual_entry_scope.py tests/regression_dashboard_overdue_count_tolerance.py tests/regression_mirror_template_sync.py tests/regression_dashboard_workspace_layout_contract.py tests/test_schedule_summary_observability.py::test_dashboard_accepts_preparsed_result_summary_dict`：34 passed。
- 本地 Playwright 桌面和窄屏验证：首页值班台非空，4 条待处理、6 张风险卡、4 个快捷入口可见，未发现文字溢出。
- Claude Code 复审：两个 `model="opus"` 子代理和 Claude 主自查均 OK，无阻塞。
