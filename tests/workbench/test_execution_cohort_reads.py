"""Complete paginated cohorts use bounded ledger reads in one snapshot."""

from core.models.content import content_text
from core.services.workbench.dashboard.facts import typed
from core.services.workbench.execution.field_workspace import FieldWorkspaceService
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


def three_operations(case):
    second, third = case.op("OP2", seq=2), case.op("OP3", seq=3)
    case.plan(2, [case.op_id, second, third])
    return case.op_id, second, third


def test_bounded_cohort_matches_single_load_with_revisions_voids_and_legacy(ledger_case, monkeypatch):
    from core.services.execution import ledger_reader
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    ids = three_operations(case)
    case.command("create", case.task(2, ids[0]), case.values(3))
    second = case.command("create", case.task(2, ids[1]), case.values(1))["data"]["rows"][0]
    case.command("correct", second["report_ref"], {"original_revision_ref": second["revision_ref"],
                 "reason": "Checked operation counter", "remark": "Corrected evidence"})
    third = case.command("create", case.task(2, ids[2]), case.values(0))["data"]["rows"][0]
    case.command("report_void", third["report_ref"], {"original_revision_ref": third["revision_ref"],
                 "reason": "Duplicate empty report", "declared_operator": "Foreman"})
    tasks = [case.task(2, op) for op in ids]
    headers = case.ledger.repo.task_headers(tasks)
    refs = [headers[task]["operation_ref"] for task in tasks]
    reads, clocks = [], []
    original_read, original_clock = WorkbenchExecutionRepository.reports, case.ledger.current_plan_provider

    def reports(repo, selected, limit):
        reads.append(list(selected))
        return original_read(repo, selected, limit)

    def current(conn):
        clocks.append(True)
        return original_clock(conn)

    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", reports)
    monkeypatch.setattr(case.ledger, "current_plan_provider", current)
    monkeypatch.setattr(ledger_reader, "MAX_OPERATIONS", 2)
    with case.ledger.read_snapshot():
        facts = case.ledger.load_many(refs + refs[:1], comparison_plan_ref=case.plan_ref(2))
        projected = case.ledger.project_loaded(facts, contexts=False)
        assert list(facts["operations"]) == refs
        assert [len(group) for group in reads] == [2, 1]
        assert len(clocks) == 1
    workspace = case.ledger.workspace_projection(case.plan_ref(2), [
        {"task_ref": case.task(2, op), "operation_ref": ref, "plan_ref": case.plan_ref(2)} for op, ref in zip(ids, refs)])
    assert workspace["projections"] == [row.to_dict() for row in projected]
    assert [len(group) for group in reads[2:]] == [2, 1]
    monkeypatch.setattr(ledger_reader, "MAX_OPERATIONS", 10000)
    with case.ledger.read_snapshot():
        single = case.ledger.load(refs, comparison_plan_ref=case.plan_ref(2))
        expected = case.ledger.project_loaded(single, contexts=False)
    assert content_text(typed(facts)) == content_text(typed(single))
    assert [row.to_dict() for row in projected] == [row.to_dict() for row in expected]
    assert len(projected[1].reports[0].correction_history) == 2
    assert len(projected[2].voided_reports) == 1


def test_large_cohort_reads_task_plan_once_and_keeps_requested_duplicate_guard(ledger_case, monkeypatch):
    from core.services.execution import ledger_reader
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    ids = three_operations(case)
    other = case.op("UNSELECTED", seq=4)
    case.plan(3, list(ids) + [other])
    tasks = [case.task(3, op) for op in list(ids) + [other]]
    headers = case.ledger.repo.task_headers(tasks)
    refs = [headers[task]["operation_ref"] for task in tasks[:-1]]
    plan_ref = case.plan_ref(3)
    calls = {"cohort": [], "directed": []}
    original_cohort = WorkbenchExecutionRepository.cohort_task_rows
    original_directed = WorkbenchExecutionRepository.task_rows

    def cohort(repo, selected, selected_plan):
        calls["cohort"].append((list(selected), selected_plan))
        return original_cohort(repo, selected, selected_plan)

    def directed(repo, selected, selected_plan):
        calls["directed"].append((list(selected), selected_plan))
        return original_directed(repo, selected, selected_plan)

    monkeypatch.setattr(WorkbenchExecutionRepository, "cohort_task_rows", cohort)
    monkeypatch.setattr(WorkbenchExecutionRepository, "task_rows", directed)
    monkeypatch.setattr(ledger_reader, "MAX_OPERATIONS", 2)
    with case.ledger.read_snapshot():
        loaded = case.ledger.load_many(refs)
        assert set(loaded["current_tasks"]) == set(refs)
        assert set(case.ledger._snapshot_task_maps[plan_ref]) == set(refs)
        assert case.ledger.load_many(refs)["current_tasks"] == loaded["current_tasks"]
        assert calls == {"cohort": [(refs, plan_ref)], "directed": []}
    # A small range keeps its directed read, and a fresh snapshot sees new facts.
    with case.ledger.read_snapshot():
        case.ledger.load_many(refs[:2])
    assert calls["directed"] == [(refs[:2], plan_ref)]


def test_field_visible_finish_dates_narrow_before_ledger_and_keep_inclusive_days(ledger_case, monkeypatch):
    from core.services.execution import ledger_reader
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    ids = three_operations(case)
    for op, day in zip(ids, (1, 2, 3)):
        case.conn.execute("UPDATE Schedule SET start_time=?,end_time=? WHERE version=2 AND op_id=?",
                          (f"2026-01-{day:02d}T08:00:00", f"2026-01-{day:02d}T10:00:00", op))
    reads, original = [], WorkbenchExecutionRepository.reports

    def reports(repo, refs, limit):
        reads.append(list(refs))
        return original(repo, refs, limit)

    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", reports)
    monkeypatch.setattr(ledger_reader, "MAX_OPERATIONS", 2)
    reader = FieldWorkspaceService(case.conn)
    with reader.read_snapshot():
        full, _, _ = reader.cohort({})
    assert full["summary"]["tasks"] == 3 and [len(group) for group in reads] == [2, 1]
    reads.clear()
    scope = {"plan_finish_date_from": "2026-01-01", "plan_finish_date_to": "2026-01-02", "state": "unreported"}
    with reader.read_snapshot():
        selected, _, _ = reader.cohort(scope)
    assert [task["planned_end"][:10] for task in selected["tasks"]] == ["2026-01-01", "2026-01-02"]
    assert selected["summary"]["tasks"] == selected["summary"]["state_scope_tasks"] == 2
    assert [len(group) for group in reads] == [2]
