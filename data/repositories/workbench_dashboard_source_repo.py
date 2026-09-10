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
                    raise WorkbenchCommandRejected("identity_missing", "来源永久身份重复，未选择任意引用。")
                result[row["entity_key"]] = row
        if set(result) != set(keys):
            raise WorkbenchCommandRejected("identity_missing", "来源永久身份缺失，读取不会补建或替换。")
        return result
