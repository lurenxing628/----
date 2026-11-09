"""Atomic receipts, original-intent replay, correction history and dry-run batches."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


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
    preparation = case.writer.prepare_batch([{"action": "create", "ref": task, "payload": case.values(1)}])
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
    with case.ledger.read_snapshot():
        first = case.ledger.load([saved["operation_ref"]], comparison_plan_ref=case.plan_ref(1))
        second = case.ledger.load([saved["operation_ref"]], comparison_plan_ref=case.plan_ref(1))
        assert first["plan"] is second["plan"]
        assert first["reports"][saved["operation_ref"]] is second["reports"][saved["operation_ref"]]
        assert len(reads) == 1
    case.ledger.project_operations([saved["operation_ref"]])
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
    preparation = case.writer.prepare_batch([
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
    with case.ledger.read_snapshot():
        projected = case.ledger.project_operations([saved['operation_ref']])
        provider = ExecutionFactProvider(case.conn, ledger=case.ledger)
        first = provider.facts_by_scope([scope], execution_projections=projected)
        second = provider.facts_by_scope([scope], execution_projections=projected)
        assert first == second and first[scope].target_quantity == 10
    assert calls == {'plan': 1, 'tasks': 1, 'scope': 0, 'resources': 1, 'orphans': 1}


@pytest.mark.parametrize("method", ["revision_clock", "scope_task_rows"])
def test_execution_adapter_translates_ledger_read_rejection(ledger_case, monkeypatch, method):
    from core.errors import AppError
    from core.models.operation_execution_scope import OperationExecutionScope
    from core.services.scheduler.execution.execution_fact_provider import ExecutionFactProvider
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

    case = ledger_case
    schedule_id = case.conn.execute("SELECT id FROM Schedule WHERE op_id=?", (case.op_id,)).fetchone()[0]
    scope = OperationExecutionScope.from_values(schedule_version=1, schedule_id=schedule_id, op_id=case.op_id, batch_id="B1")
    operation_ref = WorkbenchPlanIdentityRepository(case.conn).get_operation_refs([case.op_id])[case.op_id]
    projected = case.ledger.project_operations([operation_ref])

    def deny(*_args, **_kwargs):
        raise WorkbenchCommandRejected("ledger_read_rejected", "injected ledger read rejection", 409)

    # Rejected before the snapshot opens, or while adapting facts against the supplied projections.
    monkeypatch.setattr(case.ledger, method, deny)
    with pytest.raises(AppError) as error:
        ExecutionFactProvider(case.conn, ledger=case.ledger).facts_by_scope([scope], execution_projections=projected)
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
    from core.services.execution import projection as exec_projection
    from core.services.workbench.execution import production_report_validation as report_validation

    case = ledger_case
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(4, remark="initial"))["data"]["rows"][0]
    op_ref = saved["operation_ref"]

    history_calls = []
    orig_history = exec_projection.build_correction_history

    def counted_history(*args, **kwargs):
        history_calls.append(True)
        return orig_history(*args, **kwargs)

    monkeypatch.setattr(exec_projection, "build_correction_history", counted_history)
    with case.ledger.read_snapshot():
        light = case.ledger.project_loaded(case.ledger.load([op_ref]), include_history=False)[0]
    assert history_calls == []
    assert len(light.reports) == 1 and light.reports[0].correction_history == []

    with case.ledger.read_snapshot():
        full = case.ledger.project_loaded(case.ledger.load([op_ref]), include_history=True)[0]
    assert len(history_calls) == 1
    assert len(full.reports[0].correction_history) == 1

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


def test_bounded_report_and_void_reads_skip_sql_sort_and_preserve_sql_order(ledger_case, monkeypatch):
    from data.repositories import workbench_execution_repo

    case = ledger_case
    second = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, second])
    first_saved = case.command("create", case.task(2, case.op_id), case.values(2))["data"]["rows"][0]
    first_corrected = case.command(
        "correct",
        first_saved["report_ref"],
        {"original_revision_ref": first_saved["revision_ref"], "completed_quantity": 3, "reason": "Recount"},
    )["data"]["rows"][0]
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
        cap_ctx.setattr(workbench_execution_repo, "_CHUNK_SIZE", 1)
        cap_ctx.setattr(
            workbench_execution_repo,
            "stored_report_values",
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

    req_key = "corrupt-seq-request-key"
    case.conn.execute(
        "INSERT INTO WorkbenchCommandReceipts(request_key, receipt_ref, action, context_ref, input_json, outcome_json) "
        "VALUES (?, ?, 'execution.report_correct', ?, '{}', '{}')",
        (req_key, "a" * 32, first_saved["report_ref"]),
    )
    case.conn.execute(
        "INSERT INTO WorkbenchProductionReportRevisions"
        "(revision_ref, report_ref, sequence, previous_revision_ref, action, values_json, reason, "
        "local_operator, declared_operator, recorded_at, request_key) "
        "VALUES (?, ?, 'bad-seq', ?, 'correct', '{}', 'corrupt', 'op', 'op', '2026-09-09T11:00:00', ?)",
        ("b" * 48, first_saved["report_ref"], first_corrected["revision_ref"], req_key),
    )
    reports, heads, count = case.ledger.repo.reports([first_saved["operation_ref"]], 10)
    assert count == 3
    assert heads[first_saved["operation_ref"]] == [first_saved["report_ref"]]
    assert [row["sequence"] for row in reports[first_saved["operation_ref"]][first_saved["report_ref"]]] == [1, 2, "bad-seq"]
    with pytest.raises(WorkbenchCommandRejected) as bad_seq_err:
        case.ledger.project_operations([first_saved["operation_ref"]])
    assert bad_seq_err.value.code == "storage_failure" and bad_seq_err.value.status == 500

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
        case.ledger.project_operations([second_saved["operation_ref"]])
    assert orphan_err.value.code == "storage_failure" and orphan_err.value.status == 500
