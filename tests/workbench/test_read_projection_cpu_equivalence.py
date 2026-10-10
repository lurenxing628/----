"""Same-snapshot read reuse keeps stored types, identity guards and local dates."""

import math
from datetime import date, datetime, timezone

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.capacity.plan_calendar_intervals import instant
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.workbench.dashboard.facts import typed
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from data.repositories.schedule_time_sql import parse_dt_for_sql
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute, corrupt_update
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401


def _operation_ref(case):
    return case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=?",
                             (str(case.op_id),)).fetchone()[0]


def _task_reads(monkeypatch):
    calls = []
    original = WorkbenchExecutionRepository.task_rows

    def read(repo, operation_refs, plan_ref):
        calls.append(plan_ref)
        return original(repo, operation_refs, plan_ref)

    monkeypatch.setattr(WorkbenchExecutionRepository, "task_rows", read)
    return calls


def test_same_plan_load_keeps_partial_report_and_independent_current_comparison_rows(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    plan_ref = case.plan_ref(1)
    case.command("create", case.task(1, case.op_id), case.values(4))
    calls = _task_reads(monkeypatch)
    before = all_rows(case.conn)
    with case.ledger.read_snapshot():
        facts = case.ledger.load([_operation_ref(case)], comparison_plan_ref=plan_ref)
        assert calls == [plan_ref]
        current, comparison = facts["current_tasks"], facts["comparison_tasks"]
        assert canonical_json(current) == canonical_json(comparison)
        assert current is not comparison
        ref = next(iter(current))
        assert current[ref] is not comparison[ref]
        row = case.ledger.project_loaded(facts, contexts=False)[0]
        assert row.current_task_ref == row.comparison_task_ref == case.task(1, case.op_id)
        assert (row.known_completed_quantity, row.remaining_quantity, row.execution_state) == (4, 6, "partial")
        original = current[ref]["lock_status"]
        comparison[ref]["lock_status"] = "private probe"
        assert current[ref]["lock_status"] == original
    assert all_rows(case.conn) == before


def test_different_plan_load_keeps_both_historical_task_mappings(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    old = case.plan_ref(1)
    case.plan(2, [case.op_id], start="2026-09-10T08:00:00", end="2026-09-10T10:00:00")
    current = case.plan_ref(2)
    calls = _task_reads(monkeypatch)
    before = all_rows(case.conn)
    with case.ledger.read_snapshot():
        facts = case.ledger.load([_operation_ref(case)], comparison_plan_ref=old)
        ref = next(iter(facts["operations"]))
        assert calls == [current, old]
        assert facts["current_tasks"][ref]["task_ref"] == case.task(2, case.op_id)
        assert facts["comparison_tasks"][ref]["task_ref"] == case.task(1, case.op_id)
        assert facts["current_tasks"][ref]["start_time"] != facts["comparison_tasks"][ref]["start_time"]
    assert all_rows(case.conn) == before


def test_same_claimed_plan_still_resolves_its_permanent_identity_before_task_read(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    nonexistent = "f" * 48
    reader = ExecutionLedgerReader(case.conn, current_plan_provider=lambda conn: {"plan_ref": nonexistent})
    calls = _task_reads(monkeypatch)
    before = all_rows(case.conn)
    with reader.read_snapshot():
        with pytest.raises(WorkbenchPlanReferenceError):
            reader.load([_operation_ref(case)], comparison_plan_ref=nonexistent)
    assert calls == []
    assert all_rows(case.conn) == before


def test_same_plan_duplicate_operation_mapping_is_still_rejected_without_writes(ledger_case):
    case = ledger_case
    case.install()
    other = case.op("OP2", seq=2)
    case.conn.execute("""INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time)
        VALUES (1,?,'M1','O1','2026-09-09T11:00:00','2026-09-09T12:00:00')""", (other,))
    case.conn.commit()
    # Isolated fixture corruption: two independent arrangements now claim the
    # same permanent operation. Restore the original schema before the read.
    corrupt_update(case.conn, "WorkbenchPlanSourceRefs", """UPDATE WorkbenchPlanSourceRefs
        SET operation_ref=? WHERE kind='schedule_row' AND operation_id=? AND version=1""",
        (_operation_ref(case), other))
    before = all_rows(case.conn)
    with case.ledger.read_snapshot():
        with pytest.raises(WorkbenchCommandRejected) as error:
            case.ledger.load([_operation_ref(case)], comparison_plan_ref=case.plan_ref(1))
    assert (error.value.code, error.value.status) == ("constraint_conflict", 409)
    assert all_rows(case.conn) == before


def _admission(case):
    _, candidates = compute(case)
    candidate, scope, _, capture = load_adoption_candidate(case.conn, candidates[0])
    run = CandidateStore(case.conn).run(candidate["run_ref"])
    return scope, capture, run["accepted_at"]


@pytest.mark.parametrize("different", [1.0, True, "1"])
def test_admission_canonical_comparison_keeps_nested_storage_type_differences(candidate_case, different):
    case = candidate_case
    scope, capture, accepted_at = _admission(case)
    ref = capture["execution"][0]["operation_ref"]
    # Both are otherwise valid complete persisted DTOs. Python equality would
    # equate the float/bool values with 1; canonical evidence must reject them.
    capture["execution"][0]["data_gaps"] = [{"storage_probe": 1}]
    scope[ref]["execution"]["data_gaps"] = [{"storage_probe": different}]
    with pytest.raises(WorkbenchCommandRejected) as error:
        AdmissionBaseline(capture, GenerationFacts(capture), scope, accepted_at)
    assert error.value.code == "candidate_baseline_invalid"


def test_admission_still_checks_agreeing_dtos_against_original_archived_work(candidate_case):
    case = candidate_case
    scope, capture, accepted_at = _admission(case)
    original = GenerationFacts(capture)
    AdmissionBaseline(capture, original, scope, accepted_at)
    ref = capture["execution"][0]["operation_ref"]
    quantity = capture["execution"][0]["target_quantity"] + 1
    capture["execution"][0]["target_quantity"] = quantity
    scope[ref]["execution"]["target_quantity"] = quantity
    # The two redundant DTOs agree; the independently reconstructed archive
    # still disagrees. Reusing serialization must not remove that second proof.
    with pytest.raises(WorkbenchCommandRejected) as error:
        AdmissionBaseline(capture, GenerationFacts(capture), scope, accepted_at)
    assert error.value.code == "candidate_baseline_invalid"


def test_admission_duplicate_operation_dtos_with_distinct_values_are_still_rejected(candidate_case):
    scope, capture, accepted_at = _admission(candidate_case)
    facts = GenerationFacts(capture)
    duplicate = dict(capture["execution"][0])
    duplicate["target_quantity"] += 1
    capture["execution"].append(duplicate)
    with pytest.raises(WorkbenchCommandRejected) as error:
        AdmissionBaseline(capture, facts, scope, accepted_at)
    assert error.value.code == "candidate_baseline_invalid"


@pytest.mark.parametrize("value,expected", [
    ("2026-09-09", datetime(2026, 9, 9)),
    ("2026/09/09 08：30", datetime(2026, 9, 9, 8, 30)),
    ("2026-09-09T08:30:00.000001", datetime(2026, 9, 9, 8, 30, 0, 1)),
    ("2026-09-09 08:30:00.999999", datetime(2026, 9, 9, 8, 30, 0, 999999)),
    ("0001-01-01 00:00:00", datetime(1, 1, 1)),
    (datetime(2026, 9, 9, 8, 30, fold=1), datetime(2026, 9, 9, 8, 30)),
])
def test_calendar_instant_retains_lossless_factory_local_time(value, expected):
    result = instant(value)
    assert type(result) is datetime and result == expected and result.fold == 0
    assert result.isoformat(sep=" ") == parse_dt_for_sql(value)


@pytest.mark.parametrize("value", [
    None, "", "2026-02-30", "2026-09-09 24:00:00", "2026-09-09T08:30:00.1234567",
    "2026-09-09T08:30:00+08:00", datetime(2026, 9, 9, tzinfo=timezone.utc),
])
def test_calendar_instant_rejects_unproven_dates_including_point_times(value):
    with pytest.raises(ValueError, match="Invalid local plan/calendar time"):
        instant(value)


def _original_plain(value):
    """Pre-optimization storage contract, including unsupported scalar subclasses."""
    if isinstance(value, dict):
        return {key: _original_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_original_plain(item) for item in value]
    if isinstance(value, (date, datetime)):
        return {"storage_type": type(value).__name__, "iso": value.isoformat()}
    if isinstance(value, bytes):
        return {"storage_type": "blob", "hex": value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"storage_type": "float", "value": str(value)}
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("Unsupported private plan fact type: " + type(value).__name__)


def _original_typed(value):
    if isinstance(value, set):
        return sorted(_original_typed(item) for item in value)
    if isinstance(value, dict):
        return {key: _original_typed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_original_typed(item) for item in value]
    return _original_plain(value)


class _Text(str):
    pass


class _Count(int):
    pass


class _Measure(float):
    pass


class _Date(date):
    pass


@pytest.mark.parametrize("value", [
    None, False, True, 0, -1, 1 << 70, "", "quantity\x00中文",
    0.0, -0.0, 1.25, float("inf"), float("-inf"), float("nan"),
    date(2026, 9, 9), datetime(2026, 9, 9, 8, 30, 0, 1),
    datetime(2026, 9, 9, tzinfo=timezone.utc), _Date(2026, 9, 9),
    b"", b"\x00\xff", bytearray(b"raw"), _Text("text"), _Count(3),
    _Measure(1.25), _Measure(float("inf")), object(),
    [None, True, 0, 0.0, "0"], (date(2026, 9, 9), b"raw", float("nan")),
    {"task": {"quantity": 1 << 54, "complete": False}, "date": date(2026, 9, 9),
     "raw": b"\xff", "amount": float("inf"), "remaining": (None, 1.0)},
    set(), {3, 1, 2}, {date(2026, 9, 9)},
    {date(2026, 9, 9), date(2026, 9, 10)}, {None, 1}, {b"a", b"b"},
    {"unresolved": {3, 1, 2}, "rows": ({"done": True, "target": 10},)},
])
@pytest.mark.parametrize("project,original", [(plain_plan_facts, _original_plain), (typed, _original_typed)])
def test_primitive_fastpath_retains_original_storage_types_and_failures(value, project, original):
    try:
        expected = canonical_json(original(value))
    except TypeError as error:
        with pytest.raises(TypeError) as actual:
            canonical_json(project(value))
        assert str(actual.value) == str(error)
    else:
        assert canonical_json(project(value)) == expected


class _UnhashableMeta(type):
    __hash__ = None


class _HashFailureMeta(type):
    def __hash__(cls):
        raise AssertionError("Projection must not hash an object's class")


class _TextEqualityMeta(type):
    def __hash__(cls):
        return hash(str)

    def __eq__(cls, other):
        return other is str


class _UnhashableDict(dict, metaclass=_UnhashableMeta):
    pass


class _UnhashableDate(date, metaclass=_UnhashableMeta):
    pass


class _HashFailureDict(dict, metaclass=_HashFailureMeta):
    pass


class _HashFailureDate(date, metaclass=_HashFailureMeta):
    pass


class _TextEqualityDict(dict, metaclass=_TextEqualityMeta):
    pass


class _TextEqualityDate(date, metaclass=_TextEqualityMeta):
    pass


@pytest.mark.parametrize("value", [
    _UnhashableDict(day=date(2026, 9, 9), rows=[{"blob": b"raw"}]),
    _UnhashableDate(2026, 9, 9),
    _HashFailureDict(day=date(2026, 9, 9), rows=[{"blob": b"raw"}]),
    _HashFailureDate(2026, 9, 9),
    _TextEqualityDict(day=date(2026, 9, 9), rows=[{"blob": b"raw"}]),
    _TextEqualityDate(2026, 9, 9),
])
@pytest.mark.parametrize("project,original", [(plain_plan_facts, _original_plain), (typed, _original_typed)])
def test_exact_primitive_types_do_not_hash_or_trust_metaclass_scalar_equality(value, project, original):
    result = project(value)
    assert canonical_json(result) == canonical_json(original(value))
    assert type(result) is dict and result is not value
    if isinstance(value, dict):
        assert result["day"] == {"storage_type": "date", "iso": "2026-09-09"}
        assert result["rows"] is not value["rows"]
        result["rows"].append({"private": True})
        assert len(value["rows"]) == 1


@pytest.mark.parametrize("dict_type", [_UnhashableDict, _HashFailureDict, _TextEqualityDict])
@pytest.mark.parametrize("project,original", [(plain_plan_facts, _original_plain), (typed, _original_typed)])
def test_metaclass_does_not_override_original_nested_value_error_order(dict_type, project, original):
    value = dict_type(first=bytearray(b"unsupported"), day=date(2026, 9, 9), later=object())
    with pytest.raises(TypeError) as before:
        original(value)
    with pytest.raises(TypeError) as after:
        project(value)
    assert str(before.value) == str(after.value) == "Unsupported private plan fact type: bytearray"
