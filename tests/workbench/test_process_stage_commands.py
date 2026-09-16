"""Stage inputs, real command atomicity, resource choices and independent cycles."""

from copy import deepcopy
from dataclasses import replace

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.process.workflow_state import read_workflow, record_confirmation
from core.services.workbench.commands import WorkbenchCommandService
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
    scale_inputs,
    seed_stage_scale,
    source_input,
    stage_database,
    storage,
)
from tests.workbench.process_route_support import read_only_probe

_stage_fixture = stage_database


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm"))
def test_requires_outer_transaction(stage_conn, action):
    with pytest.raises(RuntimeError, match="BEGIN IMMEDIATE"):
        WorkbenchProcessMutationService(stage_conn).apply(action, {}, identity_for(stage_conn))


@pytest.mark.parametrize("bad", (None, "P1", {}, "kind", "inactive", "key", "revision"))
def test_rechecks_identity_and_rejects_without_writes(stage_conn, bad):
    identity = identity_for(stage_conn)
    if isinstance(bad, str) and bad in ("kind", "inactive", "key", "revision"):
        identity = replace(identity, **{"kind": {"kind": "supplier"}, "inactive": {"active": False},
                                      "key": {"entity_key": "PROC-002"}, "revision": {"revision": 0}}[bad])
    else:
        identity = bad
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected):
        with TransactionManager(stage_conn).transaction(begin_immediate=True):
            WorkbenchProcessMutationService(stage_conn).apply("route_confirm", route_input(stage_conn), identity)
    assert storage(stage_conn) == before


@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
def test_stage_cannot_skip_previous_confirmation(stage_conn, action):
    before = storage(stage_conn)
    payload = source_input(stage_conn) if action == "source_confirm" else hours_input(stage_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, action, payload)
    assert exc.value.code == "stage_not_ready" and storage(stage_conn) == before


@pytest.mark.parametrize("change", ("missing", "duplicate", "foreign", "deleted", "bad_ref", "wrong_kind"))
@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
def test_requires_exact_active_operation_set(stage_conn, action, change):
    prepare_stages(stage_conn)
    payload = source_input(stage_conn) if action == "source_confirm" else hours_input(stage_conn)
    if change == "missing":
        payload["operations"].pop()
    elif change == "duplicate":
        payload["operations"].append(dict(payload["operations"][0]))
    else:
        payload["operations"][0]["ref"] = {"foreign": op_ref(stage_conn, 10, "PROC-003"),
            "deleted": op_ref(stage_conn, 10, "PROC-004"), "bad_ref": "z" * 48,
            "wrong_kind": ref_for(stage_conn, "op_type", "PROC-IN")}[change]
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, action, payload)
    assert storage(stage_conn) == before


@pytest.mark.parametrize("field", ("setup_hours", "unit_hours", "external_days", "total_days"))
@pytest.mark.parametrize("bad", (None, "", "0", True, False, float("nan"), float("inf"), -1, 10 ** 500))
def test_invalid_numbers_cannot_be_normalized(stage_conn, field, bad):
    payload = hours_input(stage_conn)
    row = payload["groups"][0] if field == "total_days" else next(item for item in payload["operations"] if field in item)
    row[field] = bad
    if field == "external_days" and bad is None:
        normalized = WorkbenchProcessMutationService.normalize("hours_confirm", payload)
        assert next(item for item in normalized["operations"] if "external_days" in item)[field] is None
        return
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchProcessMutationService.normalize("hours_confirm", payload)


def test_zero_hours_need_explicit_unit_review_but_setup_zero_is_normal(stage_conn):
    payload = hours_input(stage_conn)
    payload["confirm_zero_unit_hours"] = False
    prepare_stages(stage_conn)
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "hours_confirm", payload)
    assert exc.value.code == "zero_unit_hours_confirmation_required"
    assert exc.value.operation_refs and storage(stage_conn) == before
    for row in payload["operations"]:
        if "unit_hours" in row:
            row.update(setup_hours=0, unit_hours=1)
    assert WorkbenchProcessMutationService.normalize("hours_confirm", payload)["confirm_zero_unit_hours"] is False
    for field, row in (("external_days", payload["operations"][1]), ("total_days", payload["groups"][0])):
        bad = deepcopy(payload)
        (bad["groups"][0] if field == "total_days" else bad["operations"][1])[field] = 0
        with pytest.raises(WorkbenchCommandRejected):
            WorkbenchProcessMutationService.normalize("hours_confirm", bad)


