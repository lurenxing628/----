"""Current-source verification is part of the normal atomic registration command."""

import json
import sqlite3

import pytest

from core.infrastructure.workbench_outsourcing_source_schema import contract_issues, install, objects
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from tests.workbench.outsourcing_legacy_source_support import assert_empty_registration, evidence
from tests.workbench.outsourcing_legacy_source_support import legacy_source_case as _legacy_source_case  # noqa: F401
from tests.workbench.outsourcing_support import original_rows
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


def test_ten_legacy_targets_preview_and_register_once_without_rewriting_history(legacy_source_case):
    case = legacy_source_case
    before, originals = evidence(case.conn), original_rows(case.conn)
    with case.reader.read_snapshot():
        rows = case.reader.targets()["items"]
    assert len(rows) == 10 and all(row["can_register"] for row in rows)
    assert all(row["source_resolution"] == {"basis": "current_relation", "confirmation_ref": None} for row in rows)
    preview = case.preview(case.payload(merged=True))
    assert preview["target"]["part"]["business_code"] == "XP1"
    assert_empty_registration(case.conn)
    committed = case.confirm(preview, key="legacy-source-once-key")
    ref, fact = committed["data"]["outsourcing_ref"], committed["data"]["fact_ref"]
    rows = case.conn.execute("SELECT * FROM WorkbenchOutsourcingSourceConfirmations ORDER BY operation_ref").fetchall()
    assert [tuple(row) for row in rows] == [(op, case.entity_ref("batch", "XB1"), fact) for op in preview["input"]["target"]["operation_refs"]]
    assert case.detail(ref)["source_state"] == "current"
    assert case.detail(ref)["can_preview"] is True
    update = case.preview({"outsourcing_ref": ref, "declared_operator": "Receiver", "reason": "Checked arrival",
                           "returned": "2026-09-10T10:00:00", "confirmedState": "returned"})
    assert update["target"]["source_resolution"] == {"basis": "registration_confirmation", "confirmation_ref": fact}
    case.confirm(update)
    assert case.detail(ref)["source_state"] == "current" and case.detail(ref)["history_count"] == 2
    replay = case.confirm(preview, key="legacy-source-once-key")
    assert replay["replayed"] is True and replay["receipt_ref"] == committed["receipt_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingSourceConfirmations").fetchone()[0] == 2
    recorded = case.conn.execute("SELECT source_facts_json FROM WorkbenchOutsourcingFacts WHERE fact_ref=?", (fact,)).fetchone()[0]
    assert all(op["origin"]["batch_ref"] is None for op in json.loads(recorded)["operations"])
    assert evidence(case.conn) == before and original_rows(case.conn) == originals
    assert case.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_new_operation_uses_birth_without_extra_binding_or_input(outsourcing_case):
    case = outsourcing_case
    preview = case.preview(case.payload())
    assert set(preview["input"]["target"]) == {"kind", "batch_ref", "supplier_ref", "operation_refs"}
    assert preview["target"]["source_resolution"] == {"basis": "birth_record", "confirmation_ref": None}
    result = case.confirm(preview)
    assert case.detail(result["data"]["outsourcing_ref"])["source_state"] == "current"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingSourceConfirmations").fetchone()[0] == 0


def test_mixed_birth_and_legacy_group_keeps_stable_identity(legacy_source_case):
    case = legacy_source_case
    case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id) "
                      "VALUES ('NEW','XB1',11,'XT1','Heat treatment','external','XS1')")
    case.conn.commit()
    payload = case.payload(merged=True)
    payload["target"]["operation_refs"][1] = case.operation_ref("NEW")
    preview = case.preview(payload)
    first = case.confirm(preview)
    ref = first["data"]["outsourcing_ref"]
    assert case.detail(ref)["source_state"] == "current"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingSourceConfirmations").fetchone()[0] == 1
    with pytest.raises(WorkbenchCommandRejected) as duplicate:
        case.confirm(preview)
    assert duplicate.value.code == "constraint_conflict"
    update = case.preview({"outsourcing_ref": ref, "declared_operator": "Clerk", "reason": "Rechecked group"})
    assert update["target"]["source_resolution"]["basis"] == "registration_confirmation"
    case.confirm(update)
    assert case.detail(ref)["source_state"] == "current"


@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("table", ["Batches", "Suppliers", "BatchOperations"])
def test_same_number_replacement_never_rebinds_old_legacy_preview(legacy_source_case, table, registered):
    case = legacy_source_case
    preview = case.preview(case.payload())
    ref = None
    if registered:
        ref = case.confirm(preview)["data"]["outsourcing_ref"]
        preview = case.preview({"outsourcing_ref": ref, "declared_operator": "Clerk", "reason": "Recheck original"})
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    where = " WHERE op_code='XO1'" if table == "BatchOperations" else ""
    case.conn.execute("INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table + where)
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected):
        case.confirm(preview)
    if registered:
        assert case.detail(ref)["source_state"] != "current"
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingSourceConfirmations").fetchone()[0] == 1
    else:
        assert_empty_registration(case.conn)


