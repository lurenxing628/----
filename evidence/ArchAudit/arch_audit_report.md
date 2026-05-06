# APS 架构合规审计报告

- 生成时间：2026-05-06 22:36:53
- 仓库根目录：`/Users/lurenxing/Documents/GitHub/----`

## 总结
- 总问题数：81
  - 分层违反：0
  - 文件超限：1
  - 禁止模式：0
  - 命名问题：3
  - 裸字符串枚举：15
  - 枚举集合比较（INFO）：5
  - 缺少 future annotations：1
  - 公开方法缺返回类型注解：0
  - Service 循环依赖：0
  - Route 越层导入 Repository：0
  - 潜在死代码公开方法：46
  - 圈复杂度超标（>15）：15
  - 圈复杂度扫描跳过：0
  - 类型注解扫描跳过：0
  - Vulture 死代码（min_confidence=80）：0
  - Vulture 扫描跳过：1
- 跳过/信息项总计：1（不影响 PASS/FAIL）
- 结论：FAIL（存在违反项）

## 圈复杂度分布
- A 简单(1-5): 1961 ##################################################
- B 低(6-10): 459 ##################################################
- C 中(11-20): 119 ##################################################
- D 高(21-30): 4 ####
- E 很高(31-40): 0
- F 极高(41+): 0

## 分层违反
- 无

## 文件超限
- [SIZE] core/services/personnel/operator_machine_service.py - 504 行（超过 500 行限制）

## 禁止模式
- 无

## 命名问题
- [NAMING] web/routes/_scheduler_compat.py - 文件名不是 snake_case
- [NAMING] core/services/scheduler/_sched_utils.py - 文件名不是 snake_case
- [NAMING] core/services/scheduler/_sched_display_utils.py - 文件名不是 snake_case

## 裸字符串枚举
- [ENUM] web/routes/system_plugins.py:52 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/form_values.py:52 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_calendar_pages.py:34 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_calendar_pages.py:35 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_calendar_pages.py:31 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_calendar_pages.py:32 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:95 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:102 - 裸字符串比较 '== "no"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:149 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:160 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:167 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:178 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/domains/scheduler/scheduler_config_display_state.py:185 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] core/services/scheduler/resource_dispatch_support.py:143 - 裸字符串比较 '== "external"'，应使用 enums.py 枚举
- [ENUM] core/services/system/system_config_service.py:35 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举

## 枚举集合比较（INFO）
- [ENUM-INFO] web/routes/domains/scheduler/scheduler_gantt.py:34 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/domains/scheduler/scheduler_gantt.py:36 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/domains/scheduler/scheduler_batch_detail.py:145 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/domains/scheduler/scheduler_batch_detail.py:147 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/_sched_display_utils.py:41 - 枚举集合比较 ['normal', 'urgent', 'critical']（可能是输入校验），建议使用 enums.py/normalize

## 缺少 future annotations
- [FUTURE] web/routes/domains/scheduler/__init__.py - 缺少 from __future__ import annotations

## 公开方法缺返回类型注解
- 无

## Service 循环依赖
- 无

## Route 越层导入 Repository
- 无