@pytest.mark.parametrize("location", ("top", "operation", "group"))
def test_unknown_hours_fields_reject(stage_conn, location):
    payload = hours_input(stage_conn)
    row = {"top": payload, "operation": payload["operations"][0], "group": payload["groups"][0]}[location]
    row["unexpected"] = 1
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchProcessMutationService.normalize("hours_confirm", payload)


@pytest.mark.parametrize("change", ("category", "supplier", "inactive", "incapable", "profile", "confirmed", "unknown", "type_kind"))
def test_source_preview_and_apply_share_basic_validation(stage_conn, change):
    prepare_stages(stage_conn, source=False)
    payload = source_input(stage_conn)
    row = payload["operations"][1]
    if change == "category":
        row.update(source="internal", supplier_ref=None)
    elif change == "supplier":
        payload["operations"][0]["supplier_ref"] = row["supplier_ref"]
    elif change in ("inactive", "incapable"):
        stage_conn.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S'" if change == "inactive" else "DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='PROC-S'")
        if change == "incapable":
            stage_conn.execute("UPDATE Suppliers SET op_type_id=NULL WHERE supplier_id='PROC-S'")
        stage_conn.commit()
    elif change == "profile":
        stage_conn.execute("INSERT INTO WorkbenchSupplierProfiles(supplier_id,inactive_reason) VALUES ('PROC-S','disabled')")
        stage_conn.commit()
    elif change == "confirmed":
        row["confirmed"] = 1
    elif change == "unknown":
        row["unexpected"] = None
    else:
        row["op_type_ref"] = row["supplier_ref"]
    before = storage(stage_conn)
    service = WorkbenchProcessMutationService(stage_conn)
    with read_only_probe(stage_conn), pytest.raises(WorkbenchCommandRejected):
        service.affected_groups("source_confirm", payload, identity_for(stage_conn))
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "source_confirm", payload)
    assert storage(stage_conn) == before


def test_source_changes_only_selected_fields_never_global_category_or_hours(stage_conn):
    prepare_stages(stage_conn, source=False)
    before_ops, before_groups, batches = op_rows(stage_conn), group_rows(stage_conn), downstream(stage_conn)
    payload = source_input(stage_conn)
    payload["operations"][1].update(source="internal", op_type_ref=ref_for(stage_conn, "op_type", "PROC-IN"), supplier_ref=None)
    del payload["discard_group_refs"]
    service = WorkbenchProcessMutationService(stage_conn)
    before = storage(stage_conn)
    with read_only_probe(stage_conn):
        affected = service.affected_groups("source_confirm", payload, identity_for(stage_conn))
    assert affected == [ref_for(stage_conn, "template_external_group", "PROC-G")] and storage(stage_conn) == before
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "source_confirm", payload)
    assert exc.value.code == "group_discard_required" and storage(stage_conn) == before
    payload["discard_group_refs"] = affected
    run_stage(stage_conn, "source_confirm", payload)
    assert op_rows(stage_conn) == {**before_ops, 20: {**before_ops[20], "source": "internal", "op_type_id": "PROC-IN", "supplier_id": None, "ext_group_id": None}}
    assert before_groups and group_rows(stage_conn) == {} and downstream(stage_conn) == batches
    assert stage_conn.execute("SELECT category FROM OpTypes WHERE op_type_id='PROC-EX'").fetchone()[0] == "external"


