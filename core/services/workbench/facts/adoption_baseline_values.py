"""Bounded, lossless evidence reads; no connection converter or metadata repair."""

from typing import NoReturn

from core.infrastructure.read_evidence import verified_read
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_json import load_strict_json
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository

REASONS = {
    "no_adoption_baseline": "这是首版正式计划，没有上一版可供对比。",
    "adoption_evidence_missing": "采用记录缺少必要的原始凭据，认不出采用时的正式计划是第几版，这里不显示对比。",
    "adoption_source_archived": "采用时那次排产、试调方案或试调草稿已归档或删除，原始数据核对不全，这里不显示对比。",
    "adoption_snapshot_invalid": "采用记录与归档数据不一致，无法对比。",
    "adoption_baseline_archived": "采用时那一版正式计划或它的工序安排已归档或删除，对不全，这里不显示对比。",
    "adoption_reference_invalid": "初始计划关联的记录已失效，无法对比。",
    "adoption_baseline_drift": "采用时那一版正式计划的安排后来被改过，和当时记下的原值不一样了，不能当初始计划用。",
    "adoption_plan_drift": "所选正式计划的安排和采用时的来源已经不一样了，确认不了当时的对比。",
}

_SOURCES = {"workbench_candidate_adoption": ("candidate_adoption", "scheduling.candidate.adopt", "candidate_ref", "run_ref"),
            "workbench_trial_adoption": ("trial_adoption", "trial.scenario.adopt", "scenario_ref", "draft_ref")}


class AdoptionBaselineUnavailable(Exception):
    def __init__(self, code, gap):
        super().__init__(gap)
        self.code, self.gap = code, gap


def fail(code="adoption_snapshot_invalid", gap="adoption_snapshot") -> NoReturn:
    raise AdoptionBaselineUnavailable(code, gap)


def require(condition, gap):
    if not condition:
        fail(gap=gap)


def _evidence_too_large() -> NoReturn:
    raise WorkbenchCommandRejected("query_too_large", "完整采用凭据超过 64 MB 上限。请缩小查询范围后重试。", 413)


def stored(text):
    # A BLOB in the TEXT column is its own storage gap, not unreadable JSON.
    if type(text) is not str:
        fail(gap="json_storage_type")
    return load_strict_json(text, on_malformed=lambda: fail(gap="invalid_stored_json"),
                            on_duplicate=lambda: fail(gap="duplicate_json_key"),
                            on_nonfinite=lambda: fail(gap="nonfinite_json_number"),
                            expected=dict, on_unexpected=lambda: fail(gap="json_object"),
                            limit=(64 * 1024 * 1024, _evidence_too_large))


def schedule_rows(conn, version):
    return WorkbenchPlanBaselineRepository(conn).schedule_rows_by_version(version)


def indexed(rows, key):
    require(type(rows) is list, "snapshot_rows")
    result = {}
    for row in rows:
        require(type(row) is dict and type(row.get(key)) in (str, int), "snapshot_row_identity")
        require(row[key] not in result, "duplicate_snapshot_identity")
        result[row[key]] = row
    return result


def read_adoption_record(conn, *, plan_ref, version, history, receipt=None, receipt_result=None):
    """Verify one recorded adoption and its receipt, retaining its exact official version."""
    raw = history.get("result_summary") if history else None
    return verified_read(conn, ("adoption_record", plan_ref, version, raw), lambda: _read_adoption_record(
        conn, plan_ref, version, raw, receipt=receipt, receipt_result=receipt_result))


