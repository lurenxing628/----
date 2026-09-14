"""The shell owner calls register_actual_gantt_routes(bp); no write endpoints."""

from io import BytesIO

from flask import current_app, g, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import public_ref
from core.services.workbench.actual_gantt import MAX_ACTUAL_RESPONSE_BYTES, ActualGanttService, bind_axis_time
from core.services.workbench.actual_gantt_export import actual_gantt_csv
from core.services.workbench.actual_gantt_scope import COHORT_KEYS, VIEW_KEYS, ActualGanttScope

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot


def _scope(export=False, related=False):
    allowed = set(COHORT_KEYS) | {"snapshot_ref"}
    if related:
        allowed.add("target_task_ref")
    if export:
        allowed |= set(VIEW_KEYS) | {"format"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "现场甘特的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)
    return ActualGanttScope.parse({key: request.args[key] for key in COHORT_KEYS if key in request.args})


def _read(scope, *, chain_target=None):
    reader = ActualGanttService(g.db, current_app.logger)
    with reader.read_snapshot():
        data, state = reader.workspace(scope, chain_target=chain_target)
        snapshot = bind_read_snapshot(scope.scope(), state, request.args.get("snapshot_ref"))
    return bind_axis_time(data, snapshot["as_of"], snapshot["snapshot_ref"]), snapshot


@api_endpoint
def actual_gantt_workspace():
    data, snapshot = _read(_scope())
    response = query_success(data, snapshot)
    if len(response.get_data()) > MAX_ACTUAL_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "这次要读的现场甘特数据太多，系统没有给出不完整结果。请缩小日期范围或减少所选批次后点「刷新」。", 413)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def actual_gantt_related_chain():
    scope = _scope(related=True)
    target = request.args.get("target_task_ref")
    public_ref(target)
    if not request.args.get("snapshot_ref"):
        raise WorkbenchCommandRejected("snapshot_required", "数据已更新，关联工序还没有打开。请点「刷新」后重新选择。", 400)
    data, snapshot = _read(scope, chain_target=target)
    response = query_success({key: data[key] for key in ("plan", "scope", "critical_chain")}, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def actual_gantt_export():
    scope = _scope(export=True)
    if not request.args.get("snapshot_ref") or request.args.get("format") != "csv":
        raise WorkbenchCommandRejected("invalid_input", "数据已更新，没有开始下载。请点「刷新」后重新点「导出 CSV」。", 400)
    data, snapshot = _read(scope)
    content, rows, operations = actual_gantt_csv(data, snapshot, {key: request.args[key] for key in VIEW_KEYS if key in request.args})
    response = send_file(BytesIO(content), mimetype="text/csv;charset=utf-8", as_attachment=True,
                         download_name="现场实际甘特-" + snapshot["as_of"].replace(":", "") + ".csv", max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-Row-Count"] = str(rows)
    response.headers["X-Workbench-Operation-Count"] = str(operations)
    return response


def register_actual_gantt_routes(bp):
    bp.add_url_rule("/api/workbench/v1/actual-gantt", view_func=actual_gantt_workspace, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/actual-gantt/chain", view_func=actual_gantt_related_chain, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/actual-gantt/export", view_func=actual_gantt_export, methods=["GET"])
