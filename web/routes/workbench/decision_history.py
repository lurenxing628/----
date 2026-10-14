"""Archived history and complete native downloads through one read contract."""

from io import BytesIO

from flask import g, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_decision_history import QUERY_FIELDS
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot


def _query(extra=()):
    if set(request.args) - set(QUERY_FIELDS + extra) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "历史筛选含重复或不支持的字段，请重新选择。", 422)
    return dict(request.args)


@api_endpoint
def decision_history():
    values = _query()
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        from core.services.workbench.history.queries import read_decision_history

        data, scope, state = read_decision_history(g.db, values)
        snapshot = bind_read_snapshot(scope, state, token)
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def decision_history_export():
    values = _query(("format", "section"))
    fmt, section, token = values.pop("format", None), values.pop("section", "entries"), values.pop("snapshot_ref", None)
    if fmt not in ("csv", "xlsx") or section not in ("entries", "conditions", "configurations", "all") or fmt == "csv" and section == "all":
        raise WorkbenchCommandRejected("invalid_input", "CSV 可导出单个分区，XLSX 可导出分区或全部历史资料。", 422)
    if not token:
        raise WorkbenchCommandRejected("invalid_input", "请刷新历史资料后导出。", 422)
    with PLAN_READ_SLOTS.slot():
        from core.services.workbench.history.export import read_history_export, write_history_export

        data, scope, state = read_history_export(g.db, values)
        snapshot = bind_read_snapshot(scope, state, token)
        download = write_history_export(data, snapshot, fmt, section)
    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    return response


def register_decision_history_routes(bp):
    base = "/api/workbench/v1/scheduling/decision-history"
    bp.add_url_rule(base, view_func=decision_history, methods=["GET"])
    bp.add_url_rule(base + "/export", view_func=decision_history_export, methods=["GET"])
