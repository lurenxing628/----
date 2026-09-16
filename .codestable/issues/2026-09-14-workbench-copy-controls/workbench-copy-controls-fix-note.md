---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 工作台文案清理、共享图标补齐与甘特控件修复
---

## 授权与范围

用户批准执行统合后的七项任务：批次搜索图标、计划版本及共享图标、关键链排版、实际甘特搜索双框、视图切换按钮套框、值班台可读问题说明与同类分组、全项目用户文案清理。用户明确不跑门禁、不自动提交。

起步时已有 9 个跟踪文件改动：试调图标与命名、现场筛选分页、实际甘特固定列层级及其构建产物/测试。另有三份前轮修复记录、数据库备份目录和运行锁。保留这些内容，本轮继续在相应正式源码实施，未清理用户数据。

## 完成清单

| 任务 | 实施位置与结果 |
|---|---|
| 批次搜索图标 | BatchWorkspace.jsx 使用 ResourceControls.Icon，31-batches-resources.css 将放大镜放入输入框既有留白 |
| 共享图标缺项 | ResourceControls.jsx 补 files、list-checks、lock、git-compare-arrows、eye、rotate-ccw；main.jsx 侧栏复用共享 Icon，移除前轮局部 square-pen 绘图副本 |
| 关键链布局 | ActualGanttControls.jsx 将节点及前驱关系组织为连续横排，独立横向滚动；标题与说明单独成行，节点图标与文字横排；工艺实线、设备/人员依赖虚线 |
| 搜索框双边框 | 33-gantt-foundation.css 去除搜索容器边框，保留输入边框；精确覆盖共享 padding，避免图标压字 |
| 视图切换按钮套框 | 去外围框，按钮和容器统一 32px 高，保留选中状态 |
| 值班台问题说明 | DashboardPanels.jsx 按 code+message 合并缺口原因，全部条目和计数保留；外协来源异常改为明确关联资料问题及联系维护人员；dashboard_external.py 使用现有 label+business_code 显示工序名称（代码），未拆解代码、未新增查询或DTO字段 |
| 文案清理与同步 | 正式前端、相关服务/模型/仓储、冷恢复页面、导出说明、scheduler_manual.md 同步删改；移除固定无结果的整体产能就绪度块，保留分项进度和批次入口 |

典型修正：

- 报表空态“当前范围暂无报工记录”；晚完成阈值准确说明为超过 10 分钟。
- 人员班次“人员班次待设置 / 请为该人员选择有效班次”。
- 操作结果待确认仍提示查询结果，保留对应禁重复提交和恢复机制。
- 校准采用范围纠正为更新所选现有模板定额，保留已有批次不变及新工序使用规则。
- 删除候选收益免责、试调列表/历史重复说明、系统页面与帮助入口自证；文件空值、清空、跨页选中和恢复覆盖等操作规则保留。
- 试调 CSV 保留 22 列、原数值精度、未知与空白区别及编码，长提示缩为方案/时间/数量；解码说明移到折叠帮助。
- 计划读取失败只显示一次错误，保留刷新入口；资料检查未完成不再误写成读取失败或笼统要求刷新。

## 结构与业务边界验证

- 对当前工作区 124 个改动生产 Python 文件按 Python 3.8 解析，再移除文字常量对比 HEAD 的 AST；123 个仅文字变化。
- 唯一额外结构变化为 dashboard_external.py 中展示标签的拼接，没有增加 SQL、查询、DTO 字段或改变判断。
- 未修改排产算法、业务校验、错误码、数据库结构或业务数据。服务启动及页面读取属于正常运行。
- 导入原型快照未修改；本轮 symbol_locator 自动更新的 8 份调用图快照在起步时干净，已只恢复这些无关生成变动。

## 构建

命令：`.venv/bin/python scripts/workbench/build.py`

- 最终 build_id：`29b3ea9e074e9d3344d4d6392ba63107d05499717e48b051510097f43ab08bb8`
- 目标 Chrome109，260 个清单资产；沿用本地编译器及离线资源，没有引入运行时依赖。
- 已同步 static/workbench 下构建产物与 asset-manifest.json。

## 验证结果

各组独立执行，存在重复覆盖，不累加成不重复总测试数。首轮个别旧文案/旧选择器断言失败，均在保留业务断言的前提下同步并复测通过。

### 主线程图标、布局与页面联动

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_workbench_visual_controls.py \
  tests/workbench/test_actual_gantt_ui.py \
  tests/workbench/test_shared_controls_widgets.py \
  tests/workbench/test_workbench_plain_language.py \
  tests/workbench/test_ui_navigation_guard.py \
  tests/workbench/test_final_navigation_host.py
