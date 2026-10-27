"""Same-snapshot read reuse keeps stored types, identity guards and local dates."""

import math
from datetime import date, datetime, timezone
from typing import Any

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant
from core.services.workbench.dashboard.facts import typed
from core.services.workbench.facts.candidate_archive import load_adoption_candidate
from core.services.workbench.facts.candidate_baseline import AdmissionBaseline
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import (
    operation_labels,
    project_validated_tasks,
    tasks_projection_with_intervals,
    validate_saved_tasks,
)
from core.services.workbench.facts.decision_delivery import project_decision_delivery
from core.services.workbench.facts.plan_serialization import plain_plan_facts
from core.services.workbench.facts.resource_projection import resource_cohort
from core.services.workbench.run.decision_source import DecisionSource
from core.shared.strict_json import canonical_json
from data.repositories.schedule_time_sql import parse_dt_for_sql
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute, corrupt_update


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


def test_same_plan_load_keeps_partial_report_and_shared_current_comparison_rows(ledger_case, monkeypatch):
    case = ledger_case
    plan_ref = case.plan_ref(1)
    case.command("create", case.task(1, case.op_id), case.values(4))
    calls = _task_reads(monkeypatch)
    before = all_rows(case.conn)
    with case.ledger.read_snapshot():
        facts = case.ledger.load([_operation_ref(case)], comparison_plan_ref=plan_ref)
        assert calls == [plan_ref]
        current, comparison = facts["current_tasks"], facts["comparison_tasks"]
        assert canonical_json(current) == canonical_json(comparison)
        assert current is comparison
        ref = next(iter(current))
        assert current[ref] is comparison[ref]
        row = case.ledger.project_loaded(facts, contexts=False)[0]
        assert row.current_task_ref == row.comparison_task_ref == case.task(1, case.op_id)
        assert (row.known_completed_quantity, row.remaining_quantity, row.execution_state) == (4, 6, "partial")
    assert all_rows(case.conn) == before


def test_different_plan_load_keeps_both_historical_task_mappings(ledger_case, monkeypatch):
    case = ledger_case
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


def test_current_plan_owner_rejects_inactive_permanent_identity_before_task_read(ledger_case, monkeypatch):
    case = ledger_case
    plan_ref = case.plan_ref(1)
    corrupt_update(case.conn, "WorkbenchPlanSourceRefs", "UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE ref=?", (plan_ref,))
    calls = _task_reads(monkeypatch)
    before = all_rows(case.conn)
    with case.ledger.read_snapshot():
        with pytest.raises(WorkbenchCommandRejected) as error:
            case.ledger.load([_operation_ref(case)], comparison_plan_ref=plan_ref)
    assert error.value.code == "execution_ledger_unavailable"
    assert calls == []
    assert all_rows(case.conn) == before


def test_same_plan_duplicate_operation_mapping_is_still_rejected_without_writes(ledger_case):
    case = ledger_case
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


def test_cross_layer_schema_checks_share_leaf_contracts_in_one_snapshot(candidate_case, monkeypatch):
    from collections import Counter

    from core.infrastructure import workbench_execution_ledger_schema
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.facts import candidate_archive
    from core.services.workbench.run import preflight_execution
    from core.services.workbench.run.preflight_facts import PreflightFacts
    from data.repositories import (
        workbench_calibration_query_repo,
        workbench_execution_repo,
        workbench_plan_identity_repo,
        workbench_template_lineage_repo,
    )

    calls = Counter()
    checks = (
        ("ledger", "execution_ledger_contract_issues", (workbench_execution_repo, workbench_execution_ledger_schema)),
        ("void", "execution_void_contract_issues", (workbench_execution_repo,)),
        ("metadata", "workbench_metadata_contract_issues", (workbench_calibration_query_repo, workbench_template_lineage_repo)),
        ("process", "workbench_process_contract_issues", (workbench_calibration_query_repo, workbench_template_lineage_repo)),
        ("identity", "workbench_plan_identity_contract_issues",
         (workbench_plan_identity_repo, workbench_template_lineage_repo, candidate_archive)),
        ("lineage", "template_lineage_contract_issues", (workbench_template_lineage_repo,)),
    )
    for name, symbol, modules in checks:
        original = vars(modules[0])[symbol]

        def checked(conn, *, structure, _name=name, _original=original):
            calls[_name] += 1
            return _original(conn, structure=structure)

        for module in modules:
            monkeypatch.setattr(module, symbol, checked)

    conn = candidate_case.conn
    execution = WorkbenchExecutionRepository(conn)
    lineage = workbench_template_lineage_repo.WorkbenchTemplateLineageRepository(conn)
    calibration = workbench_calibration_query_repo.WorkbenchCalibrationQueryRepository(conn)
    identities = workbench_plan_identity_repo.WorkbenchPlanIdentityRepository(conn)
    with TransactionManager(conn).transaction():
        for _ in range(2):
            assert execution.schema_issues() == []
            assert lineage.schema_state() == "loaded" and not lineage.identity_schema_broken()
            assert calibration.schema_installed()
            candidate_archive.require_adoption_schema(conn)
            identities.read_revision()
            assert preflight_execution.execution_projections(PreflightFacts(conn), []) == {}
        assert calls == {name: 1 for name, _, _ in checks}


