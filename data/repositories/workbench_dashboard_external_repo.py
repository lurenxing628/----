"""External identity mapping with the original Dashboard state/history codec."""

from core.infrastructure.workbench_dashboard_external_schema import contract_issues, objects, orphaned_handling_receipts
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_ROWS, bounded
from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository, corrupt
from data.repositories.workbench_dashboard_source_repo import rows


class WorkbenchDashboardExternalRepository(WorkbenchDashboardRepository):
    items_table = "WorkbenchDashboardExternalItems"
    states_table = "WorkbenchDashboardExternalStates"
    history_table = "WorkbenchDashboardExternalHistory"

    def schema_state(self):
        names = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master")}
        if not names & set(objects()):
            return "unavailable" if orphaned_handling_receipts(self.conn) else "not_connected"
        return "unavailable" if contract_issues(self.conn) else "loaded"

    def require_schema(self):
        if self.schema_state() != "loaded":
            raise WorkbenchCommandRejected("dashboard_external_unavailable", "外协处置台账未安装或结构不完整，需由主线明确迁移；未补表。", 503)

    def receipt_mappings(self, refs):
        selected = bounded(rows(self.conn, "SELECT * FROM WorkbenchDashboardExternalItems ORDER BY item_ref LIMIT ?", (MAX_ROWS + 1,)))
        result = {row["outsourcing_ref"]: row for row in selected}
        if set(result) != set(refs):
            corrupt()
        if self.conn.execute("SELECT 1 FROM WorkbenchDashboardExternalItems e JOIN WorkbenchDashboardItems i ON i.item_ref=e.item_ref LIMIT 1").fetchone():
            corrupt()
        return result

    def _validate_states(self, stored):
        super()._validate_states(stored)
        for row in stored:
            source = row["origin"].get("source", {})
            members = [member[0] for member in self.conn.execute(
                "SELECT operation_ref FROM WorkbenchOutsourcingMembers WHERE outsourcing_ref=? ORDER BY operation_ref", (row["outsourcing_ref"],))]
            if source.get("outsourcing_ref") != row["outsourcing_ref"] or source.get("operation_refs") != members or not members:
                corrupt()
