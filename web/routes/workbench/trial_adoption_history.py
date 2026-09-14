"""Independent coordinator hook; no write endpoints or DDL."""

import re

from flask import g, request

from core.models.workbench_trial import reject
from core.services.workbench.trial_adoption_history import WorkbenchTrialAdoptionHistoryService, history_scope

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot


@api_endpoint
def trial_adoption_history(scenario_ref):
    allowed = {"page", "size", "status", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        reject("invalid_input", "采用记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)
    numbers = {}
    for key, default in (("page", "1"), ("size", "20")):
        raw = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,5}", raw) is None:
            reject("invalid_input", "页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
        numbers[key] = int(raw)
    if numbers["page"] > 1 and not request.args.get("snapshot_ref"):
        reject("snapshot_required", "翻页位置已失效，请回到第 1 页重新查询。", 400)
    status = request.args.get("status", "all")
    scope = history_scope(scenario_ref, status, numbers["size"])
    data, digest = WorkbenchTrialAdoptionHistoryService(g.db).read(scenario_ref, status=status, **numbers)
    response = query_success(data, bind_read_snapshot(scope, digest, request.args.get("snapshot_ref")))
    response.headers["Cache-Control"] = "no-store"
    return response


def register_trial_adoption_history_routes(bp):
    bp.add_url_rule("/api/workbench/v1/trial/scenarios/<scenario_ref>/adoption-history",
                    view_func=trial_adoption_history, methods=["GET"])
