"""Preflight consumes the exact common fan-out and join used by real admission."""

import pytest

from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.input_admission import piece_admission_issues
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged
from tests.workbench.test_material_stage_release import add_requirement


def test_excluded_common_predecessor_excludes_every_piece_and_join(run_case):
    case = run_case
    ids = split(case)
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL WHERE id=?", (ids[None, 10],))
    case.conn.commit()
    settings = case.settings(missing_resource_policy="exclude")
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(settings))
    rows = {(row["piece_id"], row["sequence"]): row for row in data["tasks"]}
    first = rows[None, 10]
    assert all("op_id" not in row for row in data["tasks"])
    assert data["counts"]["ready_tasks"] == 0
    assert "piece_scope_incomplete" in {row["code"] for row in data["blockers"]}
    for piece in ("item-A", "item-B", "item-C"):
        assert rows[piece, 20]["predecessor_refs"] == [first["operation_ref"]]
        assert rows[piece, 20]["status"] == rows[piece, 30]["status"] == "skipped"
    assert set(rows[None, 40]["predecessor_refs"]) == {rows[piece, 30]["operation_ref"] for piece in ("item-A", "item-B", "item-C")}
    assert rows[None, 40]["status"] == "skipped"
    assert unchanged(case, lambda: piece_admission_issues(case.conn, settings))[0]["code"] == "piece_scope_incomplete"


@pytest.mark.parametrize("missing", [("item-B", 30), (None, 40)])
def test_any_resource_exclusion_reports_the_same_incomplete_piece_scope(run_case, missing):
    case = run_case
    ids = split(case)
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL WHERE id=?", (ids[missing],))
    case.conn.commit()
    settings = case.settings(missing_resource_policy="exclude", material_strategy="stage")
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(settings))
    assert "piece_scope_incomplete" in {row["code"] for row in data["blockers"]}
    assert unchanged(case, lambda: piece_admission_issues(case.conn, settings))[0]["code"] == "piece_scope_incomplete"


@pytest.mark.parametrize("damage,reason", [("missing_piece", "piece_scope_incomplete"),
    ("missing_stage", "piece_stage_incomplete"), ("common_collision", "piece_dependency_ambiguous")])
def test_preflight_exposes_actual_piece_structure_errors(run_case, damage, reason):
    case = run_case
    ids = split(case)
    if damage == "missing_piece":
        case.conn.execute("DELETE FROM BatchOperations WHERE piece_id='item-C'")
    elif damage == "missing_stage":
        case.conn.execute("DELETE FROM BatchOperations WHERE id=?", (ids["item-C", 30],))
    else:
        case.operation(seq=20)
    case.conn.commit()
    settings = case.settings()
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(settings))
    assert data["counts"]["ready_tasks"] == 0
    assert reason in {row["code"] for row in data["blockers"]}
    assert all(reason in {row["code"] for row in task["issues"]} for task in data["tasks"])
    assert unchanged(case, lambda: piece_admission_issues(case.conn, settings))[0]["code"] == reason


@pytest.mark.parametrize("deferred_sequence,common,ready_count", [(None, True, 8), (None, False, 6),
    (40, True, 7), (15, True, 1)])
def test_preflight_graph_and_stage_prefix_match_real_input(run_case, deferred_sequence, common, ready_count):
    case = run_case
    ids = split(case, common=common)
    if deferred_sequence is not None:
        later = ids[None, 40] if deferred_sequence == 40 else case.operation(seq=15)
        add_requirement(case, later, [])
    settings = case.settings(material_strategy="stage")
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(settings))
    prepared = unchanged(case, lambda: prepare_candidate_run_input(case.conn, settings, case.projections()))
    assert not data["blockers"] and data["counts"]["ready_tasks"] == ready_count
    graph = {row["operation_ref"]: row["predecessor_refs"] for row in prepared.dispositions}
    assert {row["operation_ref"]: row["predecessor_refs"] for row in data["tasks"]} == graph
    assert {row["operation_ref"]: row["status"] for row in data["tasks"]} == {
        row["operation_ref"]: row["status"] for row in prepared.dispositions}


def test_started_common_predecessor_never_becomes_a_completion_exemption(run_case):
    case = run_case
    ids = split(case)
    first = ids[None, 10]
    case.plan(1, [first])
    case.command("create", case.task(1, first), case.values(1))
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(case.settings()))
    assert data["counts"]["ready_tasks"] == 0
    assert "execution_review_required" in {row["code"] for row in data["blockers"]}
    assert all(row["status"] == "skipped" for row in data["tasks"] if row["sequence"] != 10)


def test_completed_common_predecessor_keeps_its_actual_completion_exemption(run_case):
    case = run_case
    ids = split(case)
    first = ids[None, 10]
    case.plan(1, [first])
    case.command("create", case.task(1, first), case.values(3))
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL WHERE id=?", (first,))
    case.conn.commit()
    settings = case.settings(missing_resource_policy="exclude")
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(settings))
    prepared = unchanged(case, lambda: prepare_candidate_run_input(case.conn, settings, case.projections()))
    assert not data["blockers"] and data["counts"]["ready_tasks"] == 7
    protected = next(row for row in data["tasks"] if row["sequence"] == 10)
    assert protected["status"] == "protected" and protected["execution"]["execution_state"] == "complete"
    graph = {row["operation_ref"]: row["predecessor_refs"] for row in prepared.dispositions}
    assert {row["operation_ref"]: row["predecessor_refs"] for row in data["tasks"]} == graph


@pytest.mark.parametrize("piece", [False, True])
def test_disabled_ready_check_ignores_the_same_ready_date_in_preflight_and_input(run_case, piece):
    case = run_case
    if piece:
        split(case)
    case.conn.execute("UPDATE Batches SET ready_status='no',ready_date='2030-01-01'")
    case.conn.commit()
    settings = case.settings(ready_check=False, end_date="2026-09-09")
    prepared = unchanged(case, lambda: prepare_candidate_run_input(case.conn, settings, case.projections()))
    data, _ = unchanged(case, lambda: PreflightService(case.conn).evaluate(settings))
    assert len(prepared.algo_ops) == (8 if piece else 1)
    assert not data["blockers"] and data["counts"]["ready_tasks"] == len(prepared.algo_ops)
    assert all(row["status"] == "eligible" and row["material_ready_date"] is None for row in data["tasks"])
