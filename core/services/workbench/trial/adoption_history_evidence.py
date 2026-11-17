"""Keep receipts authoritative; audit fields use structured ScheduleHistory columns."""

from typing import NoReturn

from core.models.content import read_stored_json
from core.models.workbench_load_limits import MAX_WINDOW_OPERATIONS
from core.models.workbench_trial import reference, reject
from core.services.workbench.facts.trial_policy import load_scenario_with_resources
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository


def invalid() -> NoReturn:
    reject("adoption_history_invalid", "采用记录里的试调方案、草稿和结果对不上，这里没有改动原记录。请刷新后重试。")


def scenario_headers(conn, scenario_ref):
    trial_repo = WorkbenchTrialRepository(conn)
    header = trial_repo.scenario_header(scenario_ref)
    if header is None:
        reject("entity_not_found", "未找到指定试调场景。", 404)
    draft = trial_repo.draft_header(header["draft_ref"])
    if draft is None:
        reject("adoption_history_invalid", "试调方案的原草稿缺失，请联系维护人员核对。")
    return trial_repo, header, draft


def read_bounded_scenario(trial_repo, scenario_ref, *, header):
    _, saved, _ = load_scenario_with_resources(trial_repo, scenario_ref, row_limit=MAX_WINDOW_OPERATIONS, header=header)
    if saved["scenario_ref"] != header["scenario_ref"] or saved["draft_ref"] != header["draft_ref"]:
        invalid()
    return saved


def receipt_plan(row):
    value = read_stored_json(row["outcome_json"], dict)
    try:
        data = value["data"]
        plan = data["official_plan"]
        plan_ref = plan["plan_ref"]
        version = plan["version"]
        row_count = data["row_count"]
    except (KeyError, TypeError):
        invalid()
    if value.get("result") != "committed" or type(plan) is not dict or plan.get("kind") != "official":
        invalid()
    reference(plan_ref)
    if type(version) is not int or version < 1:
        invalid()
    return {"plan_ref": plan_ref, "version": version, "row_count": row_count}


def gap(code, message):
    return {"code": code, "message": message}


def audit_fields(*, history):
    empty = {"reason": None, "declared_operator": None, "application_operator": None, "adopted_at": None}
    if history is None:
        return empty, [gap("audit_missing", "找不到对应的正式计划历史，采用信息暂时无法确认。")]
    return {key: history[key] for key in empty}, []
