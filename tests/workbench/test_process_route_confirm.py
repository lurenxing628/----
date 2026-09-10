"""Route preservation, explicit group loss acknowledgement and unknown stages."""

from copy import deepcopy

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.workflow_state import operation_confirmations, read_workflow
from core.services.workbench.process_mutations import WorkbenchProcessMutationService
from tests.workbench.process_commands_support import (
    KEY,
    downstream,
    group_rows,
    hours_input,
    identity_for,
    op_ref,
    op_rows,
    prepare_stages,
    ref_for,
    route_input,
    run_stage,
    source_input,
    stage_database,
    storage,
)
from tests.workbench.process_route_support import read_only_probe

_stage_fixture = stage_database


@pytest.mark.parametrize("mode", ("text", "rows"))
def test_route_reconfirmation_preserves_complete_old_rows_groups_and_manual_choices(stage_conn, mode):
    stage_conn.execute("UPDATE PartOperations SET op_type_id='PROC-Q',setup_hours=5.5,unit_hours=6.75 WHERE part_no='PROC-001' AND seq=10")
    stage_conn.commit()
    before_ops, before_groups, batches = op_rows(stage_conn), group_rows(stage_conn), downstream(stage_conn)
    payload = route_input(stage_conn)
    if mode == "rows":
        payload["route"] = {"mode": "rows", "rows": [{"seq": seq, "op_type_name": row["op_type_name"]} for seq, row in before_ops.items()]}
    refs = [op_ref(stage_conn, seq) for seq in before_ops]
    run_stage(stage_conn, "route_confirm", payload)
    assert op_rows(stage_conn) == before_ops and group_rows(stage_conn) == before_groups
    assert refs == [op_ref(stage_conn, seq) for seq in before_ops] and downstream(stage_conn) == batches
    assert read_workflow(stage_conn, "PROC-001")["source"]["state"] == "unconfirmed"


def test_unknown_new_operation_has_explicit_nulls_not_internal_or_one_day(stage_conn):
    before = op_rows(stage_conn)
    run_stage(stage_conn, "route_confirm", route_input(stage_conn, "10车削20热处理30检验40尚未建档"))
    after = op_rows(stage_conn)
    assert {seq: after[seq] for seq in before} == before
    assert [after[40][name] for name in ("op_type_id", "source", "supplier_id", "ext_days", "setup_hours", "unit_hours")] == [None] * 6
    assert read_workflow(stage_conn, "PROC-001")["stage"] == "source"
    states = operation_confirmations(stage_conn, "PROC-001")
    assert states[op_ref(stage_conn, 40)]["source"]["state"] == "unconfirmed"
    stage_conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('NEW','尚未建档','internal')")
    stage_conn.commit()
    payload = source_input(stage_conn)
    # Fill the explicit binding after the independent resource-create command.
    payload["operations"][-1].update(source="internal", op_type_ref=ref_for(stage_conn, "op_type", "NEW"), supplier_ref=None)
    run_stage(stage_conn, "source_confirm", payload, key=KEY + "-bind")
    assert op_rows(stage_conn)[40]["op_type_id"] == "NEW"


@pytest.mark.parametrize("text", ("10车削20热处理30检验40数控", "10车削20热处理30检验40热处理"))
def test_only_new_operations_receive_preview_suggestions_with_null_internal_hours(stage_conn, text):
    if "数控" in text:
        stage_conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('CNC','数控','internal')")
        stage_conn.commit()
    before = op_rows(stage_conn)
    run_stage(stage_conn, "route_confirm", route_input(stage_conn, text))
    after = op_rows(stage_conn)
    assert {seq: after[seq] for seq in before} == before
    assert after[40]["setup_hours"] is None and after[40]["unit_hours"] is None
    assert after[40]["source"] == ("internal" if "数控" in text else "external")


