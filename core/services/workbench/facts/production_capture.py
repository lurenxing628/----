"""One transaction owns lossless production originals and their business views.

A saved production facts archive has one shape: ``{"columns", "tables", "revisions"}``. ``tables`` holds
exactly ``SCOPED_ARCHIVE_TABLES``, each row a list in the order of that table's ``columns``, which are the
table's current declared columns (one Schema version; an older database is refused, never migrated).
``revisions`` are the source revisions it was captured under.
"""

from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.infrastructure.schema_declaration import DeclaredTable, declared_tables, load_schema_sql
from core.infrastructure.schema_structure import SchemaStructure
from core.models.enums import (
    ADOPTION_SOURCE_KIND_VALUES,
    BATCH_OPERATION_STATUS_VALUES,
    BATCH_PRIORITY_VALUES,
    BATCH_STATUS_VALUES,
    FLAG_VALUES,
    LOCK_STATUS_VALUES,
    MACHINE_DOWNTIME_STATUS_VALUES,
    MACHINE_STATUS_VALUES,
    MERGE_MODE_VALUES,
    OP_TYPE_CATEGORY_VALUES,
    OPERATOR_STATUS_VALUES,
    PLAN_SOURCE_KIND_VALUES,
    READY_STATUS_VALUES,
    SHIFT_CYCLE_DAYS_MAX,
    SHIFT_DAY_OFFSET_MAX,
    SHIFT_PROFILE_STATUS_VALUES,
    SKILL_LEVEL_VALUES,
    SOURCE_TYPE_VALUES,
    SUPPLIER_STATUS_VALUES,
    YESNO_VALUES,
)
from core.services.scheduler.resource_pool_builder import RESOURCE_FACT_TABLES, CapturedResourceFacts
from core.services.workbench.facts.source_revisions import PREFLIGHT_SOURCE_KEYS, read_source_revisions
from core.shared.strict_parse import is_exact_positive_int, is_external_days, is_stored_number, is_stored_time_us
from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

SCOPED_ARCHIVE_FULL_TABLES = (
    "SchemaVersion",
    "ScheduleConfig",
    "Machines",
    "MachineOpTypes",
    "MachineDowntimes",
    "Operators",
    "OperatorSkill",
    "OperatorMachine",
    "WorkbenchOperatorProfiles",
    "Suppliers",
    "WorkbenchSupplierOpTypes",
    "WorkbenchSupplierProfiles",
    "OpTypes",
    "WorkbenchOpTypePolicies",
    "ResourceTeams",
    "WorkbenchMachineGroups",
    "WorkbenchMachineGroupMembers",
    "WorkCalendar",
    "OperatorCalendar",
    "WorkbenchShiftProfiles",
    "WorkbenchShiftPatternDays",
    "WorkbenchCalendarDefaults",
)

SCOPED_ARCHIVE_TABLES = frozenset(
    SCOPED_ARCHIVE_FULL_TABLES
    + (
        "WorkbenchEntityRefs",
        "Batches",
        "Parts",
        "BatchOperations",
        "WorkbenchPlanSourceRefs",
        "BatchMaterials",
        "BatchMaterialReviews",
        "BatchMaterialStages",
        "BatchMaterialArrivals",
        "BatchExternalContexts",
        "ScheduleHistory",
        "Schedule",
    )
)

CORRUPT_ARCHIVE = "Corrupt production facts archive"


def _one_of(values):
    return values.__contains__


def _null_or(admits):
    return lambda value: value is None or admits(value)


def _flag(value):
    return type(value) is int and value in FLAG_VALUES


def _integer_between(low, high):
    return lambda value: type(value) is int and low <= value <= high


def _positive_amount(value):
    return is_stored_number(value, positive=True)


def _positive_count(value):
    return is_stored_number(value, integer=True, positive=True)