def _admission(case):
    _, candidates = compute(case)
    run, _, scope, _, capture, _ = load_adoption_candidate(case.conn, candidates[0])
    assert scope is not None
    return scope, capture, run["accepted_at"]


def test_admission_decodes_saved_execution_once_without_replaying_disposition_or_history(candidate_case, monkeypatch):
    from collections import Counter

    from core.services.workbench.facts import candidate_facts
    from core.services.workbench.facts.archived_calendar import ArchivedCalendar

    scope, capture, accepted_at = _admission(candidate_case)
    ref = capture["execution"][0]["operation_ref"]
    scope[ref]["execution"]["data_gaps"] = [{"earlier_disposition_copy": True}]
    calls = Counter()
    decode = candidate_facts.archived_table

    def table(archive, name):
        calls[name] += 1
        return decode(archive, name)

    monkeypatch.setattr(candidate_facts, "archived_table", table)
    facts = GenerationFacts(capture)
    first = AdmissionBaseline(capture, facts, scope)
    second = AdmissionBaseline(capture, facts, scope)
    calendar = ArchivedCalendar(facts.archive, facts=facts)
    assert calendar.table("Machines") is facts.table("Machines")
    assert first.selected == second.selected == set(scope)
    assert first.facts.execution[ref] is capture["execution"][0]
    assert calls and max(calls.values()) == 1
    assert not set(calls) & {"WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchExecutionLegacyFacts"}


