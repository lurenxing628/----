# Phase 覆盖矩阵 / Backlog 清单（对齐 ArchAudit）

- 时间：2026-02-28 20:55
- 目的：将 `evidence/ArchAudit/arch_audit_report.md` 中的高风险条目（复杂度/类型注解/潜在死代码/裸枚举）全部**明确归属**到 Phase2/3/4/5 或 Backlog，并写清理由与触发条件，避免后续闭环“范围爆炸/遗漏”。

## 当前事实基线（用于对齐）

- 最新 ArchAudit：`evidence/ArchAudit/arch_audit_report.md`（2026-02-28 19:47:31）
  - 裸字符串枚举：80
  - 缺少 future annotations：0（已清零）
  - 公开方法缺返回类型注解：6
  - 潜在死代码公开方法：10
  - 圈复杂度超标（>15）：49
- Service 层直连 SQL 盘点：`audit/2026-02/20260228_1945_service_sql_inventory.md`
- 枚举映射表（含模板/前端登记）：`audit/2026-02/20260228_2025_enum_mapping.md`

## 已完成阶段（本里程碑已闭环）

- **Phase0b/Tooling/Freeze**：基线补齐 + 冻结快照（见 `audit/2026-02/20260228_1925_phase0b_baseline_refresh.md` 与 `evidence/Baseline/Phase0b_20260228_1932/`）
- **Phase0c**：future annotations 清零（见 `audit/2026-02/20260228_1955_phase0c_future_annotations_closeout.md`）
- **Phase1b**：scheduler 残留复杂度闭环（见 `audit/2026-02/20260228_2010_phase1b_scheduler_residual_closeout.md`）

## Phase 覆盖矩阵（剩余待做）

> 说明：以下“归属”用于排期与影响域控制；实际执行应按计划每批 2~6 文件推进，并遵循分层/SQL 参数化/文档联动门禁。

### Phase2：Excel 导入链路闭环

- **Excel 基础设施（typehint/复杂度/死代码线索）**
  - `core/services/common/excel_service.py`（TYPEHINT + DEAD-CODE 线索）
  - `core/services/common/openpyxl_backend.py`（TYPEHINT + COMPLEXITY）
  - `core/services/common/pandas_backend.py`（TYPEHINT + COMPLEXITY；保持可选依赖）
  - `core/services/common/tabular_backend.py`（TYPEHINT）
  - `core/services/common/excel_audit.py` / `core/services/common/excel_validators.py` / `core/services/common/excel_import_executor.py`（按批次闭环）
- **Excel 路由 confirm 高复杂度（归入 Excel 链路，不提前放到 Phase4）**
  - `web/routes/personnel_excel_operator_calendar.py`（COMPLEXITY）
  - `web/routes/process_excel_part_operation_hours.py`（COMPLEXITY E）
  - `web/routes/process_excel_routes.py`（COMPLEXITY D）
  - `web/routes/scheduler_excel_calendar.py`（COMPLEXITY D）
  - `web/routes/excel_demo.py`（COMPLEXITY；如仅示例用途可转 Backlog）
- **Process unit_excel 工具链（F 级）**
  - `core/services/process/unit_excel/template_builder.py`（COMPLEXITY F + DEAD-CODE 线索）
  - `core/services/process/unit_excel/parser.py`（COMPLEXITY）
  - `core/services/process/unit_excel_converter.py`（DEAD-CODE 线索）

### Phase3：业务域服务闭环（Process → Personnel → Equipment）

- **Personnel**
  - `core/services/personnel/operator_machine_service.py`（COMPLEXITY F/E + 裸枚举 + Service 直连 SQL）
- **Process**
  - `core/services/process/deletion_validator.py`（COMPLEXITY D + DEAD-CODE 线索 + 裸枚举）
  - `core/services/process/external_group_service.py`（TYPEHINT + COMPLEXITY D + 裸枚举）
  - `core/services/process/route_parser.py`（COMPLEXITY D + 裸枚举）
  - `core/services/process/part_service.py`（裸枚举 + Service 直连 SQL；随工艺闭环修复）
