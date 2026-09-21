from __future__ import annotations

from typing import Any, Dict

ENDPOINT_TO_MANUAL_ID: Dict[str, str] = {
    "dashboard.index": "dashboard_first_run",
    "personnel.list_page": "personnel_management",
    "personnel.detail_page": "personnel_detail",
    "personnel.teams_page": "personnel_teams",
    "personnel.operator_calendar_page": "personnel_calendar",
    "equipment.list_page": "equipment_management",
    "equipment.detail_page": "equipment_detail",
    "equipment.downtime_batch_page": "equipment_downtime_batch",
    "process.list_parts": "process_parts",
    "process.part_detail": "process_part_detail",
    "process.op_types_page": "process_op_types",
    "process.op_type_detail": "process_op_type_detail",
    "process.suppliers_page": "process_suppliers",
    "process.supplier_detail": "process_supplier_detail",
    "scheduler.batches_page": "scheduler_batches",
    "scheduler.batches_manage_page": "scheduler_batches_manage",
    "scheduler.batch_detail": "scheduler_batch_detail",
    "scheduler.config_page": "scheduler_config",
    "scheduler.calendar_page": "scheduler_calendar",
    "scheduler.gantt_page": "scheduler_gantt",
    "scheduler.resource_dispatch_page": "scheduler_dispatch",
    "scheduler.analysis_page": "scheduler_analysis",
    "scheduler.week_plan_page": "scheduler_week_plan",
    "material.materials_page": "material_master",
    "material.batch_materials_page": "material_batch",
    "reports.index": "reports_index",
    "reports.overdue_page": "reports_overdue",
    "reports.utilization_page": "reports_utilization",
    "reports.execution_review_page": "reports_execution_review",
    "reports.downtime_page": "reports_downtime",
    "system.backup_page": "system_backup",
    "system.logs_page": "system_logs",
    "system.history_page": "system_history",
}


MANUAL_ENTRY_ENDPOINTS: Dict[str, str] = {
    manual_id: endpoint for endpoint, manual_id in ENDPOINT_TO_MANUAL_ID.items()
}


ENDPOINT_OVERRIDES: Dict[str, Dict[str, Any]] = {}
