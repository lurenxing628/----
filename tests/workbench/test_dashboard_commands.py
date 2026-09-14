"""Atomic lifecycle, stable references, strict fields and no duplicate history."""

import pytest

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.dashboard_support import close_payload, follow, source_rows  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case


def test_close_reopen_keeps_original_evidence_and_risk(dashboard_case):
    case = dashboard_case
    before = source_rows(case.conn)
    item = case.item()
    closed = case.command(item, close_payload())
    assert closed["result"] == "committed" and closed["data"]["risk"]["active"] is True
    item = case.item()
    assert item["allowed_transitions"] == [] and item["handling"]["status"] == "closed"
    assert item["write_context"]["capabilities"] == {"reopen": True}
    with pytest.raises(WorkbenchCommandRejected):
        case.command(item, follow())
    reopened = case.command(item, {"reason": "Physical evidence needs second verification"}, action="reopen")
    assert reopened["data"]["handling"]["status"] == "following"
    assert reopened["data"]["handling"]["completed_at"] is None
    history = case.history(item["item_ref"])
    assert len(history) == 2
    assert history[0]["before"]["completion_evidence"] == close_payload()["completion_evidence"]
    assert history[0]["reason"] == "Physical evidence needs second verification"
    assert history[1]["source_snapshot"]["source"]["risk"]["active"] is True
    assert source_rows(case.conn) == before


def test_same_intent_replay_and_unchanged_do_not_duplicate(dashboard_case):
    case = dashboard_case
    original = case.item()
    first = case.command(original, follow(), key="dashboard-same-intent-01")
    replay = case.command(original, follow(), key="dashboard-same-intent-01")
    assert first["receipt_ref"] == replay["receipt_ref"] and replay["replayed"]
    with pytest.raises(WorkbenchCommandRejected, match="操作编号对应的内容"):
        case.command(original, follow(owner="Other"), key="dashboard-same-intent-01")
    unchanged = case.command(case.item(), follow())
    assert unchanged["result"] == "unchanged"
    assert len(case.history(original["item_ref"])) == 1


@pytest.mark.parametrize("patch", [{"remark": None}, {"remark": " "}, {"owner": None}, {"deadline": "2026-02-30"},
    {"action": None}, {"owner": 5}, {"remark": False}, {"completed_at": "2026-09-10T13:00:00"},
    {"completed_at": "2026-09-10T11:00:00Z"}, {"completion_evidence": "已完成。"}, {"completion_evidence": "done!"},
    {"evidence_reference_text": None}, {"evidence_ref": "a" * 48}])
def test_invalid_close_is_atomic(dashboard_case, patch):
    case = dashboard_case
    item = case.item()
    with pytest.raises((ValidationError, WorkbenchCommandRejected)):
        case.command(item, close_payload(**patch))
    assert not case.history(item["item_ref"])
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchDashboardStates").fetchone()[0] == 0


def test_partial_patch_preserves_fields_and_explicit_null_obeys_contract(dashboard_case):
    case = dashboard_case
    case.command(case.item(), follow())
    result = case.command(case.item(), {"target_status": "awaiting_verification", "remark": "Check again"})
    assert result["data"]["handling"]["owner"] == "Planner"
    with pytest.raises(ValidationError):
        case.command(case.item(), {"target_status": "awaiting_verification", "remark": "Check again", "owner": None})


def test_source_drift_rejects_old_context_then_keeps_closed_risk_separate(dashboard_case):
    case = dashboard_case
    item = case.item()
    case.conn.execute("UPDATE Batches SET due_date='2026-09-07'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command(item, follow())
    assert error.value.code == "stale_write"
    case.command(case.item(), close_payload())
    case.conn.execute("UPDATE Batches SET due_date='2026-09-20'")
    case.conn.commit()
    current = case.item()
    assert current["risk"]["active"] is False and current["handling"]["status"] == "closed"
    assert case.history(current["item_ref"])[0]["source_snapshot"]["source"]["risk"]["active"] is True


def test_new_official_never_retargets_old_actual_handling(dashboard_case):
    case = dashboard_case
    old = case.item("actual")
    case.command(old, follow())
    case.plan(2)
    case.conn.commit()
    items = [row for row in case.read()[0]["items"] if row["category"] == "actual"]
    previous = next(row for row in items if row["item_ref"] == old["item_ref"])
    current = next(row for row in items if row["item_ref"] != old["item_ref"])
    assert previous["risk"]["active"] is None and previous["source_state"] == "not_currently_evaluated"
    assert previous["source"]["task_ref"] == old["source"]["task_ref"]
    assert current["source"]["task_ref"] != old["source"]["task_ref"]
    assert not previous["navigation"][0]["enabled"]
