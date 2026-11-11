"""Complete paginated cohorts use bounded ledger reads in one snapshot."""

from core.models.content import content_text
from core.services.workbench.execution.field_workspace import FieldWorkspaceService
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


def three_operations(case):
    second, third = case.op("OP2", seq=2), case.op("OP3", seq=3)
    case.plan(2, [case.op_id, second, third])
    return case.op_id, second, third


def test_bounded_cohort_matches_single_load_with_revisions_voids_and_legacy(ledger_case, monkeypatch):
    from core.services.execution import ledger_reader
    from core.services.execution.ledger_reader import project_loaded_facts
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
    with case.ledger.read_snapshot() as scope:
        facts = case.ledger.load_many(scope, refs + refs[:1], comparison_plan_ref=case.plan_ref(2))
        projected = project_loaded_facts(facts)
        assert list(facts["operations"]) == refs
        assert [len(group) for group in reads] == [2, 1]
        assert len(clocks) == 1
    with case.ledger.read_snapshot() as scope:
        workspace = case.ledger.workspace_projection(scope, case.plan_ref(2), [
            {"task_ref": case.task(2, op), "operation_ref": ref, "plan_ref": case.plan_ref(2)} for op, ref in zip(ids, refs)])
    assert workspace["projections"] == [row.to_dict() for row in projected]
    assert [len(group) for group in reads[2:]] == [2, 1]
    monkeypatch.setattr(ledger_reader, "MAX_OPERATIONS", 10000)
    with case.ledger.read_snapshot() as scope:
        single = case.ledger.load(scope, refs, comparison_plan_ref=case.plan_ref(2))
        expected = project_loaded_facts(single)
    assert content_text(facts) == content_text(single)
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
    with case.ledger.read_snapshot() as scope:
        loaded = case.ledger.load_many(scope, refs)
        assert set(loaded["current_tasks"]) == set(refs)
        assert set(scope.task_maps[plan_ref]) == set(refs)
        assert case.ledger.load_many(scope, refs)["current_tasks"] == loaded["current_tasks"]
        assert calls == {"cohort": [(refs, plan_ref)], "directed": []}
    # A small range keeps its directed read, and a fresh snapshot sees new facts.
    with case.ledger.read_snapshot() as scope:
        case.ledger.load_many(scope, refs[:2])
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
    with reader.read_snapshot() as ws_scope:
        full, _ = reader.cohort(ws_scope, reader.prepare_read(ws_scope, {}))
    assert full["summary"]["tasks"] == 3 and [len(group) for group in reads] == [2, 1]
    reads.clear()
    scope = {"plan_finish_date_from": "2026-01-01", "plan_finish_date_to": "2026-01-02", "state": "unreported"}
    with reader.read_snapshot() as ws_scope:
        selected, _ = reader.cohort(ws_scope, reader.prepare_read(ws_scope, scope))
    assert [task["planned_end"][:10] for task in selected["tasks"]] == ["2026-01-01", "2026-01-02"]
    assert selected["summary"]["tasks"] == selected["summary"]["state_scope_tasks"] == 2
    assert [len(group) for group in reads] == [2]


def test_field_page_constructs_report_dicts_only_for_sliced_page_tasks(ledger_case, monkeypatch):
    from core.models.workbench_execution import ExecutionProjection
    from core.services.workbench.execution import field_workspace

    case = ledger_case
    op_ids = [case.op_id] + [case.op(f"OP-BULK-{idx:02d}", seq=idx + 1) for idx in range(1, 30)]
    case.plan(2, op_ids)
    for op_id in op_ids:
        case.command("create", case.task(2, op_id), case.values(1))

    report_row_calls = []
    to_dict_calls = []
    orig_report_rows = field_workspace.CohortTaskExecution.report_rows
    orig_to_dict = ExecutionProjection.to_dict

    monkeypatch.setattr(
        field_workspace.CohortTaskExecution,
        "report_rows",
        lambda self, *a, **kw: (report_row_calls.append(self.projection.operation_ref), orig_report_rows(self, *a, **kw))[1],
    )
    monkeypatch.setattr(
        ExecutionProjection,
        "to_dict",
        lambda self: (to_dict_calls.append(self.operation_ref), orig_to_dict(self))[1],
    )

    reader = FieldWorkspaceService(case.conn)
    with reader.read_snapshot() as ws_scope:
        cohort, _ = reader.cohort(ws_scope, reader.prepare_read(ws_scope, {}))
    assert cohort["summary"]["tasks"] == 30 and cohort["summary"]["reports"] == 30
    assert len(report_row_calls) == 0 and len(to_dict_calls) == 0

    paged = reader.page(cohort, 1, 1)
    assert len(paged["tasks"]) == 1
    assert len(report_row_calls) == 0 and len(to_dict_calls) == 1
