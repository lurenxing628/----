"""个人工作日历的读写路由。

写入照「编辑可操作设备」那条已跑通的链路：先用月份或范围的写令牌确认人员及日历事实没有变化，再进命令服务。
范围清除是两段式（先只读预览命中哪些天，再确认），单日保存和清除是一段式，与全局日历页一致。
"""

import re

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint, validate_request_key
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from web.api_responses import query_success

from .api_responses import api_endpoint
from .calendars_preview import calendar_now
from .read_context import bind_read_snapshot
from .resource_action_context import json_body, read_endpoint
from .write_context import issue_write_context, validate_write_context

ACTIONS = {"upsert": "operator.calendar_upsert", "delete": "operator.calendar_delete",
           "range_clear": "operator.calendar_range_clear"}


def _reader():
    return WorkbenchResourceQueryService(g.db, "operator", current_app.logger)


def _service(operator_code):
    return WorkbenchOperatorCalendarService(g.db, operator_code, current_app.logger, clock=calendar_now)


def _operator_code(reader, ref):
    return reader.resolve(ref).entity_key


def _month_input():
    if set(request.args) - {"year", "month", "snapshot_ref"} or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "个人日历的查询条件有重复或不支持的项，当前月份没有变化。请刷新页面后重新选择月份。", 400)
    values = {}
    for key in ("year", "month"):
        text = request.args.get(key, "")
        if re.fullmatch(r"[1-9][0-9]{0,3}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "请填写有效的年份和 1 至 12 的月份，当前月份没有变化。", 400)
        values[key] = int(text)
    return values


def _month_binding(record, month):
    return {"resource": record.state, "year": month["year"], "month": month["month"],
            "default_periods": month["default_periods"],
            "days": [{key: day[key] for key in ("date", "row", "identity", "history")} for day in month["days"]]}


@read_endpoint
def operator_calendar_month(ref):
    values = _month_input()
    reader = _reader()
    with reader.read_snapshot(capture_fingerprint=False):
        record = reader.detail(ref)
        service = _service(_operator_code(reader, ref))
        month = service.month(**values)
        days = []
        for day in month["days"]:
            public = {**WorkbenchOperatorCalendarService.public_day(day), "default_periods": month["default_periods"],
                      **{key: day[key] for key in ("day", "weekday", "is_weekend", "is_today")}}
            days.append(public)
        by_date = {day["date"]: day for day in days}
        data = {key: month[key] for key in ("year", "month", "as_of", "time_basis", "previous_month", "next_month", "stats")}
        data.update(operator_ref=ref, days=days,
                    cells=[by_date[cell["date"]] if cell is not None else None for cell in month["cells"]])
        binding = _month_binding(record, month)
        data["write_context"] = issue_write_context(ref, [ACTIONS["upsert"], ACTIONS["delete"], ACTIONS["range_clear"]], binding)
        snapshot = bind_read_snapshot({"kind": "operator_calendar", "ref": ref, **values}, input_fingerprint(binding),
                                      request.args.get("snapshot_ref"))
    return query_success(data, snapshot)


def _command_body(extra=()):
    body = json_body({"request_key", "write_token", "input"}, extra)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    return body


def _guarded_day(ref, action, write_token, service, day):
    """Bind the original month, including calendar revisions and absence history."""
    record = _reader().detail(ref)
    month = service.month(int(day[:4]), int(day[5:7]))
    validate_write_context(write_token, ref, ACTIONS[action], _month_binding(record, month))
    state = next(item for item in month["days"] if item["date"] == day)
    return {key: state[key] for key in ("date", "explicit", "calendar_ref", "revision", "row", "identity", "history")}


def _guarded_range(ref, write_token, service, payload):
    record = _reader().detail(ref)
    preview = service.preview_range_clear(payload)
    validate_write_context(write_token, ref, ACTIONS["range_clear"], {"resource": record.state, "preview": preview})
    return preview


@api_endpoint
def operator_calendar_command(ref, action):
    body = _command_body()
    reader = _reader()
    service = _service(_operator_code(reader, ref))
    payload = service.normalize(action, body["input"])
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=ACTIONS[action], context_ref=ref,
        normalized_input={"operator_ref": ref, **payload},
        guard=lambda: _guarded_day(ref, action, body["write_token"], service, payload["date"]),
        mutate=lambda checked: service._apply_checked(action, payload, checked))
    return jsonify(outcome)


@read_endpoint
def operator_calendar_range_preview(ref):
    body = json_body({"input"})
    reader = _reader()
    # 只借 read_snapshot 的读事务；这次的快照要绑这段日期的个人日历内容，不是整份人员列表。
    with reader.read_snapshot(capture_fingerprint=False):
        service = _service(_operator_code(reader, ref))
        preview = service.preview_range_clear(body["input"])
        data = {"operator_ref": ref, "range": preview["request"], "count": preview["count"],
                "days": [WorkbenchOperatorCalendarService.public_day(day) for day in preview["days"]],
                "write_context": issue_write_context(ref, [ACTIONS["range_clear"]], {"resource": reader.detail(ref).state, "preview": preview})}
        snapshot = bind_read_snapshot({"kind": "operator_calendar_range", "ref": ref, **preview["request"]},
                                      input_fingerprint(preview["days"]))
    return query_success(data, snapshot)


@api_endpoint
def operator_calendar_range_clear(ref):
    body = _command_body()
    reader = _reader()
    service = _service(_operator_code(reader, ref))
    payload = service.normalize("range_clear", body["input"])
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=ACTIONS["range_clear"], context_ref=ref,
        normalized_input={"operator_ref": ref, **payload},
        guard=lambda: _guarded_range(ref, body["write_token"], service, payload),
        mutate=lambda checked: service._apply_checked("range_clear", payload, checked))
    return jsonify(outcome)


def register_operator_calendar_routes(bp):
    base = "/api/workbench/v1/entities/operator/<ref>/calendar"
    bp.add_url_rule(base + "/month", view_func=operator_calendar_month, methods=["GET"])
    for action in ("upsert", "delete"):
        bp.add_url_rule(base + "/" + action, endpoint="operator_calendar_" + action,
                        view_func=operator_calendar_command, defaults={"action": action}, methods=["POST"])
    bp.add_url_rule(base + "/range-preview", view_func=operator_calendar_range_preview, methods=["POST"])
    bp.add_url_rule(base + "/range-clear", view_func=operator_calendar_range_clear, methods=["POST"])
