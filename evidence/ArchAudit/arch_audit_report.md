# APS 架构合规审计报告

- 生成时间：2026-03-13 13:53:59
- 仓库根目录：`D:\Github\APS Test`

## 总结
- 总问题数：53
  - 分层违反：0
  - 文件超限：1
  - 禁止模式：0
  - 命名问题：1
  - 裸字符串枚举：4
  - 枚举集合比较（INFO）：16
  - 缺少 future annotations：0
  - 公开方法缺返回类型注解：0
  - Service 循环依赖：0
  - Route 越层导入 Repository：0
  - 潜在死代码公开方法：9
  - 圈复杂度超标（>15）：38
  - 圈复杂度扫描跳过：0
  - 类型注解扫描跳过：0
  - Vulture 死代码（min_confidence=80）：0
  - Vulture 扫描跳过：0
- 跳过/信息项总计：0（不影响 PASS/FAIL）
- 结论：FAIL（存在违反项）

## 圈复杂度分布
- A 简单(1-5): 1054 ##################################################
- B 低(6-10): 289 ##################################################
- C 中(11-20): 98 ##################################################
- D 高(21-30): 16 ################
- E 很高(31-40): 2 ##
- F 极高(41+): 2 ##

## 分层违反
- 无

## 文件超限
- [SIZE] core/services/personnel/operator_machine_service.py - 503 行（超过 500 行限制）

## 禁止模式
- 无

## 命名问题
- [NAMING] core/services/scheduler/_sched_utils.py - 文件名不是 snake_case

## 裸字符串枚举
- [ENUM] web/routes/personnel_calendar_pages.py:32 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_calendar_pages.py:33 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_calendar_pages.py:34 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_calendar_pages.py:35 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举

## 枚举集合比较（INFO）
- [ENUM-INFO] web/routes/scheduler_batch_detail.py:140 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_batch_detail.py:142 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_gantt.py:30 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_gantt.py:32 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/system_plugins.py:28 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/common/enum_normalizers.py:149 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/personnel/operator_machine_service.py:53 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/personnel/operator_machine_service.py:55 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/personnel/operator_machine_service.py:75 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/personnel/operator_machine_service.py:77 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:405 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:411 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:428 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:439 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:486 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/gantt_tasks.py:43 - 枚举集合比较 ['normal', 'urgent', 'critical']（可能是输入校验），建议使用 enums.py/normalize

## 缺少 future annotations
- 无

## 公开方法缺返回类型注解
- 无

## Service 循环依赖
- 无

## Route 越层导入 Repository
- 无

## 潜在死代码公开方法
- [DEAD-CODE] core/services/personnel/resource_team_service.py:112 - 公开方法 get_usage_counts() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/process/part_operation_hours_excel_import_service.py:22 - 公开方法 add_error() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_engine.py:34 - 公开方法 is_priority_allowed() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_engine.py:44 - 公开方法 work_window() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:106 - 公开方法 get_operator_calendar() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:143 - 公开方法 upsert_operator_calendar_no_tx() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:148 - 公开方法 delete_operator_calendar() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_service.py:152 - 公开方法 delete_operator_calendar_all_no_tx() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/system/system_config_service.py:141 - 公开方法 get_snapshot_readonly() 无外部调用者（潜在死代码）

