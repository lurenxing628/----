"""ES presentation only: real worker, adoption receipts and read-only DTOs."""

from copy import deepcopy

import pytest

from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.plan_projection import _captured_quantities
from core.services.workbench.run_candidate_facts import GenerationFacts
from core.services.workbench.run_candidate_storage import CandidateStore
from core.services.workbench.run_candidate_tasks import operation_labels
from core.services.workbench.run_candidates import WorkbenchRunCandidateQueryService
from tests.workbench.piece_chain_support import adopt_candidate, adopt_trial, piece_layout, saved_trial
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.plan_catalog_support import candidate, scenario
from tests.workbench.run_candidate_baseline_support import baseline
from tests.workbench.run_candidate_support import compute, retained
from tests.workbench.test_piece_chain_end_to_end import workspace
from tests.workbench.trial_support import snapshot

PIECES = ("第一件主体多字中文业务编号甲", "第二件主体多字中文业务编号乙", "第三件主体多字中文业务编号丙")


def real_case(case):
    ids = piece_layout(case)
    for old, new in zip(("item-A", "item-B", "item-C"), PIECES):
        case.conn.execute("UPDATE BatchOperations SET piece_id=? WHERE piece_id=?", (new, old))
    case.batch("B2", quantity=1)
    case.operation(batch="B2", seq=10, unit_hours=.5)
    case.conn.commit()
    for version in (1, 2, 3, 4):
        case.plan(version, [ids[None, 10]], end="2026-09-09T08:45:00")
    candidate(case.conn, 3, "critical_best", op_id=ids[None, 10])
    scenario(case.conn, "es-original-scene", 3, op_id=ids[None, 10])
    case.conn.commit()
    receipt = case.command("create", case.task(4, ids[None, 10]), case.values(
        3, actual_end="2026-09-09T08:45:00", effective_processing_hours=.75))
    assert receipt["ok"], receipt
    return ids, compute(case, case.settings("B1", "B2"))


def assert_quantities(tasks, basis=None):
    assert len(tasks) == 9
    for row in tasks:
        b1 = row.get("batch_id", row.get("batch_label")) == "B1"
        assert row["quantity"] == (1 if row["piece_id"] is not None or not b1 else 3), row
        assert row["batch_quantity"] == (3 if b1 else 1), row
        if row["piece_id"] is not None:
            assert row["piece_id"] in PIECES
        if basis is not None:
            assert row["quantity_basis"] == basis and row["quantity_reason"] is None, row


def test_real_piece_candidate_official_trial_and_old_plans_retain_evidence(trial_case):
    case = trial_case
    ids, (_, refs) = real_case(case)
    original = snapshot(case.conn)
    with retained(case.conn):
        data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(refs[0]))
        compared, _ = baseline(case, refs[0])
        assert_quantities(data["tasks"])
        assert_quantities(compared["comparisons"])
        old = workspace(case.conn, case.plan_ref(4))
        assert old["tasks"][0]["quantity"] is None
        assert old["tasks"][0]["batch_quantity"] is None
        assert old["tasks"][0]["quantity_reason"] == "plan_target_not_recorded"
    first = adopt_candidate(case, refs[0])["data"]["official_plan"]
    with retained(case.conn):
        formal = workspace(case.conn, first["plan_ref"])
        assert_quantities(formal["tasks"], "run_admission")
        assert {(row["operation_ref"], row["start"], row["end"]) for row in formal["tasks"]} == {
            (row["operation_ref"], row["start"], row["end"]) for row in data["tasks"]}
    draft, _, saved = saved_trial(case, {"plan_ref": first["plan_ref"]}, op_id=ids[None, 40])
    assert_quantities(draft["tasks"])
    protected = next(row for row in draft["tasks"] if row["batch_id"] == "B1" and row["sequence"] == 10)
    assert protected["locked"] and not protected["edit_context"]["can_change"]
    second = adopt_trial(case, saved)["data"]["official_plan"]
    with retained(case.conn):
        final = workspace(case.conn, second["plan_ref"])
        assert_quantities(final["tasks"], "trial_creation")
        assert_quantities([row["before"] for row in final["projections"]["baseline"]["items"]], "run_admission")
        assert workspace(case.conn, first["plan_ref"])["tasks"] == formal["tasks"]
        assert workspace(case.conn, case.plan_ref(4))["tasks"] == old["tasks"]
    after = snapshot(case.conn)
    for table in ("Batches", "BatchOperations", "OperationExecutionEvents", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions",
                  "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks", "ScheduleCandidateRows", "ScheduleAdjustmentScenarioRow"):
        assert after[table] == original[table], table
    for table in ("Schedule", "WorkbenchPlanSourceRefs", "WorkbenchEntityRefs", "WorkbenchTaskRefs", "WorkbenchCommandReceipts"):
        assert {row[0]: row for row in after[table]}.items() >= {row[0]: row for row in original[table]}.items(), table
    assert case.conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 31


