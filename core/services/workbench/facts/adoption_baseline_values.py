"""Bounded, lossless evidence reads; no connection converter or metadata repair."""

from typing import NoReturn

from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_json import load_strict_json
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


def raw_table_rows(rows, table):
    """A raw read returns None when the table has no columns; that is missing evidence, not a storage error."""
    if rows is None:
        fail("adoption_evidence_missing", table)
    return rows


def schedule_rows(conn, version):
    return raw_table_rows(WorkbenchPlanBaselineRepository(conn).raw_schedule_rows_by_version(version), "Schedule")


def indexed(rows, key):
    require(type(rows) is list, "snapshot_rows")
    result = {}
    for row in rows:
        require(type(row) is dict and type(row.get(key)) in (str, int), "snapshot_row_identity")
        require(row[key] not in result, "duplicate_snapshot_identity")
        result[row[key]] = row
    return result
