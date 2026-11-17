"""Atomic receipts, original-intent replay, correction history and dry-run batches."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as lineage_fixture  # noqa: F401


def test_correct_keeps_stable_number_and_every_original_value(ledger_case):
    case = ledger_case
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(4, remark="original"))["data"]["rows"][0]
    original = case.report_projection(saved["report_ref"])
    payload = {"completed_quantity": 6, "remark": "corrected", "original_revision_ref": original.revision_ref,
               "reason": "Checked counter", "declared_operator": "declared-foreman"}
    case.command("correct", original.report_ref, payload)
    result = case.report_projection(original.report_ref)
    assert result.report_no == original.report_no and result.report_ref == original.report_ref
    assert result.completed_quantity == 6
    assert result.correction_history[0]["after"]["completed_quantity"] == 4
    assert result.correction_history[1]["before"]["remark"] == "original"
    assert result.correction_history[1]["reason"] == "Checked counter"
    assert result.local_operator == "local-os-user" and result.declared_operator == "declared-foreman"
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", original.report_ref, payload)
    assert error.value.code == "stale_write"


def test_correction_finishing_after_downstream_planned_start_is_rejected_with_its_arrangement(ledger_case):
    """更正后的完工晚于后道正式安排的开工就拦下，与开工同一时刻不算冲突；比较和公开安排都按已保存的起止时刻。"""
    from tests.workbench.execution_ledger_support import END, START, publish_official_plan

    case = ledger_case
    downstream = case.op("OP2", seq=2)
    publish_official_plan(case.conn, 2, [
        {"op_id": case.op_id, "machine_id": "M1", "operator_id": "O1", "start_time": START, "end_time": END},
        {"op_id": downstream, "machine_id": "M1", "operator_id": "O1",
         "start_time": "2026-09-09T11:00:00", "end_time": "2026-09-09T12:00:00"},
    ])
    case.conn.commit()
    saved = case.command("create", case.task(2, case.op_id), case.values(10))["data"]["rows"][0]
    touching = case.command("correct", saved["report_ref"], {
        "original_revision_ref": saved["revision_ref"], "actual_end": "2026-09-09T11:00:00", "reason": "核对完工"})
    assert touching["result"] == "committed"
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", saved["report_ref"], {
            "original_revision_ref": touching["data"]["rows"][0]["revision_ref"],
            "actual_end": "2026-09-09T11:30:00", "reason": "核对完工"})
    assert error.value.code == "constraint_conflict"
    (conflict,) = error.value.conflicts
    assert (conflict["code"], conflict["operation_code"]) == ("downstream_time_conflict", "OP2")
    assert conflict["plan"] == {"plan_ref": case.plan_ref(2), "task_ref": case.task(2, downstream), "version": 2,
                                "start": "2026-09-09T11:00:00", "end": "2026-09-09T12:00:00"}


def test_mid_mutation_exception_rolls_back_report_revision_clock_and_receipt(ledger_case, monkeypatch):
    case = ledger_case
    before = all_rows(case.conn)
    original = WorkbenchExecutionReportRepository.append

    def fail(self, row, *, request_key):
        original(self, row, request_key=request_key)
        raise RuntimeError("injected after append")

    monkeypatch.setattr(WorkbenchExecutionReportRepository, "append", fail)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command("create", case.task(1, case.op_id), case.values(1), key="ledger-rollback-000001")
    assert all_rows(case.conn) == before
    assert case.writer.commands.lookup("ledger-rollback-000001") is None


def test_report_preparation_batches_relatives_and_shares_unchanged_facts(ledger_case, monkeypatch):
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    middle, last = case.op("OP2", seq=2), case.op("OP3", seq=3)
    case.plan(2, [case.op_id, middle, last])
    task = case.task(2, middle)
    case.command("create", task, case.values(1))
    read_groups, plans = [], []
    original_read = WorkbenchExecutionRepository.reports
    original_plan = case.writer.ledger.current_plan_provider

    def reports(repo, refs, limit):
        read_groups.append(set(refs))
        return original_read(repo, refs, limit)

    def plan(conn):
        plans.append(True)
        return original_plan(conn)

    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", reports)
    monkeypatch.setattr(case.writer.ledger, "current_plan_provider", plan)
    with case.writer.ledger.read_snapshot() as ledger_scope:
        preparation = case.writer.prepare_batch_in_scope(ledger_scope, [{"action": "create", "ref": task, "payload": case.values(1)}])
    assert len(plans) == 1 and len(read_groups) == 2
    assert len(read_groups[0]) == 1 and len(read_groups[1]) == 2 and not read_groups[0] & read_groups[1]
    assert preparation.facts["operations"] is preparation.before["operations"]
    assert preparation.facts["plan"] is preparation.before["plan"]
    assert preparation.facts["reports"] is not preparation.before["reports"]
    operation_ref = preparation.resolved[0]["operation_ref"]
    old = next(iter(preparation.before["reports"][operation_ref].values()))
    retained = preparation.facts["reports"][operation_ref][old[0]["report_ref"]]
    assert old is not retained and old[0] is retained[0]
    # A direct command enters the same scope and reads fresh current facts.
    read_groups.clear()
    case.command("create", task, case.values(1))
    assert len(plans) == 2 and len(read_groups) == 2


def test_ledger_snapshot_reuses_loaded_facts_and_next_snapshot_refreshes(ledger_case, monkeypatch):
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    saved = case.command("create", case.task(1, case.op_id), case.values(1))["data"]["rows"][0]
    reads, original = [], WorkbenchExecutionRepository.reports

    def reports(repo, refs, limit):
        reads.append(list(refs))
        return original(repo, refs, limit)

    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", reports)
    with case.ledger.read_snapshot() as scope:
        first = case.ledger.load(scope, [saved["operation_ref"]], comparison_plan_ref=case.plan_ref(1))
        second = case.ledger.load(scope, [saved["operation_ref"]], comparison_plan_ref=case.plan_ref(1))
        assert first["plan"] is second["plan"]
        assert first["reports"][saved["operation_ref"]] is second["reports"][saved["operation_ref"]]
        assert len(reads) == 1
    with case.ledger.read_snapshot() as scope:
        case.ledger.project_operations(scope, [saved["operation_ref"]])
    assert len(reads) == 2


def test_report_preparation_chunks_dependencies_across_valid_batch_routes(ledger_case, monkeypatch):
    from core.models.workbench_execution_input import MAX_OPERATIONS
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B2','P1',10)")
    second = case.op("B2-OP1", batch="B2")
    case.conn.executemany("""INSERT INTO BatchOperations
        (op_code,batch_id,seq,op_type_id,op_type_name,source)
        VALUES (?,?,?,'T1','Turning','internal')""",
        [(f"{batch}-OP{seq}", batch, seq) for batch in ("B1", "B2") for seq in range(2, 6002)])
    case.plan(2, [case.op_id, second])
    reads, plans = [], []
    original_read = WorkbenchExecutionRepository.reports
    original_plan = case.writer.ledger.current_plan_provider

    def reports(repo, refs, limit):
        reads.append(set(refs))
        return original_read(repo, refs, limit)

    def plan(conn):
        plans.append(True)
        return original_plan(conn)

    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", reports)
    monkeypatch.setattr(case.writer.ledger, "current_plan_provider", plan)
    with case.writer.ledger.read_snapshot() as ledger_scope:
        preparation = case.writer.prepare_batch_in_scope(ledger_scope, [
            {"action": "create", "ref": case.task(2, op_id), "payload": case.values(1)}
            for op_id in (case.op_id, second)])

    assert len(preparation.appended) == 2 and len(plans) == 1
    assert len(reads[0]) == 2
    assert [len(group) for group in reads[1:]] == [MAX_OPERATIONS, 12000 - MAX_OPERATIONS]
    assert len(set.union(*reads)) == sum(map(len, reads)) == 12002
    assert case.conn.execute("SELECT count(*) FROM WorkbenchProductionReports").fetchone()[0] == 0


def test_execution_adapter_consumes_one_ledger_plan_task_and_resource_scope(ledger_case, monkeypatch):
    from core.models.operation_execution_scope import OperationExecutionScope
    from core.services.scheduler.execution.execution_fact_provider import ExecutionFactProvider
    from data.repositories.execution_ledger_scope_repo import ExecutionLedgerScopeRepository
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository

    case = ledger_case
    saved = case.command('create', case.task(1, case.op_id), case.values(1))['data']['rows'][0]
    schedule_id = case.conn.execute('SELECT id FROM Schedule WHERE version=1 AND op_id=?', (case.op_id,)).fetchone()[0]
    scope = OperationExecutionScope.from_values(schedule_version=1, schedule_id=schedule_id, op_id=case.op_id, batch_id='B1')
    calls = {'plan': 0, 'tasks': 0, 'scope': 0, 'resources': 0, 'orphans': 0}
    original_plan = case.ledger.current_plan_provider

    def plan(conn):
        calls['plan'] += 1
        return original_plan(conn)

    monkeypatch.setattr(case.ledger, 'current_plan_provider', plan)
    for cls, name, counter in [(WorkbenchExecutionRepository, 'task_rows', 'tasks'),
            (WorkbenchExecutionRepository, 'resources', 'resources'),
            (ExecutionLedgerScopeRepository, 'scope_task_rows', 'scope'),
            (ExecutionLedgerScopeRepository, 'reported_operation_without_schedule_row', 'orphans')]:
        original = getattr(cls, name)

        def captured(self, *args, original=original, counter=counter, **kwargs):
            calls[counter] += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(cls, name, captured)
    with case.ledger.read_snapshot() as ledger_scope:
        projected = case.ledger.project_operations(ledger_scope, [saved['operation_ref']])
        provider = ExecutionFactProvider(ledger=ledger_scope)
        first = provider.facts_by_scope([scope], execution_projections=projected)
        second = provider.facts_by_scope([scope], execution_projections=projected)
        assert first == second and first[scope].target_quantity == 10
    assert calls == {'plan': 1, 'tasks': 1, 'scope': 0, 'resources': 1, 'orphans': 1}


@pytest.mark.parametrize("method", ["read_clock", "scope_task_rows"])
def test_execution_adapter_translates_ledger_read_rejection(ledger_case, monkeypatch, method):
    from core.errors import AppError
    from core.models.operation_execution_scope import OperationExecutionScope
    from core.services.execution.ledger_reader import ExecutionLedgerReader
    from core.services.scheduler.execution.execution_fact_provider import ExecutionFactProvider
    from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

    case = ledger_case
    schedule_id = case.conn.execute("SELECT id FROM Schedule WHERE op_id=?", (case.op_id,)).fetchone()[0]
    scope = OperationExecutionScope.from_values(schedule_version=1, schedule_id=schedule_id, op_id=case.op_id, batch_id="B1")
    operation_ref = WorkbenchPlanIdentityRepository(case.conn).get_operation_refs([case.op_id])[case.op_id]
    with case.ledger.read_snapshot() as initial_scope:
        projected = case.ledger.project_operations(initial_scope, [operation_ref])

    def deny(*_args, **_kwargs):
        raise WorkbenchCommandRejected("ledger_read_rejected", "injected ledger read rejection", 409)

    # Rejected before the snapshot opens, or while adapting facts against the supplied projections.
    monkeypatch.setattr(ExecutionLedgerReader, method, deny)
    with pytest.raises(AppError) as error:
        with ledger_read_snapshot(case.conn) as ledger_scope:
            ExecutionFactProvider(ledger=ledger_scope).facts_by_scope(
                [scope], execution_projections=projected
            )
    assert error.value.details == {"reason": "ledger_read_rejected"}


def test_correct_remark_preserves_actual_operator_with_legacy_external_skill(ledger_case):
    case = ledger_case
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(4, remark="original"))["data"]["rows"][0]
    original = case.report_projection(saved["report_ref"])
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('LEGACY-EXT','LegacyExt','external')")
    case.conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O1','LEGACY-EXT')")
    case.conn.commit()
    payload = {"remark": "remark only", "original_revision_ref": original.revision_ref, "reason": "Add note"}
    outcome = case.command("correct", original.report_ref, payload)
    assert outcome["result"] == "committed"
    assert case.report_projection(original.report_ref).remark == "remark only"


def test_lightweight_execution_projection_skips_history_and_caches_parsed_period(ledger_case, monkeypatch):
    import sqlite3

    from core.services.execution import projection as exec_projection
    from core.services.workbench.execution import production_report_validation as report_validation
    from data.repositories import workbench_execution_repo

    case = ledger_case
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(4, effective_processing_hours=0.1, remark="initial"))["data"]["rows"][0]
    case.command(
        "correct",
        saved["report_ref"],
        {
            "original_revision_ref": saved["revision_ref"],
            "effective_processing_hours": 0.1,
            "remark": "revised",
            "reason": "Update note",
        },
    )
    case.command("create", task, case.values(2, effective_processing_hours=0.2, remark="second"))
    op_ref = saved["operation_ref"]

    state_row = case.conn.execute(
        "SELECT * FROM OperationExecutionStates WHERE operation_ref = ?", (op_ref,)
    ).fetchone()
    assert state_row is not None
    assert state_row["active_report_count"] == 2
    assert state_row["known_completed_quantity"] == 6
    assert state_row["known_effective_hours_text"] == "0.3"
    assert state_row["unknown_hour_count"] == 0

    with pytest.raises(sqlite3.IntegrityError, match="execution report identity is immutable"):
        case.conn.execute(
            "UPDATE WorkbenchProductionReports SET report_no = 'MUTATED' WHERE report_ref = ?",
            (saved["report_ref"],),
        )

    history_calls = []
    orig_history = exec_projection.build_correction_history
    monkeypatch.setattr(
        exec_projection,
        "build_correction_history",
        lambda *args, **kwargs: (history_calls.append(True), orig_history(*args, **kwargs))[1],
    )

    with case.ledger.read_snapshot() as scope:
        with monkeypatch.context() as light_ctx:
            light_ctx.setattr(
                workbench_execution_repo,
                "read_stored_json",
                lambda *_: pytest.fail("include_history=False must not parse values_json"),
            )
            light_facts = case.ledger.load(scope, [op_ref], include_history=False)
            light = case.ledger.project_loaded(light_facts, include_history=False)[0]
        assert history_calls == []
        assert len(light.reports) == 2
        assert [r.revision_count for r in light.reports] == [2, 1]
        assert all(r.correction_history == [] for r in light.reports)

        # Calling include_history=True on the SAME scope afterwards must still load full revision history.
        full_facts = case.ledger.load(scope, [op_ref], include_history=True)
        full = case.ledger.project_loaded(full_facts, include_history=True)[0]
    assert len(history_calls) == 2
    assert [len(r.correction_history) for r in full.reports] == [2, 1]
    assert [r.revision_count for r in full.reports] == [2, 1]

    # Verify actual_period, actual_period_basis, and _constraint_signature cache on ExecutionProjection.
    first_period = exec_projection.actual_period(light)
    first_basis = exec_projection.actual_period_basis(light)
    first_sig = report_validation._constraint_signature(light)
    assert "actual_period" in light.__dict__["_cache"]
    assert "actual_period_basis" in light.__dict__["_cache"]
    assert "constraint_signature" in light.__dict__["_cache"]

    assert exec_projection.actual_period(light) is first_period
    assert exec_projection.actual_period_basis(light) is first_basis
    assert report_validation._constraint_signature(light) is first_sig


def test_ledger_counts_and_quantities_are_typed_by_their_table_checks(ledger_case):
    """报工条数、修订次数与序号、完成数量是单条计数（整数，下限 0 或 1，至多 2**53-1）；已知完成数量是按条累加的合计，
    只要求非负整数。原来的 ``>= 0`` / ``> 0`` 放行文本与小数（数字 < 文本），现在列上的 CHECK 拦住。"""
    case = ledger_case
    case.plan(2, [case.op_id])
    saved = case.command("create", case.task(2, case.op_id), case.values(2))["data"]["rows"][0]
    report, op_ref = saved["report_ref"], saved["operation_ref"]

    def rejected(sql, *params):
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            case.conn.execute(sql, params)

    for column in ("active_report_count", "unknown_quantity_count", "unknown_hour_count"):
        for value in (-1, 1.5, "x", 2**53):
            rejected("UPDATE OperationExecutionStates SET " + column + "=? WHERE operation_ref=?", value, op_ref)
        case.conn.execute("UPDATE OperationExecutionStates SET " + column + "=? WHERE operation_ref=?", (2**53 - 1, op_ref))
    for value in (-1, 1.5, "x"):
        rejected("UPDATE OperationExecutionStates SET known_completed_quantity=? WHERE operation_ref=?", value, op_ref)
    case.conn.execute("UPDATE OperationExecutionStates SET known_completed_quantity=? WHERE operation_ref=?", (2**53, op_ref))
    for value in (0, 1.5, "x", 2**53):
        rejected("UPDATE WorkbenchProductionReports SET revision_count=? WHERE report_ref=?", value, report)
    for value in (-1, 1.5, "x", 2**53):
        rejected("UPDATE WorkbenchProductionReports SET completed_quantity=? WHERE report_ref=?", value, report)
    for value in (None, 0, 2**53 - 1):
        case.conn.execute("UPDATE WorkbenchProductionReports SET completed_quantity=? WHERE report_ref=?", (value, report))
    for value in (0, 1.5, "bad-seq"):
        rejected("INSERT INTO WorkbenchProductionReportRevisions(revision_ref, report_ref, sequence, previous_revision_ref, "
                 "action, values_json, reason, local_operator, declared_operator, recorded_at, request_key) "
                 "VALUES (?, ?, ?, ?, 'correct', '{}', 'r', 'op', 'op', '2026-09-09T11:00:00', 'k')",
                 "b" * 48, report, value, saved["revision_ref"])
    case.conn.rollback()


def test_bounded_report_and_void_reads_skip_sql_sort_and_preserve_sql_order(ledger_case, monkeypatch):
    from data.repositories import workbench_execution_repo

    case = ledger_case
    second = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, second])
    first_saved = case.command("create", case.task(2, case.op_id), case.values(2))["data"]["rows"][0]
    case.command(
        "correct",
        first_saved["report_ref"],
        {"original_revision_ref": first_saved["revision_ref"], "completed_quantity": 3, "reason": "Recount"},
    )
    second_saved = case.command("create", case.task(2, second), case.values(1))["data"]["rows"][0]
    case.command(
        "report_void",
        second_saved["report_ref"],
        {"original_revision_ref": second_saved["revision_ref"], "reason": "Voided", "declared_operator": "Foreman"},
    )
    op_refs = [first_saved["operation_ref"], second_saved["operation_ref"]]

    plans = []
    original_fetchall = case.ledger.repo.fetchall

    def explain_fetchall(sql, params=()):
        details = [row[-1] for row in case.conn.execute("EXPLAIN QUERY PLAN " + sql, params)]
        plans.append(details)
        return original_fetchall(sql, params)

    monkeypatch.setattr(case.ledger.repo, "fetchall", explain_fetchall)
    case.ledger.repo.reports(op_refs, 10)
    case.ledger.repo.report_voids(op_refs, 10)
    assert len(plans) == 2
    assert all("USE TEMP B-TREE FOR ORDER BY" not in detail for details in plans for detail in details)

    with monkeypatch.context() as cap_ctx:
        cap_ctx.setattr(
            workbench_execution_repo,
            "read_stored_json",
            lambda *_: pytest.fail("Must not parse values_json when report cap is exceeded"),
        )
        plans.clear()
        capped_reports, capped_heads, capped_count = case.ledger.repo.reports(op_refs, 1)
        assert capped_reports == {} and capped_heads == {} and capped_count == 2
        assert len(plans) == 1

        plans.clear()
        capped_voids, capped_void_count = case.ledger.repo.report_voids(
            [second_saved["operation_ref"], first_saved["operation_ref"]], 0
        )
        assert capped_voids == {} and capped_void_count == 1
        assert len(plans) == 1

    orphan_ref = "0" * 48
    case.conn.execute(
        "INSERT INTO WorkbenchProductionReports"
        "(report_ref, report_no, operation_ref, recorded_against_task_ref, recorded_against_plan_ref, source, recorded_at) "
        "VALUES (?, 'ORPHAN-001', ?, ?, ?, 'manual', '2026-09-09T11:00:00')",
        (orphan_ref, second_saved["operation_ref"], case.task(2, second), case.plan_ref(2)),
    )
    orphan_reports, orphan_heads, orphan_count = case.ledger.repo.reports([second_saved["operation_ref"]], 10)
    assert orphan_count == 2
    assert orphan_heads[second_saved["operation_ref"]] == sorted([orphan_ref, second_saved["report_ref"]])
    assert list(orphan_reports[second_saved["operation_ref"]]) == [second_saved["report_ref"]]
    with pytest.raises(WorkbenchCommandRejected) as orphan_err:
        with case.ledger.read_snapshot() as scope:
            case.ledger.project_operations(scope, [second_saved["operation_ref"]])
    assert orphan_err.value.code == "storage_failure" and orphan_err.value.status == 500


def test_large_integer_effective_hours_persists_exact_text_and_roundtrips_exact_int(ledger_case):
    case = ledger_case
    huge_hours = (1 << 53) - 1
    task = case.task(1, case.op_id)

    created = case.command(
        "create",
        task,
        case.values(2, actual_start=None, actual_end=None, effective_processing_hours=huge_hours),
    )
    assert created["result"] == "committed"
    saved = created["data"]["rows"][0]
    op_ref = saved["operation_ref"]

    with case.ledger.read_snapshot() as scope:
        light = case.ledger.project_loaded(
            case.ledger.load(scope, [op_ref], include_history=False), include_history=False
        )[0]
        full = case.ledger.project_loaded(
            case.ledger.load(scope, [op_ref], include_history=True), include_history=True
        )[0]
    assert type(light.reports[0].effective_processing_hours) is int
    assert light.reports[0].effective_processing_hours == huge_hours
    assert type(full.reports[0].effective_processing_hours) is int
    assert full.reports[0].effective_processing_hours == huge_hours

    corrected = case.command(
        "correct",
        saved["report_ref"],
        {
            "original_revision_ref": saved["revision_ref"],
            "completed_quantity": 4,
            "effective_processing_hours": huge_hours,
            "reason": "Recount quantity while keeping exact large integer hours",
        },
    )
    assert corrected["result"] == "committed"

    state_row = case.conn.execute(
        "SELECT known_effective_hours_text, unknown_hour_count FROM OperationExecutionStates WHERE operation_ref = ?",
        (op_ref,),
    ).fetchone()
    assert state_row["known_effective_hours_text"] == str(huge_hours)
    assert state_row["unknown_hour_count"] == 0

    with case.ledger.read_snapshot() as scope:
        light_after = case.ledger.project_loaded(
            case.ledger.load(scope, [op_ref], include_history=False), include_history=False
        )[0]
        full_after = case.ledger.project_loaded(
            case.ledger.load(scope, [op_ref], include_history=True), include_history=True
        )[0]
    assert type(light_after.reports[0].effective_processing_hours) is int
    assert light_after.reports[0].effective_processing_hours == huge_hours
    assert light_after.reports[0].completed_quantity == 4
    assert type(full_after.reports[0].effective_processing_hours) is int
    assert full_after.reports[0].effective_processing_hours == huge_hours
    assert full_after.reports[0].correction_history[-1]["after"]["effective_processing_hours"] == huge_hours


def test_effective_hours_state_sum_preserves_exact_precision_above_28_digits(ledger_case):
    from decimal import Decimal, getcontext

    from core.models.hours import sum_hours
    from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository

    case = ledger_case
    second = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, second])
    largest = (1 << 53) - 1

    first_created = case.command(
        "create",
        case.task(2, case.op_id),
        case.values(1, actual_start=None, actual_end=None, effective_processing_hours=largest),
    )
    assert first_created["result"] == "committed"
    first_op_ref = first_created["data"]["rows"][0]["operation_ref"]
    first_state = case.conn.execute(
        "SELECT known_effective_hours_text FROM OperationExecutionStates WHERE operation_ref = ?",
        (first_op_ref,),
    ).fetchone()
    assert first_state["known_effective_hours_text"] == str(largest)
    assert Decimal(first_state["known_effective_hours_text"]) == Decimal(largest)

    second_task = case.task(2, second)
    second_created = case.command(
        "create",
        second_task,
        case.values(1, actual_start=None, actual_end=None, effective_processing_hours=largest),
    )
    case.command(
        "create",
        second_task,
        case.values(1, actual_start=None, actual_end=None, effective_processing_hours=1e-20),
    )
    second_op_ref = second_created["data"]["rows"][0]["operation_ref"]
    second_state = case.conn.execute(
        "SELECT known_effective_hours_text FROM OperationExecutionStates WHERE operation_ref = ?",
        (second_op_ref,),
    ).fetchone()
    expected_mixed = Decimal("9007199254740991.00000000000000000001")
    assert sum_hours([largest, 1e-20]).known == expected_mixed
    assert second_state["known_effective_hours_text"] == "9007199254740991.00000000000000000001"
    assert Decimal(second_state["known_effective_hours_text"]) == expected_mixed
    summary = WorkbenchFieldQueryRepository(case.conn).field_summary(2, {})
    assert summary["known_effective_processing_hours"] == float(sum_hours([largest, expected_mixed]).known)
    assert getcontext().prec == 28


_HOUR_PERIODS = (("2026-09-09T08:00:00", "2026-09-09T09:00:00"), ("2026-09-09T09:00:00", "2026-09-09T10:00:00"))


@pytest.mark.parametrize(
    ("reports", "total", "known", "unknown", "hour_reason"),
    [
        (((4, 0.1), (6, 0.2)), 0.3, 0.3, 0, None),
        ((), None, None, 0, "production_reports_missing"),
        (((4, 0.1), (6, None)), None, 0.1, 1, "processing_hours_unknown"),
        (((4, None), (6, None)), None, None, 2, "processing_hours_unknown"),
    ],
    ids=["complete", "empty", "partly_unknown", "all_unknown"],
)
def test_field_report_calibration_and_dashboard_hours_share_exact_totals(
    lineage_case, reports, total, known, unknown, hour_reason
):
    """同一道工序的报工经四个出口：0.1+0.2 精确为 0.3；空集与未知工时都不当 0，合计只在全部已知时给出。"""
    from flask import Blueprint

    from core.services.workbench.dashboard.execution import actual
    from core.services.workbench.dashboard.service import WorkbenchDashboardService
    from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository
    from tests.workbench.execution_ledger_support import NOW
    from tests.workbench.field_workspace_support import FieldAPI, success
    from tests.workbench.template_lineage_support import calibration, create
    from web.routes.workbench.reports import register_report_routes

    case = lineage_case
    op_id = create(case, "HOURS-001")
    case.plan(2, [op_id])
    task = case.task(2, op_id)
    for (quantity, hours), (start, end) in zip(reports, _HOUR_PERIODS):
        created = case.command(
            "create", task, case.values(quantity, effective_processing_hours=hours, actual_start=start, actual_end=end)
        )
        assert created["result"] == "committed"
    operation_ref = case.conn.execute("SELECT operation_ref FROM Schedule WHERE task_ref = ?", (task,)).fetchone()[0]

    field = WorkbenchFieldQueryRepository(case.conn).field_summary(2, {})
    assert (
        field["effective_processing_hours"], field["known_effective_processing_hours"], field["unknown_hour_reports"]
    ) == (total, known, unknown)

    api = FieldAPI(case)
    report_routes = Blueprint("hour_exit_reports", __name__)
    register_report_routes(report_routes)
    api.app.register_blueprint(report_routes)
    report = success(api.client.get("/api/workbench/v1/analytics", query_string={"topic": "records"}))["data"]["summary"]
    assert (
        report["effective_processing_hours"], report["known_effective_processing_hours"], report["unknown_hour_events"]
    ) == (total, known, unknown)

    sample = calibration(case)["samples_by_ref"][operation_ref]
    assert sample["effective_processing_hours"] == total
    reasons = {row["code"] for row in sample["exclusion_reasons"]}
    assert reasons & {"production_reports_missing", "processing_hours_unknown"} == ({hour_reason} if hour_reason else set())

    dashboard = WorkbenchDashboardService(case.conn)
    with dashboard.read_snapshot():
        sources = dashboard.load(NOW)
    sources.facts.project()
    item = next(row for row in actual(sources.facts)[0] if row["source"]["operation_ref"] == operation_ref)
    assert item["source"]["hours"]["effective_processing_hours"] == total