@pytest.mark.parametrize("change", ["batch", "supplier", "member", "part", "label"])
def test_legacy_preview_rejects_source_changes_atomically(legacy_source_case, change):
    case = legacy_source_case
    preview = case.preview(case.payload(merged=True))
    if change == "batch":
        case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('XB2','XP1',10)")
        case.conn.execute("UPDATE BatchOperations SET batch_id='XB2' WHERE op_code='XO2'")
    elif change == "supplier":
        case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('XS2','Other','XT1')")
        case.conn.execute("UPDATE BatchOperations SET supplier_id='XS2' WHERE op_code='XO2'")
    elif change == "member":
        case.conn.execute("UPDATE BatchOperations SET piece_id='split' WHERE op_code='XO2'")
    elif change == "part":
        case.conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('XP2','Other')")
        case.conn.execute("UPDATE Batches SET part_no='XP2' WHERE batch_id='XB1'")
    else:
        case.conn.execute("UPDATE Suppliers SET name='Renamed' WHERE supplier_id='XS1'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        case.confirm(preview)
    assert rejected.value.code in ("constraint_conflict", "stale_write")
    assert_empty_registration(case.conn)


@pytest.mark.parametrize("stage", ["source", "receipt"])
def test_failure_rolls_back_all_legacy_members_and_confirmation(legacy_source_case, stage):
    case = legacy_source_case
    before = evidence(case.conn)
    preview = case.preview(case.payload(merged=True))
    table = "WorkbenchOutsourcingSourceConfirmations" if stage == "source" else "WorkbenchCommandReceipts"
    condition = " WHEN (SELECT COUNT(*) FROM WorkbenchOutsourcingSourceConfirmations)=1" if stage == "source" else ""
    case.conn.execute("CREATE TRIGGER injected_source_failure BEFORE INSERT ON " + table +
                      condition + " BEGIN SELECT RAISE(ABORT,'injected source failure'); END")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandUncertain):
        case.confirm(preview, key="legacy-source-failure-key")
    assert_empty_registration(case.conn)
    assert evidence(case.conn) == before
    case.conn.execute("DROP TRIGGER injected_source_failure")
    case.conn.commit()
    assert case.confirm(preview, key="legacy-source-failure-key")["result"] == "committed"


def test_binding_cannot_claim_another_registrations_first_fact(legacy_source_case):
    case = legacy_source_case
    first = case.confirm(case.preview(case.payload()))
    with pytest.raises(sqlite3.IntegrityError, match="first registration"):
        case.conn.execute("INSERT INTO WorkbenchOutsourcingSourceConfirmations(operation_ref,batch_ref,fact_ref) VALUES (?,?,?)",
                          (case.operation_ref("XO2"), case.entity_ref("batch", "XB1"), first["data"]["fact_ref"]))
    case.conn.rollback()
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingSourceConfirmations").fetchone()[0] == 1


@pytest.mark.parametrize("event", ["UPDATE", "DELETE", "REPLACE"])
def test_source_binding_is_permanent(legacy_source_case, event):
    case = legacy_source_case
    case.confirm(case.preview(case.payload()))
    table = "WorkbenchOutsourcingSourceConfirmations"
    sql = {"UPDATE": "UPDATE " + table + " SET batch_ref=batch_ref", "DELETE": "DELETE FROM " + table,
           "REPLACE": "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table}[event]
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    with pytest.raises(sqlite3.IntegrityError):
        case.conn.execute(sql)
    case.conn.rollback()
    assert case.conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 1


def test_source_schema_transaction_idempotence_and_partial_rejection(outsourcing_case):
    conn = outsourcing_case.conn
    assert contract_issues(conn) == []
    with pytest.raises(RuntimeError, match="migration transaction"):
        install(conn)
    conn.execute("BEGIN")
    before = conn.total_changes
    install(conn)
    assert conn.total_changes == before
    conn.rollback()
    conn.execute("DROP TRIGGER wb_outsourcing_source_confirmation_guard")
    conn.commit()
    conn.execute("BEGIN")
    with pytest.raises(RuntimeError, match="Cannot install or repair"):
        install(conn)
    conn.rollback()
    assert contract_issues(conn) == ["missing_outsourcing_source_schema:wb_outsourcing_source_confirmation_guard"]
    for name, sql in reversed(list(objects().items())):
        if name != "wb_outsourcing_source_confirmation_guard":
            conn.execute('DROP ' + sql.split()[1] + ' "' + name + '"')
    conn.commit()
    conn.execute("BEGIN")
    install(conn)
    assert contract_issues(conn) == []
    conn.rollback()
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='WorkbenchOutsourcingSourceConfirmations'").fetchone() is None
