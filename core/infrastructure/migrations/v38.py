"""Remove duplicate indexes and repair the recognized whitespace values missed by v4."""

from core.models import enums

from ..migration_common import MigrationOutcome
from ..schema_structure import SchemaStructure
from ..transaction import TransactionManager
from ..workbench_resource_schema import resource_objects, workbench_resource_contract_issues
from .v4_sanitizers import normalize_enum_text

_DUPLICATE_INDEXES = (
    ("idx_operator_calendar_operator_date", "OperatorCalendar", ("operator_id", "date"), 0),
    ("idx_schedule_adjustment_scenario_draft", "ScheduleAdjustmentScenario", ("source_draft_id",), 0),
    ("idx_operation_execution_events_op_revision_unique", "OperationExecutionEvents",
     ("schedule_version", "schedule_id", "op_id", "batch_id", "source_table", "effective_plan_role", "previous_state_revision"), 1),
)
_ENUM_FIELDS = (
    ("Batches", "priority", enums.BATCH_PRIORITY_VALUES),
    ("Batches", "ready_status", enums.READY_STATUS_VALUES),
    ("Batches", "status", enums.BATCH_STATUS_VALUES),
    ("BatchOperations", "source", enums.SOURCE_TYPE_VALUES),
    ("BatchOperations", "status", enums.BATCH_OPERATION_STATUS_VALUES),
    ("Schedule", "lock_status", enums.LOCK_STATUS_VALUES),
    ("BatchMaterials", "ready_status", enums.READY_STATUS_VALUES),
    ("Parts", "route_parsed", enums.YESNO_VALUES),
    ("OpTypes", "category", tuple(item.value for item in enums.OpTypeCategory)),
    ("PartOperations", "source", enums.SOURCE_TYPE_VALUES),
    ("PartOperations", "status", enums.PART_OPERATION_STATUS_VALUES),
    ("ExternalGroups", "merge_mode", enums.MERGE_MODE_VALUES),
    ("OperatorMachine", "skill_level", tuple(item.value for item in enums.SkillLevel)),
    ("OperatorMachine", "is_primary", enums.YESNO_VALUES),
    ("WorkCalendar", "day_type", enums.CALENDAR_DAY_TYPE_STORED_VALUES),
    ("WorkCalendar", "allow_normal", enums.YESNO_VALUES),
    ("WorkCalendar", "allow_urgent", enums.YESNO_VALUES),
    ("OperatorCalendar", "day_type", enums.CALENDAR_DAY_TYPE_STORED_VALUES),
    ("OperatorCalendar", "allow_normal", enums.YESNO_VALUES),
    ("OperatorCalendar", "allow_urgent", enums.YESNO_VALUES),
    ("Machines", "status", enums.MACHINE_STATUS_VALUES),
    ("Operators", "status", enums.OPERATOR_STATUS_VALUES),
    ("Suppliers", "status", enums.SUPPLIER_STATUS_VALUES),
    ("Materials", "status", enums.MATERIAL_STATUS_VALUES),
    ("MachineDowntimes", "scope_type", enums.DOWNTIME_SCOPE_TYPE_VALUES),
    ("MachineDowntimes", "status", enums.MACHINE_DOWNTIME_STATUS_VALUES),
)


def _retained_unique_indexes(structure, name, table, columns):
    # A real table UNIQUE/PK survives; no automatic index name is assumed.
    indexes = structure.index_list(table)
    retained = [row for row in indexes if row[1] != name and row[2] and row[3] in ("u", "pk") and not row[4]
                and tuple(col[2] for col in structure.index_info(row[1])) == columns]
    if not retained:
        raise RuntimeError("Duplicate-index migration requires the retained unique key: " + table)
    return indexes, retained


def _index_key(structure, name):
    return tuple(tuple(col[2:5]) for col in structure.index_xinfo(name) if col[5])


def _recognized_duplicate(structure, definition, indexes, retained):
    name, table, columns, unique = definition
    if name not in structure.objects:
        return False
    index = next((row for row in indexes if row[1] == name), None)
    if (structure.index_table(name) != table or index is None or index[2] != unique or index[4]
            or tuple(col[2] for col in structure.index_info(name)) != columns):
        raise RuntimeError("Cannot remove an unrecognized index: " + name)
    keys = _index_key(structure, name)
    if not any(keys == _index_key(structure, row[1]) for row in retained):
        raise RuntimeError("Cannot remove an index with different key semantics: " + name)
    return True


def _drop_duplicate_indexes(conn):
    structure = SchemaStructure(conn)
    removals = []
    for definition in _DUPLICATE_INDEXES:
        name, table, columns, _unique = definition
        indexes, retained = _retained_unique_indexes(structure, name, table, columns)
        if _recognized_duplicate(structure, definition, indexes, retained):
            removals.append(name)
    for name in removals:
        conn.execute('DROP INDEX "' + name + '"')


def _repair_whitespace(conn):
    issues = workbench_resource_contract_issues(conn)
    if issues:
        raise RuntimeError("Whitespace migration requires complete resource metadata: " + "; ".join(issues))
    definitions = resource_objects()
    reason_triggers = ("wb_resource_operator_status_reason", "wb_resource_supplier_status_reason")
    # Normalizing encoding is not a status transition. Preserve reasons at their
    # writer boundary, while identity/history triggers still record real changes.
    for name in reason_triggers:
        conn.execute('DROP TRIGGER "' + name + '"')
    for table, field, values in _ENUM_FIELDS:
        normalize_enum_text(conn, table=table, field=field, allowed_values=values)
    for name in reason_triggers:
        conn.execute(definitions[name])


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        _drop_duplicate_indexes(conn)
        _repair_whitespace(conn)
    return MigrationOutcome.APPLIED
