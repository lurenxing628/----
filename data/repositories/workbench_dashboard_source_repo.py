"""Bounded SELECTs with original SQLite storage types, including legacy dates; no rulings here."""

from core.infrastructure.connection_guards import schema_contract_memo
from core.models.enums import SOURCE_TYPE_VALUES, SourceType, read_source_type
from core.models.workbench_dashboard import MAX_FACT_ROWS, MAX_ROWS, bounded

from .calendar_facts_repo import DOWNTIME_STATUS_SQL
from .schedule_time_sql import parse_dt_for_sql

TABLES = {"SchemaVersion", "BatchMaterialReviews", "BatchMaterialArrivals", "Batches", "BatchMaterials", "Materials", "MachineDowntimes", "Machines",
          "WorkbenchDashboardDowntimeRefs"}
# Fixed identifier expansion: caller-supplied names only select an entry, never reach SQL text.
_FROM = {name: ' FROM "' + name + '"' for name in TABLES}


def rows(conn, sql, params=(), *, select=None, limit=None):
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    result = []
    for row in cursor:
        item = dict(zip(names, row))
        if select is not None and not select(item):
            continue
        result.append(item)
        if limit is not None and len(result) >= limit:
            break
    return bounded(result, MAX_FACT_ROWS if limit is None else max(limit, MAX_ROWS))


def source_gap_rows(conn, limit):
    """Stream unknown sources and legacy external values outside canonical registration reads."""
    def selected(row):
        row["source_kind"] = read_source_type(row["source"])
        return row["source_kind"] not in SOURCE_TYPE_VALUES or (
            row["source_kind"] == SourceType.EXTERNAL.value and row["source"] != SourceType.EXTERNAL.value)

    return rows(conn, """SELECT r.ref AS operation_ref, b.ref AS batch_ref,
        m.outsourcing_ref, +o.op_code AS business_code,
        +o.source AS source
        FROM BatchOperations o
        LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
        LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
        LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
        WHERE typeof(o.source)!='text' OR o.source COLLATE BINARY NOT IN ('internal','external')
        ORDER BY o.id""", select=selected, limit=limit)


class DashboardSourceRepository:
    def __init__(self, conn):
        self.conn = conn
        self.structure = schema_contract_memo(conn).structure

    def _select_list(self, name):
        columns = [row[1] for row in self.structure.table_info(name)]
        return ",".join('+"' + column + '" AS "' + column + '"' for column in columns)

    def table(self, name):
        return bounded(rows(self.conn, "SELECT " + self._select_list(name) + _FROM[name] + " ORDER BY rowid LIMIT ?", (MAX_FACT_ROWS + 1,)), MAX_FACT_ROWS)

    def downtime_capture(self, *, machine_ids):
        """Keep raw rowid order and SQLite's time/status/order facts from one SELECT."""
        wanted = frozenset(machine_ids)
        self.conn.create_function("aps_calendar_machine_selected", 1, lambda key: int(key in wanted))
        selected = "aps_calendar_machine_selected(md.machine_id) AND " + DOWNTIME_STATUS_SQL
        private = [DOWNTIME_STATUS_SQL + " AS __calendar_admitted",
                   selected + " AS __calendar_selected",
                   "CASE WHEN " + selected + " THEN TRIM(CAST(md.start_time AS TEXT)) END AS __calendar_start",
                   "CASE WHEN " + selected + " THEN TRIM(CAST(md.end_time AS TEXT)) END AS __calendar_end"]
        cursor = None
        try:
            cursor = self.conn.execute("SELECT " + self._select_list("MachineDowntimes") + "," + ",".join(private) +
                                      " FROM MachineDowntimes md ORDER BY rowid LIMIT ?", (MAX_FACT_ROWS + 1,))
            names = [column[0] for column in cursor.description]
            boundary = len(names) - len(private)
            captured, prepared = [], []
            for row in cursor:
                raw = dict(zip(names[:boundary], row[:boundary]))
                captured.append(raw)
                interval = dict(zip(names[boundary:], row[boundary:]))
                if interval.pop("__calendar_selected"):
                    start, end = parse_dt_for_sql(interval["__calendar_start"]), parse_dt_for_sql(interval["__calendar_end"])
                    interval.update(__calendar_start=start, __calendar_end=end,
                                    __calendar_valid=int(start is not None and end is not None and end > start))
                else:
                    interval["__calendar_valid"] = None
                prepared.append((raw, interval))
            bounded(captured, MAX_FACT_ROWS)
            return captured, prepared
        finally:
            if cursor is not None:
                cursor.close()
            self.conn.create_function("aps_calendar_machine_selected", 1, None)

    def entity_ref_rows(self, kind, keys):
        """Active WorkbenchEntityRefs rows for the keys, in key order; duplicates are returned as-is."""
        result = []
        for start in range(0, len(keys), 300):
            chunk = keys[start:start + 300]
            result.extend(rows(self.conn, "SELECT * FROM WorkbenchEntityRefs WHERE kind=? AND active=1 AND entity_key IN (" +
                               ",".join("?" for _ in chunk) + ")", [kind] + chunk))
        return result
