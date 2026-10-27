"""Real adoption reads reuse proven sources only inside one SQLite snapshot."""

import json
import sqlite3
from collections import Counter
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest

from core.infrastructure import read_evidence
from core.infrastructure.connection_guards import query_only
from core.infrastructure.read_evidence import read_evidence_scope, verified_read
from core.models.content import same
from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.models.workbench_plan_scope import MAX_PLAN_RESPONSE_BYTES, PlanReadScope
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.facts import adoption_baseline_sources
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable, stored
from core.services.workbench.plan import adoption_baseline, adoption_baseline_identity, projection
from core.services.workbench.plan.point_evidence import official_point_work
from core.services.workbench.plan.process_order import project_process_order
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from core.shared.strict_json import canonical_json
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
from tests.workbench.plan_adoption_baseline_support import adopt_candidate, mutate_json
from tests.workbench.plan_read_support import make_api
from tests.workbench.run_candidate_support import corrupt_update
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


@pytest.fixture
def adopted_versions(trial_case):
    case = trial_case
    first = adopt_candidate(case, "reuse-first")
    case.conn.execute("UPDATE Batches SET quantity=5 WHERE batch_id='B1'")
    case.conn.commit()
    second = adopt_candidate(case, "reuse-second")
    return case, first, second


def _workspace(case, plan):
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        return reader.workspace(PlanReadScope(plan["plan_ref"]))


def _track_sources(monkeypatch):
    calls = []
    load = adoption_baseline_sources._candidate_source

    def observed(conn, audit):
        calls.append((audit["run_ref"], audit["candidate_ref"]))
        return load(conn, audit)

    monkeypatch.setattr(adoption_baseline_sources, "_candidate_source", observed)
    return calls


