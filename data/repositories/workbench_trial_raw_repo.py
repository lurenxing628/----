"""Trial snapshots read SQLite storage values, not connection DATE converters."""

from .workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository


def _quote(name):
    if type(name) is not str or not name or "\x00" in name:
        raise ValueError("Raw SQLite column/table name is invalid")
    return '"' + name.replace('"', '""') + '"'


def _read(conn, names, source, params=(), order="", expressions=None):
    # Unary + keeps the SQLite storage class and suppresses DECLTYPES. Synthetic
    # aliases also prevent a legacy column named "x [DATE]" invoking COLNAMES.
    overrides = expressions or {}
    columns = [overrides.get(name, "+" + _quote(name)) + ' AS "trial_raw_' + str(index) + '"'
               for index, name in enumerate(names)]
    cursor = conn.execute("SELECT " + ",".join(columns) + " FROM " + source + order, params)
    return [dict(zip(names, tuple(row))) for row in cursor]


def read_raw_table(conn, name):
    quoted = _quote(name)
    names = [row[1] for row in conn.execute("PRAGMA table_info(" + quoted + ")")]
    if not names:
        raise ValueError("Required raw SQLite table has no columns: " + name)
    return names, _read(conn, names, quoted, order=" ORDER BY rowid")


class WorkbenchTrialRawPlanRepository(WorkbenchPlanCatalogRepository):
    """Keep the existing complete-plan SQL/limits, suppress only Python converters."""

    def fetchall(self, sql, params=()):
        params = () if params is None else params
        source = "(" + sql + ")"
        metadata = self.conn.execute("SELECT * FROM " + source + " LIMIT 0", params)
        names = [column[0] for column in metadata.description]
        if not names or len(set(names)) != len(names):
            raise ValueError("Raw plan projection columns must be explicit and unique")
        expressions = {}
        if "due_date" in names and "batch_id" in names:
            # The shared detail SQL casts due_date for display. A saved original
            # must instead retain the exact source value, including legacy BLOBs.
            expressions["due_date"] = ('(SELECT +"due_date" FROM "Batches" '
                                       'WHERE "Batches"."batch_id"="trial_plan"."batch_id")')
        return _read(self.conn, names, source + ' AS "trial_plan"', params, expressions=expressions)
