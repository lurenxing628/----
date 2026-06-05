from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from flask import Blueprint, current_app, g, request

from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.schedule_result_view_context import plan_role_filter_fields
from web.navigation_context import set_current_workbench_navigation_context
from web.request_resource_context import request_report_resource_context
from web.routes.history_summary_logging import log_history_summary_parse_warning
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.dashboard_workbench import build_dashboard_workbench_summary
from web.viewmodels.scheduler_history_summary import parse_history_summary_state

bp = Blueprint("dashboard", __name__)


def _positive_version(value: Any) -> int:
    try:
        version = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return version if version > 0 else 0


def _requested_version() -> Tuple[int, str]:
    raw = _request_arg("version")
    if not raw:
        return 0, ""
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return 0, f"请求的排产版本 {raw} 不是有效数字，已回到最新排产版本显示首页值班台。"
    if version <= 0:
        return 0, f"请求的排产版本 v{raw} 不可用，已回到最新排产版本显示首页值班台。"
    return version, ""


def _today_range(now: datetime) -> Dict[str, str]:
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return {
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _row_op_ids(rows: List[Dict[str, Any]]) -> List[int]:
    out: List[int] = []
    seen = set()
    for row in rows:
        try:
            op_id = int(row.get("op_id") or 0)
        except (TypeError, ValueError):
            continue
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        out.append(op_id)
    return out


def _strict_count_value(value: Any, field: str) -> Tuple[int, str]:
    if value is None or str(value).strip() == "":
        return 0, f"排产摘要缺少{field}，首页暂时不能展示准确数量。"
    if isinstance(value, bool):
        return 0, f"排产摘要里的{field}不是整数，首页暂时不能展示准确数量。"
    if isinstance(value, int):
        if value < 0:
            return 0, f"排产摘要里的{field}不能是负数，首页暂时不能展示准确数量。"
        return value, ""
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip()), ""
    return 0, f"排产摘要里的{field}不是整数，首页暂时不能展示准确数量。"


def _summary_overdue_count(summary: Any) -> Tuple[int, str]:
    if not isinstance(summary, dict):
        return 0, ""
    if "overdue_batches" not in summary:
        return 0, "排产摘要缺少超期批次数，首页暂时不能展示准确数量。"
    overdue_payload = summary.get("overdue_batches")
    if isinstance(overdue_payload, dict):
        if "count" not in overdue_payload:
            return 0, "排产摘要缺少超期批次数，首页暂时不能展示准确数量。"
        return _strict_count_value(overdue_payload.get("count"), "超期批次数")
    if isinstance(overdue_payload, list):
        return len(overdue_payload), ""
    return 0, "排产摘要里的超期批次清单格式不对，首页暂时不能展示准确数量。"


def _parse_state_with_summary_error(parse_state: Dict[str, Any], error: str) -> Dict[str, Any]:
    if not error:
        return parse_state
    out = dict(parse_state or {})
    out["parse_failed"] = True
    out["user_message"] = error
    return out


def _load_plan_time_span(services: Any, version: int, plan_role: str, scenario_id: str) -> Tuple[Any, str]:
    if version <= 0:
        return None, ""
    try:
        return services.schedule_plan_query_service.get_plan_time_span_for_view(version, plan_role, scenario_id or None), ""
    except Exception as exc:  # pragma: no cover - 防止首页被坏历史阻断
        current_app.logger.warning("首页值班台读取计划日期范围失败（version=%s）：%s", version, exc)
        return None, "计划日期范围读取失败，首页暂时不能判断甘特、资源派工和报表需要的日期。"


def _load_today_rows(services: Any, version: int, now: datetime, plan_role: str, scenario_id: str) -> Tuple[List[Dict[str, Any]], str]:
    if version <= 0:
        return [], ""
    dr = _today_range(now)
    try:
        rows = services.schedule_plan_query_service.list_plan_detail_rows_between_for_view(
            version=version,
            role=plan_role,
            scenario_id=scenario_id or None,
            start_time=dr["start"],
            end_time=dr["end"],
        )
    except Exception as exc:  # pragma: no cover - 防止首页被坏历史阻断
        current_app.logger.warning("首页值班台读取今日计划失败（version=%s）：%s", version, exc)
        return [], "今日正式计划读取失败，首页暂时不能判断哪些任务现场情况待确认。"
    return [dict(row) for row in rows], ""