def test_candidate_and_trial_adoption_reuse_frozen_inputs_without_optimizer_preparation(trial_case, monkeypatch):
    from core.services.scheduler.resource_pool_builder import CapturedResourceFacts
    from core.services.scheduler.run import schedule_input_runtime_support as runtime_support
    from core.services.workbench.run import input as run_input
    from core.services.workbench.run import input_runtime
    from core.services.workbench.run.candidate_adoption_validation import validate_adoption
    from tests.workbench.run_candidate_adoption_support import candidate
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_adoption_service

    case = trial_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id], end="2026-09-09T11:00:00")
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_end,shift_hours,efficiency,"
                      "allow_normal,allow_urgent) VALUES ('2026-09-09','workday','08:00','16:00',8,1,'yes','yes')")
    case.conn.execute("INSERT INTO MachineDowntimes(machine_id,scope_type,scope_value,start_time,end_time,"
                      "reason_code,status) VALUES ('M1','machine','M1','2026-09-09 16:00:00',"
                      "'2026-09-09 17:00:00','maintenance','active')")
    case.conn.commit()
    ref = candidate(case, case.settings(hold_window={"start": "2026-09-09T09:00", "end": "2026-09-09T09:01"}))
    saved = saved_scenario(case, {"base": {"candidate_ref": ref}}, changed=False)
    before, changes = snapshot(case.conn), case.conn.total_changes
    optimizer = (
        (input_runtime, "_load_runtime_resource_inputs", input_runtime._load_runtime_resource_inputs),
        (input_runtime, "reserve_execution_machines", input_runtime.reserve_execution_machines),
        (run_input, "build_operation_efforts", run_input.build_operation_efforts),
        (run_input, "saved_seed_efforts", run_input.saved_seed_efforts),
    )
    checks = (
        (input_runtime, "_freeze_hold_window", input_runtime._freeze_hold_window),
        (input_runtime, "_validate_calendar_row", input_runtime._validate_calendar_row),
        (input_runtime, "_validate_downtime_row", input_runtime._validate_downtime_row),
        (runtime_support, "_resolve_algo_ops_to_schedule", runtime_support._resolve_algo_ops_to_schedule),
        (runtime_support, "_ensure_internal_runtime_hours", runtime_support._ensure_internal_runtime_hours),
    )
    calls = {}
    for module, name, original in optimizer + checks:
        calls[name] = Mock(wraps=original)
        monkeypatch.setattr(module, name, calls[name])
    qualifications = create_autospec(CapturedResourceFacts.validate_fixed, side_effect=CapturedResourceFacts.validate_fixed)
    monkeypatch.setattr(CapturedResourceFacts, "validate_fixed", qualifications)

    evidence = validate_adoption(case.conn, ref)
    assert evidence.prepared.frozen_op_ids == {case.op_id}
    rows = {row.op_id: row for row in evidence.payload.schedule_rows}
    assert rows[case.op_id].start_time == datetime(2026, 9, 9, 8)
    assert rows[case.op_id].end_time == datetime(2026, 9, 9, 11)
    assert rows[successor].start_time >= rows[case.op_id].end_time
    for _, name, _ in checks:
        assert calls[name].call_count == 1, name
    candidate_qualifications = qualifications.call_count
    assert candidate_qualifications > 0

    preview = trial_adoption_service(case.conn).preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    for _, name, _ in checks:
        assert calls[name].call_count == 2, name
    assert qualifications.call_count > candidate_qualifications
    for _, name, _ in optimizer:
        calls[name].assert_not_called()
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_full_workspace_keeps_two_version_quantities_and_exact_uncached_output(adopted_versions, monkeypatch):
    case, first, second = adopted_versions
    audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?",
                                       (second["version"],)).fetchone()[0])
    artifact = json.loads(case.conn.execute(
        "SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=? AND run_ref=?",
        (audit["candidate_ref"], audit["run_ref"])).fetchone()[0])
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    data, state = _workspace(case, second)
    baseline = data["projections"]["baseline"]
    assert baseline["state"] == "available" and baseline["baseline_plan"]["plan_ref"] == first["plan_ref"]
    provenance = data["provenance"]
    assert provenance["state"] == "available" and provenance["source_kind"] == "candidate_adoption"
    assert provenance["baseline"]["baseline_ref"] == first["plan_ref"]
    assert provenance["baseline"]["version"] == first["version"]
    assert provenance["baseline"]["captured_at"] == provenance["accepted_at"]
    assert provenance["algorithm"]["mode"] == "greedy" and provenance["source_label"] == artifact["label"]
    assert provenance["source_ref"] == audit["candidate_ref"] and provenance["run_ref"] == audit["run_ref"]
    assert provenance["run_ref"] and provenance["source_ref"] and provenance["adopted_at"]
    assert data["tasks"][0]["quantity"] == 5
    assert baseline["items"][0]["before"]["quantity"] == 3
    assert baseline["items"][0]["after"]["quantity"] == 5
    assert len(calls) == 2 and set(Counter(calls).values()) == {1}
    assert len(canonical_json(data).encode("utf-8")) <= MAX_PLAN_RESPONSE_BYTES
    with monkeypatch.context() as uncached:
        for module in (adoption_baseline_sources, adoption_baseline, read_evidence):
            uncached.setattr(module, "verified_read", lambda conn, key, load: load())
        old_data, old_state = _workspace(case, second)
    assert canonical_json(data) == canonical_json(old_data) and state == old_state
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_dashboard_has_one_complete_source_proof_and_frozen_quantity(adopted_versions, monkeypatch):
    case, _, second = adopted_versions
    case.conn.execute("UPDATE Batches SET quantity=7 WHERE batch_id='B1'")
    case.conn.commit()
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    data, _ = read_dashboard_analysis(case.conn, second["plan_ref"], query=DashboardAnalysisQuery("timeline"),
                                      as_of=datetime.now().replace(microsecond=0))
    assert len(calls) == 1
    assert data["tasks"][0]["quantity"] == data["tasks"][0]["batch_quantity"] == 5
    assert data["tasks"][0]["quantity_basis"] == "run_admission"
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_task_facts_without_reuse_scope_still_verify_source_once(adopted_versions, monkeypatch):
    case, _, second = adopted_versions
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    reader = WorkbenchPlanQueryService(case.conn)
    # This reader has a transaction but intentionally no evidence scope. It
    # must use the facts returned with its proof, not reprove them.
    with reader.read_snapshot():
        quantities, reason, operations = PlanReadContext(case.conn).adopted_task_facts(second["plan_ref"])
    assert reason is None and quantities is not None and quantities[case.op_id]["quantity"] == 5
    assert operations is not None and operations[case.op_id]["source"] == "internal"
    assert len(calls) == 1
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_candidate_admission_proof_reuses_strict_fields_and_preserves_extra_official_checks(adopted_versions, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.facts import run_input_codec

    case, _, second = adopted_versions
    audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?",
                                       (second["version"],)).fetchone()[0])
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = []
    for dto in (run_input_codec.ExecutionProjection, run_input_codec.ProductionReport):
        original = dto.__init__

        def observed(self, *args, _init=original, **kwargs):
            calls.append(type(self).__name__)
            _init(self, *args, **kwargs)

        monkeypatch.setattr(dto, "__init__", observed)
    with TransactionManager(case.conn).transaction(), read_evidence_scope(case.conn):
        source = adoption_baseline_sources.candidate_source_evidence(case.conn, audit)
        proof = source["admission_proof"]
        values = projection._source_quantities("candidate_adoption", source["arranged"], source["generation_facts"])
        assert values[case.op_id]["quantity"] == values[case.op_id]["batch_quantity"] == 5
        assert values[case.op_id]["quantity_reason"] is None and calls == []
        adoption_baseline_identity.verify_capture(proof.baseline, proof.tables, admission_proof=proof)
        official = next(row for row in proof.tables["WorkbenchPlanSourceRefs"]
                        if row["kind"] == "official" and row["active"] == 1
                        and row["version"] == proof.baseline["version"])
        for field in ("source_table", "plan_role"):
            saved = official[field]
            official[field] = "wrong-owner"
            try:
                with pytest.raises(AdoptionBaselineUnavailable) as error:
                    adoption_baseline_identity.verify_capture(proof.baseline, proof.tables, admission_proof=proof)
                assert (error.value.code, error.value.gap) == ("adoption_snapshot_invalid", "archived_official_reference")
            finally:
                official[field] = saved
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_empty_admission_proof_keeps_null_version_schedule_rejection():
    baseline = {"plan_ref": None, "version": None, "rows": []}
    tables = {"ScheduleHistory": [], "Schedule": [{"id": 1, "op_id": 1, "version": None}]}
    proof = SimpleNamespace(baseline=baseline, tables=tables)
    with pytest.raises(AdoptionBaselineUnavailable) as error:
        adoption_baseline_identity.verify_capture(baseline, tables, admission_proof=proof)
    assert error.value.gap == "baseline_matches_archived_schedule"


