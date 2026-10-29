"""Same-snapshot read reuse keeps stored types, identity guards and local dates."""

from datetime import datetime, timezone

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant
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
from core.services.workbench.facts.resource_projection import resource_cohort
from core.services.workbench.run.decision_source import DecisionSource
from core.shared.strict_json import canonical_json
from data.repositories.schedule_time_sql import parse_dt_for_sql
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute


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
            assert preflight_execution.execution_projections(PreflightFacts(conn), [], prepared=[]) == {}
        assert calls == {name: 1 for name, _, _ in checks}


def _admission(case):
    _, candidates = compute(case)
    run, _, scope, _, capture, _, _ = load_adoption_candidate(case.conn, candidates[0])
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
    assert not set(calls) & {"WorkbenchProductionReports", "WorkbenchProductionReportRevisions"}


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
