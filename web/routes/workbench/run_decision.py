"""同次候选总览与下载共用一个比较投影。"""

from io import BytesIO
from typing import Dict

from flask import g, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, reference
from core.services.workbench.decision_file_export import write_decision_xlsx
from core.services.workbench.run.decision import read_run_decision, read_run_decision_summary
from core.services.workbench.run.decision_completion_queries import read_completion_batches
from core.services.workbench.run.decision_export import read_decision_export, write_run_decision_export
from core.services.workbench.run.decision_preparation_queries import read_preparation_details
from core.services.workbench.run.decision_process import read_process_details
from core.services.workbench.run.decision_queries import read_decision_details
from core.services.workbench.run.decision_resource_workspace import read_resource_workspace
from core.services.workbench.run.decision_resources import read_resource_details
from core.services.workbench.run.decision_workspace import read_reference_workspace
from web.api_responses import json_response, query_payload, query_success

from .api_responses import api_endpoint, rejection_payload
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, current_snapshot_time, rebind_read_snapshot, snapshot_binder
from .request_json import single_value_arguments

_QUERY = ("comparison_mode", "reference_candidate_ref", "selected_candidate_ref", "range_start", "range_end", "resource_view")
_FILTERS = ("batch_ref", "resource_ref", "change_kind", "sort", "order", "delivery_filter", "selected_batch_ref")
_RESOURCE_PERIOD_FILTERS = ("grain", "pressure_threshold", "display_start", "display_end", "bucket_start", "bucket_end")


def _query(allowed) -> Dict[str, str]:
    values = single_value_arguments(allowed, message="比较条件含重复或不支持的项，请重新选择比较范围。", status=422)
    for name in ("selected_candidate_ref", "reference_candidate_ref"):
        if name in values:
            reference(values[name])
    return values


def _response(data, snapshot):
    return query_success(data, snapshot, byte_limit=MAX_RESPONSE_BYTES, too_large_code="candidate_capacity_exceeded")


def _read(run_ref, reader):
    allowed = _QUERY + ("snapshot_ref",)
    values = _query(allowed)
    query = {key: values[key] for key in _QUERY if key in values}
    with PLAN_READ_SLOTS.slot():
        return reader(g.db, run_ref, bind_snapshot=snapshot_binder(request.args.get("snapshot_ref")), **query)


def _detail(run_ref, section):
    values = _query(_QUERY + _FILTERS + ("page", "size", "snapshot_ref"))
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_decision_details(g.db, run_ref, section, bind_snapshot=snapshot_binder(token), **values)
    return _response(data, snapshot)


@api_endpoint
def run_decision_batches(run_ref):
    return _detail(run_ref, "batches")


@api_endpoint
def run_decision_operations(run_ref):
    return _detail(run_ref, "operations")


@api_endpoint
def run_decision_completion_batches(run_ref):
    values = _query(_QUERY + ("completion_filter", "sort", "order", "page", "size", "snapshot_ref"))
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_completion_batches(g.db, run_ref, bind_snapshot=snapshot_binder(token), **values)
    return _response(data, snapshot)


@api_endpoint
def run_decision_process(run_ref):
    values = _query(_QUERY + ("process_candidate_ref", "objective", "record_kind", "sort", "order", "page", "size", "snapshot_ref"))
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_process_details(g.db, run_ref, bind_snapshot=snapshot_binder(token), **values)
    return _response(data, snapshot)


def _preparation_detail(run_ref, section):
    filters = ("machine_ref", "sort", "order") + (("batch_ref", "allocation_state", "work_scope") if section == "preparation" else ("event_side",))
    values = _query(_QUERY + filters + ("page", "size", "snapshot_ref"))
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_preparation_details(g.db, run_ref, section, bind_snapshot=snapshot_binder(token), **values)
    return _response(data, snapshot)


@api_endpoint
def run_decision_preparation(run_ref):
    return _preparation_detail(run_ref, "preparation")


@api_endpoint
def run_decision_changeovers(run_ref):
    return _preparation_detail(run_ref, "changeovers")


def _resource_detail(run_ref, section):
    filters = ("resource_kind", "resource_ref", "grain", "pressure_threshold") + (
        ("pressure_filter", "sort", "order", "heatmap_page", "heatmap_size", "display_start", "display_end")
        if section == "resources" else ("bucket_start", "bucket_end"))
    values = _query(_QUERY + filters + ("page", "size", "snapshot_ref"))
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_resource_details(g.db, run_ref, section, bind_snapshot=snapshot_binder(token), **values)
    return _response(data, snapshot)


@api_endpoint
def run_decision_resources(run_ref):
    return _resource_detail(run_ref, "resources")


@api_endpoint
def run_decision_resource_days(run_ref):
    return _resource_detail(run_ref, "resource-days")


@api_endpoint
def run_decision_reference_workspace(run_ref):
    values = _query(_QUERY + ("batch_ref", "snapshot_ref"))
    token = values.pop("snapshot_ref", None)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_reference_workspace(g.db, run_ref, bind_snapshot=snapshot_binder(token), **values)
    return _response(data, snapshot)


@api_endpoint
def run_decision(run_ref):
    data, snapshot = _read(run_ref, read_run_decision)
    return _response(data, snapshot)


