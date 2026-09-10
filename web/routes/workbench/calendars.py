"""Real WorkCalendar HTTP adapter; registration is explicitly owned by the host.

GET /api/workbench/v1/calendar/month?year=2026&month=9[&snapshot_ref=...]
POST /calendar/upsert|delete: {request_key,write_token,input:{date,fields?}}
POST /calendar/range/preview: {input:{start_date,end_date,scope,operation,fields}}
POST /calendar/range/confirm: {request_key,write_token,input:{preview_ref}}

Month is one-based. Dates are factory-local ISO date keys, never UTC instants.
This prototype edits the global calendar only (LEG-056/057); no owner identifiers
or personal-calendar writes are accepted. Existing personal/shift rules survive.
Short-lived contexts are not entity identities. Absent dates have entity/ref=null;
the first actual save allocates a permanent reference through existing triggers.
"""

import re

from flask import current_app, g, jsonify, request

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.workbench.calendars import WorkbenchCalendarService
from core.services.workbench.commands import WorkbenchCommandService

from .api_responses import api_endpoint, failure, query_success
from .calendars_preview import calendar_now, release_preview, resolve_preview, retain_preview
from .calendars_projection import calendar_day, calendar_preview, calendar_snapshot
from .materials import _command_body
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    return WorkbenchCalendarService(g.db, current_app.logger, clock=calendar_now)


def _month_input():
    if set(request.args) - {"year", "month", "snapshot_ref"} or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "日历查询包含未知或重复参数。", 400)
    values = {}
    for key in ("year", "month"):
        text = request.args.get(key, "")
        if re.fullmatch(r"[1-9][0-9]{0,3}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "请提供有效年份及 1 至 12 的月份。", 400)
        values[key] = int(text)
    return values


def _day_subject(day):
    # A default date is an edit address, not a fabricated permanent entity ref.
    return "calendar:" + day


@api_endpoint
def calendar_month():
    values = _month_input()
    month = _service().month(**values)
    states = [calendar_snapshot(day) for day in month["days"]]
    snapshot = bind_read_snapshot({"kind": "calendar", **values}, input_fingerprint(states), request.args.get("snapshot_ref"))
    days = []
    for day, state in zip(month["days"], states):
        public = {**calendar_day(state), **{key: day[key] for key in ("day", "weekday", "is_weekend", "is_today")}}
        public["write_context"] = issue_write_context(_day_subject(day["date"]), ["calendar.upsert", "calendar.delete"], state)
        days.append(public)
    by_date = {day["date"]: day for day in days}
    data = {key: month[key] for key in ("year", "month", "as_of", "time_basis", "previous_month", "next_month", "stats")}
    data.update(days=days, cells=[by_date[cell["date"]] if cell is not None else None for cell in month["cells"]])
    return query_success(data, snapshot)


@api_endpoint
def calendar_day_command(action):
    body = _command_body()
    domain = _service()
    payload = domain.normalize(action, body["input"])
    subject, command = _day_subject(payload["date"]), "calendar." + action

    def guard():
        state = domain.snapshot(payload["date"])
        validate_write_context(body["write_token"], subject, command, state)
        return state

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=command, context_ref=subject, normalized_input=payload,
        guard=guard, mutate=lambda state: domain.apply(action, payload, state))
    return jsonify(outcome)


def _preview_input():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "预览必须使用 JSON 内容，不能带查询参数。", 400)
    body = request.get_json()
    if not isinstance(body, dict) or set(body) != {"input"}:
        raise WorkbenchCommandRejected("invalid_input", "预览只能提交本次填写的内容，不能附带旧资料或其他信息。", 400)
    return body["input"]


@api_endpoint
def calendar_range_preview():
    payload = WorkbenchCalendarService.normalize("preview", _preview_input())
    try:
        return _build_preview(_service(), payload)
    except (AppError, WorkbenchCommandRejected):
        raise
    except Exception:
        current_app.logger.exception("工作台日历预览读取失败")
        return failure("storage_failure", "日历预览读取失败，未修改日历，请查看运行日志后重试。", 500)


def _build_preview(domain, payload):
    preview = domain.preview(payload)
    context = issue_write_context(preview.preview_ref, ["calendar.confirm"], preview.fingerprint)
    data = calendar_preview(preview)
    data["write_context"] = context
    snapshot = bind_read_snapshot({"kind": "calendar_preview", "preview_ref": preview.preview_ref}, preview.fingerprint)
    retain_preview(preview)
    return query_success(data, snapshot)


@api_endpoint
def calendar_range_confirm():
    body = _command_body()
    domain = _service()
    payload = domain.normalize("confirm", body["input"])
    ref = payload["preview_ref"]

    def guard():
        preview = resolve_preview(ref)
        validate_write_context(body["write_token"], ref, "calendar.confirm", preview.fingerprint)
        return preview

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action="calendar.confirm", context_ref=ref, normalized_input=payload,
        guard=guard, mutate=lambda preview: domain.apply("confirm", payload, preview))
    release_preview(ref)
    return jsonify(outcome)


def register_calendar_routes(bp):
    bp.add_url_rule("/api/workbench/v1/calendar/month", view_func=calendar_month, methods=["GET"])
    for action in ("upsert", "delete"):
        bp.add_url_rule("/api/workbench/v1/calendar/" + action, endpoint="calendar_" + action,
                        view_func=calendar_day_command, defaults={"action": action}, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/calendar/range/preview", view_func=calendar_range_preview, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/calendar/range/confirm", view_func=calendar_range_confirm, methods=["POST"])