def _read_adoption_record(conn, plan_ref, version, raw, *, receipt, receipt_result):
    # Every official version is written by a candidate or trial adoption together with its audit.
    if raw is None:
        fail("adoption_evidence_missing", "ScheduleHistory")
    audit = stored(raw)
    source = audit.get("source")
    if type(source) is not str or source not in _SOURCES:
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_source")
    required = {"request_key", "baseline_ref", "baseline_version", "version", "proof", "row_count",
                "validation", "is_simulation", "reason", "declared_operator"}
    if not required <= set(audit):
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_fields")
    basis, _, context, parent = _SOURCES[source]
    if context not in audit or parent not in audit:
        fail("adoption_evidence_missing", "ScheduleHistory.adoption_source_refs")
    require(all(type(audit[key]) is str for key in ("request_key", context, parent, "reason", "declared_operator")),
            "adoption.history_fields")
    require(audit["baseline_ref"] is None or type(audit["baseline_ref"]) is str, "adoption.baseline_ref_shape")
    require(audit["baseline_version"] is None or type(audit["baseline_version"]) is int,
            "adoption.baseline_version_shape")
    require(type(audit["version"]) is int and audit["version"] == version and audit["validation"] == "valid"
            and audit["is_simulation"] is False and type(audit["row_count"]) is int and audit["row_count"] > 0,
            "adoption.history_identity")
    _proof_fields(audit, basis)
    return basis, audit, _receipt(conn, plan_ref, version, audit, receipt=receipt, result=receipt_result)


def _proof_fields(audit, basis):
    require(type(audit["proof"]) is dict, "adoption.proof_shape")
    if audit["proof"].get("proof_version") != "content_refs_v1":
        fail("adoption_snapshot_invalid", "adoption.proof_version")
    names = ({"proof_version", "candidate_ref", "run_ref", "baseline_ref", "baseline_version"}
             if basis == "candidate_adoption" else
             {"proof_version", "scenario_ref", "draft_ref", "scenario_revision", "baseline_ref", "baseline_version"})
    missing = names - set(audit["proof"])
    if missing:
        fail("adoption_evidence_missing", "adoption.proof." + ",".join(sorted(missing)))


def _receipt(conn, plan_ref, version, audit, *, receipt, result):
    _, action, context, parent = _SOURCES[audit["source"]]
    repo = WorkbenchCommandRepository(conn)
    receipt = repo.get(audit["request_key"]) if receipt is None else receipt
    if receipt is None:
        fail("adoption_evidence_missing", "adoption.command_receipt")
    require(receipt["request_key"] == audit["request_key"], "adoption.receipt_request")
    result = stored(receipt["outcome_json"]) if result is None else result
    require(result.get("result") == "committed", "adoption.receipt_committed")
    require(type(result.get("data")) is dict, "adoption.receipt_data_shape")
    data = result["data"]
    require(type(data.get("official_plan")) is dict, "adoption.receipt_official_shape")
    official = data["official_plan"]
    expected = {"plan_ref": plan_ref, "version": version, "kind": "official", "baseline_ref": audit["baseline_ref"]}
    fields = ("source_run_ref",) if context == "candidate_ref" else ("source_scenario_ref", "source_draft_ref")
    require(expected.keys() <= official.keys() and set(fields) <= official.keys(), "adoption.receipt_official_fields")
    require({context, parent, "row_count"} <= data.keys(), "adoption.receipt_scope_fields")
    require(same({key: official[key] for key in expected}, expected), "adoption.receipt_official_identity")
    require((receipt["action"], receipt["context_ref"]) == (action, audit[context]), "adoption.receipt_source")
    intent = {"confirm": True, "reason": audit["reason"], "declared_operator": audit["declared_operator"]}
    recorded_intent = stored(receipt["input_json"])
    require(set(recorded_intent) == set(intent) and all(
        type(recorded_intent[key]) is type(value) and recorded_intent[key] == value
        for key, value in intent.items()
    ), "adoption.receipt_intent")
    require(data[context] == audit[context] and data[parent] == audit[parent]
            and same(data["row_count"], audit["row_count"]), "adoption.receipt_scope")
    require(all(official[key] == audit[key[len("source_"):]] for key in fields), "adoption.receipt_provenance")
    return receipt
