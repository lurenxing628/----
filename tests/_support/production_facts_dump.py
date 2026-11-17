"""Business production facts of one database, for "this action left production unchanged" assertions.

Every table except scheduling, trial, history and interface bookkeeping, read through the same lossless
capture a run archive uses. The scheduling-preference row, bookkeeping sequence counters and receipts that
are not production input are interface bookkeeping as well.
"""

from core.infrastructure.sqlite_udf import receipt_revision_category
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_history_schema import HISTORY_TABLES
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_KEY
from core.services.workbench.facts.production_capture import ProductionFactsCapture

BOOKKEEPING_TABLES = frozenset(
    ("OperationLogs", "SystemJobState", "WorkbenchSourceRevisions", "OperationExecutionStates",
     "WorkbenchDashboardStates", "WorkbenchDashboardHistory")
    + RUN_TABLES + TRIAL_TABLES + READ_MODEL_TABLES + HISTORY_TABLES
)


def _business_row(table, row):
    if table == "sqlite_sequence":
        return row["name"] not in ("OperationLogs", "SystemJobState", "SystemConfig")
    if table == "SystemConfig":
        return row["config_key"] != SCHEDULING_PREFERENCES_KEY
    if table == "WorkbenchCommandReceipts":
        return receipt_revision_category(row["action"], row["outcome_json"]) == "production_input"
    return True


def production_facts(conn):
    """``{table: original rows}`` of every business table, read in one transaction of ``conn``."""
    with TransactionManager(conn).transaction():
        capture = ProductionFactsCapture(conn)
        return {name: [row for row in capture.table(name) if _business_row(name, row)]
                for name in sorted(capture.table_names - BOOKKEEPING_TABLES)}