def test_archived_labels_and_arrangements_keep_saved_work_without_formula_replay(candidate_case, monkeypatch):
    from core.services.workbench.facts import candidate_projection

    case = candidate_case
    scope, capture, _accepted_at = _admission(case)
    original = GenerationFacts(capture)
    AdmissionBaseline(capture, original, scope)
    ref = capture["execution"][0]["operation_ref"]
    first, _ = operation_labels(original, ref, {"op_id": original.operations[ref]})
    second, _ = operation_labels(original, ref)
    assert first == second and first is not second
    first["data_gaps"].append({"field": "private_probe", "code": "source_missing"})
    first["execution_at_generation"]["remaining_quantity"] += 1
    assert second["data_gaps"] == [] and second["execution_at_generation"] != first["execution_at_generation"]
    missing = GenerationFacts(capture)
    missing.tables["Parts"].clear()
    left, _ = operation_labels(missing, ref)
    right, _ = operation_labels(missing, ref)
    assert left["data_gaps"] == right["data_gaps"] != [] and left["data_gaps"] is not right["data_gaps"]
    with pytest.raises(WorkbenchCommandRejected) as binding:
        operation_labels(original, ref, {"op_id": original.operations[ref] + 1})
    assert binding.value.code == "candidate_artifact_invalid"
    store = CandidateStore(case.conn)
    run_ref = case.conn.execute("SELECT run_ref FROM WorkbenchRunJobs").fetchone()[0]
    candidate = store.candidates(run_ref)[0]
    rows = store.tasks(candidate["candidate_ref"])
    operation_calls, saved_operation = [], GenerationFacts.operation

    def read_operation(*args, **kwargs):
        operation_calls.append(args[1])
        return saved_operation(*args, **kwargs)

    with monkeypatch.context() as task_probe:
        task_probe.setattr(GenerationFacts, "operation", read_operation)
        projected, intervals, scheduled_ids = tasks_projection_with_intervals(rows, candidate, original)
    assert operation_calls == [row["operation_ref"] for row in rows]
    repeated = tasks_projection_with_intervals(rows, candidate, original)[0]
    assert projected == repeated
    validated, saved_intervals, validated_ids = validate_saved_tasks(rows, candidate, original, prepared_tasks={})
    assert validated_ids == scheduled_ids
    assert validated is rows and saved_intervals == intervals
    assert project_validated_tasks(validated, candidate, original, saved_intervals) == repeated
    delivery = project_decision_delivery(original, repeated, capture["input"]["batch_refs"], candidate=candidate)
    assert project_decision_delivery(original, repeated, capture["input"]["batch_refs"],
                                    candidate=candidate, intervals=saved_intervals) == delivery
    source = DecisionSource(store, run_ref)
    assert not source._projected
    assert source.resource_cohort["resources"] == resource_cohort([repeated], task_intervals=[intervals])
    assert source.delivery(candidate["candidate_ref"]) == delivery
    scheduled_checks, check_scheduled = [], candidate_projection._check_scheduled_rows

    def check_rows(scheduled, ids):
        scheduled_checks.append(ids)
        return check_scheduled(scheduled, ids)

    with monkeypatch.context() as task_probe:
        task_probe.setattr(candidate_projection, "_check_scheduled_rows", check_rows)
        rich = source.tasks(candidate["candidate_ref"])
        ready_source = source.candidate_source(candidate["candidate_ref"])
        summary = candidate_projection.candidate_summary(candidate, scope,
            scheduled_op_ids=ready_source.scheduled_op_ids)
        assert summary["completeness"] == "complete"
        assert len(scheduled_checks) == 1
        assert ready_source.scheduled_op_ids is source._scheduled_op_ids[candidate["candidate_ref"]]
    assert rich == repeated
    assert source.tasks(candidate["candidate_ref"]) is rich
    assert source.delivery(candidate["candidate_ref"]) == delivery
    assert intervals == {row["row_ref"]: (datetime.fromisoformat(row["start"]), datetime.fromisoformat(row["end"])) for row in projected}
    assert all("intervals" not in row and "task_intervals" not in row for row in projected)
    projected[0]["data_gaps"].append({"field": "private_probe", "code": "source_missing"})
    assert repeated[0]["data_gaps"] == []
    traced = {**candidate, "artifact": {**candidate["artifact"], "results": [
        dict(row, op_type_id=None) for row in candidate["artifact"]["results"]]}}
    actual = tasks_projection_with_intervals(rows, traced, original)[0]
    assert actual[0]["process_type_ref"] is actual[0]["process_type_label"] is None
    assert repeated[0]["process_type_ref"] is not None
    quantity = capture["execution"][0]["target_quantity"] + 1
    capture["execution"][0]["target_quantity"] = quantity
    scope[ref]["execution"]["target_quantity"] = quantity
    # Historical interpretation retains the saved value; generation owns the
    # formula and adoption validates against its current facts.
    saved = GenerationFacts(capture)
    AdmissionBaseline(capture, saved, scope)
    assert saved.execution[ref]["target_quantity"] == quantity


def test_admission_duplicate_operation_dtos_with_distinct_values_are_still_rejected(candidate_case):
    scope, capture, _accepted_at = _admission(candidate_case)
    facts = GenerationFacts(capture)
    duplicate = dict(capture["execution"][0])
    duplicate["target_quantity"] += 1
    capture["execution"].append(duplicate)
    with pytest.raises(WorkbenchCommandRejected) as error:
        AdmissionBaseline(capture, facts, scope)
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


def _original_typed(value: Any) -> Any:
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
    def __eq__(cls, other):
        return cls is other


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
