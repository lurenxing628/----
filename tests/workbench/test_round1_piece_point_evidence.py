"""Exact original identity/target witnesses and fail-closed legacy precision."""

from copy import deepcopy

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.plan_point_evidence import official_point_work
from core.services.workbench.zero_duration import PointEventError
from core.services.workbench.zero_duration_evidence import point_basis, trial_point_evidence, work_point_evidence
from tests.workbench.ea_zero_duration_support import adoption_service
from tests.workbench.round1_piece_point_support import adopt, candidate, layout, managed_run, workspace
from tests.workbench.round1_piece_point_support import point_case as point_case
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case


def point_work(case):
    ids = layout(case)
    ref = candidate(case)
    plan = adopt(case, ref)["data"]["official_plan"]
    work = official_point_work(case.conn, plan["version"])[ids["item-A", 50]]
    return ids, ref, plan, work


@pytest.mark.parametrize("piece", (None, "item-A"))
def test_frozen_point_missing_execution_is_a_typed_rejection(point_case, piece):
    case = point_case
    ids = layout(case, mixed=False)
    plan = adopt(case, candidate(case))["data"]["official_plan"]
    work = official_point_work(case.conn, plan["version"])[ids[piece, 40 if piece is None else 50]]
    original = {key: work[key] for key in ("operation", "batch", "execution")}
    original.update(point_basis=point_basis(work), arrangement={}, execution=None)
    with pytest.raises(PointEventError) as caught:
        trial_point_evidence(original)
    assert caught.value.code == "point_identity_unproven"


@pytest.mark.parametrize("value", (True, 1.0, 3))
def test_piece_basis_quantity_retains_exact_integer_type(point_case, value):
    _, _, _, work = point_work(point_case)
    original = {key: work[key] for key in ("operation", "batch", "execution")}
    at = work["witness"].at.isoformat()
    original["arrangement"] = {"machine_id": "M1", "operator_id": "O1", "start": at, "end": at}
    original["point_basis"] = dict(point_basis(work), quantity=value)
    with pytest.raises(PointEventError) as caught:
        trial_point_evidence(original)
    assert caught.value.code == "point_evidence_invalid"


@pytest.mark.parametrize("field,value", (("target_quantity", 3), ("target_quantity", True),
    ("target_quantity", 1.0), ("target_basis", "batch"), ("operation_ref", "0" * 48)))
def test_piece_witness_rejects_other_target_or_operation(point_case, field, value):
    _, _, _, work = point_work(point_case)
    execution = dict(work["execution"], **{field: value})
    at = work["witness"].at.isoformat()
    payload = {"op_id": work["operation"]["id"], "source": "internal", "machine_id": "M1",
               "operator_id": "O1", "start_time": at, "end_time": at}
    with pytest.raises(PointEventError):
        work_point_evidence(work["operation"], work["batch"], execution, payload,
                            operation_ref=work["execution"]["operation_ref"])


@pytest.mark.parametrize("field,value", (("piece_id", "item-B"), ("id", 999999),
                                        ("setup_hours", 1), ("unit_hours", 5e-324)))
def test_frozen_piece_basis_cannot_be_rebound_or_rounded(point_case, field, value):
    _, _, _, work = point_work(point_case)
    at = work["witness"].at.isoformat()
    original = {key: deepcopy(work[key]) for key in ("operation", "batch", "execution")}
    original["point_basis"] = point_basis(work)
    original["arrangement"] = {"machine_id": "M1", "operator_id": "O1", "start": at, "end": at}
    assert trial_point_evidence(original).quantity == 1
    original["operation"][field] = value
    with pytest.raises(PointEventError):
        trial_point_evidence(original)


def test_current_hours_do_not_rewrite_adopted_piece_witness(point_case):
    case = point_case
    ids, ref, plan, work = point_work(case)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=2 WHERE id=?", (ids["item-A", 50],))
    case.conn.commit()
    before = snapshot(case.conn)
    historical = official_point_work(case.conn, plan["version"])[ids["item-A", 50]]
    assert historical == work
    task = next(task for task in workspace(case.conn, plan["plan_ref"])["tasks"]
                if task["operation_ref"] == work["execution"]["operation_ref"])
    assert task["piece_id"] == "item-A" and task["quantity"] == 1 and task["batch_quantity"] == 3
    with pytest.raises(WorkbenchCommandRejected) as caught:
        adoption_service(case.conn).preview(ref)
    assert caught.value.code == "snapshot_stale"
    assert snapshot(case.conn) == before


def test_changed_piece_identity_cannot_borrow_original_official_witness(point_case):
    case = point_case
    ids, ref, plan, _ = point_work(case)
    case.conn.execute("UPDATE BatchOperations SET piece_id='replacement' WHERE id=?", (ids["item-A", 50],))
    case.conn.commit()
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        official_point_work(case.conn, plan["version"])
    assert caught.value.code == "point_evidence_unproven"
    with pytest.raises(WorkbenchCommandRejected) as caught:
        adoption_service(case.conn).preview(ref)
    assert caught.value.code == "snapshot_stale"
    assert snapshot(case.conn) == before


def test_legacy_bare_zero_piece_is_not_invented_evidence(point_case):
    case = point_case
    ids = layout(case, mixed=False)
    case.plan(1, list(ids.values()), start="2026-09-09T08:00:00", end="2026-09-09T08:00:00")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        workspace(case.conn, case.plan_ref(1))
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("hours", (5e-324, 1e-12))
def test_real_worker_cannot_turn_tiny_positive_piece_into_point(point_case, hours):
    case = point_case
    ids = layout(case, mixed=False)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=? WHERE id=?", (hours, ids["item-A", 50]))
    case.conn.commit()
    result = managed_run(case)
    assert result["state"] == "failed", result
    assert not result["candidates"]
    assert not case.conn.execute("SELECT 1 FROM Schedule").fetchone()
