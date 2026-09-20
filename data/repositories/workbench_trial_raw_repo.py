"""Trial snapshots read SQLite storage values, not connection DATE converters."""

from .workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository


def _quote(name):
    if type(name) is not str or not name or "\x00" in name:
        raise ValueError("Raw SQLite column/table name is invalid")
    return '"' + name.replace('"', '""') + '"'


class WorkbenchTrialRawPlanRepository(WorkbenchPlanCatalogRepository):
    """Keep the existing complete-plan SQL/limits, suppress only Python converters."""

    def fetchall(self, sql, params=()):
        params = () if params is None else params
        subquery = "(" + sql + ")"
        metadata = self.conn.execute("SELECT * FROM " + subquery + " LIMIT 0", params)
        names = [column[0] for column in metadata.description]
        if not names or len(set(names)) != len(names):
            raise ValueError("Raw plan projection columns must be explicit and unique")
        expressions = {}
        if "due_date" in names and "batch_id" in names:
            # The shared detail SQL casts due_date for display. A saved original
            # must instead retain the exact source value, including legacy BLOBs.
            expressions["due_date"] = ('(SELECT +"due_date" FROM "Batches" '
                                       'WHERE "Batches"."batch_id"="trial_plan"."batch_id")')
        # Unary + keeps the SQLite storage class and suppresses DECLTYPES. Synthetic
        # aliases also prevent a legacy column named "x [DATE]" invoking COLNAMES.
        columns = [expressions.get(name, "+" + _quote(name)) + ' AS "trial_raw_' + str(index) + '"'
                   for index, name in enumerate(names)]
        cursor = self.conn.execute("SELECT " + ",".join(columns) + " FROM " + subquery + ' AS "trial_plan"', params)
        return [dict(zip(names, tuple(row))) for row in cursor]