def test_arrangement_comparison_keeps_canonical_types_and_reuses_only_completed_intervals(monkeypatch):
    values = [None, "M1", True, 1, 1.0, -0.0, b"M1", datetime(2026, 9, 9), {"$sqlite_blob": "TTE="}, 1 << 64]
    base = {"machine_id": None, "operator_id": "O1", "start_time": "2026-09-09 08:00:00",
            "end_time": "2026-09-09 09:00:00"}
    for left in values:
        for right in values:
            current, candidate = dict(base, machine_id=left), dict(base, machine_id=right)
            expected = same({key: current[key] for key in ("machine_id", "operator_id")},
                            {key: candidate[key] for key in ("machine_id", "operator_id")})
            assert adoption_baseline_identity._arrangement_matches(current, candidate) == expected
    current, candidate = dict(base), dict(base, start_time="2026-09-09T08:00:00", end_time="2026-09-09T09:00:00")
    calls = []
    original = adoption_baseline_identity.public_time

    def observed(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(adoption_baseline_identity, "public_time", observed)
    assert adoption_baseline_identity._arrangement_matches(current, candidate,
        known_times=("2026-09-09 08:00:00", "2026-09-09 09:00:00"))
    assert calls == [candidate["start_time"], candidate["end_time"]]
    context = PlanReadContext.__new__(PlanReadContext)
    context._intervals = {}
    query = {"version": 2, "source_table": "schedule", "candidate_id": None, "scenario_id": None}
    assert context.peek_source_intervals(**query) is None
    completed = {1: (base["start_time"], base["end_time"])}
    context._intervals[context.source_key(query)] = completed
    assert context.peek_source_intervals(**query) is completed
    assert context.peek_source_intervals(**dict(query, version=3)) is None
    assert context.peek_source_intervals(**dict(query, source_table="candidate_rows", candidate_id=1)) is None


def test_caller_version_and_history_cannot_reuse_another_adoption(adopted_versions):
    case, first, second = adopted_versions
    reader = WorkbenchPlanQueryService(case.conn)
    history = WorkbenchPlanBaselineRepository(case.conn).get_history_result_summary(second["version"])
    before = snapshot(case.conn)
    assert history is not None
    with reader.read_snapshot(), read_evidence_scope(case.conn):
        context = PlanReadContext(case.conn)
        assert context.adopted_source(second["plan_ref"]) is not None
        with pytest.raises(AdoptionBaselineUnavailable):
            adoption_baseline.read_adoption_baseline(case.conn, plan_ref=second["plan_ref"],
                version=first["version"], history=history, facts={}, point_annotator=list, context=context)
        changed = dict(history)
        audit = json.loads(changed["result_summary"])
        audit["proof"]["run_ref"] = first["source_run_ref"]
        changed["result_summary"] = json.dumps(audit)
        with pytest.raises(AdoptionBaselineUnavailable):
            adoption_baseline.read_adoption_baseline(case.conn, plan_ref=second["plan_ref"],
                version=second["version"], history=changed, facts={}, point_annotator=list, context=context)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("fault", ["capture", "receipt", "arrangement"])
def test_new_request_rechecks_broken_source_and_rejects_old_snapshot(adopted_versions, fault):
    case, _, second = adopted_versions
    api = make_api(case.path)
    path = "/" + second["plan_ref"] + "/workspace"
    original = api.read(path)
    if fault == "capture":
        mutate_json(case.conn, "WorkbenchRunJobs", "baseline_json",
                    lambda value: value["rows"][0].update(end_time="2026-09-09T15:59:00"),
                    "run_ref=?", (second["source_run_ref"],))
    elif fault == "receipt":
        audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (second["version"],)).fetchone()[0])
        mutate_json(case.conn, "WorkbenchCommandReceipts", "outcome_json",
                    lambda value: value["data"]["official_plan"].update(plan_ref="f" * 48),
                    "request_key=?", (audit["request_key"],))
    else:
        corrupt_update(case.conn, "Schedule", "UPDATE Schedule SET end_time='2026-09-09T15:59:00' WHERE version=?", (second["version"],))
    before, changes = snapshot(case.conn), case.conn.total_changes
    fresh = api.read(path)["data"]
    assert fresh["tasks"][0]["quantity"] is None
    assert fresh["tasks"][0]["quantity_reason"] == "plan_target_unavailable"
    assert fresh["projections"]["baseline"]["state"] == "unavailable"
    response = api.get(path, snapshot_ref=original["meta"]["snapshot_ref"])
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_classified_source_failure_is_proved_once_per_workspace(adopted_versions, monkeypatch):
    case, _, second = adopted_versions
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET facts_json='{' WHERE run_ref=?",
                   (second["source_run_ref"],))
    before, changes = snapshot(case.conn), case.conn.total_changes
    calls = _track_sources(monkeypatch)
    data, _ = _workspace(case, second)
    assert data["tasks"][0]["quantity_reason"] == "plan_target_unavailable"
    assert data["projections"]["baseline"]["reason_code"] == "adoption_snapshot_invalid"
    assert data["projections"]["process_order"]["state"] == "unavailable"
    assert len(calls) == 1
    # The next request must recheck storage rather than retaining that failure.
    _workspace(case, second)
    assert len(calls) == 2
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


