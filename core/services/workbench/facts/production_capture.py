"""One transaction owns lossless production originals and their business views."""

from collections.abc import Mapping
from typing import Any

from core.infrastructure.schema_structure import SchemaStructure
from core.infrastructure.sqlite_udf import receipt_revision_category
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.content import content_text, same
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_KEY
from core.services.workbench.facts.schema_compat import comparable_schema
from core.services.workbench.facts.source_revisions import PREFLIGHT_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

NON_INPUT_TABLES = frozenset(("OperationLogs", "SystemJobState", "WorkbenchSourceRevisions") + RUN_TABLES + TRIAL_TABLES + READ_MODEL_TABLES + (
    "WorkbenchDashboardStates", "WorkbenchDashboardHistory",
    "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"))


def non_input_row(table, row, receipt_columns):
    """Retain actual business receipts; omit only scheduling and interface bookkeeping."""
    if type(row) not in (list, tuple):
        return False
    if table == "sqlite_sequence":
        return len(row) == 2 and row[0] in ("OperationLogs", "SystemJobState", "SystemConfig")
    if table == "SystemConfig":
        return len(row) == 5 and row[1] == SCHEDULING_PREFERENCES_KEY
    if table != "WorkbenchCommandReceipts" or len(row) != len(receipt_columns):
        return False
    receipt = dict(zip(receipt_columns, row))
    return receipt_revision_category(receipt.get("action"), receipt.get("outcome_json")) != "production_input"


class ProductionFactsCapture:
    """Lazily capture each raw table once, within the caller's current transaction."""

    def __init__(self, conn):
        self.conn = conn
        self.execution_service: Any = None
        self.runtime_resources = None
        self.execution_facts = {}
        self.structure = SchemaStructure(conn)
        self.schema = [
            [kind, name, table, sql]
            for kind, name, table, sql in sorted(
                (kind, name, table, sql)
                for name, (kind, table, sql) in self.structure.objects.items()
            )
        ]
        self.table_names = {name for kind, name, _, _ in self.schema if kind == "table"}
        self.repo = WorkbenchPreflightFactsRepository(
            conn, present_tables=self.table_names, structure=self.structure
        )
        self.columns, self.tables, self._raw_tables, self._indexes = {}, {}, {}, {}
        self._business_tables = {}
        self._archives = {}
        self._latest_plans = {}
        self._content = None
        self._revisions = None
        self._comparable_schema = None
        self._matched_archives = {}

    @property
    def revisions(self):
        if self._revisions is None:
            self._revisions = read_source_revisions(self.conn, PREFLIGHT_SOURCE_KEYS)
        return self._revisions

    @property
    def comparable_schema(self):
        if self._comparable_schema is None:
            self._comparable_schema = comparable_schema(self.schema)
        return self._comparable_schema

    def matches_archive(self, archived):
        if not isinstance(archived, Mapping):
            return None
        cached = self._matched_archives.get(id(archived))
        if cached is not None and cached[0] is archived:
            return cached[1]
        revisions = archived.get("revisions")
        if not isinstance(revisions, Mapping) or not revisions:
            return None
        matched = (
            dict(revisions) == self.revisions
            and same(comparable_schema(archived["schema"]), self.comparable_schema)
        )
        self._matched_archives[id(archived)] = (archived, matched)
        return matched

    def seed_from_named_archive(self, archived):
        if self.matches_archive(archived) is not True:
            return
        columns = archived["columns"]
        for name, rows in archived["tables"].items():
            if name not in self.tables and name in columns:
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
                {**row, **{
                    column: convert(value.encode("utf-8") if isinstance(value, str) else value)
                    if isinstance(value, (str, bytes)) and value else None
                    for column, convert in codecs.items()
                    for value in (row[column],)
                }}
                for row in originals]
        return self._business_tables[name]

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
