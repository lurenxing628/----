from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .scheduler_plan_guardrail_messages import summary_unavailable_guardrail_text
from .scheduler_report_limitations import build_report_limitations
from .scheduler_report_values import ReportPresentationValueError, _optional_number, _sum_number, downtime_summary
from .scheduler_workbench_links import (
    REPORT_PLAN_GUARD_FIELDS,
    build_workbench_link,
    build_workbench_plan_context,
    can_emit_feedback_write_urls,
)

ROLE_ADOPTED = "adopted"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    return value is not None and _text(value) != ""


def _plan_role(plan_resolution: Optional[Dict[str, Any]]) -> str:
    data = plan_resolution or {}
    return _text(data.get("requested_role")) or _text(data.get("selected_role")) or ROLE_ADOPTED


def _public_plan_label(plan_resolution: Optional[Dict[str, Any]]) -> str:
    data = plan_resolution or {}
    return (
        _text(data.get("user_label"))
        or _text(data.get("scenario_display_name"))
        or _text(data.get("scenario_name"))
        or _text(data.get("selected_label"))
        or "正式采用方案"
    )


def build_report_context(
    *,
    version: Any = None,
    plan_resolution: Optional[Dict[str, Any]] = None,
    date_from: Any = None,
    date_to: Any = None,
    query_date: Any = None,
    period_preset: Any = None,
    batch_id: Any = None,
    resource_type: Any = None,
    resource_id: Any = None,
    resource_label: str = "",
    back_to: Any = None,
) -> Dict[str, Any]:
    data = plan_resolution or {}
    parse_failed = bool(data.get("result_summary_parse_failed"))
    can_write = data.get("can_write_feedback") if "can_write_feedback" in data else None
    if parse_failed:
        can_write = False
    context = build_workbench_plan_context(
        version=version,
        plan_role=_plan_role(data),
        plan_resolution=data,
        plan_guard_fields=REPORT_PLAN_GUARD_FIELDS,
        plan_role_label_value=_public_plan_label(data),
        scenario_id=data.get("scenario_id"),
        scenario_display_label=_text(data.get("scenario_display_name")) or _text(data.get("scenario_name")),
        date_from=date_from,
        date_to=date_to,
        query_date=query_date,
        period_preset=period_preset,
        batch_id=batch_id,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label,
        back_to=back_to,
        is_preview=bool(data.get("is_scenario_preview") or data.get("is_preview")),
        can_write_feedback=can_write,
        guardrail_text=summary_unavailable_guardrail_text(
            data.get("result_summary_parse_reason"),
            blocked_action="不能写现场事实",
        )
        if parse_failed
        else "",
        guardrail_reason_type="data_gap" if parse_failed else "",
    )
    if parse_failed:
        context["can_dispatch"] = False
        context["can_write_feedback"] = False
    return context


def _context_with(
    context: Dict[str, Any],
    *,
    batch_id: Any = None,
    resource_type: Any = None,
    resource_id: Any = None,
    resource_label: str = "",
) -> Dict[str, Any]:
    out = dict(context or {})
    if _has_value(batch_id):
        out["batch_id"] = _text(batch_id)
    if _has_value(resource_type):
        out["resource_type"] = _text(resource_type)
        out["resource_type_label"] = _text(resource_type)
    if _has_value(resource_id):
        out["resource_id"] = _text(resource_id)
    if _has_value(resource_label):
        out["resource_label"] = _text(resource_label)
    return out

def _gantt_view_for_context(context: Dict[str, Any]) -> str:
    if _text((context or {}).get("resource_type")) == "operator":
        return "operator"
    return "machine"

def _execution_review_row_resource(row: Dict[str, Any]) -> Dict[str, str]:
    machine_id = _text(row.get("planned_machine_id"))
    operator_id = _text(row.get("planned_operator_id"))
    if machine_id:
        return {
            "resource_type": "machine",
            "resource_id": machine_id,
            "resource_label": _text(row.get("planned_machine_name")) or machine_id,
            "view": "machine",
        }
    if operator_id:
        return {
            "resource_type": "operator",
            "resource_id": operator_id,
            "resource_label": _text(row.get("planned_operator_name")) or operator_id,
            "view": "operator",
        }
    return {"resource_type": "", "resource_id": "", "resource_label": "", "view": "machine"}


def build_downtime_report_link(
    context: Dict[str, Any],
    *,
    label: str = "查看停机影响",
    resource_type: Any = None,
    resource_id: Any = None,
    resource_label: str = "",
) -> Dict[str, Any]:
    row_context = _context_with(context, resource_type=resource_type, resource_id=resource_id, resource_label=resource_label)
    return build_workbench_link(row_context, "downtime_report", label=label, resource_type=resource_type, resource_id=resource_id)


