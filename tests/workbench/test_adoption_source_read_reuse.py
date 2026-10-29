"""Real adoption reads reuse proven sources only inside one SQLite snapshot."""

import json
import sqlite3
from collections import Counter
from datetime import datetime
from unittest.mock import Mock, create_autospec

import pytest

from core.infrastructure import read_evidence
from core.infrastructure.connection_guards import query_only
from core.infrastructure.read_evidence import read_evidence_scope, verified_read
from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.models.workbench_plan_scope import MAX_PLAN_RESPONSE_BYTES, PlanReadScope
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.facts import adoption_baseline_sources
from core.services.workbench.plan import adoption_baseline, adoption_baseline_identity, projection
from core.services.workbench.plan.point_evidence import official_point_work
from core.services.workbench.plan.process_order import project_process_order
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from core.shared.strict_json import canonical_json
from tests.workbench.plan_adoption_baseline_support import adopt_candidate
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


def _baseline(case, plan):
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        return reader.baseline_comparison(PlanReadScope(plan["plan_ref"]))


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
    assert "evaluations" not in provenance["algorithm"]
    assert provenance["source_ref"] == audit["candidate_ref"] and provenance["run_ref"] == audit["run_ref"]
    assert provenance["run_ref"] and provenance["source_ref"] and provenance["adopted_at"]
    assert data["tasks"][0]["quantity"] == 5
    assert baseline["item_count"] == 1 and baseline["items"] == [] and baseline["items_complete"] is False
    assert len(calls) == 2 and set(Counter(calls).values()) == {1}
    baseline_detail, scope_dict, baseline_state = _baseline(case, second)
    assert baseline_state == state and scope_dict == data["scope"]
    assert baseline_detail["items_complete"] is True and baseline_detail["item_count"] == 1
    assert baseline_detail["items"][0]["before"]["quantity"] == 3
    assert baseline_detail["items"][0]["after"] == {"task_ref": data["tasks"][0]["task_ref"]}
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
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_arrangement_comparison_keeps_canonical_types_and_reuses_only_completed_intervals(monkeypatch):
    base = {"machine_id": None, "operator_id": "O1", "start_time": "2026-09-09 08:00:00",
            "end_time": "2026-09-09 09:00:00"}
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
    query = {"version": 2}
    assert context.peek_source_intervals(**query) is None
    completed = {1: (base["start_time"], base["end_time"])}
    context._intervals[context.source_key(query)] = completed
    assert context.peek_source_intervals(**query) is completed
    assert context.peek_source_intervals(**dict(query, version=3)) is None


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


def test_readonly_candidate_archive_eliminates_clone_json_and_shares_generation_facts_cache(adopted_versions, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.facts import candidate_archive, candidate_store
    from core.services.workbench.history.reading import HistoryReader
    from core.services.workbench.run.decision_source import DecisionSource

    case, _, second = adopted_versions
    audit = json.loads(case.conn.execute(
        "SELECT result_summary FROM ScheduleHistory WHERE version=?", (second["version"],)
    ).fetchone()[0])
    candidate_ref, run_ref = audit["candidate_ref"], audit["run_ref"]
    before, changes = snapshot(case.conn), case.conn.total_changes

    with TransactionManager(case.conn).transaction():
        _, _, _, _, warm_capture, _, warm_facts, _ = candidate_archive.load_adoption_candidate_with_key(
            case.conn, candidate_ref
        )

    clone_calls = Mock(wraps=candidate_store.clone_json)
    facts_calls = Mock(wraps=candidate_store.GenerationFacts)
    monkeypatch.setattr(candidate_store, "clone_json", clone_calls)
    monkeypatch.setattr(candidate_store, "GenerationFacts", facts_calls)

    with TransactionManager(case.conn).transaction(), read_evidence_scope(case.conn):
        _, _, scope, tasks, capture, _, facts, _ = candidate_archive.load_adoption_candidate_with_key(
            case.conn, candidate_ref
        )
        assert clone_calls.call_count == 0
        assert facts_calls.call_count == 0
        assert facts is warm_facts and capture is warm_capture

        readonly_store = candidate_store.ReadOnlyCandidateStore(case.conn)
        assert readonly_store.copy_on_read is False
        assert readonly_store.capture(run_ref) is warm_capture
        assert clone_calls.call_count == 0

        history_reader = HistoryReader(case.conn)
        history_run = history_reader._run(run_ref)
        assert history_run["facts"] is warm_facts
        assert history_run["capture"] is warm_capture
        assert clone_calls.call_count == 0
        assert facts_calls.call_count == 0

        decision = DecisionSource(candidate_store.CandidateStore(case.conn), run_ref)
        assert decision.facts is warm_facts
        assert facts_calls.call_count == 0

        copied_execution = [dict(row) for row in capture["execution"]]
        reused = candidate_store.cached_generation_facts(dict(capture, execution=copied_execution))
        assert reused is warm_facts
        assert facts_calls.call_count == 0

        mutable_store = candidate_store.CandidateStore(case.conn)
        mutable_capture = mutable_store.capture(run_ref)
        assert mutable_capture is not warm_capture
        mutable_capture["input"]["batch_refs"].append("mutated-in-test")
        assert "mutated-in-test" not in warm_capture["input"]["batch_refs"]
        assert tasks and scope

    dto, _ = _workspace(case, second)
    original_strategy = candidate_store.CandidateStore(case.conn).candidate(candidate_ref)["artifact"]["origin"]["strategy"]
    dto["provenance"]["algorithm"]["origin"]["strategy"] = "mutated-strategy"
    assert candidate_store.CandidateStore(case.conn).candidate(candidate_ref)["artifact"]["origin"]["strategy"] == original_strategy
    assert candidate_store.ReadOnlyCandidateStore(case.conn).candidate(candidate_ref)["artifact"]["origin"]["strategy"] == original_strategy
    fresh_dto, _ = _workspace(case, second)
    assert fresh_dto["provenance"]["algorithm"]["origin"]["strategy"] == original_strategy
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