## 圈复杂度超标
- [COMPLEXITY] web/routes/equipment_pages.py:62 list_page complexity=16 (rank C)
- [COMPLEXITY] web/routes/excel_demo.py:69 preview complexity=19 (rank C)
- [COMPLEXITY] web/routes/personnel_excel_operator_calendar.py:173 excel_operator_calendar_confirm complexity=19 (rank C)
- [COMPLEXITY] web/routes/process_excel_routes.py:109 excel_routes_confirm complexity=23 (rank D)
- [COMPLEXITY] web/routes/scheduler_config.py:221 update_config complexity=17 (rank C)
- [COMPLEXITY] web/routes/scheduler_excel_calendar.py:194 excel_calendar_confirm complexity=24 (rank D)
- [COMPLEXITY] web/routes/scheduler_run.py:25 run_schedule complexity=21 (rank D)
- [COMPLEXITY] web/routes/scheduler_week_plan.py:89 week_plan_export complexity=16 (rank C)
- [COMPLEXITY] core/services/equipment/machine_downtime_service.py:136 create_by_scope complexity=19 (rank C)
- [COMPLEXITY] core/services/personnel/operator_machine_service.py:427 apply_import_links complexity=20 (rank C)
- [COMPLEXITY] core/services/process/part_service.py:379 delete_external_group complexity=16 (rank C)
- [COMPLEXITY] core/services/process/part_service.py:424 calc_deletable_external_group_ids complexity=16 (rank C)
- [COMPLEXITY] core/services/process/route_parser.py:107 parse complexity=27 (rank D)
- [COMPLEXITY] core/services/report/calculations.py:142 compute_utilization complexity=21 (rank D)
- [COMPLEXITY] core/services/report/calculations.py:213 compute_downtime_impact complexity=24 (rank D)
- [COMPLEXITY] core/services/scheduler/batch_service.py:265 update complexity=17 (rank C)
- [COMPLEXITY] core/services/scheduler/config_service.py:159 ensure_defaults complexity=21 (rank D)
- [COMPLEXITY] core/services/scheduler/config_validator.py:11 normalize_preset_snapshot complexity=23 (rank D)
- [COMPLEXITY] core/services/scheduler/freeze_window.py:133 build_freeze_window_seed complexity=16 (rank C)
- [COMPLEXITY] core/services/scheduler/gantt_range.py:46 resolve_week_range complexity=16 (rank C)
- [COMPLEXITY] core/services/scheduler/operation_edit_service.py:160 update_external_operation complexity=18 (rank C)
- [COMPLEXITY] core/services/scheduler/resource_dispatch_excel.py:61 _detail_table_rows complexity=24 (rank D)
- [COMPLEXITY] core/services/scheduler/resource_dispatch_excel.py:101 build_resource_dispatch_workbook complexity=32 (rank E)
- [COMPLEXITY] core/services/scheduler/resource_pool_builder.py:102 load_machine_downtimes complexity=22 (rank D)
- [COMPLEXITY] core/services/scheduler/resource_pool_builder.py:221 extend_downtime_map_for_resource_pool complexity=22 (rank D)
- [COMPLEXITY] core/services/scheduler/schedule_optimizer.py:33 _run_local_search complexity=28 (rank D)
- [COMPLEXITY] core/services/scheduler/schedule_optimizer.py:187 optimize_schedule complexity=50 (rank F)
- [COMPLEXITY] core/services/scheduler/schedule_service.py:198 _run_schedule_impl complexity=51 (rank F)
- [COMPLEXITY] core/models/batch_operation.py:30 from_row complexity=21 (rank D)
- [COMPLEXITY] core/models/calendar.py:23 from_row complexity=16 (rank C)
- [COMPLEXITY] core/models/calendar.py:90 from_row complexity=17 (rank C)
- [COMPLEXITY] core/models/part_operation.py:27 from_row complexity=16 (rank C)
- [COMPLEXITY] core/infrastructure/backup.py:76 restore complexity=27 (rank D)
- [COMPLEXITY] core/infrastructure/database.py:106 ensure_schema complexity=20 (rank C)
- [COMPLEXITY] core/infrastructure/database.py:311 _migrate_with_backup complexity=22 (rank D)
- [COMPLEXITY] core/infrastructure/transaction.py:57 transaction complexity=21 (rank D)
- [COMPLEXITY] core/infrastructure/migrations/v1.py:100 _sanitize_batch_dates complexity=19 (rank C)
- [COMPLEXITY] core/infrastructure/migrations/v4.py:36 _sanitize_field complexity=33 (rank E)

## 圈复杂度扫描跳过
- 无

## 类型注解扫描跳过
- 无

## Vulture 死代码
- 无

## Vulture 扫描跳过
- 无

