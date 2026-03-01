# APS 架构合规审计报告

- 生成时间：2026-02-28 21:38:09
- 仓库根目录：`D:\Github\APS Test`

## 总结
- 总问题数：98
  - 分层违反：0
  - 文件超限：0
  - 禁止模式：0
  - 命名问题：0
  - 裸字符串枚举：52
  - 枚举集合比较（INFO）：68
  - 缺少 future annotations：0
  - 公开方法缺返回类型注解：0
  - Service 循环依赖：0
  - Route 越层导入 Repository：0
  - 潜在死代码公开方法：10
  - 圈复杂度超标（>15）：36
  - 圈复杂度扫描跳过：0
  - Vulture 死代码（min_confidence=80）：0
- 结论：FAIL（存在违反项）

## 圈复杂度分布
- A 简单(1-5): 933 ##################################################
- B 低(6-10): 254 ##################################################
- C 中(11-20): 91 ##################################################
- D 高(21-30): 16 ################
- E 很高(31-40): 1 #
- F 极高(41+): 2 ##

## 分层违反
- 无

## 文件超限
- 无

## 禁止模式
- 无

## 命名问题
- 无

## 裸字符串枚举
- [ENUM] web/routes/equipment_bp.py:16 - 裸字符串比较 '== "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/equipment_bp.py:18 - 裸字符串比较 '== "maintain"'，应使用 enums.py 枚举
- [ENUM] web/routes/equipment_bp.py:20 - 裸字符串比较 '== "inactive"'，应使用 enums.py 枚举
- [ENUM] web/routes/equipment_bp.py:26 - 裸字符串比较 '== "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/equipment_bp.py:28 - 裸字符串比较 '== "inactive"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_bp.py:16 - 裸字符串比较 '== "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_bp.py:18 - 裸字符串比较 '== "inactive"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_bp.py:24 - 裸字符串比较 '== "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_bp.py:26 - 裸字符串比较 '== "maintain"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_bp.py:28 - 裸字符串比较 '== "inactive"'，应使用 enums.py 枚举
- [ENUM] web/routes/personnel_bp.py:40 - 裸字符串比较 '== "workday"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_bp.py:17 - 裸字符串比较 '== "merged"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_bp.py:23 - 裸字符串比较 '== "external"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_excel_part_operations.py:43 - 裸字符串比较 '== "external"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_excel_part_operations.py:44 - 裸字符串比较 '== "merged"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_excel_part_operation_hours.py:84 - 裸字符串比较 '== "internal"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_excel_part_operation_hours.py:141 - 裸字符串比较 '!= "internal"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_parts.py:17 - 裸字符串比较 '== "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_parts.py:18 - 裸字符串比较 '== "internal"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_parts.py:19 - 裸字符串比较 '== "external"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_parts.py:54 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/process_suppliers.py:19 - 裸字符串比较 '== "inactive"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:61 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:63 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:87 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:89 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:113 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:115 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_batch_detail.py:166 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:11 - 裸字符串比较 '== "critical"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:13 - 裸字符串比较 '== "urgent"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:19 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:21 - 裸字符串比较 '== "partial"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:27 - 裸字符串比较 '== "pending"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:29 - 裸字符串比较 '== "scheduled"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:31 - 裸字符串比较 '== "processing"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:33 - 裸字符串比较 '== "completed"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:35 - 裸字符串比较 '== "cancelled"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_bp.py:41 - 裸字符串比较 '== "workday"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_excel_calendar.py:126 - 裸字符串比较 '== "workday"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_excel_calendar.py:138 - 裸字符串比较 '== "workday"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_excel_calendar.py:245 - 裸字符串比较 '== "workday"'，应使用 enums.py 枚举
- [ENUM] web/routes/scheduler_excel_calendar.py:257 - 裸字符串比较 '== "workday"'，应使用 enums.py 枚举
- [ENUM] core/services/material/batch_material_service.py:146 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] core/services/process/route_parser.py:184 - 裸字符串比较 '== "internal"'，应使用 enums.py 枚举
- [ENUM] core/services/process/route_parser.py:300 - 裸字符串比较 '== "external"'，应使用 enums.py 枚举
- [ENUM] core/services/report/calculations.py:152 - 裸字符串比较 '!= "internal"'，应使用 enums.py 枚举
- [ENUM] core/services/report/calculations.py:235 - 裸字符串比较 '!= "internal"'，应使用 enums.py 枚举
- [ENUM] core/services/scheduler/operation_edit_service.py:184 - 裸字符串比较 '!= "active"'，应使用 enums.py 枚举
- [ENUM] core/services/system/system_maintenance_service.py:94 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] core/services/system/system_maintenance_service.py:115 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举
- [ENUM] core/services/system/system_maintenance_service.py:136 - 裸字符串比较 '== "yes"'，应使用 enums.py 枚举

