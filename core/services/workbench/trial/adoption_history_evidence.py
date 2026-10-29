"""Keep receipts authoritative; audit fields use exact lineage and original intent."""

from typing import NoReturn

from core.models.workbench_trial import reference, reject
from core.services.workbench.facts.trial_policy import load_scenario_record
from core.shared.strict_json import load_strict_json
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .adoption_history_policy import MAX_SCENARIO_BYTES, bound


def invalid() -> NoReturn:
    reject("adoption_history_invalid", "采用记录里的试调方案、草稿和结果对不上，这里没有改动原记录。请刷新后重试。")


def json_object(raw):
    return load_strict_json(raw, on_malformed=invalid, expected=dict)


def scenario_evidence(conn, scenario_ref, _repo=None):
    trial_repo = WorkbenchTrialRepository(conn)
    header, saved = load_scenario_record(trial_repo, scenario_ref, row_limit=10000,
                                          byte_limit=MAX_SCENARIO_BYTES, size_check=bound)
    draft = trial_repo.draft_header(header["draft_ref"])
    if draft is None:
        reject("adoption_history_invalid", "试调方案的原草稿缺失，请联系维护人员核对。")
    return saved, header, draft


def receipt_plan(row, _saved=None):
    value = json_object(row["outcome_json"])
    data = value["data"]
    plan = data["official_plan"]
    if value.get("result") != "committed" or plan.get("kind") != "official":
        invalid()
    reference(plan["plan_ref"])
    if type(plan["version"]) is not int or plan["version"] < 1:
        invalid()
    return {"plan_ref": plan["plan_ref"], "version": plan["version"], "row_count": data["row_count"]}


def gap(code, message):
    return {"code": code, "message": message}


def audit_fields(row, plan, saved, _header=None, *, history, command_repo=None):
    empty = {"reason": None, "declared_operator": None, "application_operator": None, "adopted_at": None}
    if history is None:
        return empty, [gap("audit_missing", "找不到对应的正式计划历史，或同一版本有多条记录，采用信息暂时无法确认。")]
    try:
        audit = json_object(history["result_summary"])
        if (history["result_status"] != "success" or audit.get("source") != "workbench_trial_adoption"
                or audit.get("request_key") != row["request_key"] or audit.get("scenario_ref") != saved["scenario_ref"]
                or audit.get("version") != plan["version"]):
            raise ValueError("Audit lineage mismatch")
        fields = {key: audit[key] for key in empty}
        if any(type(value) is not str or not value.strip() for value in fields.values()):
            raise ValueError("Missing audit field")
        return fields, []
    except (ValueError, TypeError, KeyError):
        return empty, [gap("audit_unproven", "正式计划历史与保存结果对不上，经办人、原因和采用时间暂时不采信。")]
