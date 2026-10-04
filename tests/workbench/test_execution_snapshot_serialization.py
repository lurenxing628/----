"""Keep real ledger output and mutable-history isolation while removing scalar copies."""
from collections import OrderedDict, namedtuple
from copy import deepcopy
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import date, datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
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


def _legacy_snapshot(value):
    """The recursive snapshot this module used before the one-pass builder, kept as the oracle."""
    if type(value) in (str, int, float, bool, bytes, type(None)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _legacy_snapshot(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        return type(value)(*(_legacy_snapshot(item) for item in value))
    if isinstance(value, (list, tuple)):
        return type(value)(_legacy_snapshot(item) for item in value)
    if isinstance(value, dict):
        return type(value)((_legacy_snapshot(key), _legacy_snapshot(item)) for key, item in value.items())
    return deepcopy(value)


def _assert_same_shape(actual, expected):
    """Equal values, equal container types and equal key order all the way down."""
    assert type(actual) is type(expected)
    if isinstance(actual, dict):
        assert list(actual) == list(expected)
        for key in actual:
            _assert_same_shape(actual[key], expected[key])
    elif isinstance(actual, (list, tuple)):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            _assert_same_shape(left, right)
    else:
        assert actual == expected


def test_one_pass_snapshot_equals_legacy_recursive_snapshot(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    kept = case.command("create", task, case.values(4, remark="保留"))["data"]["rows"][0]
    case.command("correct", kept["report_ref"], {"completed_quantity": 3, "remark": "更正", "reason": "核对数量",
                 "original_revision_ref": kept["revision_ref"]})
    voided = case.command("create", task, case.values(1))["data"]["rows"][0]
    case.command("report_void", voided["report_ref"], {"original_revision_ref": voided["revision_ref"],
                 "reason": "误记", "declared_operator": "班长"})
    projection = case.ledger.get_task(task)
    assert projection.reports and projection.reports[0].correction_history and projection.voided_reports
    pair = namedtuple("Pair", "left right")
    rich = replace(projection, plan_identity=OrderedDict([("b", [1, (2, {"x": b"raw"})]), ("a", None)]), write_context={
        "nested_report": projection.reports[0], "reports": list(projection.reports), ("tuple", "key"): {"day": date(2026, 10, 4)},
        "namedtuple": pair(datetime(2026, 10, 4, 8, 30), [{"q": 1.25}]), "set": {1, 2}, "inf": float("inf"), "empty": [{}, []],
    })
    for value in (projection, projection.reports[0], rich, rich.write_context, [projection, {"k": projection.reports}]):
        expected = _legacy_snapshot(value)
        actual = value.to_dict() if hasattr(value, "to_dict") else _snapshot_value(value)
        assert actual == expected
        _assert_same_shape(actual, expected)
    assert canonical_json(projection.to_dict()) == canonical_json(_legacy_snapshot(projection))
    snapshot = rich.to_dict()
    snapshot["plan_identity"]["b"][1][1]["x"] = b"changed"
    snapshot["write_context"]["nested_report"]["correction_history"][0]["reason"] = "不得污染原记录"
    snapshot["write_context"]["namedtuple"].right[0]["q"] = 9
    assert rich.to_dict() == _legacy_snapshot(rich)


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
