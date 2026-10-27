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


@pytest.mark.parametrize("method", ["require_schema", "revision_clock"])
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
