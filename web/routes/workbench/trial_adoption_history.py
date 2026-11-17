"""Independent coordinator hook; no write endpoints or DDL."""

import re

from flask import g, request

from core.models.workbench_trial import reject
from core.services.workbench.trial.adoption_history import WorkbenchTrialAdoptionHistoryService
from core.services.workbench.trial.adoption_history_policy import MAX_DIRECTORY_BYTES
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_context import snapshot_binder
from .request_json import single_value_arguments


@api_endpoint
def trial_adoption_history(scenario_ref):
    allowed = {"page", "size", "status", "snapshot_ref"}
    single_value_arguments(allowed, message="采用记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。")
    numbers = {}
    for key, default in (("page", "1"), ("size", "20")):
        raw = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,5}", raw) is None:
            reject("invalid_input", "页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
        numbers[key] = int(raw)
    if numbers["page"] > 1 and not request.args.get("snapshot_ref"):
        reject("snapshot_required", "翻页位置已失效，请回到第 1 页重新查询。", 400)
    status = request.args.get("status", "all")
    data, snapshot = WorkbenchTrialAdoptionHistoryService(g.db).read(
        scenario_ref,
        status=status,
        bind_snapshot=snapshot_binder(request.args.get("snapshot_ref")),
        **numbers,
    )
    return query_success(data, snapshot, byte_limit=MAX_DIRECTORY_BYTES)


def register_trial_adoption_history_routes(bp):
    bp.add_url_rule("/api/workbench/v1/trial/scenarios/<scenario_ref>/adoption-history",
                    view_func=trial_adoption_history, methods=["GET"])