@pytest.mark.parametrize("change", ("remove", "rename", "insert_in_range", "restore"))
def test_group_impact_is_readonly_and_exact_ack_is_required(stage_conn, change):
    if change in ("insert_in_range", "restore"):
        stage_conn.execute("UPDATE ExternalGroups SET end_seq=25 WHERE group_id='PROC-G'")
    if change == "restore":
        stage_conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,status,ext_group_id) VALUES ('PROC-001',25,'历史','external','deleted','PROC-G')")
    stage_conn.commit()
    text = {"remove": "10车削30检验", "rename": "10车削20改名30检验", "insert_in_range": "10车削20热处理25新序30检验", "restore": "10车削20热处理25历史30检验"}[change]
    payload = route_input(stage_conn, text)
    del payload["discard_group_refs"]
    before = storage(stage_conn)
    service = WorkbenchProcessMutationService(stage_conn)
    with read_only_probe(stage_conn):
        affected = service.affected_groups("route_confirm", payload, identity_for(stage_conn))
    assert affected == [ref_for(stage_conn, "template_external_group", "PROC-G")] and storage(stage_conn) == before
    for acknowledgement in ([], ["a" * 48], affected + ["a" * 48], affected * 2):
        with pytest.raises(WorkbenchCommandRejected):
            run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": acknowledgement})
        assert storage(stage_conn) == before
    old, old_ref = op_rows(stage_conn), op_ref(stage_conn, 20)
    run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": affected})
    assert group_rows(stage_conn) == {}
    assert op_rows(stage_conn)[20] == {**old[20], "ext_group_id": None,
        **({"status": "deleted"} if change == "remove" else {"op_type_name": "改名"} if change == "rename" else {})}
    assert op_ref(stage_conn, 20) == old_ref


def test_renamed_internal_sequence_updates_only_name_retains_old_choices(stage_conn):
    before, ref = op_rows(stage_conn), op_ref(stage_conn)
    run_stage(stage_conn, "route_confirm", route_input(stage_conn, "10新名字20热处理30检验"))
    assert op_rows(stage_conn) == {**before, 10: {**before[10], "op_type_name": "新名字"}}
    assert op_ref(stage_conn) == ref


def test_deleted_same_sequence_restores_same_row_but_not_old_confirmations(stage_conn):
    # Keep this test independent of the merged-cycle confirmation contract.
    stage_conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    stage_conn.commit()
    prepare_stages(stage_conn)
    run_stage(stage_conn, "hours_confirm", hours_input(stage_conn), key=KEY + "-hours")
    original, ref = op_rows(stage_conn)[30], op_ref(stage_conn, 30)
    run_stage(stage_conn, "route_confirm", route_input(stage_conn, "10车削20热处理"), key=KEY + "-remove")
    assert op_rows(stage_conn)[30] == {**original, "status": "deleted"}
    run_stage(stage_conn, "route_confirm", route_input(stage_conn, "10车削20热处理30检验"), key=KEY + "-restore")
    assert op_rows(stage_conn)[30] == original and op_ref(stage_conn, 30) == ref
    assert not read_workflow(stage_conn, "PROC-001")["ready"]
    assert operation_confirmations(stage_conn, "PROC-001")[ref]["source"]["state"] == "unconfirmed"


def test_route_confirmation_does_not_rewrite_existing_valid_confirmation_rows(stage_conn):
    prepare_stages(stage_conn)
    refs = tuple(tuple(row) for row in stage_conn.execute("SELECT * FROM WorkbenchProcessOperationConfirmations ORDER BY operation_ref,stage"))
    before_ops, before_groups = op_rows(stage_conn), group_rows(stage_conn)
    run_stage(stage_conn, "route_confirm", route_input(stage_conn))
    assert tuple(tuple(row) for row in stage_conn.execute("SELECT * FROM WorkbenchProcessOperationConfirmations ORDER BY operation_ref,stage")) == refs
    assert op_rows(stage_conn) == before_ops and group_rows(stage_conn) == before_groups


