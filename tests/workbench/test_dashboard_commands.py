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


def _watch_prefetch(case, monkeypatch, unrelated_commits):
    """Record whether another writer could take the write lock during each dashboard load."""
    import sqlite3

    from core.services.workbench.dashboard.service import WorkbenchDashboardService
    from tests.workbench.dashboard_support import connect

    loads, original_load, original_project = [], WorkbenchDashboardService.load, WorkbenchDashboardService.project

    def other_writer(sql=None):
        other = connect(case.path)
        other.isolation_level = None
        try:
            other.execute("PRAGMA busy_timeout=0")
            other.execute("BEGIN IMMEDIATE")
            if sql:
                other.execute(sql)
            other.execute("COMMIT" if sql else "ROLLBACK")
            return True
        except sqlite3.OperationalError:
            return False
        finally:
            other.close()

    def load(self, *args, **kwargs):
        loads.append(other_writer())
        return original_load(self, *args, **kwargs)

    def project(self, sources):
        result = original_project(self, sources)
        if not self.conn.in_transaction and len(loads) <= unrelated_commits:
            # 锁外算完、拿锁之前有人提交了一条与值班台无关的写入：库版本变了，看板内容没变。
            assert other_writer("INSERT INTO OperationLogs(log_level,module,action) VALUES ('info','test','unrelated')")
        return result

    monkeypatch.setattr(WorkbenchDashboardService, "load", load)
    monkeypatch.setattr(WorkbenchDashboardService, "project", project)
    return loads


@pytest.mark.parametrize("unrelated_commits,expected", [(0, [True]), (1, [True, True]), (2, [True, True, False])])
def test_guard_reuses_the_prefetched_dashboard_unless_the_database_changed(dashboard_case, monkeypatch, unrelated_commits, expected):
    case = dashboard_case
    item = case.item()
    loads = _watch_prefetch(case, monkeypatch, unrelated_commits)
    result = case.command(item, follow())
    assert result["result"] == "committed"
    # True：整份看板在写锁外读取，别的连接仍能拿写锁；库在拿锁前变了就回到锁外重算一次，
    # 第二次仍变才在写锁里重算（False），保证命令总能完成。
    assert loads == expected
    assert len(case.history(item["item_ref"])) == 1


def test_replay_returns_before_recomputing_the_dashboard(dashboard_case, monkeypatch):
    case = dashboard_case
    item = case.item()
    first = case.command(item, follow(), key="dashboard-replay-prefetch-01")
    loads = _watch_prefetch(case, monkeypatch, 0)
    replay = case.command(item, follow(), key="dashboard-replay-prefetch-01")
    assert replay["replayed"] and replay["receipt_ref"] == first["receipt_ref"]
    assert loads == []
