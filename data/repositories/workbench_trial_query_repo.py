"""Trial and run bookkeeping tables excluded from production-facts snapshots."""

from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES

BOOKKEEPING_TABLES = frozenset(TRIAL_TABLES + RUN_TABLES) | {
    "WorkbenchCommandReceipts", "OperationLogs", "SystemJobState", "sqlite_sequence"}
BOOKKEEPING_TABLES |= {"WorkbenchDashboardStates", "WorkbenchDashboardHistory",
                       "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"}
