"""Standalone registration; every continuation validates the original read scope."""

import re
from urllib.parse import quote

from flask import Response, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_master_overview import invalid, read_scope
from core.services.workbench import messages
from core.services.workbench.master_overview import MasterOverviewService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot

BASE = "/api/workbench/v1/master-overview"


def _request(extra=(), require_snapshot=False):
    allowed = {"scope", "snapshot_ref"} | set(extra)
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        invalid("资料总览的查询条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。")
    scope = read_scope(request.args.get("scope", "{}"))
    token = request.args.get("snapshot_ref")
    if require_snapshot and not token:
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
    return scope, token


def _page(key):
    value = request.args.get(key, "1")
    if re.fullmatch(r"[1-9][0-9]{0,8}", value) is None:
        invalid("页码填写不对，列表没有变化。请回到第 1 页重新查询。")
    return int(value)


def _response(data, snapshot):
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def master_overview_list():
    page = _page("page")
    scope, token = _request(("page",), require_snapshot=page > 1)
    reader = MasterOverviewService(g.db)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(scope.scope(), state, token)
        data = reader.page(scope, page)
    return _response(data, snapshot)


@api_endpoint
def master_overview_detail(domain, ref):
    scope, token = _request(("section", "detail_page"), require_snapshot=True)
    section = request.args.get("section", "issues")
    if section not in ("issues", "relations", "fields"):
        invalid("要看的详情类别不对，详情没有打开。请刷新页面后重新点开这一行。")
    reader = MasterOverviewService(g.db)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(scope.scope(), state, token)
        data = reader.detail(scope, domain, ref, section, _page("detail_page"))
    return _response(data, snapshot)


@api_endpoint
def master_overview_locate(domain, ref):
    scope, token = _request(require_snapshot=True)
    reader = MasterOverviewService(g.db)
    with reader.read_snapshot() as state:
        bind_read_snapshot(scope.scope(), state, token)
        target_scope, data = reader.locate(scope, domain, ref)
        snapshot = bind_read_snapshot(target_scope.scope(), state)
    return _response(data, snapshot)


@api_endpoint
def master_overview_export():
    scope, token = _request(require_snapshot=True)
    assert token is not None
    reader = MasterOverviewService(g.db)
    with reader.read_snapshot() as state:
        bind_read_snapshot(scope.scope(), state, token)
        content, count = reader.csv(scope)
    filename = "基础资料待维护项.csv" if scope.view == "issues" else "基础资料清单.csv"
    response = Response(content, content_type="text/csv; charset=utf-8")
    response.headers.update({"Cache-Control": "no-store", "X-Workbench-Snapshot-Ref": token,
                             "X-Workbench-Row-Count": str(count), "Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename)})
    return response


def register_master_overview_routes(bp):
    bp.add_url_rule(BASE, view_func=master_overview_list, methods=["GET"])
    bp.add_url_rule(BASE + "/entities/<domain>/<ref>", view_func=master_overview_detail, methods=["GET"])
    bp.add_url_rule(BASE + "/locate/<domain>/<ref>", view_func=master_overview_locate, methods=["GET"])
    bp.add_url_rule(BASE + "/export", view_func=master_overview_export, methods=["GET"])
