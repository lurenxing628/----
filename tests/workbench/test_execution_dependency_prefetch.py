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
    dependencies.projections = lambda refs: requested.append(set(refs))
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
