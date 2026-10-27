"""One transaction owns lossless production originals and their business views."""

from typing import Any, NoReturn

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.content import content_text
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_ACTION, SCHEDULING_PREFERENCES_KEY
from core.shared.strict_json import load_strict_json
from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

NON_INPUT_TABLES = frozenset(("OperationLogs", "SystemJobState") + RUN_TABLES + TRIAL_TABLES + READ_MODEL_TABLES + (
    "WorkbenchDashboardStates", "WorkbenchDashboardHistory",
    "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"))
NON_INPUT_RECEIPT_ACTIONS = (SCHEDULING_PREFERENCES_ACTION, "scheduling.run")
NON_INPUT_RECEIPT_PREFIXES = ("trial.", "dashboard.")


def _unreadable_outcome() -> NoReturn:
    raise ValueError("Receipt outcome is not strict JSON")


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
    action = receipt.get("action")
    if type(action) is str and (action in NON_INPUT_RECEIPT_ACTIONS
                               or action.startswith(NON_INPUT_RECEIPT_PREFIXES)):
        return True
    text = receipt.get("outcome_json")
    if type(text) is not str:
        return False
    try:
        outcome = load_strict_json(text, on_malformed=_unreadable_outcome)
    except ValueError:
        # 读不出的回执不算可省略的记账行，原样留在输入里。
        return False
    return type(outcome) is dict and outcome.get("result") == "unchanged"


class ProductionFactsCapture:
    """Lazily capture each raw table once, within the caller's current transaction."""

    def __init__(self, conn):
        self.conn = conn
        self.execution_service: Any = None
        self.runtime_resources = None
        self.execution_facts = {}
        self.schema = sorted((kind, name, table, sql)
                             for name, (kind, table, sql) in schema_contract_memo(conn).structure.objects.items())
        self.table_names = {name for kind, name, _, _ in self.schema if kind == "table"}
        self.repo = WorkbenchPreflightFactsRepository(conn, present_tables=self.table_names,
            non_input_receipt_actions=NON_INPUT_RECEIPT_ACTIONS,
            non_input_receipt_prefixes=NON_INPUT_RECEIPT_PREFIXES)
        self.columns, self.tables, self._raw_tables, self._indexes = {}, {}, {}, {}
        self.column_types, self._business_tables = {}, {}
        self._archives = {}
        self._latest_plans = {}
        self._content = None

    def table(self, name):
        if name not in self.tables:
            columns, rows = self.repo.capture_table(name)
            self.columns[name], self._raw_tables[name] = columns, rows
            self.column_types[name] = self.repo.column_types[name]
            self.tables[name] = [dict(zip(columns, row)) for row in rows]
        return self.tables[name]

    def business_table(self, name):
        """Apply the original registered SQLite codecs once, preserving the raw archive."""
        if name not in self._business_tables:
            originals = self.table(name)
            codecs, inputs = self.repo.converters[name], self.repo.codec_inputs[name]
            self._business_tables[name] = originals if not codecs else [
                {**row, **{column: convert(value) if value is not None and len(value) else None
                           for (column, convert), value in zip(codecs.items(), encoded)}}
                for row, encoded in zip(originals, inputs)]
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
            for name, rows in self._raw_tables.items():
                if name in NON_INPUT_TABLES:
                    continue
                originals = [row for row in rows if not non_input_row(name, row, receipt_columns)]
                tables[name] = ([dict(zip(self.columns[name], row)) for row in originals] if named
                                else [list(row) for row in originals])
            self._archives[named] = {"version": "production-facts-v2", "schema": self.schema,
                "columns": {name: self.columns[name] for name in tables}, "tables": tables}
        return self._archives[named]

    def content(self):
        if self._content is None:
            self._content = content_text(self.archive())
        return self._content