@pytest.mark.parametrize("raw", ['{', '[]', '{"x":NaN}', '{"x":1e400}', '{"x":1,"x":2}'])
def test_adoption_json_decode_classifies_invalid_documents(raw):
    with pytest.raises(AdoptionBaselineUnavailable) as error:
        stored(raw)
    assert error.value.code == "adoption_snapshot_invalid"


@pytest.mark.parametrize("error_type", [KeyError, TypeError, ValueError])
def test_source_programming_errors_escape_all_readers_and_are_not_cached(adopted_versions, monkeypatch, error_type):
    case, _, second = adopted_versions
    original = adoption_baseline_sources._candidate_source
    calls = []
    def broken_source(conn, audit):
        calls.append(True)
        raise error_type("injected internal source failure")
    monkeypatch.setattr(adoption_baseline_sources, "_candidate_source", broken_source)
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        context = PlanReadContext(case.conn)
        with context.read_scope():
            history = context.history(second["version"])
            readers = (
                lambda: context.adopted_task_facts(second["plan_ref"]),
                lambda: project_process_order(case.conn, plan_ref=second["plan_ref"], context=context),
                lambda: adoption_baseline.read_adoption_baseline(case.conn, plan_ref=second["plan_ref"],
                    version=second["version"], history=history, facts={}, point_annotator=list, context=context),
                lambda: official_point_work(case.conn, second["version"], context=context),
            )
            for read in readers:
                with pytest.raises(error_type, match="injected internal source failure"):
                    read()
            assert len(calls) == len(readers)
            monkeypatch.setattr(adoption_baseline_sources, "_candidate_source", original)
            source = context.adopted_source(second["plan_ref"])
            assert source is not None and source["audit"]["version"] == second["version"]


