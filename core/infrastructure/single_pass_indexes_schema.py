"""Performance indexes owned by the single-pass workflow migration."""

from .schema_structure import schema_objects
from .workbench_metadata_schema import canonical_sql

ADDED = {
    "idx_batch_materials_batch": "CREATE INDEX IF NOT EXISTS idx_batch_materials_batch ON BatchMaterials(batch_id)",
    "idx_batch_operations_supplier": "CREATE INDEX IF NOT EXISTS idx_batch_operations_supplier ON BatchOperations(supplier_id)",
    "idx_part_operations_supplier": "CREATE INDEX IF NOT EXISTS idx_part_operations_supplier ON PartOperations(supplier_id)",
}
REMOVED = {
    "idx_operator_machine_operator": "CREATE INDEX IF NOT EXISTS idx_operator_machine_operator ON OperatorMachine(operator_id)",
    "idx_schedule_candidate_version": "CREATE INDEX IF NOT EXISTS idx_schedule_candidate_version ON ScheduleCandidate(version)",
    "idx_schedule_candidate_selection_version": "CREATE INDEX IF NOT EXISTS idx_schedule_candidate_selection_version ON ScheduleCandidateSelection(version)",
    "idx_operation_execution_events_schedule": "CREATE INDEX IF NOT EXISTS idx_operation_execution_events_schedule ON OperationExecutionEvents(schedule_id)",
}
_DECLARED = {name: canonical_sql(sql) for name, sql in ADDED.items()}


def contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
    return ["bad_index: " + name for name, expected in _DECLARED.items()
            if name not in actual or canonical_sql(actual[name] or "") != expected]