## 潜在死代码公开方法
- [DEAD-CODE] core/services/scheduler/calendar_service.py:107 - 公开方法 get_operator_calendar() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:144 - 公开方法 upsert_operator_calendar_no_tx() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:149 - 公开方法 delete_operator_calendar() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:153 - 公开方法 delete_operator_calendar_all_no_tx() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/schedule_service.py:136 - 公开方法 get_external_merge_hint_for_op() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/schedule_service.py:142 - 公开方法 get_external_merge_hint() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_engine.py:41 - 公开方法 is_priority_allowed() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_engine.py:51 - 公开方法 work_window() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/gantt_service.py:41 - 公开方法 get_latest_version_or_1() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_read_service.py:135 - 公开方法 list_config_rows() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_read_service.py:153 - 公开方法 build_preset_entries() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_outcome.py:183 - 公开方法 effective_snapshot() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_outcome.py:192 - 公开方法 to_snapshot_dict() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_outcome.py:195 - 公开方法 to_effective_snapshot_dict() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_outcome.py:198 - 公开方法 raw_effective_mismatches() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_outcome.py:216 - 公开方法 to_outcome_dict() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_outcome.py:237 - 公开方法 to_public_outcome_dict() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/active_preset_state.py:21 - 公开方法 can_preserve_baseline() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/active_preset_state.py:43 - 公开方法 drifted() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:315 - 公开方法 get_active_preset_meta() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:326 - 公开方法 list_presets() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:387 - 公开方法 set_strategy() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:390 - 公开方法 set_weights() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:396 - 公开方法 set_dispatch() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:399 - 公开方法 set_auto_assign_enabled() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:402 - 公开方法 set_ortools() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:405 - 公开方法 set_prefer_primary_skill() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:408 - 公开方法 set_enforce_ready_default() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:411 - 公开方法 set_holiday_default_efficiency() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:414 - 公开方法 set_algo_mode() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:417 - 公开方法 set_time_budget_seconds() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:420 - 公开方法 set_objective() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_service.py:423 - 公开方法 set_freeze_window() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_preset_service.py:115 - 公开方法 validate_preset_name() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_save_service.py:79 - 公开方法 current_provenance_state() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_save_service.py:126 - 公开方法 apply_visible_change_plan() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_save_service.py:141 - 公开方法 apply_visible_repair_plan() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_page_save_service.py:260 - 公开方法 raw_persisted_state() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_write_service.py:42 - 公开方法 set_fields_mark_custom() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config/config_write_service.py:99 - 公开方法 set_yes_no_field() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/run/schedule_persistence.py:32 - 公开方法 to_repo_rows() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/run/schedule_optimizer_steps.py:25 - 公开方法 schedule() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/system/system_config_service.py:198 - 公开方法 get_snapshot_readonly() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/system/system_config_service.py:204 - 公开方法 get_value_with_presence() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/personnel/resource_team_service.py:112 - 公开方法 get_usage_counts() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/process/part_operation_hours_excel_import_service.py:32 - 公开方法 add_error() 无外部调用者（潜在死代码）

## 圈复杂度超标
- [COMPLEXITY] web/routes/process_excel_routes.py:214 excel_routes_confirm complexity=27 (rank D)
- [COMPLEXITY] core/services/scheduler/resource_dispatch_excel.py:157 _summary_pairs complexity=19 (rank C)
- [COMPLEXITY] core/services/scheduler/resource_dispatch_support.py:26 extract_overdue_batch_ids_with_meta complexity=19 (rank C)
- [COMPLEXITY] core/services/scheduler/gantt_range.py:46 resolve_week_range complexity=16 (rank C)
- [COMPLEXITY] core/services/scheduler/gantt_week_plan.py:32 build_week_plan_rows complexity=17 (rank C)
- [COMPLEXITY] core/services/scheduler/operation_edit_service.py:168 update_external_operation complexity=21 (rank D)
- [COMPLEXITY] core/services/equipment/machine_downtime_service.py:136 create_by_scope complexity=19 (rank C)
- [COMPLEXITY] core/services/personnel/operator_machine_service.py:408 apply_import_links complexity=21 (rank D)
- [COMPLEXITY] core/services/personnel/operator_machine_query_service.py:26 _normalize_row complexity=19 (rank C)
- [COMPLEXITY] core/models/batch_operation.py:57 from_row complexity=21 (rank D)
- [COMPLEXITY] core/models/calendar.py:23 from_row complexity=16 (rank C)
- [COMPLEXITY] core/models/calendar.py:90 from_row complexity=17 (rank C)
- [COMPLEXITY] core/models/part_operation.py:48 from_row complexity=16 (rank C)
- [COMPLEXITY] core/infrastructure/database.py:90 ensure_schema complexity=16 (rank C)
- [COMPLEXITY] core/infrastructure/migrations/v1.py:101 _sanitize_batch_dates complexity=20 (rank C)

## 圈复杂度扫描跳过
- 无

## 类型注解扫描跳过
- 无

## Vulture 死代码
- 无

## Vulture 扫描跳过
- [VULTURE] vulture 未安装，跳过死代码检测
