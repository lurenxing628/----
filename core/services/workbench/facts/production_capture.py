"""One transaction owns lossless production originals and their business views."""

from collections.abc import Mapping
from typing import Any, Dict, List

from core.infrastructure.schema_structure import SchemaStructure, declared_schema_table_columns
from core.infrastructure.sqlite_udf import receipt_revision_category
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.content import content_text, same
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_KEY
from core.services.scheduler.resource_pool_builder import RESOURCE_FACT_TABLES, CapturedResourceFacts
from core.services.workbench.facts.source_revisions import PREFLIGHT_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

NON_INPUT_TABLES = frozenset(("OperationLogs", "SystemJobState", "WorkbenchSourceRevisions") + RUN_TABLES + TRIAL_TABLES + READ_MODEL_TABLES + (
    "WorkbenchDashboardStates", "WorkbenchDashboardHistory",
    "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"))


CORRUPT_ARCHIVE = "Corrupt production facts archive"


def archived_table_valid(columns, rows, *, named=False):
    """One saved table: its own unique non-empty column names, rows named or positional by them.

    ``named`` archives (a trial admission's) hold only named rows.
    """
    if (type(columns) is not list or not columns or any(type(column) is not str or not column for column in columns)
            or len(set(columns)) != len(columns) or type(rows) is not list):
        return False
    names = frozenset(columns)
    return all((type(row) is dict and row.keys() == names)
               or (not named and type(row) is list and len(row) == len(columns)) for row in rows)


def validate_production_archive(archived, *, named=False):
    """Admit a saved production facts archive once and return its input table names.

    The current contract always records schema, columns, tables and revisions; columns and tables hold
    exactly the schema's input tables and their declared column sequences. A missing table is corrupt,
    never an empty one. ``named`` admits an archive written by ``archive(named=True)``, whose rows must
    all be named.
    """
    if not isinstance(archived, Mapping):
        raise ValueError(CORRUPT_ARCHIVE)
    schema, columns, tables, revisions = (archived.get(key) for key in ("schema", "columns", "tables", "revisions"))
    if (not isinstance(schema, list) or not isinstance(columns, Mapping) or not isinstance(tables, Mapping)
            or not isinstance(revisions, Mapping) or not revisions
            or any(type(k) is not str or not k or type(v) is not int or v < 1 for k, v in revisions.items())):
        raise ValueError(CORRUPT_ARCHIVE)
    try:
        declared = declared_schema_table_columns(schema, excluded_tables=NON_INPUT_TABLES)
    except ValueError as exc:
        raise ValueError(CORRUPT_ARCHIVE) from exc
    expected = set(declared)
    if (set(columns) != expected or set(tables) != expected
            or any(not archived_table_valid(columns[name], tables[name], named=named)
                   or tuple(columns[name]) != declared[name]
                   for name in expected)):
        raise ValueError(CORRUPT_ARCHIVE)
    return expected


