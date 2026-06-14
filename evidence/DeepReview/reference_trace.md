# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## web/viewmodels/dashboard_workbench.py（ViewModel 层）

### `_text()` [私有]
- 位置：第 23-24 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_safe_int()` [私有]
- 位置：第 27-31 行
- 参数：value, default
- 返回类型：Name(id='int', ctx=Load())

### `_safe_float()` [私有]
- 位置：第 34-40 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_datetime_label()` [私有]
- 位置：第 43-53 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_parse_datetime()` [私有]
- 位置：第 56-69 行
- 参数：value
- 返回类型：Name(id='datetime', ctx=Load())

### `_link()` [私有]
- 位置：第 72-73 行
- 参数：context, target_page, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_todo_item()` [私有]
- 位置：第 76-98 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_risk_card()` [私有]
- 位置：第 101-118 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_overdue_todo()` [私有]
- 位置：第 121-133 行
- 参数：context, overdue_count
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_candidate_comparison()` [私有]
- 位置：第 136-143 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_candidate_todo()` [私有]
- 位置：第 146-173 行
- 参数：context, latest_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_machine_util_ratio()` [私有]
- 位置：第 176-194 行
- 参数：latest_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_candidate_count()` [私有]
- 位置：第 197-210 行
- 参数：latest_summary
- 返回类型：Name(id='int', ctx=Load())

### `_has_current_summary()` [私有]
- 位置：第 213-217 行
- 参数：latest_summary, latest_summary_parse_state
- 返回类型：Name(id='bool', ctx=Load())

