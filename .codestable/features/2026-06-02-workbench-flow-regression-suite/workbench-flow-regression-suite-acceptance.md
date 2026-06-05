---
doc_type: feature-acceptance
feature: 2026-06-02-workbench-flow-regression-suite
status: accepted
summary: 第一版工作台主流程回归测试已落地，历史方案显示、不可写入口、内部字段和质量门禁登记已形成闭环。
tags: [aps, workbench, regression, frontend, quality-gate]
roadmap: aps-frontend-workbench
roadmap_item: workbench-flow-regression-suite
---

# 工作台主流程回归测试验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-04
> 关联方案 doc：`.codestable/features/2026-06-02-workbench-flow-regression-suite/workbench-flow-regression-suite-design.md`

## 1. 接口契约核对

**接口示例逐项核对**

- [x] `tests/regression_aps_workbench_flow_contract.py`：首页链接收集后访问分析、甘特、资源派工、报表和计划现场复盘，URL 保留版本、正式方案、日期、批次或资源上下文，符合设计里的 WorkbenchFlowStep 示例。
- [x] `tests/regression_migration_schema_contract.py`：schema 合同检测从迁移流程测试中拆出，仍进入 required tests 和运行分组，符合“新增测试必须被质量门禁持续执行”的接口约束。

**名词层“现状 → 变化”核对**

- [x] 主流程测试独立成文件，没有继续挤压 500 行边界的旧报表测试文件。
- [x] 几何登记仍由 `tests/ui_geometry_contract_data.py` 维护，浏览器烟测入口没有被塞进 required tests。
- [x] required registry 已在 `tools/test_registry_data.py`、`tools/test_registry_groups_scheduler.py`、`tools/test_registry_groups_misc.py` 和 `tests/regression_quality_gate_registry_split_scope_contract.py` 中覆盖。

**流程图核对**

- [x] “建最小数据 → 打开首页 → 访问目标页 → 断言上下文 → 守住不可写和内部字段不可见 → 登记门禁”都有测试、ViewModel 或 registry 落点。

## 2. 行为与决策核对

**需求摘要逐项验证**

- [x] 首页起点、分析、甘特、资源派工、报表、计划和现场实际都已有回归测试覆盖。
- [x] 历史正式方案、缺失版本、坏摘要、非正式方案不会在普通页面冒充当前可执行正式方案。
- [x] 当前版本坏 schema、v15 后缺现场事件表、坏历史事件、事件身份矛盾、事件状态矛盾、坏 `event_time` 和当前库里已经存在的坏事件都改成 fail-fast，不再静默补成“看起来正常”的数据。
- [x] 资源派工、工作台跳转禁用原因、报表计划状态和周计划结果状态统一使用公开中文护栏文案；`failed`、`json_decode_error` 这类内部码不会进入普通页面正文。

**明确不做逐项核对**

- [x] 未改 `core/algorithms/`。
- [x] `schema.sql` 语义变更只围绕 `OperationExecutionEvents` 身份、状态组合和迁移合同。
- [x] 未引入外链脚本、外链样式、外链字体或新前端框架。
- [x] 未实现第二阶段的现场事实延期解释、甘特资源负荷摘要、停机任务级明细、牵连批次/订单影响面。

**挂载点反向核对**

- [x] 设计第 2.3 节列出的测试、ViewModel、route 和 registry 都能在当前 diff 中找到。
- [x] `git diff --cached --name-only` 未包含 `.codestable/audits/` 或 `.codestable/checkup/`，审计和体检材料保持独立提交边界。

## 3. 验收场景核对

- [x] 首页主流程：`tests/regression_aps_workbench_flow_contract.py` 和 `tests/regression_dashboard_workbench_contract.py` 覆盖。
- [x] 上下文不丢：`tests/regression_scheduler_workbench_links_contract.py`、`tests/regression_reports_workbench_backlink_contract.py`、`tests/regression_reports_workbench_navigation_contract.py` 覆盖。
- [x] 甘特双视角和任务详情：`tests/regression_gantt_task_detail_panel_contract.py`、`tests/regression_gantt_task_detail_js_contract.py` 覆盖。
- [x] 非正式 / 历史 / 缺失 / 坏摘要复盘护栏：`tests/regression_scheduler_plan_identity_summary_guardrail.py`、`tests/regression_web_silent_fallback_contract.py`、`tests/regression_scheduler_historical_plan_label_contract.py` 覆盖。
- [x] 内部字段不可见：`tests/regression_frontend_offline_static_assets.py`、主流程测试和 `tests/regression_scheduler_analysis_diagnostic_graph_score_contract.py` 覆盖；诊断页重点影响样本不再把内部 `op_id` 拼成“工序 N”。
- [x] 内部错误码和坏数据显示不可见：`tests/regression_scheduler_workbench_link_guardrails.py`、`tests/regression_web_silent_fallback_contract.py` 覆盖资源派工、工作台链接、报表计划状态、周计划结果状态、周计划所选策略、候选方案指标、优化过程布尔值和诊断布尔值；摘要解析失败显示中文解释，不显示 `json_decode_error`，未知结果状态只显示“结果状态未知”，未知策略只显示“历史记录异常”，坏指标显示“记录异常 / 无法安全对比”。
- [x] schema 合同和迁移护栏：`tests/regression_migrations.py`、`tests/regression_migration_schema_contract.py`、`tests/regression_operation_execution_migration_v16_contract.py`、`tests/regression_operation_execution_migration_v18_contract.py`、`tests/regression_operation_execution_migration_v19_contract.py` 覆盖。
- [x] 现场事件时间、状态组合和当前正式方案护栏：`tests/regression_operation_execution_event_time_contract.py` 覆盖模型解析、仓库标准化、数据库直写拦截、事件/状态组合拒绝、非当前正式方案事件拒绝和状态聚合 fail-fast；`tests/regression_migration_schema_contract.py` 覆盖当前库已有坏事件 fail-fast；现场反馈路线、异常反馈和导入测试已确认服务层标准化没有破坏既有流程。
- [x] 真实浏览器几何探针收尾：`tests/ui_geometry_probe.mjs` 和 `tests/ui_geometry_cdp_client.mjs` 已把 CDP WebSocket 关闭、stdout/stderr 写入和 Node 退出码收口成明确流程；网络恢复后复跑 `tests/test_ui_browser_geometry_env.py` + 真实几何测试 10 passed，startup 邻居组合 4 passed，full-test-debt 分片 4032 collected 且 unexpected_failure_count 0。
- [x] 前端浏览器烟测：网络恢复后使用 in-app Browser 打开本地报表中心、甘特和周计划，确认 v12 被 v13 替代后，下拉和页面提示都展示“历史正式方案（已被新版本替代）”，旧“复盘正式方案”文案不再出现，也没有“正式采用方案 · 正式采用方案”这种重复标签。截图：`output/playwright/workbench-flow-regression-suite-reports-history-iab.png`；此前 Playwright 本地浏览器截图 `output/playwright/workbench-flow-regression-suite-reports-history.png` 只作为备用证据。该结果不能写成 Win7/Chrome 109 兼容证明。

