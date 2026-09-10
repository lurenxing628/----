"""Two-connection adoption races, rollback and no visible half-applied imports."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from core.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.process.part_operation_hours_excel_import_service import PartOperationHoursExcelImportService
from core.services.process.part_service import PartService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_stage_apply import apply_hours
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_support import INTENT, KEY, service, token
from tests.workbench.process_commands_support import hours_input, run_stage
from tests.workbench.process_quota_protection_support import (
    connect,
    file_apply,
    file_preview,
    legacy_preview,
    snapshot,
    templates,
)
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage  # noqa: F401


@pytest.mark.parametrize("entry", ["save", "file", "legacy", "stage"])
def test_waiting_writer_rechecks_committed_adoption_under_its_write_lock(quota_case, monkeypatch, entry):
    case = quota_case
    case.conn.execute("PRAGMA journal_mode=WAL")
    file_rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
    legacy_rows = legacy_preview(case.conn, {"工序": 1, "单件工时(h)": 99}, {"工序": 2, "单件工时(h)": 8})
    payload = hours_input(case.conn, "P1")
    payload["operations"][0]["unit_hours"] = 99
    facts = WorkbenchProcessQueryService(case.conn).facts()
    write_token = token(case)
    held, release, attempted = Event(), Event(), Event()
    append = WorkbenchCalibrationAdoptionRepository.append

    def paused_append(repo, *args, **kwargs):
        result = append(repo, *args, **kwargs)
        held.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(WorkbenchCalibrationAdoptionRepository, "append", paused_append)

    def adopter():
        conn = connect(case)
        try:
            with case.app.app_context():
                return service(conn).confirm(case.template_ref, write_token, KEY, INTENT)
        finally:
            conn.close()

    def writer():
        conn = connect(case)
        conn.set_trace_callback(lambda sql: attempted.set() if sql == "BEGIN IMMEDIATE" else None)
        try:
            if entry == "save":
                return PartService(conn).update_internal_hours("P1", 1, 8, 99)
            if entry == "file":
                return file_apply(conn, file_rows)[0]
            if entry == "legacy":
                return PartOperationHoursExcelImportService(conn).apply_preview_rows(legacy_rows)
            with TransactionManager(conn).transaction(begin_immediate=True):
                return apply_hours(conn, payload, facts["operations"], facts["groups"])
        except WorkbenchCommandRejected as exc:
            return exc.code
        finally:
            conn.close()

    before = snapshot(case.conn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        adopting = pool.submit(adopter)
        try:
            assert held.wait(5)
            assert snapshot(case.conn) == before
            writing = pool.submit(writer)
            assert attempted.wait(5)
            assert not writing.done()
        finally:
            release.set()
        assert adopting.result(timeout=10)["result"] == "committed"
        result = writing.result(timeout=10)
    if entry in ("save", "stage"):
        assert result == "calibration_quota_locked"
    elif entry == "file":
        assert [row["result"] for row in result] == ["skipped", "committed"]
    else:
        assert result["skipped_count"] == result["update_count"] == 1
    assert templates(case.conn)[1]["unit_hours"] == 3
    assert case.conn.execute("SELECT count(*) FROM WorkbenchCalibrationQuotaLocks").fetchone()[0] == 1


@pytest.mark.parametrize("entry", ["file", "legacy"])
def test_second_row_storage_failure_rolls_back_first_unlocked_field(locked_quota_case, entry):
    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "setup_hours": 9}, {"sequence": 2, "unit_hours": 8})
    legacy = legacy_preview(case.conn, {"工序": 1, "换型时间(h)": 9, "单件工时(h)": 3},
                            {"工序": 2, "单件工时(h)": 8})
    case.conn.execute("""CREATE TEMP TRIGGER cw_fail_second BEFORE UPDATE ON PartOperations WHEN NEW.seq=2
        BEGIN SELECT RAISE(ABORT,'CW second row failed'); END""")
    before = snapshot(case.conn)
    with pytest.raises(sqlite3.IntegrityError if entry == "file" else AppError) as caught:
        if entry == "file":
            file_apply(case.conn, rows)
        else:
            PartOperationHoursExcelImportService(case.conn).apply_preview_rows(legacy)
    assert "CW second" in str(caught.value if entry == "file" else caught.value.cause)
    assert snapshot(case.conn) == before and not case.conn.in_transaction


def test_savepoint_failure_does_not_lose_outer_work_and_outer_rollback_keeps_locks(locked_quota_case):
    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
    before = snapshot(case.conn)
    with pytest.raises(RuntimeError, match="receipt failed"):
        with TransactionManager(case.conn).transaction(begin_immediate=True):
            result, _ = file_apply(case.conn, rows)
            assert [row["result"] for row in result] == ["skipped", "committed"]
            raise RuntimeError("receipt failed")
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("entry", ["save", "file", "legacy"])
def test_commit_failure_rolls_back_ordinary_changes(locked_quota_case, entry):
    class FailCommit(sqlite3.Connection):
        def commit(self):
            raise OSError("CW commit failure")

    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
    legacy = legacy_preview(case.conn, {"工序": 1, "单件工时(h)": 99}, {"工序": 2, "单件工时(h)": 8})
    before = snapshot(case.conn)
    conn = connect(case, factory=FailCommit)
    try:
        with pytest.raises(OSError, match="CW commit"):
            if entry == "save":
                PartService(conn).update_internal_hours("P1", 1, 9, 3)
            elif entry == "file":
                file_apply(conn, rows)
            else:
                PartOperationHoursExcelImportService(conn).apply_preview_rows(legacy)
        assert not conn.in_transaction
    finally:
        conn.close()
    assert snapshot(case.conn) == before


def test_stage_receipt_failure_rolls_back_hours_and_confirmation(locked_quota_case):
    case = locked_quota_case
    payload = hours_input(case.conn, "P1")
    payload["operations"][0]["setup_hours"] = 9
    payload["operations"][1]["unit_hours"] = 8
    case.conn.execute("""CREATE TEMP TRIGGER cw_fail_receipt BEFORE INSERT ON WorkbenchCommandReceipts
        BEGIN SELECT RAISE(ABORT,'CW receipt failed'); END""")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        run_stage(case.conn, "hours_confirm", payload,
                  identity=WorkbenchProcessQueryService(case.conn).resolve(case.ref("part", "P1")))
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("entry", ["save", "file", "legacy"])
def test_same_number_replacement_while_writer_waits_never_rebinds_old_intent(locked_quota_case, entry):
    case = locked_quota_case
    case.conn.execute("PRAGMA journal_mode=WAL")
    file_rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99})
    legacy_rows = legacy_preview(case.conn, {"工序": 1, "单件工时(h)": 99})
    attempted = Event()

    def writer():
        conn = connect(case)
        conn.set_trace_callback(lambda sql: attempted.set() if sql == "BEGIN IMMEDIATE" else None)
        try:
            if entry == "save":
                PartService(conn).update_internal_hours("P1", 1, 9, 99)
            elif entry == "file":
                file_apply(conn, file_rows)
            else:
                PartOperationHoursExcelImportService(conn).apply_preview_rows(legacy_rows)
        except WorkbenchCommandRejected as exc:
            return exc.code
        finally:
            conn.close()

    case.conn.execute("BEGIN IMMEDIATE")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        try:
            assert attempted.wait(5)
            PartService(case.conn).reparse_and_save("P1", "1Turning2Turning")
            case.conn.commit()
        finally:
            case.conn.rollback()
        assert future.result(timeout=10) == "stale_write"
    assert templates(case.conn)[1]["unit_hours"] == 3
