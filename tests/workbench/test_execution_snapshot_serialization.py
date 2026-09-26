"""Keep real ledger output and mutable-history isolation while removing scalar copies."""
from collections import namedtuple
from dataclasses import asdict, replace
from datetime import datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import _snapshot_value
from core.services.workbench.execution.ledger import ExecutionLedgerService
from tests.workbench.execution_ledger_support import NOW
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture


def test_real_ledger_snapshot_matches_asdict_and_cannot_mutate_history(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    saved = case.command("create", task, case.values(4, remark="原始说明"))["data"]["rows"][0]
    case.command("correct", saved["report_ref"], {"completed_quantity": 3, "remark": "更正说明",
                 "reason": "核对数量", "original_revision_ref": saved["revision_ref"]})
    projection = case.ledger.get_task(task)
    expected = asdict(projection)
    first = projection.to_dict()
    assert first == expected
    assert projection.reports and projection.reports[0].correction_history
    first["reports"][0]["correction_history"][0]["reason"] = "不得污染原记录"
    first["reports"][0]["remark"] = "不得污染原记录"
    first["write_context"]["new"] = [1, 2]
    first["data_gaps"].append({"code": "injected"})
    assert projection.to_dict() == expected
    assert case.ledger.get_task(task).to_dict() == expected
    assert projection.reports[0].to_dict() == asdict(projection.reports[0])


def test_nested_snapshot_preserves_dataclass_container_and_fallback_types(ledger_case):
    case = ledger_case
    case.install()
    value = case.ledger.get_task(case.task(1, case.op_id))
    pair = namedtuple("Pair", "left right")
    value = replace(value, write_context={
        "list": [1, None, "微秒", {"bytes": b"raw"}],
        "tuple": (True, 0.125, {"stamp": datetime(2026, 9, 26, 1, 2, 3, 4)}),
        "namedtuple": pair(1, [2]), "set": {1, 2},
    })
    actual = value.to_dict()
    assert actual == asdict(value)
    assert type(actual["write_context"]["namedtuple"]) is pair
    actual["write_context"]["namedtuple"].right.append(3)
    actual["write_context"]["set"].add(3)
    assert value.to_dict() == asdict(value)


def test_immutable_scalars_do_not_use_generic_deepcopy(monkeypatch):
    import core.models.workbench_execution as model
    def forbidden(value):
        raise AssertionError("Immutable scalar entered generic deepcopy")
    monkeypatch.setattr(model, "deepcopy", forbidden)
    values = [None, True, False, 123, 1.5, "工序", b"wire"]
    assert _snapshot_value({"rows": values}) == {"rows": values}


@pytest.mark.parametrize("contexts", [False, True])
def test_unchanged_projection_still_enforces_reader_size_limit(ledger_case, monkeypatch, contexts):
    from core.services.execution import ledger_reader
    case = ledger_case
    case.install()
    monkeypatch.setattr(ledger_reader, "MAX_REPORT_BYTES", 1)
    ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation'").fetchone()[0]
    with case.ledger.read_snapshot():
        facts = case.ledger.load([ref])
        with pytest.raises(WorkbenchCommandRejected) as error:
            case.ledger.project_loaded(facts, contexts=contexts)
    assert error.value.code == "query_too_large"


def test_added_write_context_still_enforces_final_size_limit(ledger_case, monkeypatch):
    from core.services.workbench.execution import ledger
    case = ledger_case
    case.install()
    monkeypatch.setattr(ledger, "MAX_REPORT_BYTES", 1000)
    service = ExecutionLedgerService(case.conn, clock=lambda: NOW,
        context_factory=lambda *args: {"write_token": "x" * 2000})
    with pytest.raises(WorkbenchCommandRejected) as error:
        service.get_task(case.task(1, case.op_id))
    assert error.value.code == "query_too_large"
