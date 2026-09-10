"""Keep receipts authoritative; audit fields need exact lineage and intent hash."""

import json
import re
from datetime import datetime
from typing import NoReturn

from core.models.workbench_command import input_fingerprint, validate_request_key
from core.models.workbench_trial import reference, reject
from core.models.workbench_trial_codec import fingerprint, load_object, require_object
from data.repositories.workbench_trial_adoption_history import MAX_SCENARIO_BYTES, TrialAdoptionHistoryRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository


def invalid() -> NoReturn:
    reject("adoption_history_invalid", "采用历史的永久场景、草稿或正式回执关联不一致，未替换原记录。")


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
    WorkbenchTrialRepository(conn).require_schema()
    header, draft = repo.scenario_headers(scenario_ref)
    # Bound the permanent detail too, before the existing snapshot reader loads it.
    sizes = conn.execute("SELECT length(CAST(payload_json AS BLOB)) FROM WorkbenchTrialScenarioRows WHERE scenario_ref=? LIMIT 10001", (scenario_ref,)).fetchall()
    repo.bound(sum(row[0] or 0 for row in sizes), MAX_SCENARIO_BYTES)
    if len(sizes) > 10000:
        reject("query_too_large", "场景明细超过10000条上限，未截断。", 413)
    saved = WorkbenchTrialRepository(conn).scenario(scenario_ref)
    admission_row = conn.execute("SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft["draft_ref"],)).fetchone()
    if admission_row is None:
        invalid()
    admission = load_object(admission_row[0], draft["admission_hash"])
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
    created = conn.execute("SELECT action,context_ref FROM WorkbenchCommandReceipts WHERE request_key=?", (draft["request_key"],)).fetchone()
    receipt = repo.receipt(header["request_key"])
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
    history = repo.history(plan["version"])
    if history is None:
        return empty, [gap("audit_missing", "正式历史不存在或同版本记录不唯一，采用审计字段暂无可靠证据。")]
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
        return empty, [gap("audit_unproven", "正式历史审计与原回执或保存来源不符，人、原因和本地采用时间未采信。")]
