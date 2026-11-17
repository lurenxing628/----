"""Bounded SELECTs with original SQLite storage types."""

import json

from core.infrastructure.schema_probe import table_columns
from core.models.workbench_dashboard import MAX_FACT_ROWS, bounded

TABLES = {"SchemaVersion", "BatchMaterialReviews", "BatchMaterialArrivals", "Batches", "BatchMaterials", "Materials", "MachineDowntimes", "Machines",
          "WorkbenchDashboardDowntimeRefs"}
# Fixed identifier expansion: caller-supplied names only select an entry, never reach SQL text.
_FROM = {name: ' FROM "' + name + '"' for name in TABLES}
_WHERE_COLUMNS = {col: '"' + col + '"' for col in ("batch_id", "machine_id", "material_id", "requirement_id", "source_id")}


def rows(conn, sql, params=(), *, limit=None):
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    result = []
    for row in cursor:
        result.append(dict(zip(names, row)))
        if limit is not None and len(result) >= limit:
            break
    return bounded(result, MAX_FACT_ROWS) if limit is None else result


class DashboardSourceRepository:
    def __init__(self, conn):
        self.conn = conn
        self._columns = {}

    def _select_list(self, name):
        columns = self._columns.get(name)
        if columns is None:
            columns = self._columns[name] = table_columns(self.conn, name)
        return ",".join('+"' + column + '" AS "' + column + '"' for column in columns)

    def table(self, name):
        return rows(self.conn, "SELECT " + self._select_list(name) + _FROM[name] + " ORDER BY rowid LIMIT ?", (MAX_FACT_ROWS + 1,))

    def point_rows(self, name, column, value):
        """The row a unique key names, as a list of at most one."""
        sql = "SELECT " + self._select_list(name) + _FROM[name] + " WHERE " + _WHERE_COLUMNS[column] + "=?"
        return rows(self.conn, sql, (value,), limit=1)

    def child_rows(self, name, column, value):
        """Every row referencing value, in rowid order, under the capture bound."""
        sql = "SELECT " + self._select_list(name) + _FROM[name] + " WHERE " + _WHERE_COLUMNS[column] + "=? ORDER BY rowid LIMIT ?"
        return rows(self.conn, sql, (value, MAX_FACT_ROWS + 1))

    def rows_in(self, name, column, keys):
        # 空键集不发查询：带 ORDER BY rowid 时规划器对停机引用表走整表扫描，键集为空也照扫。
        if not keys:
            return []
        sql = (
            "SELECT " + self._select_list(name) + _FROM[name]
            + " WHERE " + _WHERE_COLUMNS[column] + " IN (SELECT value FROM json_each(?)) ORDER BY rowid LIMIT ?"
        )
        return rows(self.conn, sql, (json.dumps(list(keys)), MAX_FACT_ROWS + 1))

    def batch_exists(self, batch_id):
        return self.conn.execute('SELECT 1 FROM "Batches" WHERE batch_id=? LIMIT 1', (batch_id,)).fetchone() is not None