### `_nonnegative_count()` [私有]
- 位置：第 220-225 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_site_gap_context()` [私有]
- 位置：第 228-242 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_resource_load_todo()` [私有]
- 位置：第 245-260 行
- 参数：context, latest_summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_fact_for_op()` [私有]
- 位置：第 263-268 行
- 参数：execution_facts_by_op_id, op_id
- 返回类型：Name(id='Any', ctx=Load())

### `_fact_has_progress()` [私有]
- 位置：第 271-279 行
- 参数：fact
- 返回类型：Name(id='bool', ctx=Load())

### `_site_record_gap_rows()` [私有]
- 位置：第 282-302 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_site_record_gap_todo()` [私有]
- 位置：第 305-328 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_data_gap_todo()` [私有]
- 位置：第 331-358 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_todo_items()` [私有]
- 位置：第 361-385 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `build_dashboard_workbench_summary()` [公开]
- 位置：第 388-479 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/routes/dashboard.py:357` [Route] `workbench_summary = build_dashboard_workbench_summary(`
- **被调用者**（15 个）：`list`, `dict`, `_text`, `latest_plan_context`, `_site_gap_context`, `_todo_items`, `dashboard_data_gap_reason`, `build_cockpit_hero`, `datetime.now`, `_nonnegative_count`, `_candidate_count`, `build_dashboard_risk_cards`, `build_dashboard_quick_links`, `str`, `_machine_util_ratio`

## web/viewmodels/dashboard_workbench_cards.py（ViewModel 层）

### `_link()` [私有]
- 位置：第 18-19 行
- 参数：context, target_page, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_risk_card()` [私有]
- 位置：第 22-39 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_resource_load_card()` [私有]
- 位置：第 42-71 行
- 参数：context, resource_load_ratio
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_overdue_card()` [私有]
- 位置：第 74-91 行
- 参数：context, overdue_count
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_candidate_card()` [私有]
- 位置：第 94-120 行
- 参数：context, candidate_count
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_data_gap_card()` [私有]
- 位置：第 123-140 行
- 参数：context, data_gap_reason
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `build_dashboard_risk_cards()` [公开]
- 位置：第 143-183 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/dashboard_workbench.py:467` [ViewModel] `"risk_cards": build_dashboard_risk_cards(`
- **被调用者**（10 个）：`_risk_card`, `site_gap_card.update`, `_overdue_card`, `_candidate_card`, `_resource_load_card`, `_data_gap_card`, `_link`, `str`, `max`, `int`

### `build_dashboard_quick_links()` [公开]
- 位置：第 186-194 行
- 参数：context
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/viewmodels/dashboard_workbench.py:477` [ViewModel] `"quick_links": build_dashboard_quick_links(context),`
- **被调用者**（1 个）：`_link`

## web/routes/dashboard.py（Route 层）

### `_positive_version()` [私有]
- 位置：第 24-29 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_requested_version()` [私有]
- 位置：第 32-42 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_today_range()` [私有]
- 位置：第 45-51 行
- 参数：now
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_row_op_ids()` [私有]
- 位置：第 54-66 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_strict_count_value()` [私有]
- 位置：第 69-80 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_summary_overdue_count()` [私有]
- 位置：第 83-95 行
- 参数：summary
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_parse_state_with_summary_error()` [私有]
- 位置：第 98-104 行
- 参数：parse_state, error
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_plan_time_span()` [私有]
- 位置：第 107-114 行
- 参数：services, version, plan_role, scenario_id
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_load_today_rows()` [私有]
- 位置：第 117-132 行
- 参数：services, version, now, plan_role, scenario_id
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_load_execution_facts()` [私有]
- 位置：第 135-150 行
- 参数：rows, plan_fields
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_request_arg()` [私有]
- 位置：第 153-154 行
- 参数：name
- 返回类型：Name(id='str', ctx=Load())

### `_plan_resolution_context()` [私有]
- 位置：第 157-174 行
- 参数：services, version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_is_adopted_role_context()` [私有]
- 位置：第 177-180 行
- 参数：context
- 返回类型：Name(id='bool', ctx=Load())

### `_is_plain_plan_context()` [私有]
- 位置：第 183-189 行
- 参数：context
- 返回类型：Name(id='bool', ctx=Load())

### `_summary_matches_plan_identity()` [私有]
- 位置：第 192-197 行
- 参数：context
- 返回类型：Name(id='bool', ctx=Load())

### `_should_expose_summary_parse_failure()` [私有]
- 位置：第 200-205 行
- 参数：context
- 返回类型：Name(id='bool', ctx=Load())

### `_failed_run_applies_to_current_view()` [私有]
- 位置：第 208-230 行
- 参数：无
- 返回类型：Name(id='bool', ctx=Load())

### `_workbench_summary_parse_state()` [私有]
- 位置：第 233-245 行
- 参数：workbench_history, context, summary_matches_identity
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_summary_payload_dict()` [私有]
- 位置：第 248-250 行
- 参数：parse_state
- 返回类型：Name(id='Any', ctx=Load())

### `_workbench_history_context()` [私有]
- 位置：第 253-262 行
- 参数：history_q
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_workbench_navigation_context_from_request()` [私有]
- 位置：第 265-280 行
- 参数：services, version
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `index()` [公开]
- 位置：第 284-394 行
- 参数：无
- 返回类型：无注解
- **调用者**（4 处）：
  - `scripts/run_quality_gate.py:1924` [Script] `index = list(args).index(option)`
  - `tools/collect_full_test_debt.py:430` [Tool] `separator = raw_args.index("--")`
  - `tools/quality_gate_shared.py:1408` [Tool] `start = text.index(begin_marker) + len(begin_marker)`
  - `tools/quality_gate_shared.py:1409` [Tool] `end = text.index(end_marker)`
- **被调用者**（26 个）：`bp.get`, `len`, `datetime.now`, `_workbench_history_context`, `_workbench_navigation_context_from_request`, `set_current_workbench_navigation_context`, `_summary_matches_plan_identity`, `parse_history_summary_state`, `_workbench_summary_parse_state`, `_summary_payload_dict`, `_summary_overdue_count`, `str`, `_load_plan_time_span`, `_load_execution_facts`, `_failed_run_applies_to_current_view`

---
- 分析函数/方法数：54
- 找到调用关系：7 处
- 跨层边界风险：0 项