@api_endpoint
def run_decision_summary(run_ref):
    data, snapshot = _read(run_ref, read_run_decision_summary)
    return _response(data, snapshot)


def _resource_workspace_binder(summary_token, now):
    """Bind the summary with its own token; a stale resource-view token stays the view's own error. A fresh
    snapshot takes the other view's as_of, else ``now``, the request's one reading of the clock."""
    def bind(scope, state, resource):
        snapshot = rebind_read_snapshot(scope, state, summary_token) if summary_token is not None else None
        resource_snapshot, error = None, None
        if resource is not None:
            filters, token = resource
            try:
                resource_snapshot = bind_read_snapshot({**scope, "filters": filters}, state, token,
                                                       as_of=now if snapshot is None else snapshot["as_of"])
            except WorkbenchCommandRejected as exc:
                error = exc
            else:
                if snapshot is None:
                    snapshot = bind_read_snapshot(scope, state, as_of=resource_snapshot["as_of"])
        if snapshot is None:
            snapshot = bind_read_snapshot(scope, state, as_of=now)
        return snapshot, resource_snapshot, error
    return bind


def _resource_error(error):
    return {**rejection_payload(error), "status": error.status}


@api_endpoint
def run_decision_resource_workspace(run_ref):
    fields = ("resource_kind", "resource_ref", "grain", "pressure_threshold", "pressure_filter", "sort", "order",
              "page", "size", "heatmap_page", "heatmap_size", "display_start", "display_end")
    values = _query(_QUERY + fields + ("snapshot_ref", "resource_snapshot_ref"))
    summary_token = values.pop("snapshot_ref", None)
    resource_token = values.pop("resource_snapshot_ref", None)
    summary_query = {key: values[key] for key in _QUERY if key in values}
    resource_query = {key: values[key] for key in fields if key in values}
    if resource_token is not None:
        resource_query["snapshot_ref"] = resource_token
    with PLAN_READ_SLOTS.slot():
        data, resource_data, resource_query, resource_error, snapshot, resource_snapshot = read_resource_workspace(
            g.db, run_ref, resource_query=resource_query,
            bind_snapshot=_resource_workspace_binder(summary_token, current_snapshot_time()),
            **summary_query)
    resource_result = (_resource_error(resource_error) if resource_error is not None
                       else query_payload(resource_data, resource_snapshot) if resource_data is not None else None)
    return json_response(query_payload({**data, "resource_result": resource_result, "resource_query": resource_query}, snapshot),
        byte_limit=MAX_RESPONSE_BYTES, too_large_code="candidate_capacity_exceeded")


@api_endpoint
def run_decision_export(run_ref):
    values = _query(_QUERY + _FILTERS + _RESOURCE_PERIOD_FILTERS + ("resource_kind", "pressure_filter", "machine_ref", "allocation_state", "work_scope", "event_side", "process_candidate_ref", "objective", "record_kind", "heatmap_page", "heatmap_size", "page", "size", "snapshot_ref", "format", "section", "filter_section"))
    fmt, section, token = values.pop("format", None), values.pop("section", "overview"), values.pop("snapshot_ref", None)
    if fmt not in ("csv", "xlsx") or section not in ("overview", "batches", "operations", "resources", "resource-days", "preparation", "changeovers", "recommendation", "process", "all") or fmt == "csv" and section == "all":
        raise WorkbenchCommandRejected("invalid_input", "CSV 可导出单个页签，XLSX 可导出页签或全部比较表。", 422)
    if not token:
        raise WorkbenchCommandRejected("invalid_input", "请刷新方案比较后导出当前资料。", 422)
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_decision_export(g.db, run_ref, section, bind_snapshot=snapshot_binder(token), fmt=fmt, **values)
    download = (write_decision_xlsx(write_run_decision_export, data, snapshot, section) if fmt == "xlsx" else
                write_run_decision_export(data, snapshot, fmt, section))
    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["X-Workbench-Run-Ref"] = run_ref
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    return response


def register_run_decision_routes(bp):
    base = "/api/workbench/v1/scheduling/runs/<run_ref>/decision"
    bp.add_url_rule(base, view_func=run_decision, methods=["GET"])
    bp.add_url_rule(base + "/summary", view_func=run_decision_summary, methods=["GET"])
    bp.add_url_rule(base + "/resource-workspace", view_func=run_decision_resource_workspace, methods=["GET"])
    bp.add_url_rule(base + "/batches", view_func=run_decision_batches, methods=["GET"])
    bp.add_url_rule(base + "/operations", view_func=run_decision_operations, methods=["GET"])
    bp.add_url_rule(base + "/completion-batches", view_func=run_decision_completion_batches, methods=["GET"])
    bp.add_url_rule(base + "/process", view_func=run_decision_process, methods=["GET"])
    bp.add_url_rule(base + "/reference-workspace", view_func=run_decision_reference_workspace, methods=["GET"])
    bp.add_url_rule(base + "/resources", view_func=run_decision_resources, methods=["GET"])
    bp.add_url_rule(base + "/resource-days", view_func=run_decision_resource_days, methods=["GET"])
    bp.add_url_rule(base + "/preparation", view_func=run_decision_preparation, methods=["GET"])
    bp.add_url_rule(base + "/changeovers", view_func=run_decision_changeovers, methods=["GET"])
    bp.add_url_rule(base + "/export", view_func=run_decision_export, methods=["GET"])
