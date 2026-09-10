"""Real D05 adoption, read-only preview and exact preservation of older facts."""

import json

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import restore_snapshot
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from tests.workbench.calibration_adoption_support import (
    INTENT,
    KEY,
    PREVIEW_INTENT,
    assert_preserved,
    service,
    snapshot,
    token,
)
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.template_lineage_support import completed, create, origin
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def test_real_preview_confirm_receipt_and_future_template_only(ready_adoption_case):
    case = ready_adoption_case
    before = snapshot(case.conn)
    changes = case.conn.total_changes
    case.conn.execute("PRAGMA query_only=ON")
    preview = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert preview["suggestion"]["suggested_unit_hours"] == 3
    assert preview["validation"]["can_adopt"] is True
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    assert not case.conn.in_transaction
    case.conn.execute("PRAGMA query_only=OFF")
    result = service(case.conn).confirm(case.template_ref, preview["write_context"]["write_token"], KEY, INTENT)
    assert result["result"] == "committed" and not result["replayed"]
    data = result["data"]
    assert data["old_unit_hours"] == 1 and data["new_unit_hours"] == 3 and data["locked"] is True
    assert data["application_operator"] == "local-test-operator" and data["reason"] == INTENT["reason"]
    assert data["declared_operator"] == INTENT["declared_operator"] != data["application_operator"]
    assert data["confirmed"] is True
    assert data["template_revision_after"] == data["template_revision_before"] + 1
    assert data["adopted_at"] == "2026-09-10T12:00:00" and data["effect_scope"] == "future_template_use_only"
    assert_preserved(before, snapshot(case.conn))
    audit = dict(case.conn.execute("SELECT * FROM WorkbenchCalibrationAdoptions").fetchone())
    assert audit["declared_operator"] == INTENT["declared_operator"] and audit["confirmed"] == 1
    evidence = json.loads(audit["evidence_json"])
    assert {row["sample_ref"] for row in evidence["samples"]} == set(data["sample_refs"])
    assert len(data["sample_refs"]) == len(data["sample_revisions"]) == 5
    assert all(row["lineage_evidence_ref"] and row["report_revision_refs"] for row in evidence["samples"])
    assert restore_snapshot(audit["template_before"])["unit_hours"] == 1
    assert restore_snapshot(audit["template_after"])["unit_hours"] == 3
    assert service(case.conn).receipt(case.template_ref, KEY)["receipt_ref"] == result["receipt_ref"]
    new_id = create(case, "AFTER-ADOPTION")
    new = case.conn.execute("SELECT unit_hours FROM BatchOperations WHERE id=?", (new_id,)).fetchone()
    assert new[0] == 3 and origin(case, new_id)["template_revision"] == data["template_revision_after"]
    assert all(case.conn.execute("SELECT unit_hours FROM BatchOperations WHERE id=?", (old_id,)).fetchone()[0] == 1 for old_id in case.ids)
    assert not case.conn.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("old", [None, 0, 2])
def test_unknown_zero_and_equal_old_quota_can_be_adopted_with_real_samples(adoption_case, old):
    case = adoption_case
    case.conn.execute("UPDATE PartOperations SET unit_hours=? WHERE id=?", (old, case.template_id))
    case.conn.commit()
    completed(case, [2, 2, 2, 2, 2])
    result = service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)["data"]
    assert result["old_unit_hours"] == old and result["new_unit_hours"] == 2
    assert result["template_revision_after"] == result["template_revision_before"] + int(old != 2)


@pytest.mark.parametrize("count", [0, 4, 5, 25])
def test_real_sample_threshold_and_latest_twenty(adoption_case, count):
    case = adoption_case
    if count:
        completed(case, list(range(1, count + 1)))
    before = snapshot(case.conn)
    preview = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert preview["validation"]["can_adopt"] == (count >= 5)
    assert preview["suggestion"]["sample_count"] == min(count, 20)
    assert snapshot(case.conn) == before
    if count < 5:
        assert preview["write_context"]["write_token"] is None
        assert "insufficient_samples" in {row["code"] for row in preview["validation"]["issues"]}
    else:
        result = service(case.conn).confirm(case.template_ref, preview["write_context"]["write_token"], KEY, INTENT)
        assert result["data"]["new_unit_hours"] == (3 if count == 5 else 15.5)


def test_lock_interface_is_permanent_ref_scoped_and_requires_write_transaction(ready_adoption_case):
    case = ready_adoption_case
    repo = WorkbenchCalibrationAdoptionRepository(case.conn)
    assert repo.read_locks([case.template_ref]) == {}
    service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    lock = repo.read_locks([case.template_ref])[case.template_ref]
    assert lock["locked"] is True and lock["locked_unit_hours"] == 3
    assert lock["declared_operator"] == INTENT["declared_operator"] and lock["confirmed"] is True
    with pytest.raises(RuntimeError, match="transaction"):
        repo.require_unlocked([case.template_ref])
    with TransactionManager(case.conn).transaction(), pytest.raises(WorkbenchCommandRejected) as error:
        repo.require_unlocked([case.template_ref])
    assert error.value.code == "calibration_quota_locked"
    preview = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert preview["quota_lock"] == lock and not preview["validation"]["can_adopt"]
    assert preview["validation"]["issues"][0]["code"] == "calibration_quota_locked"


def test_old_rows_and_sqlite_types_remain_exact(ready_adoption_case):
    case = ready_adoption_case
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=1", (b"\x00\xffold-history",))
    case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=1")
    case.conn.execute("CREATE TABLE CalibrationAdoptionLegacyProbe(id INTEGER PRIMARY KEY,value)")
    for index, value in enumerate((None, 17, 2.75, "old-text", b"\x00\x80\xff")):
        case.conn.execute("INSERT INTO CalibrationAdoptionLegacyProbe VALUES (?,?)", (index, value))
    case.conn.execute("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','old','old',?)", (b"\xffold-log",))
    case.conn.commit()
    before = snapshot(case.conn)
    service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    assert_preserved(before, snapshot(case.conn))
    assert case.conn.execute("SELECT typeof(result_summary) FROM ScheduleHistory WHERE version=1").fetchone()[0] == "blob"
    assert [row[0] for row in case.conn.execute("SELECT typeof(value) FROM CalibrationAdoptionLegacyProbe ORDER BY id")] == ["null", "integer", "real", "text", "blob"]


def test_only_target_quota_and_identity_revision_change(ready_adoption_case):
    case = ready_adoption_case
    case.conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P2','Other part')")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,unit_hours) VALUES ('P2',1,'Other','internal',9)")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,unit_hours) VALUES ('P1',2,'Next','internal',7)")
    case.conn.commit()
    templates = {row["id"]: dict(row) for row in case.conn.execute("SELECT * FROM PartOperations")}
    identities = {row["ref"]: dict(row) for row in case.conn.execute("SELECT * FROM WorkbenchEntityRefs")}
    service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    templates[case.template_id]["unit_hours"] = 3.0
    identities[case.template_ref]["revision"] += 1
    assert {row["id"]: dict(row) for row in case.conn.execute("SELECT * FROM PartOperations")} == templates
    assert {row["ref"]: dict(row) for row in case.conn.execute("SELECT * FROM WorkbenchEntityRefs")} == identities


def test_zero_suggested_quota_is_real_known_zero_not_missing(adoption_case):
    case = adoption_case
    completed(case, [0, 0, 0, 0, 0])
    result = service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    assert result["data"]["new_unit_hours"] == 0 and result["data"]["locked"] is True