def test_original_baseline_is_still_checked_independently(adopted_versions, monkeypatch):
    case, first, second = adopted_versions
    corrupt_update(case.conn, "Schedule", "UPDATE Schedule SET end_time='2026-09-09T15:59:00' WHERE version=?", (first["version"],))
    before = snapshot(case.conn)
    data, _ = _workspace(case, second)
    assert data["tasks"][0]["quantity"] == 5
    assert data["projections"]["baseline"]["state"] == "unavailable"
    assert data["projections"]["baseline"]["reason_code"] == "adoption_baseline_drift"
    assert snapshot(case.conn) == before

    # Opening this adoption depends on its own source and official plan. The
    # original baseline's display remains independently unavailable.
    audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (second["version"],)).fetchone()[0])
    corrupt_update(case.conn, "ScheduleHistory", "DELETE FROM ScheduleHistory WHERE version=?", (first["version"],))
    from core.services.workbench.run.candidate_history import read_candidate_history

    calls = _track_sources(monkeypatch)
    statements, baseline_calls = [], []
    original_tasks = adoption_baseline.baseline_tasks
    def baseline_tasks(*args, **kwargs):
        baseline_calls.append(True)
        return original_tasks(*args, **kwargs)
    monkeypatch.setattr(adoption_baseline, "baseline_tasks", baseline_tasks)
    before, changes = snapshot(case.conn), case.conn.total_changes
    case.conn.set_trace_callback(statements.append)
    try:
        history, _ = read_candidate_history(case.conn, audit["candidate_ref"])
    finally:
        case.conn.set_trace_callback(None)
    assert history["total"] == 1
    entry = history["items"][0]
    assert entry["can_open"] is True and entry["evidence_gaps"] == []
    assert entry["adoption"]["reason"] == audit["reason"]
    assert entry["adoption"]["declared_operator"] == audit["declared_operator"]
    assert entry["adoption"]["baseline_ref"] == first["plan_ref"]
    assert calls == [(audit["run_ref"], audit["candidate_ref"])]
    assert baseline_calls == []
    receipt_queries = [sql.upper() for sql in statements if sql.upper().startswith("SELECT") and "FROM WORKBENCHCOMMANDRECEIPTS" in sql.upper()]
    adopted_receipts = [sql for sql in receipt_queries if "WHERE ACTION=" in sql and "CONTEXT_REF=" in sql]
    assert len(adopted_receipts) == 1
    assert "ORDER BY COMMITTED_AT_UTC,REQUEST_KEY LIMIT 10001" in adopted_receipts[0]
    assert not any("LENGTH(" in sql or "COUNT(" in sql or "SUM(" in sql for sql in receipt_queries)
    selected_histories = [sql for sql in statements if "FROM ScheduleHistory WHERE version=" in sql and "result_summary" in sql]
    assert len(selected_histories) == 1 and "LIMIT 2" in selected_histories[0]
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    data, _ = _workspace(case, second)
    assert data["tasks"][0]["quantity"] == 5
    assert data["projections"]["baseline"]["reason_code"] == "adoption_baseline_archived"
    # Immutable candidate preparation is shared across version-specific proofs;
    # every proof is still checked against that source after the memo lookup.
    calls.clear()
    from core.infrastructure.transaction import TransactionManager
    with TransactionManager(case.conn).transaction(), read_evidence_scope(case.conn):
        source = adoption_baseline_sources.candidate_source_evidence(case.conn, audit)
        later_audit = dict(audit, version=second["version"] + 1)
        assert adoption_baseline_sources.candidate_source_evidence(case.conn, later_audit) is source
        invalid_audit = dict(later_audit, proof=dict(audit["proof"], run_ref="f" * 48))
        with pytest.raises(AdoptionBaselineUnavailable):
            adoption_baseline_sources.candidate_source_evidence(case.conn, invalid_audit)
    assert calls == [(audit["run_ref"], audit["candidate_ref"])]


