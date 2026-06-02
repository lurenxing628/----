from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

from .scheduler_workbench_links import build_workbench_link, build_workbench_plan_context

ROLE_ADOPTED = "adopted"


class ReportPresentationValueError(ValueError):
    def __init__(self, message: str, *, field: str):
        self.field = field
        super().__init__(message)


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
        _text(data.get("scenario_display_name"))
        or _text(data.get("scenario_name"))
        or _text(data.get("selected_label"))
        or "正式采用方案"
    )


def _copy_plan_guard_fields(context: Dict[str, Any], plan_resolution: Optional[Dict[str, Any]]) -> None:
    data = plan_resolution or {}
    mappings = {
        "requested_plan_role": data.get("requested_role"),
        "effective_plan_role": data.get("selected_role"),
        "is_scenario_preview": data.get("is_scenario_preview"),
        "is_comparison": data.get("is_comparison"),
        "is_superseded_by_newer_version": data.get("is_superseded_by_newer_version"),
        "can_dispatch": data.get("can_dispatch"),
    }
    for key, value in mappings.items():
        if value is not None:
            context[key] = value


def build_report_context(
    *,
    version: Any = None,
    plan_id: Any = None,
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
    context = build_workbench_plan_context(
        version=version,
        plan_id=plan_id,
        plan_role=_plan_role(data),
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
        can_write_feedback=data.get("can_write_feedback") if "can_write_feedback" in data else None,
    )
    _copy_plan_guard_fields(context, data)
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


def _context_summary(context: Dict[str, Any], suffix: str = "") -> str:
    parts = [
        _text(context.get("version_label")),
        _text(context.get("plan_role_label")),
    ]
    if context.get("date_from") and context.get("date_to"):
        parts.append(f"{context['date_from']} ～ {context['date_to']}")
    if context.get("resource_label"):
        parts.append(_text(context.get("resource_label")))
    if context.get("batch_id"):
        parts.append(_text(context.get("batch_id")))
    if suffix:
        parts.append(suffix)
    return "，".join(part for part in parts if part)


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
            build_workbench_link(context, "execution_review", label="复盘正式方案"),
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
                "回答正式采用方案里计划时间和现场实际反馈是否一致。",
                "只复盘正式采用方案，不复盘模拟预览和对比参考方案。",
                build_workbench_link(context, "execution_review", label="查看计划和现场实际"),
                "icon-chart",
            ),
            _card(
                "downtime",
                "停机影响统计",
                "回答当前日期范围内哪些设备有停机记录，以及和排程有没有重叠。",
                "第一版只做设备级说明，不能证明具体影响了哪一道任务。",
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
        build_workbench_link(context, "execution_review", label="复盘正式方案"),
    ]


def build_report_limitations(report_key: str) -> Dict[str, str]:
    data = {
        "overdue": (
            "这张表能回答哪些批次晚了。",
            "它不能单独证明唯一原因；需要结合延期说明、甘特排班和现场事实继续看。",
        ),
        "utilization": (
            "这张表能回答设备和人员在当前范围内有多忙。",
            "它不能证明资源一定造成延期；需要回资源派工或甘特确认排班细节。",
        ),
        "execution_review": (
            "这张表能回答正式计划和现场实际是否一致。",
            "它不复盘模拟预览，也不在这里写现场记录。",
        ),
        "downtime": (
            "这张表能回答设备级停机时长和排程重叠情况。",
            "第一版不能证明具体影响了哪一道任务；任务级影响后续单独实现。",
        ),
    }
    answer, limitation = data.get(report_key, ("这张报表用于继续追踪排产风险。", "它不能替代对应业务页面的明细核查。"))
    return {"answer_text": answer, "limitation_text": limitation}


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
            build_workbench_link(row_context, "execution_review", label="复盘正式方案", batch_id=batch_id),
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
            build_workbench_link(row_context, "execution_review", label="复盘正式方案", resource_type=resource_type, resource_id=resource_id),
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
                label="查看现场记录入口",
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
            build_downtime_report_link(row_context, label="继续看停机影响", resource_type="machine", resource_id=resource_id, resource_label=resource_label),
            build_workbench_link(row_context, "execution_review", label="复盘正式方案", resource_type="machine", resource_id=resource_id),
        ]
        out.append(item)
    return out


def downtime_empty_message(empty_reason: Any) -> str:
    if empty_reason == "no_history":
        return "暂无排产历史，当前无法统计停机影响。"
    return "当前没有停机记录或尚未维护停机数据，请调整日期、版本，或先维护设备停机信息后再看。"


def downtime_summary(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(rows or [])
    return {
        "machine_count": len(items),
        "downtime_hours": _sum_number(items, "downtime_hours"),
        "downtime_count": int(_sum_number(items, "downtime_count")),
        "schedule_overlap_hours": _sum_number(items, "schedule_overlap_hours"),
        "schedule_overlap_count": int(_sum_number(items, "schedule_overlap_count")),
    }


def _sum_number(rows: Iterable[Dict[str, Any]], key: str) -> float:
    total = 0.0
    for row in rows or []:
        number = _optional_number((row or {}).get(key), field=key, label=f"停机影响汇总字段“{key}”")
        if number is not None:
            total += number
    return round(total, 2)


def _optional_number(value: Any, *, field: str, label: str) -> Optional[float]:
    try:
        if value is None or _text(value) == "":
            return None
        if isinstance(value, bool):
            raise ValueError(label)
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ReportPresentationValueError(f"{label}不是数字，请检查报表数据。field={field}", field=field) from exc
    if not math.isfinite(number):
        raise ReportPresentationValueError(f"{label}不是数字，请检查报表数据。field={field}", field=field)
    return number


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
