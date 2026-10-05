"""Real SQLite stage creation, editing, splitting and effective-cycle regression."""

from copy import deepcopy

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.process.workflow_state import read_workflow
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process.group_defaults import apply_default_groups
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from tests.workbench.process_commands_support import (
    group_rows,
    hours_input,
    identity_for,
    op_ref,
    op_rows,
    prepare_stages,
    ref_for,
    run_stage,
    source_input,
    stage_database,
    storage,
)
from tests.workbench.process_route_support import read_only_probe

_stage_fixture = stage_database


def add_external(conn, sequences, supplier="PROC-S", group=None):
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,supplier_id,ext_days,ext_group_id)
        VALUES ('PROC-001',?,'热处理','PROC-EX','external',?,2.5,?)""", [(seq, supplier, group) for seq in sequences])
    if group:
        conn.execute("UPDATE ExternalGroups SET end_seq=? WHERE group_id=?", (max(sequences), group))
    rows = op_rows(conn)
    conn.execute("UPDATE Parts SET route_raw=? WHERE part_no='PROC-001'", ("".join(str(seq) + row["op_type_name"] for seq, row in rows.items()),))
    conn.commit()


def row(conn, sequences, group=None, supplier="PROC-S", days=4.5):
    return {"ref": ref_for(conn, "template_external_group", group) if group else None,
            "operation_refs": [op_ref(conn, seq) for seq in sequences],
            "supplier_ref": ref_for(conn, "supplier", supplier), "total_days": days}


def test_changing_only_group_cycle_does_not_detach_or_rewrite_operations(stage_conn, monkeypatch):
    from data.repositories.part_operation_repo import PartOperationRepository
    conn = stage_conn
    prepare_stages(conn)
    before = op_rows(conn)
    monkeypatch.setattr(PartOperationRepository, "update", lambda *args: pytest.fail("unchanged group members were rewritten"))
    run_stage(conn, "groups_confirm", {"groups": [row(conn, [20], group="PROC-G", days=8.5)], "discard_group_refs": []},
              key="group-cycle-write-once")
    assert op_rows(conn) == before and group_rows(conn)["PROC-G"]["total_days"] == 8.5


def test_two_separate_stages_create_edit_and_dissolve_without_touching_other_stage(stage_conn):
    conn = stage_conn
    add_external(conn, [40, 50], "PROC-S2")
    prepare_stages(conn)
    old_group, old_ops = group_rows(conn)["PROC-G"], op_rows(conn)
    payload = {"groups": [row(conn, [40, 50], supplier="PROC-S2", days=4.25)], "discard_group_refs": []}
    before = storage(conn)
    service = WorkbenchProcessMutationService(conn)
    with read_only_probe(conn):
        preview = service.preview_groups(payload, identity_for(conn))
    assert preview[0]["action"] == "create" and preview[0]["after"]["sequences"] == ["40", "50"]
    assert storage(conn) == before
    run_stage(conn, "groups_confirm", payload, key="group-create-000001")
    groups = group_rows(conn)
    new_id = next(key for key in groups if key != "PROC-G")
    assert groups["PROC-G"] == old_group and groups[new_id]["total_days"] == 4.25
    assert op_rows(conn)[40]["ext_group_id"] == op_rows(conn)[50]["ext_group_id"] == new_id
    assert read_workflow(conn, "PROC-001")["source"]["state"] == "confirmed"
    assert not read_workflow(conn, "PROC-001")["ready"]
    payload = {"groups": [row(conn, [40, 50], group=new_id, supplier="PROC-S", days=7.125)], "discard_group_refs": []}
    run_stage(conn, "groups_confirm", payload, key="group-edit-0000001")
    assert group_rows(conn)[new_id]["supplier_id"] == "PROC-S"
    assert op_rows(conn)[40]["supplier_id"] == op_rows(conn)[50]["supplier_id"] == "PROC-S"
    assert op_rows(conn)[40]["ext_days"] == old_ops[40]["ext_days"]
    run_stage(conn, "groups_confirm", {"groups": [], "discard_group_refs": [ref_for(conn, "template_external_group", new_id)]}, key="group-unlink-00001")
    assert group_rows(conn) == {"PROC-G": old_group}
    assert op_rows(conn)[40]["ext_group_id"] is None and op_rows(conn)[40]["ext_days"] == 2.5


def test_split_range_reuses_old_group_identity_and_cycle_only_changes_explicitly(stage_conn):
    conn = stage_conn
    add_external(conn, [21, 22], group="PROC-G")
    prepare_stages(conn)
    old = group_rows(conn)["PROC-G"]
    ref = ref_for(conn, "template_external_group", "PROC-G")
    payload = {"groups": [row(conn, [20, 21], "PROC-G", days=6.75), row(conn, [22], days=2)], "discard_group_refs": []}
    run_stage(conn, "groups_confirm", payload)
    assert ref_for(conn, "template_external_group", "PROC-G") == ref
    assert group_rows(conn)["PROC-G"] == {**old, "end_seq": 21}
    assert op_rows(conn)[20]["ext_group_id"] == op_rows(conn)[21]["ext_group_id"] == "PROC-G"
    assert op_rows(conn)[22]["ext_group_id"] not in (None, "PROC-G")


@pytest.mark.parametrize("invalid", ("internal", "gap", "different_supplier", "foreign", "overlap", "capability", "duplicate"))
def test_invalid_group_edits_fail_before_any_mutation(stage_conn, invalid):
    conn = stage_conn
    add_external(conn, [40, 50], "PROC-S2")
    prepare_stages(conn)
    payload = {"groups": [row(conn, [40, 50], supplier="PROC-S2")], "discard_group_refs": []}
    if invalid == "internal":
        payload["groups"][0]["operation_refs"] = [op_ref(conn, 10)]
    elif invalid == "gap":
        payload["groups"][0]["operation_refs"] = [op_ref(conn, 20), op_ref(conn, 40)]
    elif invalid == "different_supplier":
        conn.execute("UPDATE PartOperations SET supplier_id='PROC-S' WHERE part_no='PROC-001' AND seq=50")
        conn.commit()
    elif invalid == "foreign":
        payload["groups"][0]["operation_refs"] = [op_ref(conn, 10, "PROC-003")]
    elif invalid == "overlap":
        payload["groups"][0] = row(conn, [20])
    elif invalid == "capability":
        conn.execute("DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='PROC-S2'")
        conn.commit()
    else:
        payload["groups"].append(deepcopy(payload["groups"][0]))
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(conn, "groups_confirm", payload)
    assert storage(conn) == before


def test_unmentioned_historical_group_is_preserved_and_source_is_not_auto_confirmed(stage_conn):
    conn = stage_conn
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,remark) VALUES ('HISTORY','PROC-001',99,99,'separate',13,'keep')")
    conn.commit()
    prepare_stages(conn, source=False)
    old = group_rows(conn)["HISTORY"]
    run_stage(conn, "groups_confirm", {"groups": [row(conn, [20], "PROC-G", days=9)], "discard_group_refs": []})
    assert group_rows(conn)["HISTORY"] == old
    assert read_workflow(conn, "PROC-001")["source"]["state"] == "unconfirmed"


def test_group_receipt_failure_rolls_back_ranges_members_suppliers_and_confirmations(stage_conn, monkeypatch):
    conn = stage_conn
    prepare_stages(conn)
    command = WorkbenchCommandService(conn)
    original = command.repo.insert
    def fail(**kwargs):
        original(**kwargs)
        raise OSError("after group receipt")
    monkeypatch.setattr(command.repo, "insert", fail)
    before = storage(conn)
    with pytest.raises(WorkbenchCommandUncertain):
        run_stage(conn, "groups_confirm", {"groups": [row(conn, [20], "PROC-G", supplier="PROC-S2", days=9)], "discard_group_refs": []}, command=command)
    assert storage(conn) == before


def test_source_changes_supplier_for_entire_stage_preserving_identity_range_and_total(stage_conn):
    conn = stage_conn
    add_external(conn, [21], group="PROC-G")
    prepare_stages(conn)
    old = group_rows(conn)["PROC-G"]
    payload = source_input(conn)
    for op in payload["operations"]:
        if op["source"] == "external":
            op["supplier_ref"] = ref_for(conn, "supplier", "PROC-S2")
    assert WorkbenchProcessMutationService(conn).affected_groups("source_confirm", payload, identity_for(conn)) == []
    run_stage(conn, "source_confirm", payload)
    assert group_rows(conn)["PROC-G"] == {**old, "supplier_id": "PROC-S2"}
    payload["operations"][1]["supplier_ref"] = ref_for(conn, "supplier", "PROC-S")
    before = storage(conn)
    with pytest.raises(WorkbenchCommandRejected, match="供应商必须一致"):
        run_stage(conn, "source_confirm", payload, key="partial-supplier-01")
    assert storage(conn) == before


@pytest.mark.parametrize("old_days", (None, 3.25))
def test_merged_cycle_projects_total_and_hours_save_keeps_member_history(stage_conn, old_days):
    conn = stage_conn
    conn.execute("UPDATE PartOperations SET ext_days=? WHERE part_no='PROC-001' AND seq=20", (old_days,))
    conn.commit()
    prepare_stages(conn)
    entity = WorkbenchProcessQueryService(conn).detail(identity_for(conn).ref)
    operation = entity["operations"][1]
    assert operation["external_days"] is None and operation["external_days_source"] == "group"
    payload = hours_input(conn)
    payload["operations"][1]["external_days"] = None
    payload["groups"][0]["total_days"] = 9.125
    run_stage(conn, "hours_confirm", payload)
    assert op_rows(conn)[20]["ext_days"] == old_days and group_rows(conn)["PROC-G"]["total_days"] == 9.125
    assert read_workflow(conn, "PROC-001")["ready"]


def test_default_merge_creates_only_new_contiguous_stages_with_one_supplier_cycle(stage_conn):
    conn = stage_conn
    add_external(conn, [40, 50, 70, 80])
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,setup_hours,unit_hours) VALUES ('PROC-001',60,'车削','PROC-IN','internal',0,1)")
    conn.execute("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('PROC-EX','merged')")
    conn.commit()
    old = group_rows(conn)["PROC-G"]
    with TransactionManager(conn).transaction(begin_immediate=True):
        assert apply_default_groups(conn, "PROC-001", [40, 50, 70, 80])
    groups = group_rows(conn)
    assert groups["PROC-G"] == old
    fresh = [group for key, group in groups.items() if key != "PROC-G"]
    assert {(group["start_seq"], group["end_seq"], group["total_days"]) for group in fresh} == {(40, 50, 3.25), (70, 80, 3.25)}
    with TransactionManager(conn).transaction(begin_immediate=True):
        assert not apply_default_groups(conn, "PROC-001", [40, 50, 70, 80])
    assert group_rows(conn) == groups


def test_group_defaults_are_applied_on_new_route_and_new_external_source(stage_conn):
    conn = stage_conn
    conn.execute("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('PROC-EX','merged')")
    conn.execute("UPDATE Parts SET route_raw='10车削' WHERE part_no='PROC-002'")
    conn.commit()
    identity = identity_for(conn, "PROC-002")
    run_stage(conn, "route_confirm", {"route": {"mode": "text", "route_raw": "10车削"}, "discard_group_refs": []}, identity=identity)
    source = source_input(conn, "PROC-002")
    source["operations"][0].update(source="external", op_type_ref=ref_for(conn, "op_type", "PROC-EX"), supplier_ref=ref_for(conn, "supplier", "PROC-S"))
    run_stage(conn, "source_confirm", source, identity=identity_for(conn, "PROC-002"), key="new-source-0000001")
    group = next(iter(group_rows(conn, "PROC-002").values()))
    assert group["start_seq"] == group["end_seq"] == 10 and group["total_days"] == 3.25


def test_new_route_defaults_stop_at_internal_operation_and_leave_existing_manual_groups(stage_conn):
    conn = stage_conn
    conn.execute("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('PROC-EX','merged')")
    conn.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S2'")
    conn.commit()
    old = group_rows(conn)
    payload = {"route": {"mode": "text", "route_raw": "10热处理20热处理30车削40热处理"}, "discard_group_refs": []}
    run_stage(conn, "route_confirm", payload, identity=identity_for(conn, "PROC-002"))
    created = group_rows(conn, "PROC-002")
    assert {(group["start_seq"], group["end_seq"], group["total_days"]) for group in created.values()} == {(10, 20, 3.25), (40, 40, 3.25)}
    assert group_rows(conn) == old


def test_identical_stage_edit_is_unchanged_without_rewriting_history(stage_conn):
    conn = stage_conn
    prepare_stages(conn)
    before_ops, before_groups = op_rows(conn), group_rows(conn)
    outcome = run_stage(conn, "groups_confirm", {"groups": [row(conn, [20], "PROC-G", days=6.75)], "discard_group_refs": []})
    assert outcome["result"] == "unchanged"
    assert op_rows(conn) == before_ops and group_rows(conn) == before_groups


def test_explicit_same_group_supplier_repairs_inconsistent_member_without_false_noop(stage_conn):
    conn = stage_conn
    prepare_stages(conn)
    conn.execute("UPDATE PartOperations SET supplier_id='PROC-S2' WHERE part_no='PROC-001' AND seq=20")
    conn.commit()
    payload = {"groups": [row(conn, [20], "PROC-G", days=6.75)], "discard_group_refs": []}
    changes = WorkbenchProcessMutationService(conn).preview_groups(payload, identity_for(conn))
    assert len(changes) == 1 and "工序 20 当前供应商 second" in changes[0]["before"]["supplier_label"]
    result = run_stage(conn, "groups_confirm", payload)
    assert result["result"] == "committed" and op_rows(conn)[20]["supplier_id"] == "PROC-S"
    assert group_rows(conn)["PROC-G"]["total_days"] == 6.75