def test_supplier_capabilities_use_legacy_and_explicit_union(stage_conn):
    prepare_stages(stage_conn, source=False)
    payload = source_input(stage_conn)
    payload["operations"][1]["supplier_ref"] = ref_for(stage_conn, "supplier", "PROC-S2")
    payload["discard_group_refs"] = WorkbenchProcessMutationService(stage_conn).affected_groups("source_confirm", payload, identity_for(stage_conn))
    run_stage(stage_conn, "source_confirm", payload)
    assert op_rows(stage_conn)[20]["supplier_id"] == "PROC-S2"
    assert read_workflow(stage_conn, "PROC-001")["source"]["state"] == "confirmed"


def test_hours_keep_per_operation_and_merged_totals_independent(stage_conn):
    prepare_stages(stage_conn)
    before_ops, before_groups, batches = op_rows(stage_conn), group_rows(stage_conn), downstream(stage_conn)
    payload = hours_input(stage_conn)
    payload["operations"][0].update(setup_hours=0, unit_hours=2.125)
    payload["operations"][1]["external_days"] = 4.25
    payload["groups"][0]["total_days"] = 9.5
    run_stage(stage_conn, "hours_confirm", payload)
    assert op_rows(stage_conn) == {**before_ops, 10: {**before_ops[10], "setup_hours": 0, "unit_hours": 2.125},
                                  20: {**before_ops[20], "ext_days": 4.25}}
    assert group_rows(stage_conn) == {"PROC-G": {**before_groups["PROC-G"], "total_days": 9.5}}
    assert downstream(stage_conn) == batches and read_workflow(stage_conn, "PROC-001")["ready"]


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm"))
def test_receipt_failure_rolls_back_all_business_identities_and_confirmations(stage_conn, monkeypatch, action):
    prepare_stages(stage_conn)
    payload = {"route_confirm": route_input(stage_conn, "10车削20热处理30检验40新工种"),
               "source_confirm": source_input(stage_conn), "hours_confirm": hours_input(stage_conn)}[action]
    command = WorkbenchCommandService(stage_conn)
    original = command.repo.insert

    def fail(**kwargs):
        original(**kwargs)
        raise OSError("receipt failure after insert")

    monkeypatch.setattr(command.repo, "insert", fail)
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandUncertain):
        run_stage(stage_conn, action, payload, command=command)
    assert storage(stage_conn) == before and not stage_conn.in_transaction
    assert command.lookup(KEY) is None


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm"))
def test_committed_intent_replays_before_stale_identity_or_guard(stage_conn, action):
    prepare_stages(stage_conn)
    payload = {"route_confirm": route_input(stage_conn), "source_confirm": source_input(stage_conn),
               "hours_confirm": hours_input(stage_conn)}[action]
    identity = identity_for(stage_conn)
    first = run_stage(stage_conn, action, payload, identity=identity)
    stage_conn.execute("UPDATE Parts SET remark='changed after receipt' WHERE part_no='PROC-001'")
    stage_conn.commit()
    before = storage(stage_conn)

    def stale():
        pytest.fail("replay must happen before guard")

    second = run_stage(stage_conn, action, payload, identity=identity, guard=stale)
    assert second == {**first, "replayed": True} and storage(stage_conn) == before
    different = deepcopy(payload)
    if action == "route_confirm":
        different["route"]["route_raw"] += " "
    elif action == "source_confirm":
        different["operations"][0]["op_type_ref"] = ref_for(stage_conn, "op_type", "PROC-Q")
    else:
        different["operations"][0]["unit_hours"] = 7
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, action, different)
    assert exc.value.code == "request_key_conflict"


@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
def test_stage_input_accepts_10000_and_rejects_10001_without_truncation(action):
    rows = [{"ref": format(index, "048x"), **({"source": "internal", "op_type_ref": "a" * 48,
            "supplier_ref": None, "confirmed": True} if action == "source_confirm" else {"setup_hours": 0, "unit_hours": 1})}
            for index in range(10000)]
    payload = {"operations": rows, **({"discard_group_refs": []} if action == "source_confirm" else {"groups": [], "confirm_zero_unit_hours": False})}
    assert len(WorkbenchProcessMutationService.normalize(action, payload)["operations"]) == 10000
    rows.append({**rows[0], "ref": "b" * 48})
    with pytest.raises(WorkbenchCommandRejected) as exc:
        WorkbenchProcessMutationService.normalize(action, payload)
    assert exc.value.code == "stage_too_large" and exc.value.status == 413


