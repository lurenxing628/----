"""Confirm revalidates real source drift, not browser values or stale suggestions."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.calibration_adoption_support import INTENT, KEY, PREVIEW_INTENT, connect, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case  # noqa: F401
from tests.workbench.test_template_lineage_support import origin


def _drift(case, kind):
    if kind == "quota":
        case.conn.execute("UPDATE PartOperations SET unit_hours=7 WHERE id=?", (case.template_id,))
    elif kind == "source":
        case.conn.execute("UPDATE PartOperations SET source='external' WHERE id=?", (case.template_id,))
    elif kind == "template_revert":
        case.conn.execute("UPDATE PartOperations SET op_type_name='other' WHERE id=?", (case.template_id,))
        case.conn.execute("UPDATE PartOperations SET op_type_name='Turning' WHERE id=?", (case.template_id,))
    elif kind == "instance_revert":
        case.conn.execute("UPDATE BatchOperations SET unit_hours=99 WHERE id=?", (case.ids[0],))
        case.conn.execute("UPDATE BatchOperations SET unit_hours=1 WHERE id=?", (case.ids[0],))
    elif kind == "withdraw":
        with TransactionManager(case.conn).transaction():
            case.lineage_writer.withdraw(origin(case, case.ids[0])["operation_ref"], "wrong origin confirmed")
    elif kind == "report":
        row = case.reports[2]
        case.command("correct", row["report_ref"], {"original_revision_ref": row["revision_ref"],
                                                  "effective_processing_hours": 15, "reason": "verified correction"})
    elif kind == "report_unknown":
        row = case.reports[0]
        case.command("correct", row["report_ref"], {"original_revision_ref": row["revision_ref"],
                                                  "effective_processing_hours": None, "reason": "unknown after review"})
    elif kind == "new_sample":
        from tests.workbench.test_template_lineage_support import completed

        completed(case, [9], prefix="NEW", version=3)
    else:
        raise AssertionError(kind)
    case.conn.commit()


@pytest.mark.parametrize("kind", ["quota", "source", "template_revert", "instance_revert", "withdraw", "report", "report_unknown", "new_sample"])
def test_stale_preview_rejects_real_changes_without_partial_writes(ready_adoption_case, kind):
    case = ready_adoption_case
    write_token = token(case)
    _drift(case, kind)
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert error.value.code == "stale_write"
    assert snapshot(case.conn) == before and not case.conn.in_transaction
    assert service(case.conn).receipt(case.template_ref, KEY) is None


def test_delete_replace_same_id_never_retargets_old_template_ref(ready_adoption_case):
    case = ready_adoption_case
    write_token = token(case)
    case.conn.execute("DELETE FROM PartOperations WHERE id=?", (case.template_id,))
    case.conn.execute("""INSERT INTO PartOperations(id,part_no,seq,op_type_id,op_type_name,source,unit_hours)
        VALUES (?,'P1',1,'T1','Turning','internal',1)""", (case.template_id,))
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert error.value.code == "entity_not_found"
    assert snapshot(case.conn) == before
    replacement = case.lineage_repo.template(case.template_id)["template_operation_ref"]
    assert replacement != case.template_ref
    fresh = service(case.conn).preview(replacement, PREVIEW_INTENT)
    assert not fresh["validation"]["can_adopt"] and fresh["suggestion"]["sample_count"] == 0


def test_legacy_original_drift_fails_explicitly_and_never_rewrites_archive(ready_adoption_case):
    case = ready_adoption_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    write_token = token(case)
    case.conn.execute("UPDATE OperationExecutionEvents SET remark='changed after archive'")
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert error.value.code == "calibration_source_changed"
    assert snapshot(case.conn) == before


def test_reason_and_cross_template_tokens_are_bound(ready_adoption_case):
    case = ready_adoption_case
    write_token = token(case)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).confirm(case.template_ref, write_token, KEY, {**INTENT, "reason": "different reason"})
    assert error.value.code == "stale_write"
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,unit_hours) VALUES ('P1',2,'other','internal',1)")
    other = case.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='template_operation' AND ref!=? AND active=1", (case.template_ref,)).fetchone()[0]
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).confirm(other, write_token, KEY, INTENT)
    assert error.value.code == "stale_write"


def test_confirm_rechecks_after_waiting_for_sqlite_write_lock(ready_adoption_case):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    case = ready_adoption_case
    write_token = token(case)
    acquired = Event()
    case.conn.execute("BEGIN IMMEDIATE")
    case.conn.execute("UPDATE PartOperations SET unit_hours=8 WHERE id=?", (case.template_id,))

    def confirm():
        conn = connect(case)
        conn.set_trace_callback(lambda sql: acquired.set() if sql == "BEGIN IMMEDIATE" else None)
        try:
            with case.app.app_context(), pytest.raises(WorkbenchCommandRejected) as error:
                service(conn).confirm(case.template_ref, write_token, KEY, INTENT)
            return error.value.code
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(confirm)
        try:
            assert acquired.wait(5)
            assert not future.done()
        finally:
            case.conn.commit()
        assert future.result(timeout=10) == "stale_write"
    assert case.conn.execute("SELECT unit_hours FROM PartOperations WHERE id=?", (case.template_id,)).fetchone()[0] == 8
    assert not case.conn.execute("SELECT * FROM WorkbenchCalibrationAdoptions").fetchall()
