"""旧 URL 命名空间：只保留退役/跳转策略页的 GET 规则，不再承载任何旧页面实现。

旧 HTML 页面层（web/routes 旧蓝图与 web/viewmodels）已于 2026-09-18 删除。这里按原来的
蓝图名与路径把策略页重新挂成占位规则，端点名保持不变，供 ``install_legacy_retirement``
在启动期换成跳转/410 适配器；说明书页与运行时健康接口分别由 ``manual_page`` 与
``system_runtime`` 挂在同名蓝图上。
"""

from __future__ import annotations

import importlib
from typing import Dict, Tuple

from flask import Blueprint

from .legacy_page_contract import PAGE_POLICIES

LEGACY_BLUEPRINT_NAMES: Tuple[str, ...] = (
    "dashboard", "equipment", "excel_demo", "material", "personnel", "process", "reports", "scheduler", "system",
)

# 端点 -> 完整路径（含旧蓝图前缀）。只登记策略页 GET 规则；POST/JSON/导出等旧接口已整体退役。
LEGACY_PAGE_RULES: Dict[str, str] = {
    "dashboard.index": "/",
    "equipment.detail_page": "/equipment/<machine_id>",
    "equipment.downtime_batch_page": "/equipment/downtimes/batch",
    "equipment.excel_link_page": "/equipment/excel/links",
    "equipment.excel_machine_page": "/equipment/excel/machines",
    "equipment.list_page": "/equipment/",
    "excel_demo.index": "/excel-demo/",
    "material.batch_materials_page": "/material/batches",
    "material.index": "/material/",
    "material.materials_page": "/material/materials",
    "personnel.detail_page": "/personnel/<operator_id>",
    "personnel.excel_link_page": "/personnel/excel/links",
    "personnel.excel_operator_calendar_page": "/personnel/excel/operator_calendar",
    "personnel.excel_operator_page": "/personnel/excel/operators",
    "personnel.list_page": "/personnel/",
    "personnel.operator_calendar_page": "/personnel/<operator_id>/calendar",
    "personnel.teams_page": "/personnel/teams",
    "process.excel_op_type_page": "/process/excel/op-types",
    "process.excel_part_op_hours_page": "/process/excel/part-operation-hours",
    "process.excel_part_ops_page": "/process/excel/part-operations",
    "process.excel_routes_page": "/process/excel/routes",
    "process.excel_supplier_page": "/process/excel/suppliers",
    "process.list_parts": "/process/",
    "process.op_type_detail": "/process/op-types/<op_type_id>",
    "process.op_types_page": "/process/op-types",
    "process.part_detail": "/process/parts/<part_no>",
    "process.supplier_detail": "/process/suppliers/<supplier_id>",
    "process.suppliers_page": "/process/suppliers",
    "reports.downtime_page": "/reports/downtime",
    "reports.execution_review_page": "/reports/execution-review",
    "reports.index": "/reports/",
    "reports.overdue_page": "/reports/overdue",
    "reports.utilization_page": "/reports/utilization",
    "scheduler.analysis_page": "/scheduler/analysis",
    "scheduler.batch_detail": "/scheduler/batches/<batch_id>",
    "scheduler.batches_manage_page": "/scheduler/batches",
    "scheduler.batches_page": "/scheduler/",
    "scheduler.calendar_page": "/scheduler/calendar",
    "scheduler.config_manual_page": "/scheduler/config/manual",
    "scheduler.config_page": "/scheduler/config",
    "scheduler.excel_batches_page": "/scheduler/excel/batches",
    "scheduler.excel_calendar_page": "/scheduler/excel/calendar",
    "scheduler.gantt_page": "/scheduler/gantt",
    "scheduler.resource_dispatch_page": "/scheduler/resource-dispatch",
    "scheduler.week_plan_page": "/scheduler/week-plan",
    "scheduler.week_plan_print_page": "/scheduler/week-plan/print",
    "system.backup_page": "/system/backup",
    "system.history_page": "/system/history",
    "system.index": "/system/",
    "system.logs_page": "/system/logs",
    "system.runtime_logs_page": "/system/runtime-logs",
}

# 仍由真实处理器提供的旧命名空间端点（说明书页、运行时健康接口），不登记占位规则。
_REAL_HANDLER_MODULES = ("web.routes.workbench.manual_page", "web.routes.workbench.system_runtime")

LEGACY_BLUEPRINTS: Dict[str, Blueprint] = {name: Blueprint(name, __name__) for name in LEGACY_BLUEPRINT_NAMES}
dashboard_bp = LEGACY_BLUEPRINTS["dashboard"]
scheduler_bp = LEGACY_BLUEPRINTS["scheduler"]
system_bp = LEGACY_BLUEPRINTS["system"]


def _legacy_page_placeholder(**_path_values):
    raise RuntimeError("旧页面入口只能经 install_legacy_retirement 适配后提供服务。")


def _attach_policy_rules() -> None:
    missing = sorted(endpoint for endpoint in PAGE_POLICIES if endpoint not in LEGACY_PAGE_RULES
                     and PAGE_POLICIES[endpoint] != "restyle")
    if missing:
        raise RuntimeError("策略页缺少旧路径登记：" + ", ".join(missing))
    for endpoint, rule in LEGACY_PAGE_RULES.items():
        if endpoint not in PAGE_POLICIES:
            raise RuntimeError("旧路径登记了未纳入策略的端点：" + endpoint)
        if PAGE_POLICIES[endpoint] == "restyle":
            continue
        bp_name, view_name = endpoint.split(".", 1)
        LEGACY_BLUEPRINTS[bp_name].add_url_rule(
            rule, endpoint=view_name, view_func=_legacy_page_placeholder, methods=["GET"]
        )


_attach_policy_rules()


def register_legacy_blueprints(app) -> None:
    """在注册前导入真实处理器模块，让说明书页与健康接口挂到同名蓝图上。"""
    for module_name in _REAL_HANDLER_MODULES:
        importlib.import_module(module_name)
    for name in LEGACY_BLUEPRINT_NAMES:
        app.register_blueprint(LEGACY_BLUEPRINTS[name])


__all__ = [
    "LEGACY_BLUEPRINTS", "LEGACY_BLUEPRINT_NAMES", "LEGACY_PAGE_RULES",
    "dashboard_bp", "scheduler_bp", "system_bp", "register_legacy_blueprints",
]