@pytest.mark.parametrize("change", ("missing", "foreign", "duplicate", "wrong_shape"))
def test_hours_reject_bad_group_set_and_wrong_source_shape_before_writes(stage_conn, change):
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    if change == "missing":
        payload["groups"] = []
    elif change == "foreign":
        payload["groups"][0]["ref"] = "c" * 48
    elif change == "duplicate":
        payload["groups"].append(dict(payload["groups"][0]))
    else:
        payload["operations"][0] = {"ref": op_ref(stage_conn), "external_days": 1}
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "hours_confirm", payload)
    assert storage(stage_conn) == before


def test_separate_group_hidden_total_never_reset_by_hours(stage_conn):
    stage_conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    stage_conn.commit()
    prepare_stages(stage_conn)
    old = group_rows(stage_conn)
    payload = hours_input(stage_conn)
    assert payload["groups"] == []
    payload["operations"][1]["external_days"] = 8.5
    run_stage(stage_conn, "hours_confirm", payload)
    assert group_rows(stage_conn) == old and op_rows(stage_conn)[20]["ext_days"] == 8.5


def test_merged_group_with_only_total_days_accepts_null_member_cycle(stage_conn):
    stage_conn.execute("UPDATE PartOperations SET ext_days=NULL WHERE part_no='PROC-001' AND seq=20")
    stage_conn.commit()
    prepare_stages(stage_conn)
    before = op_rows(stage_conn)
    payload = hours_input(stage_conn)
    payload["groups"][0]["total_days"] = 12.5
    assert payload["operations"][1]["external_days"] is None
    run_stage(stage_conn, "hours_confirm", payload)
    assert op_rows(stage_conn) == before
    assert group_rows(stage_conn)["PROC-G"]["total_days"] == 12.5
    assert read_workflow(stage_conn, "PROC-001")["ready"]


@pytest.mark.parametrize("grouped", (True, False))
def test_null_external_days_rejects_for_separate_or_ungrouped_operation(stage_conn, grouped):
    stage_conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    if not grouped:
        stage_conn.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE part_no='PROC-001' AND seq=20")
    stage_conn.commit()
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    payload["operations"][1]["external_days"] = None
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "hours_confirm", payload)
    assert exc.value.code == "external_days_required" and storage(stage_conn) == before


@pytest.mark.parametrize("days", (None, 0, -1, "", True))
def test_null_merged_member_cycle_does_not_bypass_invalid_group_total(stage_conn, days):
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    payload["operations"][1]["external_days"] = None
    payload["groups"][0]["total_days"] = days
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "hours_confirm", payload)
    assert storage(stage_conn) == before


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm"))
def test_outer_failure_rolls_back_provisional_outcome_and_confirmation(stage_conn, action):
    stage_conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    stage_conn.commit()
    prepare_stages(stage_conn)
    payload = {"route_confirm": route_input(stage_conn, "10车削20热处理30检验40新增"),
               "source_confirm": source_input(stage_conn), "hours_confirm": hours_input(stage_conn)}[action]
    if action == "source_confirm":
        payload["operations"][0]["op_type_ref"] = ref_for(stage_conn, "op_type", "PROC-Q")
    before = storage(stage_conn)
    with pytest.raises(RuntimeError, match="outer failure"):
        with TransactionManager(stage_conn).transaction(begin_immediate=True):
            outcome = WorkbenchProcessMutationService(stage_conn).apply(action, payload, identity_for(stage_conn))
            assert outcome.result == "committed" and stage_conn.in_transaction
            raise RuntimeError("outer failure")
    assert storage(stage_conn) == before