# The archived cells readers consume as checked values, each with the value domain its table's CHECK is generated
# from (``enum_check``, ``flag_check``, ``integer_range_check``, ``external_days_check``, ``positive_amount_check``
# and ``positive_count_check`` take these same definitions) and the column's nullability. Columns no archive reader
# consumes stay out.
_CHECKED_CELLS = (
    ("Machines", "status", _one_of(MACHINE_STATUS_VALUES)),
    ("Operators", "status", _one_of(OPERATOR_STATUS_VALUES)),
    ("WorkbenchOperatorProfiles", "skills_declared", _flag),
    ("WorkbenchEntityRefs", "active", _flag),
    ("WorkbenchPlanSourceRefs", "kind", _one_of(PLAN_SOURCE_KIND_VALUES)),
    ("WorkbenchPlanSourceRefs", "active", _flag),
    ("MachineDowntimes", "status", _one_of(MACHINE_DOWNTIME_STATUS_VALUES)),
    ("OperatorMachine", "skill_level", _one_of(SKILL_LEVEL_VALUES)),
    ("OperatorMachine", "is_primary", _one_of(YESNO_VALUES)),
    ("OpTypes", "category", _one_of(OP_TYPE_CATEGORY_VALUES)),
    ("Suppliers", "status", _one_of(SUPPLIER_STATUS_VALUES)),
    ("Suppliers", "default_days", is_external_days),
    ("WorkCalendar", "allow_normal", _one_of(YESNO_VALUES)),
    ("WorkCalendar", "allow_urgent", _one_of(YESNO_VALUES)),
    ("OperatorCalendar", "allow_normal", _one_of(YESNO_VALUES)),
    ("OperatorCalendar", "allow_urgent", _one_of(YESNO_VALUES)),
    ("WorkbenchShiftProfiles", "status", _one_of(SHIFT_PROFILE_STATUS_VALUES)),
    ("WorkbenchShiftProfiles", "cycle_days", _integer_between(1, SHIFT_CYCLE_DAYS_MAX)),
    ("WorkbenchShiftPatternDays", "day_offset", _integer_between(0, SHIFT_DAY_OFFSET_MAX)),
    ("WorkbenchShiftPatternDays", "is_rest", _flag),
    ("Batches", "quantity", _positive_count),
    ("Batches", "priority", _one_of(BATCH_PRIORITY_VALUES)),
    ("Batches", "ready_status", _one_of(READY_STATUS_VALUES)),
    ("Batches", "status", _one_of(BATCH_STATUS_VALUES)),
    ("BatchOperations", "source", _one_of(SOURCE_TYPE_VALUES)),
    ("BatchOperations", "status", _one_of(BATCH_OPERATION_STATUS_VALUES)),
    ("BatchOperations", "ext_days", _null_or(is_external_days)),
    ("BatchExternalContexts", "merge_mode", _null_or(_one_of(MERGE_MODE_VALUES))),
    ("BatchExternalContexts", "total_days", _null_or(is_external_days)),
    ("BatchMaterials", "ready_status", _one_of(READY_STATUS_VALUES)),
    ("BatchMaterialReviews", "batch_quantity", _positive_count),
    ("BatchMaterialArrivals", "quantity", _positive_amount),
    ("ScheduleHistory", "source_kind", _one_of(ADOPTION_SOURCE_KIND_VALUES)),
    ("Schedule", "source", _one_of(SOURCE_TYPE_VALUES)),
    ("Schedule", "lock_status", _one_of(LOCK_STATUS_VALUES)),
)


def _operation_source_id(source_key):
    if type(source_key) is str and source_key.isascii() and source_key.isdigit():
        value = int(source_key)
        if str(value) == source_key:
            return value
    return None


@lru_cache(maxsize=None)
def _archived_declarations() -> Dict[str, DeclaredTable]:
    """Each archived table's current declaration; schema.sql is parsed once per process."""
    declared = declared_tables(load_schema_sql())
    return {name: declared[name] for name in SCOPED_ARCHIVE_TABLES}


@lru_cache(maxsize=None)
def archived_columns() -> Dict[str, Tuple[str, ...]]:
    """Each archived table's current declared column order."""
    return {name: table.columns for name, table in _archived_declarations().items()}


def _distinct_keys(rows, positions):
    """No two rows share a key, as SQLite holds it: a key with a NULL never collides; key cells are stored scalars."""
    seen = set()
    for row in rows:
        key = tuple(row[position] for position in positions)
        if any(cell is None for cell in key):
            continue
        if any(type(cell) not in (int, float, str) for cell in key) or key in seen:
            return False
        seen.add(key)
    return True


def _valid_revisions(revisions):
    return (type(revisions) is dict and bool(revisions)
            and all(type(key) is str and key and is_exact_positive_int(value) for key, value in revisions.items()))


