"""Keep receipts authoritative; audit fields need exact lineage and intent hash."""

import json
import re
from datetime import datetime
from typing import NoReturn

from core.models.workbench_command import input_fingerprint, validate_request_key
from core.models.workbench_trial import reference, reject
from core.models.workbench_trial_codec import fingerprint, load_object, require_object
from core.services.workbench.facts.trial_policy import load_scenario, require_trial_schema
from data.repositories.workbench_trial_adoption_history import TrialAdoptionHistoryRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .adoption_history_policy import MAX_SCENARIO_BYTES, bound, load_history, load_receipt, load_scenario_headers


def invalid() -> NoReturn:
    reject("adoption_history_invalid", "采用记录里的试调方案、草稿和结果对不上，这里没有改动原记录。请刷新后重试。")


def json_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate evidence key")
            result[key] = value
        return result
    if type(raw) is not str:
        raise ValueError("Evidence is not text")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: invalid())
    if type(value) is not dict:
        raise ValueError("Evidence is not an object")
    return value


def scenario_evidence(conn, scenario_ref):
    reference(scenario_ref)
    repo = TrialAdoptionHistoryRepository(conn)
    trial_repo = WorkbenchTrialRepository(conn)
    require_trial_schema(trial_repo)
    header, draft = load_scenario_headers(repo, scenario_ref)
    # Bound the permanent detail too, before the existing snapshot reader loads it.
    sizes = repo.scenario_row_sizes(scenario_ref)
    bound(sum(size or 0 for size in sizes), MAX_SCENARIO_BYTES)
    if len(sizes) > 10000:
        reject("query_too_large", "试调方案的明细超过 10000 条上限，这次没有读取。请缩小范围。", 413)
    saved = load_scenario(trial_repo, scenario_ref)
    admission_row = repo.draft_admission(draft["draft_ref"])
    if admission_row is None:
        invalid()
    admission = load_object(admission_row["admission_json"], draft["admission_hash"])
    intent = require_object(admission.get("input"))
    baseline = require_object(admission.get("baseline"))
    source = require_object(admission.get("source"))
    expected = {"scenario_ref": scenario_ref, "draft_ref": draft["draft_ref"], "status": "saved",
                "name": header["name"], "saved_at": header["saved_at"], "base": intent["base"],
                "baseline": {key: baseline[key] for key in ("plan_ref", "version")},
                "base_identity": source["identity"]}
    if (not matches(saved, expected) or draft["status"] != "saved"
            or draft["revision"] != header["revision"] + 1
            or saved["base"] != {draft["base_kind"]: draft["base_ref"]}):
        invalid()
    created = repo.receipt_action(draft["request_key"])
    receipt = load_receipt(repo, header["request_key"])
    outcome = json_object(receipt["outcome_json"])
    if (created is None or tuple(created) != ("trial.create", draft["base_ref"])
            or (receipt["action"], receipt["context_ref"]) != ("trial.save", draft["draft_ref"])
            or outcome.get("result") != "committed" or fingerprint(outcome.get("data")) != fingerprint(saved)):
        invalid()
    return saved, header, draft


def matches(value, expected):
    # Canonical comparison also distinguishes JSON bool/int/float field types.
    return fingerprint({key: value[key] for key in expected}) == fingerprint(expected)


def _receipt_lineage(row, saved, value):
    data, plan = value["data"], value["data"]["official_plan"]
    expected_data = {"scenario_ref": saved["scenario_ref"], "draft_ref": saved["draft_ref"], "row_count": saved["task_count"]}
    expected_plan = {"source_scenario_ref": saved["scenario_ref"], "source_draft_ref": saved["draft_ref"],
                     "kind": "official", "baseline_ref": saved["baseline"]["plan_ref"]}
    if (set(value) != {"result", "data", "warnings"} or value["result"] != "committed"
            or type(value["warnings"]) is not list
            or (row["action"], row["context_ref"]) != ("trial.scenario.adopt", saved["scenario_ref"])
            or not matches(data, expected_data) or not matches(plan, expected_plan)
            or any(key in plan for key in ("candidate_ref", "run_ref", "source_run_ref"))):
        invalid()


def receipt_plan(row, saved):
    validate_request_key(row["request_key"])
    if re.fullmatch(r"[0-9a-f]{32}", row["receipt_ref"]) is None:
        invalid()
    value = json_object(row["outcome_json"])
    data = value["data"]
    plan = data["official_plan"]
    _receipt_lineage(row, saved, value)
    reference(plan["plan_ref"])
    if (type(plan["version"]) is not int
            or plan["version"] <= (saved["baseline"]["version"] or 0)
            or plan["plan_ref"] in (saved["scenario_ref"], saved["draft_ref"], saved["baseline"]["plan_ref"])):
        invalid()
    stamp = row["committed_at_utc"]
    if type(stamp) is not str or not stamp.endswith("Z"):
        invalid()
    datetime.fromisoformat(stamp[:-1])
    return {"plan_ref": plan["plan_ref"], "version": plan["version"], "row_count": data["row_count"]}


def gap(code, message):
    return {"code": code, "message": message}


def _audit_lineage(audit, row, plan, saved, header, draft):
    expected = {"source": "workbench_trial_adoption", "request_key": row["request_key"],
                "scenario_ref": saved["scenario_ref"], "draft_ref": saved["draft_ref"],
                "version": plan["version"], "row_count": plan["row_count"], "is_simulation": False,
                "baseline_ref": saved["baseline"]["plan_ref"], "baseline_version": saved["baseline"]["version"]}
    proof = {"scenario_ref": saved["scenario_ref"], "draft_ref": saved["draft_ref"],
             "scenario_hash": header["snapshot_hash"], "admission_hash": draft["admission_hash"]}
    if not matches(audit, expected) or not matches(audit["proof"], proof):
        raise ValueError("Audit lineage mismatch")


def audit_fields(repo, row, plan, saved, header, draft):
    empty = {"reason": None, "declared_operator": None, "application_operator": None, "adopted_at": None}
    history = load_history(repo, plan["version"])
    if history is None:
        return empty, [gap("audit_missing", "找不到对应的正式计划历史，或同一版本有多条记录，采用信息暂时无法确认。")]
    try:
        audit = json_object(history["result_summary"])
        _audit_lineage(audit, row, plan, saved, header, draft)
        if history["result_status"] != "success":
            raise ValueError("Not a successful history record")
        intent = {"confirm": True, "reason": audit["reason"], "declared_operator": audit["declared_operator"]}
        if input_fingerprint(intent) != row["input_hash"]:
            raise ValueError("Audit intent does not match immutable receipt")
        fields = {key: audit[key] for key in empty}
        if any(type(value) is not str or not value.strip() for value in fields.values()):
            raise ValueError("Missing audit field")
        if fields["application_operator"] != history["created_by"]:
            raise ValueError("Application operator mismatch")
        if datetime.fromisoformat(fields["adopted_at"]).tzinfo is not None:
            raise ValueError("Not factory local time")
        return fields, []
    except (ValueError, TypeError, KeyError):
        return empty, [gap("audit_unproven", "正式计划历史与保存结果对不上，经办人、原因和采用时间暂时不采信。")]