def _card(key: str, title: str, question: str, limitation: str, link: Dict[str, Any], icon_id: str) -> Dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "question_text": question,
        "limitation_text": limitation,
        "link": link,
        "icon_id": icon_id,
    }


def build_reports_index_workbench(context: Dict[str, Any], *, overdue_count: int = 0) -> Dict[str, Any]:
    overdue_hint = f"当前上下文下有 {int(overdue_count or 0)} 个超期批次。" if overdue_count else "用于追交期风险。"
    return {
        "context": context,
        "workbench_links": [
            build_workbench_link(context, "gantt", label="定位甘特", view=_gantt_view_for_context(context)),
            build_workbench_link(context, "resource_dispatch", label="回资源派工"),
            build_workbench_link(context, "execution_review", label="查看计划和现场实际"),
        ],
        "entry_cards": [
            _card(
                "overdue",
                "超期清单",
                f"回答哪些批次已经晚于交期，{overdue_hint}",
                "不能单独证明唯一原因，需要继续看延期说明或甘特排班。",
                build_workbench_link(context, "overdue_report", label="查看超期清单"),
                "icon-warn",
            ),
            _card(
                "utilization",
                "资源负荷与利用率",
                "回答哪些设备或人员在当前日期范围内最忙。",
                "不能证明资源一定会拖期，只能提示需要继续看排班明细。",
                build_workbench_link(context, "utilization_report", label="查看资源负荷"),
                "icon-chart",
            ),
            _card(
                "execution_review",
                "计划和现场实际",
                "回答当前可复盘的正式排产记录里计划时间和现场实际反馈是否一致。",
                "当前最新正式方案才能写现场记录，历史版本、模拟预览和对比参考方案只能查看。",
                build_workbench_link(context, "execution_review", label="查看计划和现场实际"),
                "icon-chart",
            ),
            _card(
                "downtime",
                "停机影响统计",
                "回答当前日期范围内哪些设备有停机记录，以及和排程有没有重叠。",
                "当前只做设备级说明，不能证明具体影响了哪一道任务。",
                build_downtime_report_link(context, label="查看停机影响"),
                "icon-device",
            ),
        ],
    }