def _load_execution_facts(rows: List[Dict[str, Any]], plan_fields: Dict[str, Any]) -> Tuple[Dict[int, Any], str]:
    op_ids = _row_op_ids(rows)
    if not op_ids:
        return {}, ""
    try:
        return (
            ExecutionFactProvider(g.db, logger=current_app.logger).facts_by_op_id_for_plan_rows(
                rows,
                plan_fields,
                include_op_ids=op_ids,
            ),
            "",
        )
    except Exception as exc:  # pragma: no cover - 防止首页被坏现场记录阻断
        current_app.logger.warning("首页值班台读取现场情况失败：%s", exc)
        return {}, "现场执行事实读取失败，首页暂时不能判断哪些任务现场情况待确认。"


def _request_arg(name: str) -> str:
    return str(request.args.get(name) or "").strip()


def _plan_resolution_context(services: Any, version: int) -> Dict[str, Any]:
    if version <= 0:
        return {}
    raw_role = _request_arg("plan_role") or ROLE_ADOPTED
    scenario_id = _request_arg("scenario_id") or None
    try:
        plan_resolution = services.schedule_plan_query_service.resolve_plan_view(version, raw_role, scenario_id).to_dict()
    except ValueError as exc:
        current_app.logger.warning("首页值班台解析方案身份失败（version=%s）：%s", version, exc)
        plan_resolution = services.schedule_plan_query_service.resolve_plan_view(version, ROLE_ADOPTED, None).to_dict()
        fields = plan_role_filter_fields(plan_resolution)
        fields["plan_identity_error"] = "请求里的方案身份不可用，已回到正式采用方案显示首页值班台。"
        fields["plan_identity_blocking_error"] = True
        fields["is_current_executable_official_version"] = False
        fields["can_dispatch"] = False
        fields["can_write_feedback"] = False
        return fields
    return plan_role_filter_fields(plan_resolution)


def _is_adopted_role_context(context: Dict[str, Any]) -> bool:
    requested_role = str(context.get("requested_plan_role") or context.get("plan_role") or ROLE_ADOPTED)
    effective_role = str(context.get("effective_plan_role") or ROLE_ADOPTED)
    return requested_role == ROLE_ADOPTED and effective_role == ROLE_ADOPTED


def _is_plain_plan_context(context: Dict[str, Any]) -> bool:
    return (
        not context.get("is_scenario_preview")
        and not context.get("is_preview_plan")
        and not context.get("is_comparison")
        and not str(context.get("scenario_id") or "").strip()
    )


def _summary_matches_plan_identity(context: Dict[str, Any]) -> bool:
    return (
        _is_adopted_role_context(context)
        and _is_plain_plan_context(context)
        and bool(context.get("is_current_executable_official_version"))
    )


def _should_expose_summary_parse_failure(context: Dict[str, Any]) -> bool:
    return (
        _is_adopted_role_context(context)
        and _is_plain_plan_context(context)
        and context.get("source_table") == SOURCE_SCHEDULE
    )


def _workbench_summary_parse_state(workbench_history: Any, context: Dict[str, Any], summary_matches_identity: bool) -> Dict[str, Any]:
    if workbench_history is None:
        return {"parse_failed": False}
    raw_summary = getattr(workbench_history, "result_summary", None)
    parse_state = parse_history_summary_state(raw_summary)
    if summary_matches_identity or (_should_expose_summary_parse_failure(context) and parse_state.get("parse_failed")):
        log_history_summary_parse_warning(
            parse_state,
            version=getattr(workbench_history, "version", None),
            log_label="首页",
        )
        return parse_state
    return {"parse_failed": False}


def _summary_payload_dict(parse_state: Dict[str, Any]) -> Any:
    payload = parse_state.get("payload")
    return payload if isinstance(payload, dict) else None


def _workbench_history_context(history_q: Any) -> Tuple[Any, Any, int, str]:
    recent = history_q.list_recent(limit=1)
    latest = recent[0] if recent else None
    requested_version, requested_history_error = _requested_version()
    workbench_history = history_q.get_by_version(requested_version) if requested_version else latest
    if requested_version and workbench_history is None and latest is not None:
        workbench_history = latest
        requested_history_error = f"请求的排产版本 v{requested_version} 不存在，已回到最新排产版本显示首页值班台。"
    workbench_version = _positive_version(getattr(workbench_history, "version", None) if workbench_history is not None else None)
    return latest, workbench_history, workbench_version, requested_history_error