def validate_production_archive(archived):
    """Admit a saved production facts archive once, at its storage boundary.

    Any other table set, column order, row shape or revision record is corrupt; a missing table is never
    read as an empty one. The JSON copy carries no table CHECK, so every cell its readers consume as a checked value
    is admitted here against its table's CHECK domain (``_CHECKED_CELLS``): machine, operator, downtime, supplier and
    shift-profile status; the active flags of entity and operation refs, the operation refs' kind and the operators'
    declared-skills flag; authorization skill level and primary flag; work-type category; calendar normal/urgent
    permissions; the shift cycle length, pattern-day offset and rest flag; batch quantity, priority, readiness and
    status;
    operation source and status; material readiness, reviewed batch quantity and arrival quantity; the official
    version's adoption kind and the official arrangement's source and lock;
    the frozen external context's merge mode; and the external cycles: ``Suppliers.default_days``, and
    ``BatchOperations.ext_days`` and ``BatchExternalContexts.total_days``, which readers add as calendar days and are
    NULL when unset. So are the
    stored microseconds its readers convert: every ``MachineDowntimes`` ``start_us < end_us`` pair, as its table CHECK
    holds, and every ``Schedule`` row's integer ``(version, op_id)`` with ``start_us <= end_us`` and its point flag
    ``is_point_event = (start_us = end_us)``, as that table's CHECKs hold (the admission baseline reads one row per
    operation and converts both, ``candidate_baseline.AdmissionBaseline.segment``).

    Readers index rows by their keys, so every table's declared primary key and unconditional UNIQUE column groups
    (``schema_declaration.declared_tables``; ``Schedule``'s ``(version, op_id)`` is one) hold here too, NULLs never
    colliding as in SQLite. Partial unique indexes bind only the rows they select; their readers check them.
    """
    if (type(archived) is not dict or archived.keys() != {"columns", "tables", "revisions"}
            or not _valid_revisions(archived["revisions"])):
        raise ValueError(CORRUPT_ARCHIVE)
    columns, tables = archived["columns"], archived["tables"]
    if type(columns) is not dict or type(tables) is not dict or columns.keys() != SCOPED_ARCHIVE_TABLES \
            or tables.keys() != SCOPED_ARCHIVE_TABLES:
        raise ValueError(CORRUPT_ARCHIVE)
    declared = archived_columns()
    for name, rows in tables.items():
        names = columns[name]
        if (type(names) is not list or tuple(names) != declared[name] or type(rows) is not list
                or any(type(row) is not list or len(row) != len(names) for row in rows)):
            raise ValueError(CORRUPT_ARCHIVE)
    downtime = declared["MachineDowntimes"]
    start, end = downtime.index("start_us"), downtime.index("end_us")
    if not all(is_stored_time_us(row[start]) and is_stored_time_us(row[end]) and row[start] < row[end]
               for row in tables["MachineDowntimes"]):
        raise ValueError(CORRUPT_ARCHIVE)
    schedule, rows = declared["Schedule"], tables["Schedule"]
    version, op, start, end, point = (schedule.index(name) for name in ("version", "op_id", "start_us", "end_us", "is_point_event"))
    if not all(type(row[version]) is int and type(row[op]) is int
               and is_stored_time_us(row[start]) and is_stored_time_us(row[end]) and row[start] <= row[end]
               and type(row[point]) is int and row[point] == int(row[start] == row[end]) for row in rows):
        raise ValueError(CORRUPT_ARCHIVE)
    for name, table in _archived_declarations().items():
        for key in table.unique_keys:
            if not _distinct_keys(tables[name], [table.columns.index(column) for column in key]):
                raise ValueError(CORRUPT_ARCHIVE)
    for name, column, admits in _CHECKED_CELLS:
        index = declared[name].index(column)
        if not all(admits(row[index]) for row in tables[name]):
            raise ValueError(CORRUPT_ARCHIVE)


def table_rows(archive, name) -> List[Dict[str, Any]]:
    """One table of an admitted archive (or of its saved calendar part), each row named by its columns."""
    columns = archive["columns"][name]
    return [dict(zip(columns, row)) for row in archive["tables"][name]]


class ArchivedTables:
    """An admitted archive's tables read by name, each decoded once; it reads like ``trial.facts.LiveTables``."""

    def __init__(self, archive):
        self._archive, self._tables = archive, {}

    def __getitem__(self, name):
        if name not in self._tables:
            self._tables[name] = table_rows(self._archive, name)
        return self._tables[name]


def _apply_sqlite_codec(convert, value):
    if value is None or value == "" or value == b"":
        return None
    if isinstance(value, str):
        return convert(value.encode("utf-8"))
    if isinstance(value, bytes):
        return convert(value)
    return value