def test_ack_cannot_discard_an_unaffected_group(stage_conn):
    payload = route_input(stage_conn)
    payload["discard_group_refs"] = [ref_for(stage_conn, "template_external_group", "PROC-G")]
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "route_confirm", payload)
    assert exc.value.code == "group_discard_required" and storage(stage_conn) == before


@pytest.mark.parametrize("damage", ("missing_ref", "foreign_group", "cross_part_member", "bad_range", "bad_status"))
def test_broken_legacy_template_fails_closed_without_repair(stage_conn, damage):
    if damage == "missing_ref":
        stage_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref=?", (op_ref(stage_conn),))
    elif damage == "foreign_group":
        stage_conn.execute("UPDATE ExternalGroups SET part_no='PROC-002' WHERE group_id='PROC-G'")
    elif damage == "cross_part_member":
        stage_conn.execute("UPDATE PartOperations SET ext_group_id='PROC-G' WHERE part_no='PROC-003'")
    elif damage == "bad_range":
        stage_conn.execute("UPDATE ExternalGroups SET start_seq=30 WHERE group_id='PROC-G'")
    else:
        stage_conn.execute("UPDATE PartOperations SET status=NULL WHERE part_no='PROC-001' AND seq=10")
    stage_conn.commit()
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "route_confirm", route_input(stage_conn))
    assert storage(stage_conn) == before


@pytest.mark.parametrize("route", ({"mode": "text", "route_raw": "10车削10检验"},
                                  {"mode": "text", "route_raw": "10车削20"},
                                  {"mode": "rows", "rows": [{"seq": True, "op_type_name": "车削"}]},
                                  {"mode": "text", "route_raw": "10车削", "unknown": 1}))
def test_bad_routes_never_mutate_existing_template(stage_conn, route):
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "route_confirm", {"route": route})
    assert storage(stage_conn) == before


def test_normalize_preserves_raw_spaces_and_owns_its_input_copy(stage_conn):
    payload = route_input(stage_conn, " 10车削 ; 20热处理\n30检验 ")
    original = deepcopy(payload)
    normalized = WorkbenchProcessMutationService.normalize("route_confirm", payload)
    assert payload == original == normalized
    payload["route"]["route_raw"] = "changed"
    assert normalized == original
    run_stage(stage_conn, "route_confirm", original)
    assert stage_conn.execute("SELECT route_raw FROM Parts WHERE part_no='PROC-001'").fetchone()[0] == original["route"]["route_raw"]


def test_structured_english_numeric_and_separator_names_persist_without_text_reparse(stage_conn):
    names = [(10, "Heat treatment"), (20, "CNC3"), (30, "Paint; coat"), (9007199254740993, "Grind / inspect")]
    stage_conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,'internal')",
                          [("ROW-TYPE-" + str(index), name) for index, (_, name) in enumerate(names)])
    stage_conn.commit()
    payload = {"route": {"mode": "rows", "rows": [{"seq": seq, "op_type_name": name} for seq, name in names]}}
    normalized = WorkbenchProcessMutationService.normalize("route_confirm", payload)
    assert normalized["route"] == payload["route"]
    identity = identity_for(stage_conn, "PROC-002")
    run_stage(stage_conn, "route_confirm", payload, identity=identity)
    before = op_rows(stage_conn, "PROC-002")
    refs = {seq: op_ref(stage_conn, seq, "PROC-002") for seq, _ in names}
    assert [(seq, row["op_type_name"]) for seq, row in before.items()] == names
    assert all(row["op_type_id"] == "ROW-TYPE-" + str(index) for index, row in enumerate(before.values()))
    run_stage(stage_conn, "route_confirm", payload, identity=identity_for(stage_conn, "PROC-002"), key=KEY + "-rows-repeat")
    assert op_rows(stage_conn, "PROC-002") == before
    assert {seq: op_ref(stage_conn, seq, "PROC-002") for seq, _ in names} == refs
