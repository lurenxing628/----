---
doc_type: issue-fix
issue: scheduler-public-readable-closeout
status: fixed
path: fast-track
fix_date: 2026-05-11
severity: high
root_cause_type: public-copy-contract
tags:
  - scheduler
  - strict-mode
  - frontend-copy
  - docs
---

# 排产公开提示补闭环修复记录

## 1. 问题描述

三个前置提交已经把说明书、甘特弹窗和严格检查文案往正确方向推进了，但 review 发现还差几处闭环：

- 严格检查和兼容读取的底层错误仍可能把 `setup_hours`、`unit_hours`、`ext_days`、`priority_weight`、`freeze_window_days` 这类内部字段名露给用户。
- 坏时间行被过滤时，部分空态只说“已全部过滤”，没有告诉用户过滤了几条，也没有说明可以去哪里看这次排产的详细提醒。
- 多个页面仍写“到排产历史查看原因”，容易让用户误以为历史页一定能定位所有数据根因。
- 文档里还有两个小口径漂移：资源排班执行记录写成“批次”，README 写成“备份和恢复”。

## 2. 根因

- 数字解析、配置快照、优化器入参等底层函数原来主要保留机器字段，出错时 message 也沿用了机器字段。
- 兼容读取事件以前带“兼容读取”这种开发口径，现场人员不一定理解。
- 甘特图、周计划、资源排班、批次页、排产分析页的剩余提醒文案分散在多个模板和 presenter 里，没有统一成“详细提醒 / 提醒摘要”的说法。
- 文档和 README 没有用同一个页面入口名做最后对齐。

## 3. 修复方案

- 增加共享字段中文名映射，并让严格解析失败时保留 `ValidationError.field` 的内部 key，同时把 `ValidationError.message` 改成现场能看懂的字段名。
- 兼容读取和非严格降级提示改成业务话：换型时间、单件工时、外协周期、高级设置里的权重和锁定天数都用中文名。
- 坏时间过滤的空态补上过滤条数；排产历史入口统一说“查看这次排产的详细提醒”，摘要不完整时说“提醒摘要”。
- 坏时间行内部样本只保留排程编号、工序编号/编码、批次号和字段名，不再带原始坏时间值。
- 把资源排班执行记录的列名改成“批次号”，README 的导航入口统一成“备份/恢复”。

## 4. 改动文件清单

- `core/shared/field_labels.py`
- `core/shared/field_parse.py`
- `core/shared/compat_parse.py`
- `core/services/scheduler/run/schedule_input_builder.py`
- `core/services/scheduler/config/config_field_coercion.py`
- `core/services/scheduler/run/optimizer_config.py`
- `core/models/schedule_config_runtime_*`
- `core/services/scheduler/_sched_display_utils.py`
- `core/services/scheduler/resource_dispatch_support.py`
- `static/js/gantt_contract.js`
- `static/js/gantt_render.js`
- `static/js/resource_dispatch.js`
- `templates/scheduler/*.html`
- `web/viewmodels/scheduler_batches_*`
- `static/docs/scheduler_manual.md`
- `web_new_test/static/docs/scheduler_manual.md`
- `docs/manual_usability_review_report.md`
- `README.md`
- 相关回归测试文件

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/regression_schedule_optimizer_cfg_snapshot_contract.py tests/regression_schedule_params_strict_blank_numeric.py tests/test_schedule_params_direct_call_contract.py tests/regression_field_parse_contract.py tests/regression_config_validator_preset_degradation.py tests/regression_config_validator_relaxed_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_compat_parse_emits_degradation.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_config_snapshot_strict_numeric.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/regression_gantt_bad_time_rows_surface_degraded.py tests/regression_resource_dispatch_bad_time_rows_surface_degraded.py tests/regression_week_plan_bad_time_rows_surface_degraded.py tests/regression_gantt_critical_outline_sync.py tests/regression_scheduler_batches_presenter_contract.py tests/regression_scheduler_analysis_observability.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py tests/test_scheduler_batches_page_viewmodel.py tests/regression_config_manual_markdown.py`
- `cmp -s static/docs/scheduler_manual.md web_new_test/static/docs/scheduler_manual.md`
- `git diff --check`

## 6. 遗留事项

- 本次不再改甘特弹窗几何逻辑本身；该问题已由前置修复处理，本次只补了脚本加载顺序测试口径。
- 本次没有跑带干净工作区要求的完整质量门禁，因为当前工作区包含本次未提交改动。
