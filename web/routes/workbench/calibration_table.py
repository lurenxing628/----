"""Calibration facets bind all toolbar filters and every other column to one snapshot."""

import json

from flask import g, request

from core.models.workbench_calibration import CalibrationQuery, unique_calibration_object
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from core.services.workbench.calibration import WorkbenchCalibrationService, filtered_suggestions
from core.services.workbench.calibration_table import facet_data, validate_facet

from .api_responses import api_endpoint, query_success
from .calibration_read_context import as_of as _as_of
from .calibration_read_context import bind as _bind
from .calibration_read_context import page_integer as _page_integer


@api_endpoint
def calibration_facets(column, selection=False):
    if set(request.args) - {"scope", "query", "page", "size", "snapshot_ref"} or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "列筛选的查询条件有重复或不支持的项，筛选没有变化。请刷新页面后重新打开列筛选。", 400)
    try:
        scope = json.loads(request.args.get("scope", "{}"), object_pairs_hook=unique_calibration_object)
    except (ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("invalid_input", "列筛选内容读不出来，筛选没有变化。请点「清除筛选」后重新选择。", 400) from exc
    if type(scope) is not dict or set(scope) - {"query", "part_ref", "source", "status", "deviation", "column_filters"}:
        raise WorkbenchCommandRejected("invalid_input", "列筛选里有不支持的列，筛选没有变化。请刷新页面后重新打开列筛选。", 400)
    query = CalibrationQuery(**scope)
    query = CalibrationQuery(**{**scope, "column_filters": {key: value for key, value in query.column_filters.items() if key != column}})
    search, number, size = request.args.get("query", ""), _page_integer("page", "1"), _page_integer("size", "100")
    validate_facet(column, search, number, size)
    if selection and number != 1:
        raise WorkbenchCommandRejected("invalid_input", "「全选当前筛选」不分页，这次没有翻页。请直接点「全选当前筛选」。", 400)
    token = request.args.get("snapshot_ref")
    if (selection or number > 1) and not token:
        raise WorkbenchCommandRejected("snapshot_required", messages.STALE, 400)
    as_of = _as_of(token)
    service = WorkbenchCalibrationService(g.db, as_of=as_of)
    bound = {"kind": "calibration_table_facets", "scope": query.scope(), "column": column, "query": search, "size": size}
    with service.read_snapshot(clock=(lambda: _as_of(None)) if token is None else None) as as_of:
        facts = service.read(query, bind_snapshot=lambda fingerprint: _bind(query, fingerprint, token, as_of, snapshot_scope=bound))
        data = facet_data(filtered_suggestions(facts["rows"], query), column, search, number, size, selection=selection)
    response = query_success(data, facts["snapshot"])
    response.headers["Cache-Control"] = "no-store"
    return response


def register_calibration_table_routes(bp):
    bp.add_url_rule("/api/workbench/v1/calibration/facets/<column>", view_func=calibration_facets, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/calibration/facet-selection/<column>", endpoint="calibration_facet_selection",
                    view_func=calibration_facets, defaults={"selection": True}, methods=["GET"])
