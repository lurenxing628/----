"""Dependency prefetch walks a whole batch once; per-operation checks stay exact."""

from types import SimpleNamespace

from core.services.workbench.execution import production_report_dependencies as module
from core.services.workbench.execution.production_report_dependencies import ReportDependencies
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


def _chain(size):
    refs = [f"OP{i:04d}" for i in range(size)]
    parents = {ref: refs[index - 1:index] if index else [] for index, ref in enumerate(refs)}
    children = {ref: refs[index + 1:index + 2] for index, ref in enumerate(refs)}
    dependencies = ReportDependencies(SimpleNamespace(conn=None), [SimpleNamespace(operation_ref=ref) for ref in refs])
    dependencies.routes["B"] = parents, children
    return dependencies, [{"batch_id": "B", "operation_ref": ref} for ref in refs]


def test_multi_root_prefetch_uses_linear_graph_visits_and_does_not_cache_all_closures(monkeypatch):
    dependencies, operations = _chain(400)
    walked, original = [], module._reachable_from

    def captured(graph, pending):
        result = original(graph, pending)
        walked.append(len(result))
        return result

    monkeypatch.setattr(module, "_reachable_from", captured)
    dependencies.prepare(operations)
    assert len(walked) == 2 and sum(walked) <= 2 * len(operations)
    assert dependencies._relative_rows == {}
    middle = operations[200]
    downstream = dependencies.relatives(middle)
    upstream = dependencies.relatives(middle, predecessors=True)
    assert len(downstream) == 199 and len(upstream) == 200
    before = len(walked)
    assert dependencies.relatives(middle) == downstream
    assert dependencies.relatives(middle, predecessors=True) == upstream
    assert len(walked) == before
    dependencies.relatives(operations[0])
    assert len(dependencies._relative_rows) == 1


def test_prefetch_preserves_merged_cycle_peers_and_shared_branch_dependencies():
    dependencies, operations = _chain(5)
    parents, children = dependencies.routes["B"]
    parents["OP0004"] = ["OP0002", "OP0003"]
    children["OP0002"].append("OP0004")
    cycle = ("B", None, "merged-group")
    dependencies.merged.update({ref: cycle for ref in ("OP0001", "OP0002")})
    dependencies.cycles[cycle] = ["OP0001", "OP0002"]
    dependencies.sequences.update({"OP0001": 1, "OP0002": 2})
    requested = []
    dependencies.projections = lambda refs: (requested.append(set(refs)), [])[1]
    dependencies.prepare([operations[1]])
    assert requested == [set(row["operation_ref"] for row in operations)]
    assert dependencies.relatives(operations[1], predecessors=True) == ["OP0000"]
    assert dependencies.relatives(operations[1]) == ["OP0003", "OP0004"]


def test_batch_preparation_computes_execution_change_once_per_operation(ledger_case, monkeypatch):
    from core.services.workbench.execution import production_report_prepare, production_report_validation

    case = ledger_case
    second = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, second])
    calls, original = [], production_report_prepare.execution_facts_changed

    def captured(before, after):
        calls.append(after.operation_ref)
        return original(before, after)

    def unexpected(*args):
        raise AssertionError("The batch already compared each operation's execution facts")

    monkeypatch.setattr(production_report_prepare, "execution_facts_changed", captured)
    monkeypatch.setattr(production_report_validation, "execution_facts_changed", unexpected)
    prepared = case.writer.prepare_batch([
        {"action": "create", "ref": case.task(2, op), "payload": case.values(1)} for op in (case.op_id, second)])
    assert len(calls) == len(set(calls)) == len(prepared.projections) == 2


def test_batch_preparation_prefetches_operator_machine_authorizations_once(ledger_case, monkeypatch):
    import pytest

    from core.services.workbench.execution.production_report_prepare import ReportBatchRejected
    from data.repositories.operator_machine_repo import OperatorMachineRepository

    case = ledger_case
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Mill','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Operator 2')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M2'),('O2','M1')")
    second, third = case.op("OP2", seq=2), case.op("OP3", seq=3)
    case.plan(2, [case.op_id, second, third])
    batch_calls = []
    original_list = OperatorMachineRepository.list_simple_rows_for_operators

    def tracked_list(repo, operator_ids):
        batch_calls.append(list(operator_ids))
        return original_list(repo, operator_ids)

    def unexpected_exists(repo, operator_id, machine_id):
        raise AssertionError(f"Unexpected per-pair OperatorMachine.exists({operator_id!r}, {machine_id!r})")

    monkeypatch.setattr(OperatorMachineRepository, "list_simple_rows_for_operators", tracked_list)
    monkeypatch.setattr(OperatorMachineRepository, "exists", unexpected_exists)
    m1, m2 = case.ref("machine", "M1"), case.ref("machine", "M2")
    o1, o2 = case.ref("operator", "O1"), case.ref("operator", "O2")
    prepared = case.writer.prepare_batch([
        {"action": "create", "ref": case.task(2, case.op_id), "payload": case.values(1, actual_machine_ref=m1, actual_operator_ref=o1)},
        {"action": "create", "ref": case.task(2, second), "payload": case.values(1, actual_machine_ref=m2, actual_operator_ref=o1)},
        {"action": "create", "ref": case.task(2, third), "payload": case.values(1, actual_machine_ref=m1, actual_operator_ref=o2)},
    ])
    assert len(prepared.appended) == 3
    assert batch_calls == [["O1", "O2"]]

    batch_calls.clear()
    with pytest.raises(ReportBatchRejected) as rejected:
        case.writer.prepare_batch([
            {"action": "create", "ref": case.task(2, case.op_id), "payload": case.values(1, actual_machine_ref=m1, actual_operator_ref=o1)},
            {"action": "create", "ref": case.task(2, second), "payload": case.values(1, actual_machine_ref=m2, actual_operator_ref=o2)},
        ])
    assert rejected.value.code == "constraint_conflict" and rejected.value.row_number == 2
    assert batch_calls == [["O1", "O2"]]
