"""Explicit old HTML boundary; importing this module never registers a route."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from werkzeug.exceptions import BadRequest

PAGE_POLICIES = MappingProxyType({
    "dashboard.index": "redirect",
    "equipment.detail_page": "redirect",
    "equipment.downtime_batch_page": "retired",
    "equipment.excel_link_page": "retired",
    "equipment.excel_machine_page": "redirect",
    "equipment.list_page": "redirect",
    "excel_demo.index": "retired",
    "material.batch_materials_page": "retired",
    "material.index": "redirect",
    "material.materials_page": "redirect",
    "personnel.detail_page": "redirect",
    "personnel.excel_link_page": "retired",
    "personnel.excel_operator_calendar_page": "retired",
    "personnel.excel_operator_page": "redirect",
    "personnel.list_page": "redirect",
    "personnel.operator_calendar_page": "retired",
    "personnel.teams_page": "retired",
    "process.excel_op_type_page": "redirect",
    "process.excel_part_op_hours_page": "redirect",
    "process.excel_part_ops_page": "retired",
    "process.excel_routes_page": "redirect",
    "process.excel_supplier_page": "redirect",
    "process.list_parts": "redirect",
    "process.op_type_detail": "redirect",
    "process.op_types_page": "redirect",
    "process.part_detail": "redirect",
    "process.supplier_detail": "redirect",
    "process.suppliers_page": "redirect",
    "reports.downtime_page": "redirect",
    "reports.execution_review_page": "redirect",
    "reports.index": "redirect",
    "reports.overdue_page": "redirect",
    "reports.utilization_page": "redirect",
    "scheduler.analysis_page": "redirect",
    "scheduler.batch_detail": "redirect",
    "scheduler.batches_manage_page": "redirect",
    "scheduler.batches_page": "redirect",
    "scheduler.calendar_page": "redirect",
    "scheduler.config_manual_page": "restyle",
    "scheduler.config_page": "retired",
    "scheduler.excel_batches_page": "redirect",
    "scheduler.excel_calendar_page": "retired",
    "scheduler.gantt_page": "redirect",
    "scheduler.resource_dispatch_page": "retired",
    "scheduler.week_plan_page": "retired",
    "scheduler.week_plan_print_page": "restyle",
    "system.backup_page": "redirect",
    "system.history_page": "retired",
    "system.index": "redirect",
    "system.logs_page": "redirect",
    "system.runtime_logs_page": "redirect",
})


class LegacyNavigationInvalid(BadRequest):
    """Malformed old context is a 400, never an unfiltered redirect."""


@dataclass(frozen=True)
class LegacyGetRequest:
    endpoint: str
    query: Tuple[Tuple[str, str], ...]
    path_values: Mapping[str, Any]


@dataclass(frozen=True)
class LegacyDownloadLink:
    label: str
    url: str


@dataclass(frozen=True)
class LegacyGetDecision:
    kind: str
    view: Optional[str] = None
    context: Mapping[str, Any] = field(default_factory=dict)
    option_ids: Tuple[str, ...] = ()
    reason_code: Optional[str] = None
    message: Optional[str] = None
    public_context: Mapping[str, str] = field(default_factory=dict)
    links: Tuple[LegacyDownloadLink, ...] = ()


def retired(code, message, *, public_context=None, links=()):
    return LegacyGetDecision("retired", reason_code=code, message=message,
                             public_context=public_context or {}, links=links)


def unique_query(pairs):
    result = {}
    for key, value in pairs:
        if type(key) is not str or type(value) is not str or key in result:
            raise LegacyNavigationInvalid("旧入口的查询条件重复或类型无效，未忽略任何条件。")
        result[key] = value
    return result
