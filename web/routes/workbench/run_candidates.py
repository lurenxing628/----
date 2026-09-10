"""Register permanent candidate GETs explicitly; no global initialization here."""

import re
from io import BytesIO

from flask import g, request, send_file

from core.models.workbench_run_candidate import (
    MAX_RESPONSE_BYTES,
    RunCandidateCatalogScope,
    RunCandidateReadScope,
    reject,
)
from core.services.workbench.run_candidate_export import write_run_candidate_export
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot

_WORKSPACE_ARGS = ("range_start", "range_end", "batch_ref", "sort", "order", "snapshot_ref")


def _arguments(allowed):
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        reject("invalid_input", "候选查询含未知或重复参数，未忽略筛选条件。", 400)


def _integer(name, default: str):
    value = request.args.get(name, default)
    if re.fullmatch(r"[1-9][0-9]{0,5}", value) is None:
        reject("invalid_input", "候选目录页码和每页数量必须为正整数。", 400)
    return int(value)


def _scope(candidate_ref):
    return RunCandidateReadScope(candidate_ref, request.args.get("range_start"), request.args.get("range_end"),
                                 request.args.get("batch_ref"), request.args.get("sort", "sequence"), request.args.get("order", "asc"))


def _response(data, snapshot):
    response = query_success(data, snapshot)
    if len(response.get_data()) > MAX_RESPONSE_BYTES:
        reject("candidate_capacity_exceeded", "候选读取响应超出容量，未截断结果。", 413)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def run_candidate_list(run_ref):
    _arguments(("status", "sort", "order", "page", "size", "snapshot_ref"))
    scope = RunCandidateCatalogScope(run_ref, request.args.get("status", "all"), request.args.get("sort", "sequence"),
                                     request.args.get("order", "asc"), _integer("page", "1"), _integer("size", "20"))
    data, state = WorkbenchRunCandidateQueryService(g.db).catalog(scope)
    snapshot = bind_read_snapshot(scope.scope(), state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)


@api_endpoint
def run_candidate_workspace(candidate_ref):
    _arguments(_WORKSPACE_ARGS)
    scope = _scope(candidate_ref)
    data, state = WorkbenchRunCandidateQueryService(g.db).workspace(scope)
    snapshot = bind_read_snapshot(scope.scope(), state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)


@api_endpoint
def run_candidate_export(candidate_ref):
    _arguments(_WORKSPACE_ARGS + ("format",))
    fmt, token = request.args.get("format"), request.args.get("snapshot_ref")
    if fmt not in ("csv", "xlsx") or not token:
        reject("invalid_input", "导出必须提供 CSV/XLSX 格式及当前候选工作区读取快照。", 400)
    scope = _scope(candidate_ref)
    data, state = WorkbenchRunCandidateQueryService(g.db).workspace(scope)
    snapshot = bind_read_snapshot(scope.scope(), state, token)
    _response(data, snapshot)
    download = write_run_candidate_export(data, snapshot, fmt)
    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    response.headers["X-Workbench-Task-Count"] = str(data["task_count"])
    response.headers["X-Workbench-Candidate-Ref"] = candidate_ref
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    return response


def register_run_candidate_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/runs/<run_ref>/candidates", view_func=run_candidate_list, methods=["GET"])
    base = "/api/workbench/v1/scheduling/candidates/<candidate_ref>"
    bp.add_url_rule(base, endpoint="run_candidate_detail", view_func=run_candidate_workspace, methods=["GET"])
    bp.add_url_rule(base + "/workspace", view_func=run_candidate_workspace, methods=["GET"])
    bp.add_url_rule(base + "/export", view_func=run_candidate_export, methods=["GET"])