def test_unchanged_group_stays_byte_for_byte_when_another_group_is_discarded(stage_conn):
    stage_conn.execute("""INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,remark)
        VALUES ('OTHER-G','PROC-001',40,40,'separate',47.5,' untouched ')""")
    stage_conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,supplier_id,ext_days,ext_group_id)
        VALUES ('PROC-001',40,'热处理','PROC-EX','external','PROC-S',2.5,'OTHER-G')""")
    stage_conn.execute("UPDATE Parts SET route_raw=route_raw||'40热处理' WHERE part_no='PROC-001'")
    stage_conn.commit()
    prepare_stages(stage_conn, source=False)
    before, unchanged_ref = group_rows(stage_conn), ref_for(stage_conn, "template_external_group", "OTHER-G")
    payload = source_input(stage_conn)
    payload["operations"][1]["supplier_ref"] = ref_for(stage_conn, "supplier", "PROC-S2")
    affected = WorkbenchProcessMutationService(stage_conn).affected_groups("source_confirm", payload, identity_for(stage_conn))
    assert unchanged_ref not in affected
    payload["discard_group_refs"] = affected
    run_stage(stage_conn, "source_confirm", payload)
    assert group_rows(stage_conn) == {"OTHER-G": before["OTHER-G"]}


def test_10000_existing_operations_can_confirm_source_and_hours_without_truncation(stage_conn):
    seed_stage_scale(stage_conn, 10000)
    # Seed an explicitly confirmed legacy route; route parsing retains its 2000-input cap.
    with TransactionManager(stage_conn).transaction(begin_immediate=True):
        record_confirmation(stage_conn, "SCALE", "route")
    source, hours = scale_inputs(stage_conn)
    assert len(source["operations"]) == len(hours["operations"]) == 10000
    identity = identity_for(stage_conn, "SCALE")
    service = WorkbenchProcessMutationService(stage_conn)
    with read_only_probe(stage_conn):
        assert service.affected_groups("source_confirm", source, identity) == []
    run_stage(stage_conn, "source_confirm", source, identity=identity, key=KEY + "-large-source")
    run_stage(stage_conn, "hours_confirm", hours, identity=identity, key=KEY + "-large-hours")
    assert stage_conn.execute("SELECT COUNT(*) FROM PartOperations WHERE part_no='SCALE' AND unit_hours=2").fetchone()[0] == 10000
    assert read_workflow(stage_conn, "SCALE")["ready"]


@pytest.mark.parametrize("action", ("route_confirm", "source_confirm", "hours_confirm"))
def test_first_confirmation_only_writes_metadata_and_repeat_retains_stamps(stage_conn, action):
    if action != "route_confirm":
        prepare_stages(stage_conn, source=action == "hours_confirm")
    payload = {"route_confirm": route_input(stage_conn), "source_confirm": source_input(stage_conn),
               "hours_confirm": hours_input(stage_conn)}[action]
    before_rows = op_rows(stage_conn), group_rows(stage_conn)
    refs = tuple(tuple(row) for row in stage_conn.execute("SELECT * FROM WorkbenchEntityRefs ORDER BY ref"))
    statements = []
    stage_conn.set_trace_callback(statements.append)
    try:
        first = run_stage(stage_conn, action, payload)
        confirmed = read_workflow(stage_conn, "PROC-001")
        second = run_stage(stage_conn, action, payload, key=KEY + "-identical")
        repeated = read_workflow(stage_conn, "PROC-001")
    finally:
        stage_conn.set_trace_callback(None)
    assert first["result"] == "committed" and second["result"] == "unchanged"
    assert not any(sql.lstrip().upper().startswith(("UPDATE PARTOPERATIONS ", "UPDATE EXTERNALGROUPS ", "UPDATE PARTS ")) for sql in statements)
    assert confirmed == repeated and (op_rows(stage_conn), group_rows(stage_conn)) == before_rows
    assert tuple(tuple(row) for row in stage_conn.execute("SELECT * FROM WorkbenchEntityRefs ORDER BY ref")) == refs


@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
def test_only_the_changed_operation_advances_its_identity_revision(stage_conn, action):
    prepare_stages(stage_conn)
    refs = {row["ref"]: row["revision"] for row in stage_conn.execute("SELECT ref,revision FROM WorkbenchEntityRefs WHERE kind='template_operation'")}
    payload = source_input(stage_conn) if action == "source_confirm" else hours_input(stage_conn)
    if action == "source_confirm":
        payload["operations"][0]["op_type_ref"] = ref_for(stage_conn, "op_type", "PROC-Q")
    else:
        payload["operations"][0]["unit_hours"] = 2.5
    changed = payload["operations"][0]["ref"]
    assert run_stage(stage_conn, action, payload)["result"] == "committed"
    after = {row["ref"]: row["revision"] for row in stage_conn.execute("SELECT ref,revision FROM WorkbenchEntityRefs WHERE kind='template_operation'")}
    assert after == {ref: revision + (ref == changed) for ref, revision in refs.items()}


def test_bulk_fixture_inputs_have_bounded_queries_and_preserve_all_rows(stage_conn):
    seed_stage_scale(stage_conn, 250)
    with read_only_probe(stage_conn) as statements:
        source, hours = source_input(stage_conn, "SCALE"), hours_input(stage_conn, "SCALE")
    assert len(source["operations"]) == len(hours["operations"]) == 250
    assert len(statements) <= 5
    assert [row["ref"] for row in source["operations"]] == [row["ref"] for row in hours["operations"]]


@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
def test_noop_skips_reconfirmation_but_first_and_invalidated_stages_record(stage_conn, monkeypatch, action):
    import core.services.process.workflow_state as workflow_state

    prepare_stages(stage_conn, source=action == "hours_confirm")
    original, calls = workflow_state.record_confirmation, []

    def recording(*args, **kwargs):
        calls.append(args[2])
        return original(*args, **kwargs)

    monkeypatch.setattr(workflow_state, "record_confirmation", recording)
    make_input = source_input if action == "source_confirm" else hours_input
    payload = make_input(stage_conn)
    assert run_stage(stage_conn, action, payload)["result"] == "committed"
    confirmed = read_workflow(stage_conn, "PROC-001")
    statements = []
    stage_conn.set_trace_callback(statements.append)
    try:
        assert run_stage(stage_conn, action, payload, key=KEY + "-noop")["result"] == "unchanged"
    finally:
        stage_conn.set_trace_callback(None)
    assert calls == [action[:-len("_confirm")]]
    assert confirmed == read_workflow(stage_conn, "PROC-001")
    assert not any("WORKBENCHPROCESS" in sql.upper() and sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
    if action == "source_confirm":
        stage_conn.execute("UPDATE OpTypes SET name='reconfirmed-name' WHERE op_type_id='PROC-IN'")
    else:
        stage_conn.execute("UPDATE PartOperations SET unit_hours=2.5 WHERE part_no='PROC-001' AND seq=10")
    stage_conn.commit()
    assert run_stage(stage_conn, action, make_input(stage_conn), key=KEY + "-changed-facts")["result"] == "committed"
    assert calls == [action[:-len("_confirm")]] * 2


def test_unchanged_confirmed_zero_does_not_require_another_acknowledgement(stage_conn):
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    run_stage(stage_conn, "hours_confirm", payload, key=KEY + "-zero-first")
    payload["confirm_zero_unit_hours"] = False
    before = storage(stage_conn)
    with TransactionManager(stage_conn).transaction(begin_immediate=True):
        outcome = WorkbenchProcessMutationService(stage_conn).apply("hours_confirm", payload, identity_for(stage_conn))
    assert outcome.result == "unchanged" and storage(stage_conn) == before
    zero = next(row for row in payload["operations"] if row.get("unit_hours") == 0)
    zero["setup_hours"] += 1
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "hours_confirm", payload, key=KEY + "-changed-zero")
    assert exc.value.code == "zero_unit_hours_confirmation_required"
    assert storage(stage_conn) == before
    payload["confirm_zero_unit_hours"] = True
    run_stage(stage_conn, "hours_confirm", payload, key=KEY + "-changed-zero-ack")
    assert read_workflow(stage_conn, "PROC-001")["ready"]