def test_oversized_capture_keeps_original_64_mib_rejection(adopted_versions):
    case, _, second = adopted_versions
    audit = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (second["version"],)).fetchone()[0])
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET facts_json=? WHERE run_ref=?",
                   ("{}" + " " * (64 * 1024 * 1024), audit["run_ref"]))
    changes = case.conn.total_changes
    response = make_api(case.path).get("/" + second["plan_ref"] + "/workspace")
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "candidate_capacity_exceeded"
    assert case.conn.total_changes == changes


def test_nested_snapshots_reuse_same_connection_and_restore_readonly_on_exception():
    first, second = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    statements, other_statements, loads = [], [], []

    def load(owner):
        loads.append(owner)
        return object()

    try:
        first.execute("BEGIN")
        second.execute("BEGIN")
        first.set_trace_callback(statements.append)
        second.set_trace_callback(other_statements.append)
        with pytest.raises(ValueError, match="scope exit"):
            with query_only(first), read_evidence_scope(first):
                original = verified_read(first, "source", lambda: load("first"))
                with read_evidence_scope(first):
                    assert verified_read(first, "source", lambda: load("same")) is original
                with read_evidence_scope(second), query_only(first):
                    assert verified_read(second, "source", lambda: load("second")) is not original
                    with read_evidence_scope(first):
                        assert verified_read(first, "source", lambda: load("first_again")) is original
                assert verified_read(first, "source", lambda: load("after_second")) is original
                with pytest.raises(sqlite3.OperationalError, match="readonly"):
                    first.execute("CREATE TABLE forbidden(value)")
                raise ValueError("scope exit")
        assert loads == ["first", "second"]
        for sql in (statements, other_statements):
            assert not any("data_version" in statement.lower() for statement in sql)
            assert [statement for statement in sql if statement.startswith("PRAGMA")] == [
                "PRAGMA query_only", "PRAGMA query_only=ON", "PRAGMA query_only=OFF"]
        first.set_trace_callback(None)
        second.set_trace_callback(None)
        assert first.execute("PRAGMA query_only").fetchone()[0] == 0
        assert second.execute("PRAGMA query_only").fetchone()[0] == 0
        # A new outer request gets its own source capture, and an already-ON
        # connection keeps that setting without a redundant SET.
        first.execute("PRAGMA query_only=ON")
        statements.clear()
        first.set_trace_callback(statements.append)
        with query_only(first), read_evidence_scope(first):
            assert verified_read(first, "source", lambda: load("new_request")) is not original
        assert statements == ["PRAGMA query_only"]
        first.set_trace_callback(None)
        assert first.execute("PRAGMA query_only").fetchone()[0] == 1
    finally:
        first.close()
        second.close()
