"""Bounded, lossless evidence reads; no connection converter or metadata repair."""

import json
from typing import NoReturn

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from core.models.workbench_trial_codec import fingerprint

REASONS = {
    "no_adoption_baseline": "采用当时没有正式基线；这是首个正式计划，不能拿自身或当前正式计划作初始基线。",
    "adoption_evidence_missing": "旧库或采用记录缺少必要的原始证据，不能证明采用当时的正式基线。",
    "adoption_source_archived": "采用的原运行、场景或草稿已归档或移除，不能完整核验原始快照。",
    "adoption_snapshot_invalid": "采用审计、回执或原始快照损坏或不一致，未改用当前数据。",
    "adoption_baseline_archived": "采用时的原正式基线或原任务已归档或移除，不能完整对照。",
    "adoption_reference_invalid": "采用时的原正式基线、工序、任务或资源引用已失效，未绑定当前同号对象。",
    "adoption_baseline_drift": "原正式基线行已不同于采用当时记录的完整原值，不能冒充初始计划。",
    "adoption_plan_drift": "所选正式计划的完整安排已不同于原采用来源，不能确认原采用对照。",
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
        raise WorkbenchCommandRejected("query_too_large", "完整采用证据超过64 MiB上限，未截断。", 413)

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
        raise WorkbenchCommandRejected("query_too_large", "完整采用基线或计划超过10000条上限，未按可见范围截断。", 413)
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
