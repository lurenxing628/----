"""Real adoption protects only unit_hours and preserves all old storage types."""

import inspect
import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import objects
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.part_service import PartService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_stage_apply import apply_hours
from tests.workbench.process_commands_support import hours_input, run_stage
from tests.workbench.process_quota_protection_support import (
    assert_rejected,
    file_apply,
    file_preview,
    preserved,
    snapshot,
    templates,
)
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage  # noqa: F401


def test_legacy_save_rejects_only_changed_locked_quota(locked_quota_case):
    case = locked_quota_case
    before = snapshot(case.conn)
    svc = PartService(case.conn)
    assert list(inspect.signature(svc.update_internal_hours).parameters) == ["part_no", "seq", "setup_hours", "unit_hours"]
    assert_rejected("calibration_quota_locked", lambda: svc.update_internal_hours("P1", 1, 8, 99))
    assert snapshot(case.conn) == before
    svc.update_internal_hours("P1", 1, 8, 3)
    svc.update_internal_hours("P1", 2, 4, 9)
    assert templates(case.conn)[1]["setup_hours"] == 8 and templates(case.conn)[1]["unit_hours"] == 3
    assert templates(case.conn)[2]["unit_hours"] == 9
    preserved(before, snapshot(case.conn))
    assert all(row["cw_hidden"] == b"hidden\x00\xff" for row in templates(case.conn).values())
    assert all(row["created_at"] == "2001-02-03 04:05:06" for row in templates(case.conn).values())


def test_legacy_noop_does_not_update_revision_or_blob(locked_quota_case):
    case = locked_quota_case
    before, changes = snapshot(case.conn), case.conn.total_changes
    PartService(case.conn).update_internal_hours("P1", 1, 0, 3)
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_workbench_mixed_save_is_atomic_and_setup_is_unlocked(locked_quota_case):
    case = locked_quota_case
    payload = hours_input(case.conn, "P1")
    payload["operations"][0].update(setup_hours=5, unit_hours=99)
    payload["operations"][1]["unit_hours"] = 8
    before = snapshot(case.conn)
    assert_rejected("calibration_quota_locked", lambda: run_stage(case.conn, "hours_confirm", payload,
        identity=WorkbenchProcessQueryService(case.conn).resolve(case.ref("part", "P1"))))
    assert snapshot(case.conn) == before
    payload["operations"][0]["unit_hours"] = 3
    result = run_stage(case.conn, "hours_confirm", payload,
        identity=WorkbenchProcessQueryService(case.conn).resolve(case.ref("part", "P1")))
    assert result["result"] == "committed"
    assert templates(case.conn)[1]["setup_hours"] == 5 and templates(case.conn)[1]["unit_hours"] == 3
    assert templates(case.conn)[2]["unit_hours"] == 8
    preserved(before, snapshot(case.conn), workflow=True)


def test_stage_cannot_use_old_snapshot_to_hide_a_locked_change(locked_quota_case):
    case = locked_quota_case
    facts = WorkbenchProcessQueryService(case.conn).facts()
    facts["operations"][0]["unit_hours"] = 99
    payload = hours_input(case.conn, "P1")
    payload["operations"][0]["unit_hours"] = 99
    before = snapshot(case.conn)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        assert_rejected("calibration_quota_locked", lambda: apply_hours(case.conn, payload, facts["operations"], facts["groups"]))
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("damage", ["missing", "partial", "audit", "lock", "quota"])
@pytest.mark.parametrize("entry", ["save", "preview", "apply", "stage"])
def test_schema_and_corrupt_audit_never_mean_unlocked(locked_quota_case, damage, entry):
    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
    payload = hours_input(case.conn, "P1")
    facts = WorkbenchProcessQueryService(case.conn).facts()
    case.conn.execute("PRAGMA foreign_keys=OFF")
    if damage == "missing":
        case.conn.execute("DROP TABLE WorkbenchCalibrationQuotaLocks")
        case.conn.execute("DROP TABLE WorkbenchCalibrationAdoptions")
    elif damage == "partial":
        case.conn.execute("DROP TRIGGER wb_calibration_quota_lock_origin")
    elif damage in ("audit", "lock"):
        table, trigger = (("WorkbenchCalibrationAdoptions", "wb_calibration_adoption_no_delete") if damage == "audit"
                          else ("WorkbenchCalibrationQuotaLocks", "wb_calibration_quota_lock_no_delete"))
        case.conn.execute("DROP TRIGGER " + trigger)
        case.conn.execute("DELETE FROM " + table)
        case.conn.execute(objects()[trigger])
    else:
        case.conn.execute("UPDATE PartOperations SET unit_hours=99 WHERE seq=1")
    case.conn.commit()
    case.conn.execute("PRAGMA foreign_keys=ON")
    before = snapshot(case.conn)
    callbacks = {
        "save": lambda: PartService(case.conn).update_internal_hours("P1", 1, 6, 3),
        "preview": lambda: file_preview(case.conn, {"sequence": 1, "unit_hours": 8}),
        "apply": lambda: file_apply(case.conn, rows),
        "stage": lambda: apply_hours(case.conn, payload, facts["operations"], facts["groups"]),
    }
    code = "adoption_schema_unavailable" if damage in ("missing", "partial") else "calibration_lock_corrupt"
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        assert_rejected(code, callbacks[entry])
    assert snapshot(case.conn) == before


@pytest.fixture
def raw_schema28_quota_conn():
    conn = sqlite3.connect(":memory:", detect_types=0)
    conn.row_factory = sqlite3.Row
    try:
        source = Path(__file__).parent / "fixtures" / "schema-v28.sql"
        conn.executescript(source.read_text(encoding="utf-8"))
        conn.execute("UPDATE SchemaVersion SET version=28 WHERE id=1")
        conn.commit()
        yield conn
    finally:
        conn.close()


def test_schema28_is_not_treated_as_no_locks(raw_schema28_quota_conn):
    from core.services.workbench.process_quota_protection import ProcessQuotaProtection

    conn = raw_schema28_quota_conn
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 28
    before = snapshot(conn)
    assert "WorkbenchCalibrationQuotaLocks" not in before
    assert "WorkbenchCalibrationAdoptions" not in before
    with pytest.raises(WorkbenchCommandRejected) as caught:
        ProcessQuotaProtection(conn).read_locks([])
    assert caught.value.code == "adoption_schema_unavailable" and caught.value.status == 503
    after = snapshot(conn)
    assert after == before
    for table in before:
        assert after[table] == before[table], table
