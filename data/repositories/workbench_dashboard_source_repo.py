"""Bounded SELECTs with original SQLite storage types, including legacy dates; no rulings here."""

from core.models.enums import SOURCE_TYPE_VALUES, SourceType, read_source_type
from core.models.workbench_dashboard import MAX_BYTES, MAX_FACT_ROWS, bounded

TABLES = {"SchemaVersion", "BatchMaterialReviews", "BatchMaterialArrivals", "Batches", "BatchMaterials", "Materials", "MachineDowntimes", "Machines",
          "WorkbenchDashboardDowntimeRefs", "ScheduleHistory", "Schedule", "BatchOperations"}
VERSIONED_TABLES = {"Schedule", "ScheduleHistory"}
# Fixed identifier expansion: caller-supplied names only select an entry, never reach SQL text.
_QUOTED = {name: '"' + name + '"' for name in TABLES}
_FROM = {name: ' FROM "' + name + '"' for name in TABLES}


def rows(conn, sql, params=(), *, select=None, limit=None):
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    result, size = [], 0
    for row in cursor:
        item = dict(zip(names, row))
        if select is not None and not select(item):
            continue
        size += sum(len(value) if type(value) is bytes else len(value.encode("utf-8")) if type(value) is str else 16 for value in row)
        bounded(range(size), MAX_BYTES)
        result.append(item)
        if limit is not None and len(result) >= limit:
            break
    return result


def latest_outsourcing_fact_rows(conn, ref):
    """某条外协登记最新一条确认事实（原始存储值，最多 1 行）。"""
    return rows(conn, "SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT 1", (ref,))


def source_gap_rows(conn, limit):
    """Stream unknown sources and legacy external values outside canonical registration reads."""
    def selected(row):
        row["source_kind"] = read_source_type(row["source"])
        return row["source_kind"] not in SOURCE_TYPE_VALUES or (
            row["source_kind"] == SourceType.EXTERNAL.value and row["source"] != SourceType.EXTERNAL.value)

    return rows(conn, """SELECT r.ref AS operation_ref, b.ref AS batch_ref,
        m.outsourcing_ref, CASE WHEN 1 THEN o.op_code END AS business_code,
        CASE WHEN 1 THEN o.source END AS source
        FROM BatchOperations o
        LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
        LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
        LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
        ORDER BY o.id""", select=selected, limit=limit)


class DashboardSourceRepository:
    def __init__(self, conn):
        self.conn = conn
        self.present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def _select_list(self, name):
        columns = [row[1] for row in self.conn.execute("PRAGMA table_info(" + _QUOTED[name] + ")")]
        return ",".join('CASE WHEN 1 THEN "' + column + '" END AS "' + column + '"' for column in columns)

    def table(self, name, *, limit=MAX_FACT_ROWS):
        if name not in TABLES:
            raise ValueError("Not a dashboard source")
        if name not in self.present:
            return None
        return bounded(rows(self.conn, "SELECT " + self._select_list(name) + _FROM[name] + " ORDER BY rowid LIMIT ?", (limit + 1,)), limit)

    def selected_raw(self, name, version):
        if name not in VERSIONED_TABLES:
            raise ValueError("Not a versioned source")
        return bounded(rows(self.conn, "SELECT " + self._select_list(name) + _FROM[name] + " WHERE version=? ORDER BY rowid LIMIT ?",
                            (version, MAX_FACT_ROWS + 1)), MAX_FACT_ROWS)

    def entity_ref_rows(self, kind, keys):
        """Active WorkbenchEntityRefs rows for the keys, in key order; duplicates are returned as-is."""
        result = []
        keys = sorted(set(keys))
        for start in range(0, len(keys), 300):
            chunk = keys[start:start + 300]
            result.extend(rows(self.conn, "SELECT * FROM WorkbenchEntityRefs WHERE kind=? AND active=1 AND entity_key IN (" +
                               ",".join("?" for _ in chunk) + ")", [kind] + chunk))
        return result