def _workbench_navigation_context_from_request(services: Any, version: int) -> Dict[str, Any]:
    resource = request_report_resource_context()
    context = {
        "version": str(version) if version > 0 else "",
        "plan_id": _request_arg("plan_id"),
        "date_from": _request_arg("date_from") or _request_arg("start_date"),
        "date_to": _request_arg("date_to") or _request_arg("end_date"),
        "query_date": _request_arg("query_date"),
        "period_preset": _request_arg("period_preset"),
        "batch_id": _request_arg("batch_id"),
        "resource_type": resource["resource_type"],
        "resource_id": resource["resource_id"],
        "resource_label": resource["resource_label"],
        "back_to": _request_arg("back_to"),
    }
    context.update(_plan_resolution_context(services, version))
    return context


@bp.get("/")
def index():
    services = g.services
    batch_svc = services.batch_service
    history_q = services.schedule_history_query_service

    pending_count = len(batch_svc.list(status="pending"))
    scheduled_count = len(batch_svc.list(status="scheduled"))
    overdue_count = 0

    now = datetime.now()
    _latest, workbench_history, workbench_version, requested_history_error = _workbench_history_context(history_q)
    navigation_context = _workbench_navigation_context_from_request(services, workbench_version)
    if requested_history_error:
        navigation_context["plan_identity_error"] = requested_history_error
        navigation_context["plan_identity_blocking_error"] = True
        navigation_context["plan_identity_blocking_scope"] = "workbench_continuation"
        navigation_context["is_current_executable_official_version"] = False
        navigation_context["can_dispatch"] = False
        navigation_context["can_write_feedback"] = False
    set_current_workbench_navigation_context(navigation_context)
    summary_matches_identity = _summary_matches_plan_identity(navigation_context)
    history_summary_parse_state = parse_history_summary_state(
        getattr(workbench_history, "result_summary", None) if workbench_history is not None else None
    )
    workbench_summary_parse_state = _workbench_summary_parse_state(
        workbench_history,
        navigation_context,
        summary_matches_identity,
    )
    history_summary_data = _summary_payload_dict(history_summary_parse_state)
    workbench_summary_data = _summary_payload_dict(workbench_summary_parse_state)
    overdue_count, _history_count_error = _summary_overdue_count(history_summary_data)
    workbench_overdue_count, workbench_count_error = _summary_overdue_count(workbench_summary_data)
    count_error = workbench_count_error or (_history_count_error if _should_expose_summary_parse_failure(navigation_context) else "")
    if count_error:
        workbench_summary_parse_state = _parse_state_with_summary_error(workbench_summary_parse_state, count_error)
        workbench_summary_data = None
        workbench_overdue_count = 0
    latest_summary = workbench_summary_data if summary_matches_identity else None
    workbench_plan_role = str(navigation_context.get("plan_role") or ROLE_ADOPTED)
    workbench_scenario_id = str(navigation_context.get("scenario_id") or "")
    plan_time_span, plan_time_span_load_error = _load_plan_time_span(
        services, workbench_version, workbench_plan_role, workbench_scenario_id
    )
    if summary_matches_identity:
        today_rows, today_rows_load_error = _load_today_rows(
            services,
            workbench_version,
            now,
            workbench_plan_role,
            workbench_scenario_id,
        )
    else:
        today_rows, today_rows_load_error = (
            [],
            "当前查看方案不是当前可执行正式方案，首页暂时不能判断哪些任务现场情况待确认。",
        )
    execution_facts_by_op_id, execution_facts_load_error = _load_execution_facts(
        today_rows,
        {
            "version": workbench_version,
            "source_table": SOURCE_SCHEDULE,
            "effective_plan_role": workbench_plan_role,
            "scenario_id": workbench_scenario_id or None,
        },
    )
    workbench_summary = build_dashboard_workbench_summary(
        pending_count=pending_count,
        scheduled_count=scheduled_count,
        overdue_count=workbench_overdue_count,
        latest_history=workbench_history,
        latest_summary=latest_summary,
        latest_summary_parse_state=workbench_summary_parse_state,
        plan_time_span=plan_time_span,
        plan_time_span_load_error=plan_time_span_load_error,
        today_rows=today_rows,
        today_rows_load_error=today_rows_load_error,
        execution_facts_by_op_id=execution_facts_by_op_id,
        execution_facts_load_error=execution_facts_load_error,
        navigation_context=navigation_context,
        now=now,
    )
    set_current_workbench_navigation_context(workbench_summary["latest_plan"])

    return render_template(
        "dashboard.html",
        title="首页",
        pending_count=pending_count,
        scheduled_count=scheduled_count,
        overdue_count=overdue_count,
        latest_history=workbench_history,
        latest_summary=latest_summary,
        workbench_summary=workbench_summary,
    )
