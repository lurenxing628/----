"""Reject uncertain inputs without converting missing values into valid data."""

from dataclasses import replace
from datetime import timedelta

import pytest

from core.infrastructure.errors import ValidationError
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.workbench.run_compute import compute_candidate_run, compute_prepared_candidate_run
from core.services.workbench.run_input import prepare_candidate_run_input
from core.services.workbench.run_input_rows import batch_model
from tests.workbench.test_run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.test_run_compute_support import unchanged


@pytest.mark.parametrize("table,field,value,reason", [
    ("Batches", "quantity", None, "quantity_unknown"),
    ("Batches", "quantity", 1.5, "quantity_unknown"),
    ("Batches", "quantity", -1, "quantity_unknown"),
    ("Batches", "quantity", float("inf"), "quantity_unknown"),
    ("Batches", "status", None, "invalid_batch_state"),
    ("Batches", "status", "unknown", "invalid_batch_state"),
    ("Batches", "priority", None, "invalid_batch_state"),
    ("Batches", "ready_status", None, "invalid_ready_status"),
    ("Batches", "due_date", "2026-02-30", "invalid_batch_date"),
    ("BatchOperations", "setup_hours", None, "hours_missing"),
    ("BatchOperations", "setup_hours", -0.1, "hours_missing"),
    ("BatchOperations", "setup_hours", float("inf"), "hours_missing"),
    ("BatchOperations", "unit_hours", None, "hours_missing"),
    ("BatchOperations", "unit_hours", "unknown", "hours_missing"),
    ("BatchOperations", "unit_hours", float("nan"), "hours_missing"),
    ("BatchOperations", "unit_hours", -0.1, "hours_missing"),
    ("BatchOperations", "unit_hours", float("inf"), "hours_missing"),
    ("BatchOperations", "source", None, "invalid_operation_state"),
    ("BatchOperations", "status", None, "invalid_operation_state"),
    ("BatchOperations", "seq", 0, "invalid_operation_identity"),
])
def test_invalid_stored_fields_fail_before_dispatch(run_case, table, field, value, reason):
    case = run_case
    # Older SQLite schemas permit these raw unknown values; they must stay unknown.
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    if table == "Batches" and field == "quantity" and value is None:
        raw = dict(case.conn.execute("SELECT * FROM Batches").fetchone())
        raw[field] = value
        action = lambda: batch_model(raw)
    else:
        case.conn.execute("UPDATE " + table + " SET " + field + "=?", (value,))
        case.conn.commit()
        action = lambda: prepare_candidate_run_input(case.conn, case.settings(), [])
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, action)
    assert error.value.reason == reason


def test_zero_hours_preserved_but_existing_payload_rejects_instant_work(run_case):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0")
    case.conn.commit()
    prepared = unchanged(case, lambda: prepare_candidate_run_input(case.conn, case.settings(), case.projections()))
    assert prepared.operations[0].unit_hours == prepared.operations[0].setup_hours == 0
    result = unchanged(case, lambda: compute_prepared_candidate_run(case.conn, prepared))
    assert result.state == "complete" and result.result_persisted is False
    assert len(result.candidate_payloads) == 4
    disposition, = result.dispositions
    assert disposition["op_id"] == case.op_id and disposition["status"] == "eligible"
    assert disposition["operation_ref"] == case.projections()[0].operation_ref
    for payload in result.candidate_payloads.values():
        point, = payload.schedule_rows
        assert point.op_id == case.op_id and payload.scheduled_op_ids == {case.op_id}
        assert point.start_time == point.end_time
        assert (point.machine_id, point.operator_id) == ("M1", "O1")
        # Workbench supplies evidence explicitly; legacy callers do not inherit it.
        with pytest.raises(ValidationError) as error:
            unchanged(case, lambda: build_validated_schedule_payload(payload.schedule_rows,
                operations=prepared.operations, allowed_op_ids={case.op_id}))
        assert error.value.details["reason"] == "no_actionable_schedule_rows"
        assert any("without verified point evidence" in item for item in error.value.details["validation_errors"])


def test_zero_quantity_is_excluded_without_becoming_missing(run_case):
    case = run_case
    # The original exclusion contract remains valid for external work only.
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Heat treatment','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','EXT')")
    case.conn.execute("UPDATE Batches SET quantity=0")
    case.conn.execute("""UPDATE BatchOperations SET source='external',op_type_id='EXT',
        op_type_name='Heat treatment',supplier_id='S1',ext_days=1,machine_id=NULL,operator_id=NULL""")
    case.batch("B2")
    other = case.operation("B2")
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings("B1", "B2"), case.projections()))
    assert result.schedule_input.batches["B1"].quantity == 0
    assert result.state == "partial" and result.result_persisted is False
    zero = next(row for row in result.dispositions if row["op_id"] == case.op_id)
    assert zero["status"] == "skipped" and [item["code"] for item in zero["issues"]] == ["zero_quantity"]
    assert zero["execution"]["target_quantity"] == zero["execution"]["remaining_quantity"] == 0
    assert len(result.candidate_payloads) == 4
    assert all(payload.scheduled_op_ids == {other} and len(payload.schedule_rows) == 1
               for payload in result.candidate_payloads.values())


