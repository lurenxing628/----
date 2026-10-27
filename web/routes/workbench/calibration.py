"""Exclusive calibration GET endpoints; the main integrator owns registration."""

from typing import Any, Dict

from flask import g, request, send_file

from core.models.workbench_calibration import DUPLICATE_FILTER_MESSAGE, MAX_RESPONSE_BYTES, CalibrationQuery
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from core.services.workbench.calibration.export import export_calibration
from core.services.workbench.calibration.service import WorkbenchCalibrationService
from core.shared.strict_json import load_strict_json
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot, current_snapshot_time, page_integer, resolve_read_snapshot
from .request_json import rejecter


def _arguments(*, export, detail):
    allowed = {"query", "part_ref", "source", "status", "deviation", "page", "size", "sort", "direction", "snapshot_ref", "column_filters"}
    if export:
        allowed.add("format")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "工时校准的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)
    fields: Dict[str, Any] = {key: value for key, value in request.args.items() if key not in ("snapshot_ref", "format", "page", "size")}
    fields.update(number=page_integer(request.args.get("page", "1"), max_digits=7), size=page_integer(request.args.get("size", "20"), max_digits=7))
    if "column_filters" in fields:
        fields["column_filters"] = load_strict_json(
            fields["column_filters"], on_malformed=rejecter("列筛选内容读不出来，当前筛选没有变化。请点「清除筛选」后重新选择。"),
            on_duplicate=rejecter(DUPLICATE_FILTER_MESSAGE))
    query = CalibrationQuery(**fields)
    token = request.args.get("snapshot_ref")
    if (export or detail) and not token:
        raise WorkbenchCommandRejected("snapshot_required", messages.STALE, 400)
    return query, token


def _read(*, export=False, suggestion_ref=None):
    query, token = _arguments(export=export, detail=suggestion_ref is not None)
    binding = resolve_read_snapshot(token) if token is not None else None
    as_of = binding.as_of_time if binding is not None else None
    service = WorkbenchCalibrationService(g.db, as_of=as_of)
    facts = service.read(
        query,
        clock=current_snapshot_time if binding is None else None,
        bind_snapshot=lambda content: bind_read_snapshot(query.scope(), content, token, as_of=service.as_of, binding=binding),
    )
    snapshot = facts["snapshot"]
    data, rows = service.workspace(facts, query, snapshot, suggestion_ref=suggestion_ref, export=export)
    if export:
        file = export_calibration(data, rows, snapshot, request.args.get("format", "csv"))
        response = send_file(file.data, mimetype=file.content_type, as_attachment=True, download_name=file.filename, max_age=0)
        response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
        response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
        response.headers["X-Workbench-Row-Count"] = str(file.estimated_rows)
    else:
        response = query_success(data, snapshot, byte_limit=MAX_RESPONSE_BYTES,
            too_large_message="这次要读的校准明细超过 8 MB，系统没有给出不完整内容。请缩小筛选范围后点「刷新」。")
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def calibration_list():
    return _read()


@api_endpoint
def calibration_detail(suggestion_ref):
    return _read(suggestion_ref=suggestion_ref)


@api_endpoint
def calibration_export():
    return _read(export=True)


def register_calibration_routes(bp):
    from .calibration_table import register_calibration_table_routes

    bp.add_url_rule("/api/workbench/v1/calibration", view_func=calibration_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/calibration/export", view_func=calibration_export, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/calibration/<suggestion_ref>", view_func=calibration_detail, methods=["GET"])
    register_calibration_table_routes(bp)
