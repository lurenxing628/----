"""Exact additive metadata allowed by historical-fixture upgrades to current."""

from core.infrastructure.workbench_dashboard_external_schema import objects as dashboard_external_objects
from core.infrastructure.workbench_outsourcing_schema import workbench_outsourcing_objects
from core.infrastructure.workbench_plan_identity_write_guard import objects as guard_objects

V30_EMPTY_TABLES = (
    "WorkbenchOutsourcingReceipts", "WorkbenchOutsourcingMembers", "WorkbenchOutsourcingFacts",
)
V30_TABLES = ("WorkbenchOutsourcingOperationOrigins",) + V30_EMPTY_TABLES
V31_TABLES = ("WorkbenchDashboardExternalItems", "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory")


def missing_v30_issues():
    return ({"missing_outsourcing_schema:" + name for name in workbench_outsourcing_objects()} |
            {"missing_workbench_plan_write_guard: " + name for name in guard_objects()})


def missing_v31_issues():
    return {"missing_dashboard_external_schema:" + name for name in dashboard_external_objects()}


def assert_v31_receipt_maps_only(conn):
    """Exact receipt-to-item bijection; never infer handling from shipment facts."""
    receipts = {row[0] for row in conn.execute("SELECT outsourcing_ref FROM WorkbenchOutsourcingReceipts")}
    items = list(conn.execute("SELECT item_ref,category,outsourcing_ref FROM WorkbenchDashboardExternalItems"))
    assert len(items) == len(receipts) and {row[2] for row in items} == receipts
    refs = {row[0] for row in items}
    assert len(refs) == len(items)
    assert all(type(ref) is str and len(ref) == 48 and set(ref) <= set("0123456789abcdef") for ref in refs)
    assert all(row[1] == "external" and row[0] != row[2] for row in items)
    assert refs.isdisjoint(row[0] for row in conn.execute("SELECT item_ref FROM WorkbenchDashboardItems"))
    assert all(tuple(row) == ("text", "text", "text") for row in conn.execute(
        "SELECT typeof(item_ref),typeof(category),typeof(outsourcing_ref) FROM WorkbenchDashboardExternalItems"))
    for name in V31_TABLES[1:]:
        assert conn.execute('SELECT * FROM "' + name + '"').fetchall() == [], name
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def assert_v30_source_maps_only(conn):
    """Only permanent operation birth evidence may identify the batch instance."""
    for name in V30_EMPTY_TABLES:
        assert conn.execute('SELECT * FROM "' + name + '"').fetchall() == [], name
    births = {}
    for ref, batch in conn.execute("SELECT operation_ref,batch_ref FROM WorkbenchTemplateLineageEvents "
                                   "WHERE event_type='created' ORDER BY event_id"):
        births.setdefault(ref, batch)
    source_ids = {str(row[0]) for row in conn.execute("SELECT id FROM BatchOperations")}
    expected = {(ref, births.get(ref)) for ref, source in conn.execute(
        "SELECT ref,source_key FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")
        if source in source_ids}
    actual = [tuple(row) for row in conn.execute(
        "SELECT operation_ref,batch_ref FROM WorkbenchOutsourcingOperationOrigins")]
    assert len(actual) == len(expected) and set(actual) == expected
    assert all(tuple(row) in (("text", "text"), ("text", "null")) for row in conn.execute(
        "SELECT typeof(operation_ref),typeof(batch_ref) FROM WorkbenchOutsourcingOperationOrigins"))
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