def build_report_page_links(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    gantt_view = _gantt_view_for_context(context)
    return [
        build_workbench_link(context, "reports_index", label="回报表中心"),
        build_workbench_link(context, "gantt", label="定位甘特", view=gantt_view),
        build_workbench_link(context, "resource_dispatch", label="回资源派工"),
        build_workbench_link(context, "execution_review", label="查看计划和现场实际"),
    ]


def _is_gantt_diagnosis_action(action: Dict[str, Any]) -> bool:
    link = _text(action.get("link"))
    if not link:
        return False
    if _text(action.get("label")) == "查看甘特图":
        return True
    return link.split("?", 1)[0] == "/scheduler/gantt"


def _decorate_diagnosis_action(action: Dict[str, Any], row_context: Dict[str, Any], batch_id: Any) -> Dict[str, Any]:
    item = dict(action)
    if _is_gantt_diagnosis_action(item):
        link = build_workbench_link(
            row_context,
            "gantt",
            label=_text(item.get("label")) or "查看甘特图",
            view=_gantt_view_for_context(row_context),
            batch_id=batch_id,
        )
        item["link"] = link["url"]
    return item


def _decorate_diagnosis_item(item: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(item)
    batch_id = out.get("batch_id") or context.get("batch_id")
    row_context = _context_with(context, batch_id=batch_id)
    out["suggested_actions"] = [
        _decorate_diagnosis_action(action, row_context, batch_id)
        if isinstance(action, dict)
        else action
        for action in out.get("suggested_actions") or []
    ]
    return out


def decorate_delay_diagnosis_context(delay_diagnosis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(delay_diagnosis or {})
    items_by_batch = {}
    for batch_id, item in (out.get("items_by_batch") or {}).items():
        if isinstance(item, dict):
            items_by_batch[batch_id] = _decorate_diagnosis_item(item, context)
        else:
            items_by_batch[batch_id] = item
    out["items_by_batch"] = items_by_batch
    return out


def decorate_overdue_rows(rows: Iterable[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for row in rows or []:
        item = dict(row or {})
        batch_id = item.get("batch_id")
        row_context = _context_with(context, batch_id=batch_id)
        gantt_view = _gantt_view_for_context(row_context)
        item["workbench_links"] = [
            build_workbench_link(row_context, "gantt", label="定位甘特", view=gantt_view, batch_id=batch_id),
            build_workbench_link(row_context, "resource_dispatch", label="回资源派工", batch_id=batch_id),
            build_workbench_link(row_context, "execution_review", label="查看计划和现场实际", batch_id=batch_id),
            build_workbench_link(row_context, "delay_diagnosis", label="查看为什么晚了", batch_id=batch_id),
        ]
        out.append(item)
    return out


def _utilization_percent(row: Dict[str, Any]) -> Optional[float]:
    utilization = _optional_number(row.get("utilization"), field="utilization", label="利用率")
    if utilization is None:
        return None
    return round(utilization * 100.0, 2)


def decorate_utilization_rows(
    rows: Iterable[Dict[str, Any]],
    context: Dict[str, Any],
    *,
    resource_type: str,
) -> List[Dict[str, Any]]:
    id_key = "machine_id" if resource_type == "machine" else "operator_id"
    name_key = "machine_name" if resource_type == "machine" else "operator_name"
    view = "machine" if resource_type == "machine" else "operator"
    out = []
    for row in rows or []:
        item = dict(row or {})
        item["utilization_percent"] = _utilization_percent(item)
        resource_id = item.get(id_key)
        resource_label = _text(item.get(name_key)) or _text(resource_id)
        row_context = _context_with(
            context,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label,
        )
        item["workbench_links"] = [
            build_workbench_link(row_context, "resource_dispatch", label="查看资源排班", resource_type=resource_type, resource_id=resource_id),
            build_workbench_link(row_context, "gantt", label="定位甘特", view=view, resource_type=resource_type, resource_id=resource_id),
            build_workbench_link(row_context, "overdue_report", label="查看相关超期", resource_type=resource_type, resource_id=resource_id),
            build_workbench_link(row_context, "execution_review", label="查看计划和现场实际", resource_type=resource_type, resource_id=resource_id),
        ]
        out.append(item)
    return out


def decorate_execution_review_rows(rows: Iterable[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for row in rows or []:
        item = dict(row or {})
        batch_id = item.get("batch_id_label")
        row_resource = _execution_review_row_resource(item)
        row_context = _context_with(
            context,
            batch_id=batch_id,
            resource_type=row_resource["resource_type"],
            resource_id=row_resource["resource_id"],
            resource_label=row_resource["resource_label"],
        )
        can_write_feedback = can_emit_feedback_write_urls(row_context)
        item["workbench_links"] = [
            build_workbench_link(
                row_context,
                "resource_dispatch",
                label="回资源派工",
                batch_id=batch_id,
                resource_type=row_resource["resource_type"],
                resource_id=row_resource["resource_id"],
            ),
            build_workbench_link(
                row_context,
                "gantt",
                label="定位甘特",
                view=row_resource["view"],
                batch_id=batch_id,
                resource_type=row_resource["resource_type"],
                resource_id=row_resource["resource_id"],
            ),
            build_workbench_link(
                row_context,
                "resource_dispatch",
                label="查看现场记录入口" if can_write_feedback else "现场记录入口不可用",
                disabled=not can_write_feedback,
                disabled_reason="" if can_write_feedback else _text(
                    build_workbench_link(row_context, "execution_review").get("disabled_reason")
                ) or "当前方案只能查看，不能写现场记录。",
                batch_id=batch_id,
                resource_type=row_resource["resource_type"],
                resource_id=row_resource["resource_id"],
            ),
        ]
        out.append(item)
    return out


def decorate_downtime_rows(rows: Iterable[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for row in rows or []:
        item = dict(row or {})
        resource_id = item.get("machine_id")
        resource_label = _text(item.get("machine_name")) or _text(resource_id)
        row_context = _context_with(
            context,
            resource_type="machine",
            resource_id=resource_id,
            resource_label=resource_label,
        )
        item["workbench_links"] = [
            build_workbench_link(row_context, "resource_dispatch", label="查看设备排班", resource_type="machine", resource_id=resource_id),
            build_workbench_link(row_context, "gantt", label="定位设备甘特", view="machine", resource_type="machine", resource_id=resource_id),
            build_downtime_report_link(
                row_context,
                label="继续看停机影响",
                resource_type="machine",
                resource_id=resource_id,
                resource_label=resource_label,
            ),
            build_workbench_link(row_context, "execution_review", label="查看计划和现场实际", resource_type="machine", resource_id=resource_id),
        ]
        out.append(item)
    return out


def downtime_empty_message(empty_reason: Any) -> str:
    if empty_reason == "no_history":
        return "暂无排产历史，当前无法统计停机影响。"
    return "当前没有停机记录或尚未维护停机数据，请调整日期、版本，或先维护设备停机信息后再看。"


__all__ = [
    "build_report_context",
    "build_report_limitations",
    "build_report_page_links",
    "build_reports_index_workbench",
    "decorate_delay_diagnosis_context",
    "decorate_downtime_rows",
    "decorate_execution_review_rows",
    "decorate_overdue_rows",
    "decorate_utilization_rows",
    "downtime_empty_message",
    "downtime_summary",
    "ReportPresentationValueError",
]
