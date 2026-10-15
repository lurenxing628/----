"""Bounded SELECTs with original SQLite storage types, including legacy dates; no rulings here."""

from core.infrastructure.connection_guards import schema_contract_memo
from core.models.enums import SOURCE_TYPE_VALUES, SourceType, read_source_type
from core.models.workbench_dashboard import MAX_BYTES, MAX_FACT_ROWS, bounded

from .calendar_facts_repo import DOWNTIME_STATUS_SQL
from .schedule_time_sql import parse_dt_for_sql

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
        WHERE typeof(o.source)!='text' OR o.source COLLATE BINARY NOT IN ('internal','external')
        ORDER BY o.id""", select=selected, limit=limit)


class DashboardSourceRepository:
    def __init__(self, conn):
        self.conn = conn
        self.present = {name for name, (kind, _table, _sql) in schema_contract_memo(conn).structure.objects.items() if kind == "table"}

    def _select_list(self, name):
        columns = [row[1] for row in self.conn.execute("PRAGMA table_info(" + _QUOTED[name] + ")")]
        return ",".join('CASE WHEN 1 THEN "' + column + '" END AS "' + column + '"' for column in columns)

    def table(self, name, *, limit=MAX_FACT_ROWS):
        if name not in TABLES:
            raise ValueError("Not a dashboard source")
        if name not in self.present:
            return None
        return bounded(rows(self.conn, "SELECT " + self._select_list(name) + _FROM[name] + " ORDER BY rowid LIMIT ?", (limit + 1,)), limit)

    def downtime_capture(self, *, machine_ids=None, limit=MAX_FACT_ROWS):
        """Keep raw rowid order and SQLite's time/status/order facts from one SELECT."""
        if "MachineDowntimes" not in self.present:
            return None, None
        wanted = None if machine_ids is None else frozenset(machine_ids)
        self.conn.create_function("aps_calendar_machine_selected", 1,
                                  lambda key: int(wanted is None or key in wanted))
        selected = "aps_calendar_machine_selected(md.machine_id) AND " + DOWNTIME_STATUS_SQL
        private = [DOWNTIME_STATUS_SQL + " AS __calendar_admitted",
                   selected + " AS __calendar_selected",
                   "CASE WHEN " + selected + " THEN TRIM(CAST(md.start_time AS TEXT)) END AS __calendar_start",
                   "CASE WHEN " + selected + " THEN TRIM(CAST(md.end_time AS TEXT)) END AS __calendar_end"]
        for field in ("start_time", "end_time"):
            stem = "__calendar_" + field
            private.extend(("CASE typeof(md." + field + ") WHEN 'null' THEN 0 WHEN 'integer' THEN 1 "
                            "WHEN 'real' THEN 1 WHEN 'text' THEN 2 ELSE 3 END AS " + stem + "_rank",
                            "CASE WHEN typeof(md." + field + ")='text' THEN CAST(md." + field + " AS BLOB) "
                            "ELSE md." + field + " END AS " + stem + "_value"))
        cursor = None
        try:
            cursor = self.conn.execute("SELECT " + self._select_list("MachineDowntimes") + "," + ",".join(private) +
                                      " FROM MachineDowntimes md ORDER BY rowid LIMIT ?", (limit + 1,))
            names = [column[0] for column in cursor.description]
            boundary = len(names) - len(private)
            captured, prepared, size = [], [], 0
            for row in cursor:
                raw = dict(zip(names[:boundary], row[:boundary]))
                size += sum(len(value) if type(value) is bytes else len(value.encode("utf-8")) if type(value) is str else 16
                            for value in row[:boundary])
                bounded(range(size), MAX_BYTES)
                captured.append(raw)
                interval = dict(zip(names[boundary:], row[boundary:]))
                if interval.pop("__calendar_selected"):
                    start, end = parse_dt_for_sql(interval["__calendar_start"]), parse_dt_for_sql(interval["__calendar_end"])
                    interval.update(__calendar_start=start, __calendar_end=end,
                                    __calendar_valid=int(start is not None and end is not None and end > start))
                else:
                    interval["__calendar_valid"] = None
                prepared.append((raw, interval))
            bounded(captured, limit)
            return captured, prepared
        finally:
            if cursor is not None:
                cursor.close()
            self.conn.create_function("aps_calendar_machine_selected", 1, None)

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