class ProductionFactsCapture:
    """Lazily capture each raw table once, within the caller's current transaction."""

    def __init__(self, conn):
        self.conn = conn
        self.runtime_resources = None
        self.decoded_periods: Dict[str, List[Dict[str, Any]]] = {}
        self.structure = SchemaStructure(conn)
        self.table_names = {name for name, (kind, _, _) in self.structure.objects.items() if kind == "table"}
        self.repo = WorkbenchPreflightFactsRepository(conn, structure=self.structure)
        self.columns, self.tables, self._raw_tables, self._indexes = {}, {}, {}, {}
        self._business_tables = {}
        self._resource_facts = None
        self._latest_plans = {}
        self._revisions = None

    @property
    def revisions(self):
        if self._revisions is None:
            self._revisions = read_source_revisions(self.conn, PREFLIGHT_SOURCE_KEYS)
        return self._revisions

    def revisions_record(self) -> Dict[str, Any]:
        return {"revisions": self.revisions}

    def matches_admitted(self, archived):
        """Production unchanged since an admitted archive's capture."""
        return archived["revisions"] == self.revisions

    def matches_recorded(self, recorded):
        """Production unchanged since a stored ``revisions_record()``, admitted here at its storage boundary."""
        if type(recorded) is not dict or recorded.keys() != {"revisions"} or not _valid_revisions(recorded["revisions"]):
            raise ValueError(CORRUPT_ARCHIVE)
        return recorded["revisions"] == self.revisions

    def prefill_from_admitted(self, archived):
        """While production still matches an admitted archive, fill each unread whole table from it.

        Only ``SCOPED_ARCHIVE_FULL_TABLES`` are archived whole; tables this capture already read keep what it read.
        """
        if not self.matches_admitted(archived):
            return
        for name in SCOPED_ARCHIVE_FULL_TABLES:
            if name not in self.tables:
                self.columns[name] = archived["columns"][name]
                self._raw_tables[name] = archived["tables"][name]
                self.tables[name] = table_rows(archived, name)

    def _raw_table(self, name):
        self.table(name)
        return self._raw_tables[name]

    def table(self, name):
        if name not in self.tables:
            columns, rows = self.repo.capture_table(name)
            self.columns[name], self._raw_tables[name] = columns, rows
            self.tables[name] = [dict(zip(columns, row)) for row in rows]
        return self.tables[name]

    def business_table(self, name):
        """Apply the original registered SQLite codecs once, preserving the raw archive."""
        if name not in self._business_tables:
            originals = self.table(name)
            codecs = self.repo.table_converters(name)
            self._business_tables[name] = originals if not codecs else [
                {
                    **row,
                    **{
                        column: _apply_sqlite_codec(convert, row[column])
                        for column, convert in codecs.items()
                    },
                }
                for row in originals
            ]
        return self._business_tables[name]

    def resource_facts(self) -> CapturedResourceFacts:
        if self._resource_facts is None:
            self._resource_facts = CapturedResourceFacts(
                {name: self.business_table(name) for name in RESOURCE_FACT_TABLES}
            )
        return self._resource_facts

    def index(self, name, key):
        identity = name, key
        if identity not in self._indexes:
            self._indexes[identity] = {row[key]: row for row in self.table(name)}
        return self._indexes[identity]

    def latest_plan_rows(self, version):
        """One last-official projection per operation."""
        if version not in self._latest_plans:
            operations = self.index("BatchOperations", "id")
            latest = {}
            for row in self.business_table("Schedule"):
                if row["version"] > version:
                    continue
                op_id = row["op_id"]
                previous = latest.get(op_id)
                if previous is None or row["version"] > previous["version"]:
                    # Schedule.op_id references BatchOperations(id) ON DELETE CASCADE.
                    operation = operations[op_id]
                    latest[op_id] = {**row, "schedule_id": row["id"],
                                     "batch_id": operation["batch_id"], "source": operation["source"]}
            self._latest_plans[version] = {op_id: latest[op_id] for op_id in sorted(latest)}
        return self._latest_plans[version]

    def scoped_archive(
        self,
        batch_refs: Iterable[str],
        *,
        baseline_version: Optional[int] = None,
        extra_batch_ids: Iterable[str] = (),
        busy_operation_refs: Iterable[str] = (),
    ) -> Dict[str, Any]:
        selected_batch_refs = set(batch_refs)
        target_batch_ids = set(extra_batch_ids)
        busy_op_refs = set(busy_operation_refs)

        entity_refs = self.table("WorkbenchEntityRefs")
        for row in entity_refs:
            if row["active"] == 1 and row["kind"] == "batch" and row["ref"] in selected_batch_refs:
                target_batch_ids.add(row["entity_key"])

        all_ops = self.table("BatchOperations")
        plan_refs = self.table("WorkbenchPlanSourceRefs")
        ops_by_id = {row["id"]: row for row in all_ops} if (busy_op_refs or baseline_version is not None) else {}

        if busy_op_refs:
            for row in plan_refs:
                if row["kind"] == "operation" and row["active"] == 1 and row["ref"] in busy_op_refs:
                    op = ops_by_id.get(_operation_source_id(row["source_key"]))
                    if op is not None:
                        target_batch_ids.add(op["batch_id"])

        max_ver_by_op: Dict[Any, int] = {}
        if baseline_version is not None:
            for row in self.table("Schedule"):
                if row["version"] <= baseline_version and row["version"] > max_ver_by_op.get(row["op_id"], 0):
                    max_ver_by_op[row["op_id"]] = row["version"]
            for op_id in max_ver_by_op:
                op = ops_by_id.get(op_id)
                if op is not None:
                    target_batch_ids.add(op["batch_id"])

        kept_batches = [row for row in self.table("Batches") if row["batch_id"] in target_batch_ids]
        target_part_nos = {row["part_no"] for row in kept_batches}
        kept_parts = [row for row in self.table("Parts") if row["part_no"] in target_part_nos]
        kept_ops = [row for row in all_ops if row["batch_id"] in target_batch_ids]
        target_op_ids = {row["id"] for row in kept_ops}
        kept_entity_refs = [
            row
            for row in entity_refs
            if row["active"] == 1
            and (
                row["kind"] != "batch"
                or row["ref"] in selected_batch_refs
                or row["entity_key"] in target_batch_ids
            )
        ]
        kept_plan_refs = [
            row
            for row in plan_refs
            if row["kind"] == "operation"
            and row["active"] == 1
            and (_operation_source_id(row["source_key"]) in target_op_ids or row["ref"] in busy_op_refs)
        ]
        kept_materials = [row for row in self.table("BatchMaterials") if row["batch_id"] in target_batch_ids]
        target_req_ids = {row["id"] for row in kept_materials}
        kept_reviews = [row for row in self.table("BatchMaterialReviews") if row["requirement_id"] in target_req_ids]
        kept_stages = [row for row in self.table("BatchMaterialStages") if row["requirement_id"] in target_req_ids]
        kept_arrivals = [row for row in self.table("BatchMaterialArrivals") if row["requirement_id"] in target_req_ids]
        kept_ext_contexts = [row for row in self.table("BatchExternalContexts") if row["operation_id"] in target_op_ids]

        if baseline_version is not None:
            kept_schedule = [
                row
                for row in self.table("Schedule")
                if row["op_id"] in target_op_ids and row["version"] == max_ver_by_op.get(row["op_id"])
            ]
            kept_versions = {baseline_version} | {row["version"] for row in kept_schedule}
            kept_history = [row for row in self.table("ScheduleHistory") if row["version"] in kept_versions]
        else:
            kept_schedule = []
            kept_history = []

        scoped = {
            "WorkbenchEntityRefs": kept_entity_refs,
            "Batches": kept_batches,
            "Parts": kept_parts,
            "BatchOperations": kept_ops,
            "WorkbenchPlanSourceRefs": kept_plan_refs,
            "BatchMaterials": kept_materials,
            "BatchMaterialReviews": kept_reviews,
            "BatchMaterialStages": kept_stages,
            "BatchMaterialArrivals": kept_arrivals,
            "BatchExternalContexts": kept_ext_contexts,
            "ScheduleHistory": kept_history,
            "Schedule": kept_schedule,
        }
        # Without a baseline Schedule and ScheduleHistory stay unread; their (empty) tables keep the declared columns.
        for name in scoped:
            if name not in self.columns:
                self.columns[name] = list(archived_columns()[name])

        tables: Dict[str, List[Any]] = {}
        for name in sorted(SCOPED_ARCHIVE_TABLES):
            if name in scoped:
                columns = self.columns[name]
                tables[name] = [[row[column] for column in columns] for row in scoped[name]]
            else:
                tables[name] = [list(row) for row in self._raw_table(name)]

        return {
            "columns": {name: self.columns[name] for name in tables},
            "tables": tables,
            "revisions": self.revisions,
        }
