"""External identity mapping with the original Dashboard state/history storage; no rulings here."""

from core.infrastructure.schema_structure import SchemaStructure
from core.infrastructure.workbench_dashboard_external_schema import contract_issues, objects, orphaned_handling_receipts
from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository
from data.repositories.workbench_dashboard_source_repo import rows


class WorkbenchDashboardExternalRepository(WorkbenchDashboardRepository):
    items_table = "WorkbenchDashboardExternalItems"
    states_table = "WorkbenchDashboardExternalStates"
    history_table = "WorkbenchDashboardExternalHistory"

    def schema_state(self):
        structure = SchemaStructure(self.conn)
        if not structure.objects.keys() & set(objects()):
            return "unavailable" if orphaned_handling_receipts(self.conn) else "not_connected"
        return "unavailable" if contract_issues(self.conn, structure=structure) else "loaded"

    def schema_installed(self):
        return self.schema_state() == "loaded"

    def external_items(self, limit):
        """All external item identities ordered by item_ref; reads limit+1 rows."""
        return rows(self.conn, "SELECT * FROM WorkbenchDashboardExternalItems ORDER BY item_ref LIMIT ?", (limit + 1,))

    def shares_item_ref_with_dashboard_items(self):
        return self.conn.execute("SELECT 1 FROM WorkbenchDashboardExternalItems e JOIN WorkbenchDashboardItems i "
                                 "ON i.item_ref=e.item_ref LIMIT 1").fetchone() is not None
