"""Prototype disposition, not shipment confirmation or production reporting."""

import pytest

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import DashboardQuery
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_handling_support import external_items, ledger_counts, production_storage
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import close_payload, follow
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401


def test_close_reopen_keeps_real_risk_facts_and_original_evidence(external_handling_case):
    case = external_handling_case
    ref = case.register(merged=True)
    before = production_storage(case.conn)
    summary = case.read()[0]["categories"]["external"]
    original = case.item("external")
    assert original["source"]["outsourcing_ref"] == ref
    assert original["source"]["kind"] == "outsourcing_receipt" and original["source"]["target_kind"] == "merged"
    assert len(original["source"]["operation_refs"]) == 2
    assert original["item_ref"] != ref
    case.command(original, follow())
    case.command(case.item("external"), {"target_status": "awaiting_verification", "remark": "Check dispatch evidence"})
    closed = case.command(case.item("external"), close_payload())
    current = case.item("external")
    assert closed["result"] == "committed" and current["risk"]["active"] is True
    assert current["handling"]["status"] == "closed" and current["allowed_transitions"] == []
    assert current["handling"]["evidence_verification"] == "not_verified"
    assert current["write_context"]["capabilities"] == {"reopen": True}
    after = case.read()[0]["categories"]["external"]
    assert {key: value for key, value in after.items() if key not in ("handling_count", "closed_count")} == {
        key: value for key, value in summary.items() if key not in ("handling_count", "closed_count")}
    assert after["handling_count"] == after["closed_count"] == 1
    case.command(current, {"reason": "Receiving evidence still needs verification"}, action="reopen")
    reopened = case.item("external")
    assert reopened["handling"]["status"] == "following"
    for field in ("completed_at", "completion_evidence", "evidence_reference_text", "evidence_ref"):
        assert reopened["handling"][field] is None
    history = case.history(original["item_ref"])
    assert len(history) == 4 and all(row["receipt_ref"] for row in history)
    assert history[0]["before"]["completion_evidence"] == close_payload()["completion_evidence"]
    assert history[1]["after"]["evidence_reference_text"] == close_payload()["evidence_reference_text"]
    assert production_storage(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchDashboardHistory").fetchone()[0] == 0


def test_not_yet_overdue_is_a_tracking_item_but_unregistered_is_not(external_handling_case):
    case = external_handling_case
    ref = case.register(planned="2026-09-11T12:00:00")
    items = external_items(case)
    assert len(items) == 1 and items[0]["risk"]["active"] is False
    assert items[0]["source"]["outsourcing_ref"] == ref
    summary = case.read()[0]["categories"]["external"]
    assert summary["unregistered_count"] == summary["unknown_count"] == 2 and summary["risk_count"] is None
    assert summary["known_risk_count"] == 0 and summary["handling_supported"] is True
    case.command(items[0], follow())
    result = case.read(DashboardQuery(category="external", status="open", query="Planner"))[0]
    assert result["page"]["total"] == 1


def test_return_preserves_handling_and_history_without_using_closed_as_return(external_handling_case):
    case = external_handling_case
    ref = case.register()
    item = case.item("external")
    case.command(item, close_payload())
    history = case.history(item["item_ref"])
    case.returned(ref)
    current = case.item("external")
    assert current["item_ref"] == item["item_ref"] and current["handling"]["status"] == "closed"
    assert current["risk"]["active"] is False and current["source"]["receipt"]["returned"] == "2026-09-10T10:00:00"
    assert case.history(item["item_ref"]) == history
    assert case.read()[0]["categories"]["external"]["returned_count"] == 1
    other = case.register(2, returned="2026-09-10T10:00:00", confirmedState="returned")
    assert all(row["source"]["outsourcing_ref"] != other for row in external_items(case))


def test_same_intent_replay_and_no_change_do_not_duplicate_history(external_handling_case):
    case = external_handling_case
    case.register()
    item = case.item("external")
    first = case.command(item, follow(), key="external-handling-replay-01")
    replay = case.command(item, follow(), key="external-handling-replay-01")
    assert replay["replayed"] and replay["receipt_ref"] == first["receipt_ref"]
    with pytest.raises(WorkbenchCommandRejected, match="同一请求"):
        case.command(item, follow(owner="Other"), key="external-handling-replay-01")
    result = case.command(case.item("external"), follow())
    assert result["result"] == "unchanged" and result["data"]["history_ref"] is None
    assert len(case.history(item["item_ref"])) == 1


@pytest.mark.parametrize("patch", [{"owner": None}, {"deadline": "2026-02-30"}, {"action": None}, {"remark": " "},
    {"completed_at": "2026-09-10T13:00:00"}, {"completion_evidence": "已处理"}, {"evidence_reference_text": None}, {"evidence_ref": "a" * 48}])
def test_original_dto_validation_rejects_invalid_close_atomically(external_handling_case, patch):
    case = external_handling_case
    case.register()
    before = ledger_counts(case.conn)
    with pytest.raises((ValidationError, WorkbenchCommandRejected)):
        case.command(case.item("external"), close_payload(**patch))
    assert ledger_counts(case.conn) == before


def test_fresh_context_required_after_fact_changes(external_handling_case):
    case = external_handling_case
    ref = case.register()
    old = case.item("external")
    case.command(old, follow())
    stale = case.item("external")
    case.returned(ref)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(stale, close_payload())
    assert error.value.code == "stale_write"
    case.command(case.item("external"), close_payload())
    assert len(case.history(old["item_ref"])) == 2