def non_input_row(table, row, receipt_columns):
    """Retain actual business receipts; omit only scheduling and interface bookkeeping."""
    if table == "sqlite_sequence":
        return row[0] in ("OperationLogs", "SystemJobState", "SystemConfig")
    if table == "SystemConfig":
        return row[1] == SCHEDULING_PREFERENCES_KEY
    if table != "WorkbenchCommandReceipts":
        return False
    receipt = dict(zip(receipt_columns, row))
    return receipt_revision_category(receipt["action"], receipt["outcome_json"]) != "production_input"


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
        self.schema = [
            [kind, name, table, sql]
            for kind, name, table, sql in sorted(
                (kind, name, table, sql)
                for name, (kind, table, sql) in self.structure.objects.items()
            )
        ]
        self.table_names = {name for kind, name, _, _ in self.schema if kind == "table"}
        self.repo = WorkbenchPreflightFactsRepository(conn, structure=self.structure)
        self.columns, self.tables, self._raw_tables, self._indexes = {}, {}, {}, {}
        self._business_tables = {}
        self._resource_facts = None
        self._archives = {}
        self._latest_plans = {}
        self._content = None
        self._revisions = None
        self._matched_archives = {}

    @property
    def revisions(self):
        if self._revisions is None:
            self._revisions = read_source_revisions(self.conn, PREFLIGHT_SOURCE_KEYS)
        return self._revisions

    def matches_archive(self, archived):
        """Admit a stored archive at its first entry, then compare it with this transaction's production."""
        validate_production_archive(archived)
        return self.matches_admitted(archived)

    def matches_admitted(self, archived):
        """Compare an archive its caller already admitted, once per archive object."""
        cached = self._matched_archives.get(id(archived))
        if cached is not None and cached[0] is archived:
            return cached[1]
        matched = same(archived["schema"], self.schema) and archived["revisions"] == self.revisions
        self._matched_archives[id(archived)] = (archived, matched)
        return matched

    def matches_recorded(self, recorded):
        """Production unchanged since an admitted archive's capture: its source revisions under its schema.

        ``recorded`` needs only that archive's ``revisions`` and ``schema``.
        """
        return recorded["revisions"] == self.revisions and same(recorded["schema"], self.schema)

    def seed_from_admitted_archive(self, archived):
        """Seed from a named archive its caller admitted with ``validate_production_archive(named=True)``."""
        if not self.matches_admitted(archived):
            return
        columns = archived["columns"]
        for name, rows in archived["tables"].items():
            if name not in self.tables:
                self.columns[name] = list(columns[name])
                self.tables[name] = list(rows)
        self._archives[True] = archived

    def _raw_table(self, name):
        if name not in self._raw_tables:
            if name not in self.tables:
                self.table(name)
            else:
                cols = self.columns[name]
                self._raw_tables[name] = [tuple(row[col] for col in cols) for row in self.tables[name]]
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

    def rows_for_ids(self, name, ids):
        indexed = self.index(name, "id")
        return {key: indexed[key] for key in ids if key in indexed}

    def latest_plan_rows(self, version):
        """One last-official projection; preserve duplicate identities as conflicts."""
        if version not in self._latest_plans:
            from core.services.scheduler.run.schedule_execution_resource_facts import execution_conflict

            operations = self.index("BatchOperations", "id")
            latest, duplicates = {}, set()
            for row in self.business_table("Schedule"):
                if row["version"] > version:
                    continue
                op_id = row["op_id"]
                previous = latest.get(op_id)
                if previous is None or row["version"] > previous["version"]:
                    operation = operations.get(op_id, {})
                    latest[op_id] = {**row, "schedule_id": row["id"],
                                     "batch_id": operation.get("batch_id"), "source": operation.get("source")}
                    duplicates.discard(op_id)
                elif row["version"] == previous["version"]:
                    duplicates.add(op_id)
            if duplicates:
                raise execution_conflict("duplicate_previous_schedule_rows")
            self._latest_plans[version] = {op_id: latest[op_id] for op_id in sorted(latest)}
        return self._latest_plans[version]

    def archive(self, *, named=False):
        if named not in self._archives:
            for kind, name, _, _ in self.schema:
                if kind == "table" and name not in NON_INPUT_TABLES:
                    self.table(name)
            receipt_columns = self.columns.get("WorkbenchCommandReceipts", [])
            tables = {}
            for name in list(self.tables):
                if name in NON_INPUT_TABLES:
                    continue
                rows = self._raw_table(name)
                originals = [row for row in rows if not non_input_row(name, row, receipt_columns)]
                tables[name] = ([dict(zip(self.columns[name], row)) for row in originals] if named
                                else [list(row) for row in originals])
            self._archives[named] = {
                "version": "production-facts-v2",
                "schema": self.schema,
                "columns": {name: self.columns[name] for name in tables},
                "tables": tables,
                "revisions": dict(self.revisions),
            }
        return self._archives[named]

    def content(self):
        if self._content is None:
            self._content = content_text(self.archive())
        return self._content
