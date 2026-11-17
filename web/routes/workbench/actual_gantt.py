"""The shell owner calls register_actual_gantt_routes(bp); no write endpoints."""

from io import BytesIO

from flask import current_app, g, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.execution.actual_gantt import MAX_ACTUAL_RESPONSE_BYTES, ActualGanttService, bind_axis_time
from core.services.workbench.execution.actual_gantt_export import actual_gantt_csv
from core.services.workbench.execution.actual_gantt_scope import COHORT_KEYS, VIEW_KEYS, ActualGanttScope
from core.shared.key_sets import keys_conform
from web.api_responses import query_success

from .api_responses import read_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, read_snapshot_time, rebind_read_snapshot
from .request_json import BodyTexts, read_json_body, rejecter

_REJECTED = "现场甘特的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。"
_BODY = BodyTexts(transport=_REJECTED, malformed=_REJECTED, incomplete=_REJECTED)


def _request(export=False):
    """The read scope travels in the POST body: a batch list can be longer than a request line allows."""
    allowed = COHORT_KEYS + ("snapshot_ref",) + (VIEW_KEYS + ("format",) if export else ())
    body = read_json_body(_BODY)
    if not keys_conform(body, (), allowed):
        rejecter(_REJECTED)()
    return body, ActualGanttScope.parse({key: body[key] for key in COHORT_KEYS if key in body})


def _read(scope, token, *, full_workspace):
    reader = ActualGanttService(g.db, current_app.logger)
    as_of, binding = read_snapshot_time(token)
    snapshot = None
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot() as gantt_scope:
            if token is not None:
                scope_dict, state = reader.prebind_scope(gantt_scope, scope)
                snapshot = rebind_read_snapshot(scope_dict, state, token, binding=binding)
            data, state = reader.workspace(gantt_scope, scope, full_workspace=full_workspace)
    if snapshot is None:
        snapshot = bind_read_snapshot(scope.scope(), state, as_of=as_of)
    data = bind_axis_time(data, snapshot["as_of"])
    return data, snapshot


@read_endpoint
def actual_gantt_workspace():
    body, scope = _request()
    data, snapshot = _read(scope, body.get("snapshot_ref"), full_workspace=True)
    return query_success(data, snapshot, byte_limit=MAX_ACTUAL_RESPONSE_BYTES,
        too_large_message="这次要读的现场甘特数据太多，系统没有给出不完整结果。请缩小日期范围或减少所选批次后点「刷新」。")


@read_endpoint
def actual_gantt_export():
    body, scope = _request(export=True)
    if not body.get("snapshot_ref") or body.get("format") != "csv":
        raise WorkbenchCommandRejected("invalid_input", "数据已更新，没有开始下载。请点「刷新」后重新点「导出」，再点「下载 CSV」。", 400)
    data, snapshot = _read(scope, body["snapshot_ref"], full_workspace=False)
    content, rows, operations = actual_gantt_csv(data, snapshot, {key: body[key] for key in VIEW_KEYS if key in body})
    if len(content) > MAX_ACTUAL_RESPONSE_BYTES:
        raise WorkbenchCommandRejected(
            "query_too_large", f"现场甘特 CSV 超过 {MAX_ACTUAL_RESPONSE_BYTES // (1024 * 1024)} MB，请缩小范围后重新导出。", 413
        )
    response = send_file(BytesIO(content), mimetype="text/csv;charset=utf-8", as_attachment=True,
                         download_name="现场实际甘特-" + snapshot["as_of"].replace(":", "") + ".csv", max_age=0)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-Row-Count"] = str(rows)
    response.headers["X-Workbench-Operation-Count"] = str(operations)
    return response


def register_actual_gantt_routes(bp):
    bp.add_url_rule("/api/workbench/v1/actual-gantt", view_func=actual_gantt_workspace, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/actual-gantt/export", view_func=actual_gantt_export, methods=["POST"])