def test_formal_target_never_follows_current_batch_quantity(trial_case):
    case = trial_case
    _, (_, refs) = real_case(case)
    official = adopt_candidate(case, refs[0])["data"]["official_plan"]
    before = workspace(case.conn, official["plan_ref"])["tasks"]
    case.conn.execute("UPDATE Batches SET quantity=99 WHERE batch_id='B1'")
    case.conn.commit()
    with retained(case.conn):
        after = workspace(case.conn, official["plan_ref"])["tasks"]
        assert after == before
        assert_quantities(after, "run_admission")


@pytest.mark.parametrize("quantity", [0, None, True, -1, 1.5])
def test_candidate_and_plan_projection_quantity_boundaries_do_not_infer_one(trial_case, quantity):
    case = trial_case
    _, (run_ref, refs) = real_case(case)
    facts = GenerationFacts(CandidateStore(case.conn).capture(run_ref))
    ref = next(ref for ref, op in facts.operations.items() if facts.tables["BatchOperations"][op]["piece_id"] == PIECES[0])
    facts.execution[ref] = dict(facts.execution[ref], target_quantity=quantity)
    before = deepcopy(facts.execution)
    item, op = operation_labels(facts, ref)
    expected = 0 if type(quantity) is int and quantity == 0 else None
    assert item["quantity"] == expected and item["batch_quantity"] == 3
    projected = _captured_quantities(op, facts.tables["Batches"][op["batch_id"]], facts.execution[ref], "run_admission")
    assert projected["quantity"] == expected and projected["batch_quantity"] == 3
    assert facts.execution == before
    facts.execution.pop(ref)
    assert operation_labels(facts, ref)[0]["quantity"] is None


def test_missing_original_receipt_makes_formal_quantity_explicitly_unknown(trial_case):
    case = trial_case
    _, (_, refs) = real_case(case)
    adopted = adopt_candidate(case, refs[0])
    case.conn.execute("DELETE FROM WorkbenchCommandReceipts WHERE receipt_ref=?", (adopted["receipt_ref"],))
    case.conn.commit()
    with retained(case.conn):
        tasks = workspace(case.conn, adopted["data"]["official_plan"]["plan_ref"])["tasks"]
        assert all(row["quantity"] is None and row["batch_quantity"] is None and row["quantity_reason"] == "plan_target_unavailable" for row in tasks)


def test_quantity_evidence_is_batched_before_task_loop(trial_case, monkeypatch):
    from core.models.workbench_plan_scope import PlanReadScope
    from core.services.workbench.plan_projection import project_tasks
    from core.services.workbench.plan_queries import WorkbenchPlanQueryService

    case = trial_case
    _, (_, refs) = real_case(case)
    official = adopt_candidate(case, refs[0])["data"]["official_plan"]
    reader, scope = WorkbenchPlanQueryService(case.conn), PlanReadScope(official["plan_ref"])
    calls, original = [], GenerationFacts.__init__

    def measured(self, capture):
        calls.append(capture["facts_hash"])
        original(self, capture)

    monkeypatch.setattr(GenerationFacts, "__init__", measured)
    with retained(case.conn), reader.read_snapshot():
        repo, entry, _ = reader._selected(scope.plan_ref)
        rows = reader._task_rows(repo, entry, scope)
        tasks = reader.references.get_task_refs(scope.plan_ref, rows)
        operations = reader.references.get_operation_refs(row["op_id"] for row in rows)
        resources, _ = reader._resources(rows)
        counts = []
        for subset in (rows[:1], rows):
            calls.clear()
            projected = project_tasks(scope.plan_ref, subset, tasks, operations, resources, conn=case.conn)
            assert len(projected) == len(subset) and all(row["quantity"] is not None for row in projected)
            counts.append(len(calls))
        assert 0 < counts[0] == counts[1], counts