```

最终 23 passed in 30.22s。新增回归验证 7 种图标实际有非空图形、搜索图标不压字、关键链节点同排横滚、依赖关系保留、资源连线为虚线。实际甘特既有探针增加搜索/按钮单层边框和高度一致检查，覆盖 1920/1392 宽度及深浅主题。

最后仅调整资料总览未完成检查的措辞，再执行：

```bash
.venv/bin/python -m pytest -q tests/workbench/test_master_overview_reads.py tests/workbench/test_master_overview_boundaries.py
```

32 passed in 4.06s；之后重建得到上述最终 build_id。最终 Ruff 和 git diff --check 通过。

### 排产、试调、校准分组

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_trial_validation.py tests/workbench/test_trial_adoption_validation.py \
  tests/workbench/test_trial_api_schema.py tests/workbench/test_plan_workspace_projections.py \
  tests/workbench/test_plan_adoption_baseline_integrity.py tests/workbench/test_run_candidate_queries.py \
  tests/workbench/test_calibration_integrity.py tests/workbench/test_calibration_adoption.py \
  tests/workbench/test_preflight_api.py tests/workbench/test_template_lineage_calibration.py \
  tests/workbench/test_wbui_plan_gantt_models.py
```

163 passed in 30.71s；test_fe02_trial_static_contract.py 的 49 项通过；test_final_planning_l5_contract.py 同步旧提示断言后 1 项通过。5 类真实隔离 DTO 的 CSV 逐格校验通过，15 类损坏导出被拒绝；隔离数据库字节、结构及 typed rows 保持一致。

### 现场、报表、值班台、外协分组

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_ui_refinement_reports_review.py tests/workbench/test_report_read.py \
  tests/workbench/test_report_export.py tests/workbench/test_report_execution_ledger_read.py \
  tests/workbench/test_report_execution_ledger_export.py tests/workbench/test_dashboard_external_reads.py \
  tests/workbench/test_dashboard_external_identity.py tests/workbench/test_dashboard_reads.py \
  tests/workbench/test_actual_gantt_api.py tests/workbench/test_field_files_codec.py \
  tests/workbench/test_field_workspace_api.py
```

首跑 127 通过、1 个旧文案断言失败。修正该断言后：

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_field_files_codec.py tests/workbench/test_dashboard_external_identity.py \
  tests/workbench/test_outsourcing_identity.py tests/workbench/test_outsourcing_targets_labels.py \
  tests/workbench/test_outsourcing_api.py tests/workbench/test_round1_outsourcing_contract.py \
  tests/workbench/test_ui_refinement_reports_review.py
```

106 通过。最后补工序名称展示，test_dashboard_external_reads.py 与 test_dashboard_external_identity.py 共 36 项通过；覆盖正常未登记和原始关联缺失路径，存储、计数及错误码保持不变。

### 资料与系统分组

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_master_overview_reads.py tests/workbench/test_master_overview_boundaries.py \
  tests/workbench/test_du_system_restore_contract.py tests/workbench/test_du_system_restore_view.py
.venv/bin/python -m pytest -q \
  tests/workbench/test_resource_readiness.py tests/workbench/test_resource_calendar_summary.py \
  tests/workbench/test_resource_relations.py tests/workbench/test_resource_metrics.py \
  tests/workbench/test_process_queries.py tests/workbench/test_process_file_codec.py \
  tests/workbench/test_process_file_hours_preview.py tests/workbench/test_batch_files.py \
  tests/workbench/test_batch_execution_ledger_boundaries.py tests/workbench/test_material_queries.py \
  tests/workbench/test_material_files.py
.venv/bin/python -m pytest -q \
  tests/workbench/test_du_system_restore_contract.py tests/workbench/test_resource_details_widgets.py \
  tests/workbench/test_resource_file_widgets.py tests/workbench/test_process_stage_widgets.py \
  tests/workbench/test_process_widgets.py
```

第一组 37 通过、1 个旧文案断言失败，修正后包含在第三组复测通过；第二组 631 通过、1 个已删除模块选择器失败，更新为验证模块不存在、下一步入口保留，单独复测通过；第三组 5 项全部通过。

## 实际浏览器验收与交付

- 批次搜索框有放大镜且保持原留白；计划版本按钮有完整 SVG 图形。
- 实际甘特搜索容器边框 0、输入框边框 1px、文字左内边距 32px；分组按钮与容器同高。
- 六个关键链节点 y 坐标相同，定位图标横排；人员依赖连线计算样式为 4px,3px 虚线。
- 值班台同原因只显示一次，10 条工序全部保留，名称显示为“QA表处理（工序代码）”。
- 资料总览旧总免责声明已删除，人员班次的操作指引在真实数据上可见。
- 项目用现有 production 配置运行于 http://127.0.0.1:5000；没有运行门禁，没有 git commit 或 push。
- 这是当前未提交工作区的定向验证，不是 clean-worktree proof。未完整跑过所有业务流程；本轮浏览器未执行生产数据写入操作。
