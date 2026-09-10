"""Same-number replacements cannot relink shipment evidence."""

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


@pytest.mark.parametrize("table", ["BatchOperations", "Batches", "Suppliers"])
@pytest.mark.parametrize("registered", [False, True])
def test_replace_identity_even_with_recursive_triggers_off(outsourcing_case, table, registered):
    case = outsourcing_case
    payload = case.payload()
    preview = case.preview(payload)
    original_input = preview["input"]
    ref = None
    first = None
    if registered:
        first = case.confirm(preview, key="outsourcing-before-replacement-key")
        ref = first["data"]["outsourcing_ref"]
        payload = {"outsourcing_ref": ref, "declared_operator": "Clerk", "reason": "Recheck original"}
        preview = case.preview(payload)
    other = get_connection(str(case.path))
    try:
        other.execute("PRAGMA foreign_keys=OFF")
        other.execute("PRAGMA recursive_triggers=OFF")
        condition = " WHERE op_code='XO1'" if table == "BatchOperations" else ""
        other.execute("INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table + condition)
        other.commit()
    finally:
        other.close()
    with pytest.raises(WorkbenchCommandRejected):
        case.confirm(preview)
    with pytest.raises(WorkbenchCommandRejected):
        case.preview(payload)
    if ref:
        replay = case.writer().execute(original_input, request_key="outsourcing-before-replacement-key",
                                        validate_context=lambda *_: pytest.fail("replay resolved old context"))
        assert replay["receipt_ref"] == first["receipt_ref"]
        assert replay["data"] == first["data"]
        item = case.detail(ref)
        assert item["source_state"] != "current"
        assert item["history_count"] == 1
        assert item["can_preview"] is False
        with case.reader.read_snapshot():
            assert len(case.reader.history(ref)["history"]["items"]) == 1


@pytest.mark.parametrize("change", ["operation", "part", "supplier", "batch_dates"])
def test_preview_drift_and_semantic_changes_remain_fail_closed(outsourcing_case, change):
    case = outsourcing_case
    ref = case.confirm(case.preview(case.payload()))["data"]["outsourcing_ref"]
    payload = {"outsourcing_ref": ref, "declared_operator": "Clerk", "reason": "Checked existing shipment"}
    preview = case.preview(payload)
    if change == "operation":
        case.conn.execute("UPDATE BatchOperations SET op_type_name='Different treatment' WHERE op_code='XO1'")
    elif change == "part":
        case.conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('XP2','Other part')")
        case.conn.execute("UPDATE Batches SET part_no='XP2'")
    elif change == "supplier":
        case.conn.execute("UPDATE Suppliers SET default_days=1000")
    else:
        case.conn.execute("UPDATE Batches SET due_date='2026-10-01'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected):
        case.confirm(preview)
    if change in ("operation", "part"):
        with pytest.raises(WorkbenchCommandRejected) as drift:
            case.preview(payload)
        assert drift.value.code == "identity_drift"
    else:
        # Config drift invalidates the preview, but does not rewrite existing actual dates.
        refreshed = case.preview(payload)
        assert refreshed["before"] == preview["before"]
        assert case.confirm(refreshed)["result"] == "committed"


def test_membership_sealed_no_rebinding_on_update(outsourcing_case):
    case = outsourcing_case
    ref = case.confirm(case.preview(case.payload(merged=True)))["data"]["outsourcing_ref"]
    with pytest.raises(WorkbenchCommandRejected):
        case.preview({"outsourcing_ref": ref, "target": case.payload()["target"], "declared_operator": "Clerk", "reason": "New members"})
    item = case.detail(ref)
    assert len(item["target"]["operation_refs"]) == 2
    case.conn.execute("DELETE FROM BatchOperations WHERE op_code='XO1'")
    case.conn.commit()
    assert case.detail(ref)["source_state"] == "source_unavailable"
    assert len(case.detail(ref)["target"]["operation_refs"]) == 2
