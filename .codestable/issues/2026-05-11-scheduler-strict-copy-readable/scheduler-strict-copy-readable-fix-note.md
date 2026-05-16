# 排产严格检查文案改成现场能看懂的话

## 背景

排产调度页的“发现参数问题就停止排产”原来用了“配置不合法”“安全取值”“工时空着时可能按 0 小时”这些说法。现场操作人员看完以后不知道具体是哪项错、系统会怎么处理、自己要回哪里补资料。

## 根因

- 页面短说明只写“配置不合法”，没有说明实际检查范围。
- 展开说明只列了派工方式、智能派工策略、自动分配设备人员三项，但真实 `strict_mode` 还会影响工时、外协周期、权重、冻结窗口等排产输入。
- 工时规则写成“可能按 0”，但代码规则是确定的：未勾选严格检查时，换型时间和单件工时读取失败会按 0 小时继续并留下提醒；勾选严格检查时会直接报错停下。
- 排产结果提醒、甘特图提醒、配置修复提醒里还残留“安全取值”“配置无效”“时间不合法”这类偏技术的话。

## 修改

- 把排产面板短说明改成“排产设置填得不对会先停下”，并举出选项、工时、权重、锁定天数这些现场能识别的项目。
- 把展开说明改成两类检查：页面选项必须是能选到的值，数字必须是正常数字；不勾严格检查时用默认值继续，并列出空工时按 0、外协周期缺失按 1 天等例子。
- 把截止日期下方风险提示改成确定规则：不勾严格检查时工时问题按 0 小时继续并提醒，勾选后直接报错停下。
- 同步页面帮助卡、主说明书、镜像说明书、排产结果提醒、甘特图时间提醒和配置修复提醒。
- 增加回归测试，禁止排产相关用户可见文案重新出现“配置不合法”“安全取值”“可能按 0”“配置无效”“时间不合法”等旧说法。
- 把这批高风险回归测试加入质量门禁清单，避免以后只在本地临时跑过、门禁却没有守住。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frontend_ui_language_polish.py tests/regression_scheduler_run_entry_layout_contract.py tests/regression_scheduler_config_route_contract.py tests/test_holiday_default_efficiency_read_guard.py tests/regression_config_snapshot_projection_sync.py tests/regression_schedule_summary_overdue_warning_append_fallback.py tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py tests/regression_resource_dispatch_bad_time_rows_surface_degraded.py tests/regression_gantt_critical_outline_sync.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_strict_mode_dispatch_flags.py tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/regression_process_excel_part_operation_hours_import.py tests/test_part_operation_hours_import_apply_defense.py tests/test_part_operation_hours_import_apply_mixed_rows.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions`
- `node --check static/js/gantt_contract.js`
- 浏览器打开 `http://localhost:5000/scheduler/`，排产操作区不再出现旧说法，并能看到新的严格检查和工时说明。
