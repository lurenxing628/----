---
doc_type: issue-fix-note
status: completed
slug: gantt-scenario-week-plan-preview-contract
created_at: 2026-05-23
---

# 甘特图模拟草稿与模拟方案预览合同修复记录

## 1. 问题来源

本次修复来自 `e2e4bf7c..415bd017` 分支静态审查。审查指出的主要问题是：

- 甘特图后端已有 Draft 草稿服务，但 Web 路由没有创建草稿、记录调整、废弃草稿的入口。
- 保存 Scenario 和正式采用 Scenario 的操作者身份没有统一从服务端取得，Web 调用可能落成 `system` 或被请求体伪造。
- 周计划导出模拟方案时，Excel 内容本身没有写明“这是模拟预览，正式计划还没有改变”。
- 甘特图周切换链接服务端 HTML 没带 `gantt_zoom`，正常依赖前端 JS 二次修正。

## 2. 根因

- Web 层只接上了 `validate-simulate` / `save-scenario` / `publish-scenario` 三个后半段接口，草稿创建和草稿变更能力停留在服务层。
- Web 层没有统一的排产操作者来源，保存接口曾从 JSON 读取 `created_by`，发布接口曾不传 `published_by`。
- 周计划导出只把模拟方案身份放在文件名里，Excel 内部没有摘要页。
- 甘特图模板的视图切换链接和周切换链接没有使用同一套 URL 参数保留规则。

## 3. 修复范围

- `web/routes/domains/scheduler/scheduler_gantt_adjustments.py`
  - 新增 `create-draft`、`record-time-change`、`record-resource-change`、`discard-draft` 四个草稿接口。
  - `save-scenario` 改为使用服务端操作者，不再接受客户端 `created_by`。
  - `publish-scenario` 显式传入服务端操作者，避免 Web 发布落成 `system`。
- `web/bootstrap/request_services.py`
  - 给请求服务挂载 `gantt_adjustment_draft_service`。
- `core/services/scheduler/gantt_adjustment_draft_service.py`
  - 草稿创建、记录变更、废弃草稿改为事务内提交，保证 Web 请求之间能读到前一次写入。
- `web/routes/domains/scheduler/scheduler_utils.py`
  - 新增统一的排产 Web 操作者读取函数。
- `web/routes/domains/scheduler/scheduler_run.py`
- `web/routes/domains/scheduler/scheduler_week_plan.py`
  - 改用同一个服务端操作者口径。
- `core/services/scheduler/week_plan_excel.py`
  - 新增周计划 Excel 构造模块，把导出构造逻辑从 route 文件中拆出。
  - 模拟方案导出增加 `查询摘要` sheet，写明模拟方案编号、名称、基准版本和“正式计划还没有改变”。
- `templates/scheduler/gantt.html`
- `web_new_test/templates/scheduler/gantt.html`
  - 周切换链接补上 `gantt_zoom`。
  - 模拟调整按钮继续保持禁用，只把提示改成“页面编辑流程完成后开放”。
- `开发文档/系统速查表.md`
  - 补齐四个新增草稿接口，保持文档和真实路由一致。
- `.codestable/features/*`
  - 同步既有设计/验收文档里的操作者口径和周计划模拟导出口径。

## 4. 有意没有做的事

- 没有开放前端拖拽编辑入口。现在后端草稿接口已闭合，但页面编辑状态机还没完成，贸然打开按钮会让用户以为前端完整可用。
- 没有把服务层的 `published_by` 兜底删除。服务层仍保留给内部脚本和测试显式传操作者；Web 路由已经不再依赖客户端传人名。
- 没有引入登录系统。当前项目没有真实登录上下文时，Web 操作者统一记为服务端口径 `web`，重点是不能由客户端伪造，也不能默默落成 `system`。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_adjustment_validate_simulate.py tests/regression_gantt_draft_save_and_preview.py tests/regression_gantt_scenario_publish.py tests/regression_scenario_preview_secondary_outputs.py`
  - `31 passed in 3.52s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_adjustment_draft_model.py tests/regression_gantt_simulation_entry_shell.py`
  - `15 passed in 0.24s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_gantt_url_persistence.py`
  - `OK`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_scheduler_week_plan_no_reschedulable_flash.py`
  - `54 passed in 1.10s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_url_persistence.py tests/regression_gantt_default_version_span.py tests/regression_gantt_readonly_mode_contract.py`
  - `13 passed in 3.91s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_adjustment_draft_model.py tests/regression_gantt_adjustment_validate_simulate.py tests/regression_gantt_draft_save_and_preview.py tests/regression_gantt_scenario_publish.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_gantt_simulation_entry_shell.py tests/regression_gantt_default_version_span.py tests/regression_gantt_readonly_mode_contract.py tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/regression_scheduler_week_plan_no_reschedulable_flash.py`
  - `112 passed in 8.24s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_py38_contract.py`
  - `2 passed in 0.19s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/fast_static_precheck.py`
  - passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`
  - passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_quickref_vs_routes.py`
  - `OK`
- `git diff --check`
  - passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`
  - 全部门禁步骤通过，最终状态为 `passed_but_unbound`。
  - 由于工作区仍有未提交改动，本结果只能证明当前未提交状态下通过，不能当作提交后的干净工作区证明。

## 6. 对抗性审核结果

- 第一轮子代理核实确认四个问题基本属实：草稿 Web 链路缺口、操作者来源不可信、周计划模拟导出缺少内容自证、周切换服务端链接漏 `gantt_zoom`。
- 第二轮对抗性复审确认：
  - 草稿 route 只写 Draft/Change，不写正式 `Schedule` / `ScheduleHistory`。
  - 保存和发布不再使用客户端伪造操作者。
  - 周计划模拟导出 Excel 已包含内容层面的模拟方案摘要。
  - 甘特图入口仍保持禁用，没有提前开放未完成的前端编辑态。
  - 旧设计文档中的操作者口径已同步更新。

## 7. 剩余后续项

- 若后续要真正开放页面“模拟调整”按钮，需要另走前端编辑态设计和验收，重点重新审拖拽是否只写 Draft、取消是否废弃 Draft、保存 Scenario 是否冻结快照。
- 当前还没有登录用户体系，正式采用的 Web 操作者只能可信地记为 `web`。后续如果接入真实登录用户，应把 `_current_scheduler_operator()` 接到登录上下文。