## 枚举集合比较（INFO）
- [ENUM-INFO] web/routes/equipment_excel_machines.py:38 - 枚举集合比较 ['active', 'inactive', 'maintain']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/equipment_excel_machines.py:181 - 枚举集合比较 ['active', 'inactive', 'maintain']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/equipment_excel_machines.py:245 - 枚举集合比较 ['active', 'inactive', 'maintain']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/equipment_pages.py:214 - 枚举集合比较 ['active', 'maintain', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/excel_demo.py:44 - 枚举集合比较 ['active', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_bp.py:42 - 枚举集合比较 ['holiday', 'weekend']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_bp.py:55 - 枚举集合比较 ['workday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_bp.py:57 - 枚举集合比较 ['weekend']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_bp.py:59 - 枚举集合比较 ['holiday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_bp.py:66 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_bp.py:68 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/personnel_pages.py:181 - 枚举集合比较 ['active', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_op_types.py:28 - 枚举集合比较 ['internal']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_op_types.py:30 - 枚举集合比较 ['external']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_op_types.py:76 - 枚举集合比较 ['internal', 'external']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_op_types.py:145 - 枚举集合比较 ['internal', 'external']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_suppliers.py:28 - 枚举集合比较 ['active']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_suppliers.py:30 - 枚举集合比较 ['inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_suppliers.py:101 - 枚举集合比较 ['active', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/process_excel_suppliers.py:187 - 枚举集合比较 ['active', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_batch_detail.py:131 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_batch_detail.py:133 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_bp.py:44 - 枚举集合比较 ['weekend', 'holiday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_excel_calendar.py:120 - 枚举集合比较 ['workday', 'holiday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_excel_calendar.py:149 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_excel_calendar.py:152 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_excel_calendar.py:239 - 枚举集合比较 ['workday', 'holiday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_excel_calendar.py:268 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_excel_calendar.py:271 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_gantt.py:30 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_gantt.py:32 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:29 - 枚举集合比较 ['normal']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:31 - 枚举集合比较 ['urgent']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:33 - 枚举集合比较 ['critical']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:40 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:42 - 枚举集合比较 ['partial']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:44 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:70 - 枚举集合比较 ['workday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:73 - 枚举集合比较 ['weekend']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:75 - 枚举集合比较 ['holiday']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:82 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/scheduler_utils.py:84 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] web/routes/system_plugins.py:28 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/common/excel_validators.py:49 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/common/excel_validators.py:51 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/equipment/machine_excel_import_service.py:68 - 枚举集合比较 ['active', 'inactive', 'maintain']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/personnel/operator_machine_service.py:69 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/personnel/operator_machine_service.py:71 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/op_type_excel_import_service.py:57 - 枚举集合比较 ['internal']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/op_type_excel_import_service.py:59 - 枚举集合比较 ['external']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/op_type_excel_import_service.py:63 - 枚举集合比较 ['internal', 'external']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/op_type_service.py:45 - 枚举集合比较 ['internal', 'external']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/supplier_excel_import_service.py:33 - 枚举集合比较 ['active']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/supplier_excel_import_service.py:35 - 枚举集合比较 ['inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/supplier_excel_import_service.py:77 - 枚举集合比较 ['active', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/process/supplier_service.py:73 - 枚举集合比较 ['active', 'inactive']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/calendar_admin.py:84 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/calendar_admin.py:86 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:394 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:400 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:417 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:428 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/config_service.py:475 - 枚举集合比较 ['yes', 'no']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/gantt_tasks.py:42 - 枚举集合比较 ['normal', 'urgent', 'critical']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/resource_pool_builder.py:27 - 枚举集合比较 ['normal']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/scheduler/resource_pool_builder.py:96 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/system/system_config_service.py:20 - 枚举集合比较 ['yes']（可能是输入校验），建议使用 enums.py/normalize
- [ENUM-INFO] core/services/system/system_config_service.py:22 - 枚举集合比较 ['no']（可能是输入校验），建议使用 enums.py/normalize

## 缺少 future annotations
- 无

## 公开方法缺返回类型注解
- 无

## Service 循环依赖
- 无

## Route 越层导入 Repository
- 无

## 潜在死代码公开方法
- [DEAD-CODE] core/services/common/excel_service.py:61 - 公开方法 read_rows() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/common/excel_service.py:64 - 公开方法 write_rows() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/process/deletion_validator.py:173 - 公开方法 get_deletable_external_ops() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/process/unit_excel_converter.py:26 - 公开方法 convert() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/process/unit_excel/template_builder.py:35 - 公开方法 rows_by_filename() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/calendar_admin.py:95 - 公开方法 get_row() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/config_service.py:273 - 公开方法 set_active_preset() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/gantt_range.py:38 - 公开方法 start_str() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/scheduler/gantt_range.py:42 - 公开方法 end_exclusive_str() 无外部调用者（潜在死代码）
- [DEAD-CODE] core/services/system/system_job_state_query_service.py:24 - 公开方法 get_map() 无外部调用者（潜在死代码）

## 圈复杂度超标
- [COMPLEXITY] web/routes/excel_demo.py:67 preview complexity=19 (rank C)
- [COMPLEXITY] web/routes/personnel_excel_operator_calendar.py:173 excel_operator_calendar_confirm complexity=19 (rank C)
- [COMPLEXITY] web/routes/process_excel_routes.py:109 excel_routes_confirm complexity=23 (rank D)
- [COMPLEXITY] web/routes/scheduler_excel_calendar.py:193 excel_calendar_confirm complexity=24 (rank D)
- [COMPLEXITY] web/routes/scheduler_run.py:25 run_schedule complexity=21 (rank D)
- [COMPLEXITY] web/routes/scheduler_week_plan.py:89 week_plan_export complexity=16 (rank C)
- [COMPLEXITY] core/services/equipment/machine_downtime_service.py:136 create_by_scope complexity=19 (rank C)
- [COMPLEXITY] core/services/personnel/operator_machine_service.py:412 apply_import_links complexity=20 (rank C)
- [COMPLEXITY] core/services/process/part_service.py:379 delete_external_group complexity=16 (rank C)
- [COMPLEXITY] core/services/process/part_service.py:424 calc_deletable_external_group_ids complexity=16 (rank C)
- [COMPLEXITY] core/services/process/route_parser.py:105 parse complexity=27 (rank D)
- [COMPLEXITY] core/services/report/calculations.py:141 compute_utilization complexity=21 (rank D)
- [COMPLEXITY] core/services/report/calculations.py:212 compute_downtime_impact complexity=24 (rank D)
- [COMPLEXITY] core/services/scheduler/batch_service.py:258 update complexity=17 (rank C)
- [COMPLEXITY] core/services/scheduler/config_service.py:159 ensure_defaults complexity=21 (rank D)
- [COMPLEXITY] core/services/scheduler/config_validator.py:11 normalize_preset_snapshot complexity=23 (rank D)
- [COMPLEXITY] core/services/scheduler/freeze_window.py:132 build_freeze_window_seed complexity=16 (rank C)
- [COMPLEXITY] core/services/scheduler/gantt_range.py:46 resolve_week_range complexity=16 (rank C)
- [COMPLEXITY] core/services/scheduler/operation_edit_service.py:161 update_external_operation complexity=18 (rank C)
- [COMPLEXITY] core/services/scheduler/resource_pool_builder.py:113 load_machine_downtimes complexity=22 (rank D)
- [COMPLEXITY] core/services/scheduler/resource_pool_builder.py:232 extend_downtime_map_for_resource_pool complexity=22 (rank D)
- [COMPLEXITY] core/services/scheduler/schedule_optimizer.py:32 _run_local_search complexity=28 (rank D)
- [COMPLEXITY] core/services/scheduler/schedule_optimizer.py:186 optimize_schedule complexity=50 (rank F)
- [COMPLEXITY] core/services/scheduler/schedule_service.py:198 _run_schedule_impl complexity=51 (rank F)
- [COMPLEXITY] core/models/batch_operation.py:29 from_row complexity=21 (rank D)
- [COMPLEXITY] core/models/calendar.py:22 from_row complexity=16 (rank C)
- [COMPLEXITY] core/models/calendar.py:84 from_row complexity=17 (rank C)
- [COMPLEXITY] core/models/part_operation.py:26 from_row complexity=16 (rank C)
- [COMPLEXITY] core/infrastructure/backup.py:74 restore complexity=27 (rank D)
- [COMPLEXITY] core/infrastructure/database.py:42 _restore_db_file_from_backup complexity=16 (rank C)
- [COMPLEXITY] core/infrastructure/database.py:111 ensure_schema complexity=20 (rank C)
- [COMPLEXITY] core/infrastructure/database.py:276 _migrate_with_backup complexity=29 (rank D)
- [COMPLEXITY] core/infrastructure/transaction.py:58 transaction complexity=21 (rank D)
- [COMPLEXITY] core/infrastructure/migrations/v1.py:19 _ensure_columns complexity=19 (rank C)
- [COMPLEXITY] core/infrastructure/migrations/v1.py:86 _sanitize_batch_dates complexity=22 (rank D)
- [COMPLEXITY] core/infrastructure/migrations/v4.py:35 _sanitize_field complexity=39 (rank E)

## 圈复杂度扫描跳过
- 无

## Vulture 死代码
- 无

