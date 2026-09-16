"""Bounded, lossless evidence reads; no connection converter or metadata repair."""

import json
from typing import NoReturn

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.models.workbench_trial_codec import fingerprint

REASONS = {
    "no_adoption_baseline": "这是首版正式计划，没有上一版可供对比。",
    "adoption_evidence_missing": "旧数据或采用记录缺少必要的原始凭据，认不出采用时的正式计划是第几版，这里不显示对比。",
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


def same(left, right):
    return fingerprint(left) == fingerprint(right)


def stored(text):
    if type(text) is not str:
        fail(gap="json_storage_type")
    if len(text.encode("utf-8")) > 64 * 1024 * 1024:
        raise WorkbenchCommandRejected("query_too_large", "完整采用凭据超过 64 MB 上限。请缩小查询范围后重试。", 413)

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    value = json.loads(text, object_pairs_hook=pairs)
    require(type(value) is dict, "json_object")
    return value


def has_table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def raw_rows(conn, table, *, where="1=1", params=(), limit=None):
    def quote(name):
        return '"' + name.replace('"', '""') + '"'
    columns = [row[0] for row in conn.execute("SELECT name FROM pragma_table_info(?)", (table,))]
    if not columns:
        fail("adoption_evidence_missing", table)
    # Unary + and synthetic aliases bypass both DECLTYPES and COLNAMES conversion.
    fields = ",".join("+" + quote(name) + " AS raw_" + str(i) for i, name in enumerate(columns))
    sql = "SELECT " + fields + " FROM " + quote(table) + " WHERE " + where + " ORDER BY rowid"
    if limit is not None:
        sql += " LIMIT ?"
        params = tuple(params) + (limit + 1,)
    rows = [dict(zip(columns, row)) for row in conn.execute(sql, params)]
    if limit is not None and len(rows) > limit:
        raise WorkbenchCommandRejected("query_too_large", "完整的初始计划或对比计划超过 10000 条上限。请缩小时间范围后重试。", 413)
    return rows


def schedule_rows(conn, version):
    return raw_rows(conn, "Schedule", where="version=?", params=(version,), limit=MAX_PLAN_TASKS)


def indexed(rows, key):
    require(type(rows) is list, "snapshot_rows")
    result = {}
    for row in rows:
        require(type(row) is dict and type(row.get(key)) in (str, int), "snapshot_row_identity")
        require(row[key] not in result, "duplicate_snapshot_identity")
        result[row[key]] = row
    return result