- **Equipment**
  - `core/services/equipment/machine_service.py`（Service 直连 SQL：删除校验）
  - `core/services/equipment/machine_downtime_service.py`（COMPLEXITY + 裸枚举）

### Phase4：Route 边界 + 模板/前端契约

- **高复杂度 Route（优先）**
  - `web/routes/scheduler_analysis.py` + `web/viewmodels/scheduler_analysis_vm.py` + `templates/scheduler/analysis.html`（COMPLEXITY F）
  - `web/routes/system_logs.py` + `templates/system/logs.html`（COMPLEXITY）
  - `web/routes/scheduler_run.py`（COMPLEXITY D；涉及“运行排产”链路需谨慎）
- **模板/前端枚举契约**
  - 引用点登记见 `audit/2026-02/20260228_2025_enum_mapping.md`；Phase4 批次内只做“本批次触达模板”的最小一致性收敛。

### Phase5：Repository/SQL 与数据层一致性

- **固定纳入（分层修复）**
  - `core/services/material/batch_material_service.py`（Service 直连 SQL；已在清单中固定纳入 Phase5）
- **同批次可能联动（Repo 下沉/参数化/字段契约）**
  - `data/repositories/*`（随具体 SQL 下沉点决定；严格参数化）
  - `core/models/*`（`from_row()` 契约与字段一致性；如 `core/models/batch_operation.py` 的复杂度/映射问题需结合 repo 修复）
- **可选：基础设施一致性批次（若纳入）**
  - `core/infrastructure/backup.py` / `core/infrastructure/database.py` / `core/infrastructure/transaction.py`（仍有复杂度条目；仅做一致性/降复杂度，不夹带业务改动）

## Backlog（本里程碑不强行纳入；明确理由/触发条件）

- **Scheduler（仍残留 F 级，但不在 Phase1b 清单内）**
  - `core/services/scheduler/schedule_optimizer.py`（COMPLEXITY F）
  - `core/services/scheduler/schedule_service.py`（COMPLEXITY F）
  - 理由：不属于 Phase2~6 补强 runbook 的既定清单；需单独设计“行为护栏 + 性能/正确性回归”后再动。
  - 触发条件：若 Phase2~5 的改动触达优化器/调度主流程，必须先补齐定向回归与引用链追踪，再纳入治理批次。
- **Report 域**
  - `core/services/report/calculations.py`（COMPLEXITY D + 裸枚举）
  - `core/services/report/queries.py`（Service 直连 SQL）
  - 理由：report 域不在本轮闭环主线；建议单独以“报表/分析模块”闭环。
- **System maintenance**
  - `core/services/system/maintenance/cleanup_task.py`（Service 直连 SQL）
  - `core/services/system/system_maintenance_service.py`（裸枚举）
  - 理由：system 域可作为 Phase4 后续小批次或下一里程碑；需结合 UI/配置入口一并治理。
- **Migration（历史迁移脚本复杂度）**
  - `core/infrastructure/migrations/v4.py`（COMPLEXITY E）
  - 理由：迁移脚本以“可执行 + 可回放”为主，除非触发 schema 变更否则不在本轮主动重写。

## 备注：潜在死代码（统一处理口径）

- `core/services/common/excel_service.py:read_rows/write_rows`
- `core/services/process/unit_excel_converter.py:convert`
- `core/services/process/unit_excel/template_builder.py:rows_by_filename`
- `core/services/process/deletion_validator.py:get_deletable_external_ops`
- `core/services/scheduler/calendar_admin.py:get_row`
- `core/services/scheduler/config_service.py:set_active_preset`
- `core/services/scheduler/gantt_range.py:start_str/end_exclusive_str`
- `core/services/system/system_job_state_query_service.py:get_map`

处理规则：仅在“确认无引用 + 有回归覆盖”时删除；否则记账到对应 Phase/Backlog，避免误删造成隐性功能回归。

