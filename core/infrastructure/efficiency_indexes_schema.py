"""Indexes for exact run-time ordering and operation foreign-key lookups."""

from .schema_structure import schema_objects
from .workbench_metadata_schema import canonical_sql


def run_history_sort_expressions(field):
    """Keep the query and its index on the same seconds/fraction representation."""
    return "substr(" + field + ",1,19)", "substr(" + field + " || '0000000',21,6)"


ADDED = {
    **{"idx_wb_run_" + stem + "_sort": "CREATE INDEX IF NOT EXISTS idx_wb_run_" + stem + "_sort ON WorkbenchRunJobs("
        + ",".join(run_history_sort_expressions(stem + "_at")) + ",run_ref)"
       for stem in ("accepted", "started", "finished")},
    "idx_material_stage_operation": "CREATE INDEX IF NOT EXISTS idx_material_stage_operation ON BatchMaterialStages(operation_id)",
}
_DECLARED = {name: canonical_sql(sql) for name, sql in ADDED.items()}


def contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
    return ["bad_index: " + name for name, expected in _DECLARED.items()
            if name not in actual or canonical_sql(actual[name]) != expected]