## 4. 术语一致性

- “工作台主流程回归测试”“第一版完整主流程”“几何烟测登记”“required regression 登记”都保留在测试和 CodeStable 文档语境内，没有变成用户页面文案。
- 用户可见页面继续使用“正式采用方案”“历史正式方案（已被新版本替代）”“暂未记录现场实际”“计划和现场实际”等中文业务说法。
- 内部字段 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`op_id`、`schedule_id` 和内部错误码 `json_decode_error` 只允许出现在 URL、隐藏字段、日志或测试内部，不进入普通正文；周计划未知 `result_status` 也不能原样显示；没有公开工序名称时，诊断详情只展示“重点影响样本”。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md` 已补充工作台主流程回归和 required registry 的现状说明。
- [x] 本 feature 没新增业务模块，不需要新增独立 architecture 子文档。
- [x] `ui-gantt.md` 未变；本次只是锁住甘特页面在工作台主流程里的测试覆盖，不改变甘特架构边界。

## 6. requirement 回写

- [x] `.codestable/requirements/scheduler-daily-workbench.md` 是当前能力文档，本次已追加 2026-06-04 变更日志：第一版主流程回归已落地，历史方案显示和不可写入口护栏被测试锁住。

## 7. roadmap 回写

- [x] `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml` 中 `workbench-flow-regression-suite` 已由 `in-progress` 改为 `done`。
- [x] `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md` 子 feature 清单同步改为 `done`，并追加 2026-06-04 变更日志。
- [x] `validate-yaml.py --file` 已校验 feature acceptance、feature checklist 和 roadmap items。
- [x] `scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache --no-resume` 最新 run_id 为 `c2aa7501ca2dc5ccfd2e64006094f584e2c1089b:2026-06-04T22:21:34`，16 个门禁步骤全部跑完，failed 0；状态仍是 `passed_but_unbound`，只能说明当前 dirty 工作区命令链跑通，不能当成 clean proof。

## 8. attention.md 候选盘点

- [x] 无候选。本 feature 没发现每个后续 feature 都必须提前知道的新环境命令或路径陷阱。

## 9. 遗留

- 第 9 项 `workbench-user-guide-refresh` 仍是 planned，必须等第 8 项提交后按 feature 流程单独启动。
- 第二阶段 planned 项仍包括 `delay-diagnosis-site-facts-bridge`、`gantt-resource-load-summary`、`downtime-task-impact-detail`、`downstream-batch-order-impact`。
- 完整 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume` 要在本阶段提交和独立 audit/checkup 提交后、工作区干净时运行。
- `.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/` 和 `.codestable/checkup/` 是独立工作流材料，不进入本 feature 提交。
- `tools/quality_gate_shared.py` 是既有历史长门禁聚合文件，本轮只同步真实门禁命令和工具路径；本次新增/拆分的实现与测试文件保持低于 500 行，历史长文件拆分如要处理应单独走质量门禁重构。
- SubAgent round3 中有一条“证据不足”来自重排护栏测试缺 `networkx==3.1` 环境证明；网络恢复后已用项目 `.venv` 的 Python 3.8 重跑同组测试并通过。round4 指出周计划 raw `result_status` fallback 和长门禁浏览器探针收尾问题，当前都已修复并补证据。round5 又指出周计划 raw `strategy` fallback、候选坏指标展示、优化/诊断布尔值展示、现场事件聚合身份闸门、提交边界和历史长文件口径问题；本轮已修复前四类并补测试，Claude Code round5 发生 StopFailure 不能算有效证据，仍需进入 review_round_6 双轨复审确认关闭。
