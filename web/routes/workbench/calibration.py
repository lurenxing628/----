"""Exclusive calibration GET endpoints; the main integrator owns registration."""

import json
from typing import Any, Dict

from flask import g, request, send_file

from core.models.workbench_calibration import MAX_RESPONSE_BYTES, CalibrationQuery, unique_calibration_object
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.calibration import WorkbenchCalibrationService
from core.services.workbench.calibration_export import export_calibration

from .api_responses import api_endpoint, query_success
from .calibration_read_context import as_of as _as_of
from .calibration_read_context import bind as _bind
from .calibration_read_context import page_integer as _page_integer


def _arguments(*, export, detail):
    allowed = {"query", "part_ref", "source", "status", "deviation", "page", "size", "sort", "direction", "snapshot_ref", "column_filters"}
    if export:
        allowed.add("format")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "校准查询包含未知或重复参数，未忽略筛选条件。", 400)
    fields: Dict[str, Any] = {key: value for key, value in request.args.items() if key not in ("snapshot_ref", "format", "page", "size")}
    fields.update(number=_page_integer("page", "1"), size=_page_integer("size", "20"))
    if "column_filters" in fields:
        try:
            fields["column_filters"] = json.loads(fields["column_filters"], object_pairs_hook=unique_calibration_object)
        except (ValueError, TypeError) as exc:
            raise WorkbenchCommandRejected("invalid_input", "校准列筛选JSON无效。", 400) from exc
    query = CalibrationQuery(**fields)
    token = request.args.get("snapshot_ref")
    if (export or detail or query.number > 1) and not token:
        raise WorkbenchCommandRejected("snapshot_required", "分页、详情和导出须携带列表快照，请先读取列表。", 400)
    return query, token


def _read(*, export=False, suggestion_ref=None):
    query, token = _arguments(export=export, detail=suggestion_ref is not None)
    as_of = _as_of(token)
    service = WorkbenchCalibrationService(g.db, as_of=as_of)
    with service.read_snapshot(clock=(lambda: _as_of(None)) if token is None else None) as as_of:
        facts = service.read(query, bind_snapshot=lambda fingerprint: _bind(query, fingerprint, token, as_of))
        snapshot = facts["snapshot"]
        data, rows = service.workspace(facts, query, snapshot, suggestion_ref=suggestion_ref)
        if export:
            file = export_calibration(data, rows, snapshot, request.args.get("format", "csv"))
    if export:
        response = send_file(file.data, mimetype=file.content_type, as_attachment=True, download_name=file.filename, max_age=0)
        response.headers["X-Workbench-Snapshot"] = snapshot["snapshot_ref"]
        response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
        response.headers["X-Workbench-Row-Count"] = str(file.estimated_rows)
    else:
        response = query_success(data, snapshot)
        if len(response.get_data()) > MAX_RESPONSE_BYTES:
            raise WorkbenchCommandRejected("query_too_large", "完整校准详情超过8MB，请缩小范围；未截断样本出处。", 413)
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