@pytest.mark.parametrize("setup", [0, 2])
def test_zero_quantity_keeps_exact_work_without_becoming_missing(run_case, setup):
    case = run_case
    case.conn.execute("UPDATE Batches SET quantity=0")
    case.conn.execute("UPDATE BatchOperations SET setup_hours=?,unit_hours=7", (setup,))
    case.batch("B2")
    op = case.operation("B2")
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings("B1", "B2"), case.projections()))
    assert result.schedule_input.batches["B1"].quantity == 0
    assert result.state == "complete" and result.result_persisted is False
    assert len(result.candidate_payloads) == 4
    zero = next(row for row in result.dispositions if row["op_id"] == case.op_id)
    assert zero["status"] == "eligible" and zero["issues"] == []
    assert zero["execution"]["target_quantity"] == zero["execution"]["remaining_quantity"] == 0
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == {case.op_id, op} and len(payload.schedule_rows) == 2
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert rows[case.op_id].end_time - rows[case.op_id].start_time == timedelta(hours=setup)
        assert rows[op].end_time - rows[op].start_time == timedelta(minutes=45)


@pytest.mark.parametrize("setup,unit,quantity", [(-1, 1, 1), (1, -1, 1), (0, -1, 0),
                                               (0, None, 0), (None, 0, 0), (0, float("inf"), 0)])
def test_zero_total_never_hides_negative_or_unknown_hour_operands(run_case, setup, unit, quantity):
    case = run_case
    case.conn.execute("PRAGMA ignore_check_constraints=ON")
    case.conn.execute("UPDATE Batches SET quantity=?", (quantity,))
    case.conn.execute("UPDATE BatchOperations SET setup_hours=?,unit_hours=?", (setup, unit))
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "hours_missing"
    assert error.value.can_adopt is False and error.value.result_persisted is False
    assert error.value.issues[0]["op_id"] == case.op_id


@pytest.mark.parametrize("kind", ["empty", "duplicate", "dict", "foreign"])
def test_projection_contract_is_exact(run_case, kind):
    case = run_case
    projections = case.projections()
    if kind == "empty":
        projections = []
    elif kind == "duplicate":
        projections *= 2
    elif kind == "dict":
        projections = [row.to_dict() for row in projections]
    else:
        projections.append(replace(projections[0], operation_ref="f" * 48))
    with pytest.raises(CandidateRunInputError):
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))


def test_empty_and_stale_scope_never_expand_to_all_batches(run_case):
    case = run_case
    with pytest.raises(CandidateRunInputError, match="empty"):
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(batch_refs=[]), []))
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.5")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_prepared_candidate_run(case.conn, prepared))
    assert error.value.reason == "candidate_input_stale"


def test_first_multi_piece_counterexample_rejects_cross_piece_edge(run_case):
    from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
    from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch
    from core.services.scheduler.run.schedule_input_builder import build_algo_operations
    from core.services.scheduler.schedule_service import ScheduleService
    from core.services.workbench.run_input_rows import operation_model

    case = run_case
    case.conn.execute("UPDATE BatchOperations SET piece_id='piece-a'")
    case.operation(seq=2, piece_id="piece-b")
    case.conn.commit()
    operations = [operation_model(dict(row)) for row in case.conn.execute("SELECT * FROM BatchOperations ORDER BY seq")]
    batch = batch_model(dict(case.conn.execute("SELECT * FROM Batches").fetchone()))
    algo_ops = build_algo_operations(ScheduleService(case.conn), operations, strict_mode=True)
    nodes = build_operation_nodes_from_rows(algo_ops, batches={"B1": batch})
    edges = build_linear_edges_by_batch(nodes)
    assert operations[0].piece_id != operations[1].piece_id
    assert len(edges) == 1
    assert (edges[0].from_node_id, edges[0].to_node_id) == (nodes[0].node_id, nodes[1].node_id)
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: prepare_candidate_run_input(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "piece_scope_incomplete"
    assert error.value.issues[0]["batch_id"] == "B1"


@pytest.mark.parametrize("field,value", [("records_complete", 0), ("remaining_quantity", False),
                                          ("data_quality", None), ("execution_state", "scheduled")])
def test_unknown_projection_types_and_states_are_not_defaulted(run_case, field, value):
    case = run_case
    projections = [replace(case.projections()[0], **{field: value})]
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), projections))
    assert error.value.reason == "execution_projection_type"
