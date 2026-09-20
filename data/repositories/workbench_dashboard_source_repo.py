"""Bounded SELECTs with original SQLite storage types, including legacy dates."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_BYTES, MAX_FACT_ROWS, bounded

TABLES = {"Batches", "BatchMaterials", "Materials", "MachineDowntimes", "Machines",
          "WorkbenchDashboardDowntimeRefs", "ScheduleHistory", "Schedule", "BatchOperations"}


def rows(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    result, size = [], 0
    for row in cursor:
        size += sum(len(value) if type(value) is bytes else len(value.encode("utf-8")) if type(value) is str else 16 for value in row)
        bounded(range(size), MAX_BYTES)
        result.append(dict(zip(names, row)))
    return result


def latest_outsourcing_fact_rows(conn, ref):
    """某条外协登记最新一条确认事实（原始存储值，最多 1 行）。"""
    return rows(conn, "SELECT * FROM WorkbenchOutsourcingFacts WHERE outsourcing_ref=? ORDER BY sequence DESC LIMIT 1", (ref,))


def unknown_source_rows(conn, limit):
    """归属未填或非法的批次工序，连其工序编号、批次编号与外协登记编号，按 id 取 limit 行。"""
    return rows(conn, """SELECT r.ref AS operation_ref, b.ref AS batch_ref,
        m.outsourcing_ref, CASE WHEN 1 THEN o.op_code END AS business_code,
        CASE WHEN 1 THEN o.source END AS source
        FROM BatchOperations o
        LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
        LEFT JOIN WorkbenchEntityRefs b ON b.kind='batch' AND b.active=1 AND b.entity_key=o.batch_id
        LEFT JOIN WorkbenchOutsourcingMembers m ON m.operation_ref=r.ref
        WHERE o.source IS NULL OR o.source NOT IN ('internal','external')
        ORDER BY o.id LIMIT ?""", (limit,))


class DashboardSourceRepository:
    def __init__(self, conn):
        self.conn = conn
        self.present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def table(self, name, *, limit=MAX_FACT_ROWS):
        if name not in TABLES:
            raise ValueError("Not a dashboard source")
        if name not in self.present:
            return None
        columns = [row[1] for row in self.conn.execute('PRAGMA table_info("' + name + '")')]
        select = ",".join(f'CASE WHEN 1 THEN "{column}" END AS "{column}"' for column in columns)
        return bounded(rows(self.conn, 'SELECT ' + select + ' FROM "' + name + '" ORDER BY rowid LIMIT ?', (limit + 1,)), limit)

    def selected_raw(self, name, version):
        if name not in ("Schedule", "ScheduleHistory"):
            raise ValueError("Not a versioned source")
        columns = [row[1] for row in self.conn.execute('PRAGMA table_info("' + name + '")')]
        select = ",".join(f'CASE WHEN 1 THEN "{column}" END AS "{column}"' for column in columns)
        return bounded(rows(self.conn, 'SELECT ' + select + ' FROM "' + name + '" WHERE version=? ORDER BY rowid LIMIT ?',
                            (version, MAX_FACT_ROWS + 1)), MAX_FACT_ROWS)

    def entity_refs(self, kind, keys):
        result = {}
        keys = sorted(set(keys))
        for start in range(0, len(keys), 300):
            chunk = keys[start:start + 300]
            selected = rows(self.conn, "SELECT * FROM WorkbenchEntityRefs WHERE kind=? AND active=1 AND entity_key IN (" +
                            ",".join("?" for _ in chunk) + ")", [kind] + chunk)
            for row in selected:
                if row["entity_key"] in result:
                    raise WorkbenchCommandRejected("identity_missing", "来源关联资料重复，暂时无法评估，请联系维护人员核对。")
                result[row["entity_key"]] = row
        if set(result) != set(keys):
            raise WorkbenchCommandRejected("identity_missing", "来源关联资料缺失，暂时无法评估，请联系维护人员核对。")
        return result
