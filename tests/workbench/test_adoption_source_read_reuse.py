"""Real adoption reads reuse frozen inputs and snapshot scopes without notary reproof."""

import json
import sqlite3
from datetime import datetime
from unittest.mock import Mock, create_autospec

import pytest

from core.infrastructure.connection_guards import query_only
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.models.workbench_load_limits import MAX_WINDOW_RESPONSE_BYTES
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.shared.local_datetime import datetime_to_us
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
    with reader.read_snapshot() as context:
        return reader.workspace(context, PlanReadScope(plan["plan_ref"]))


def _baseline(case, plan):
    reader = WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot() as context:
        return reader.baseline_comparison(context, PlanReadScope(plan["plan_ref"]))


def test_candidate_and_trial_adoption_reuse_frozen_inputs_without_optimizer_preparation(trial_case, monkeypatch):
    from core.services.scheduler.resource_pool_builder import CapturedResourceFacts
    from core.services.scheduler.run import schedule_input_runtime_support as runtime_support
    from core.services.workbench.run import input_effort, input_runtime
    from core.services.workbench.run.candidate_adoption_validation import validate_adoption
    from tests.workbench.run_candidate_adoption_support import candidate
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as trial_adoption_service

    case = trial_case
    successor = case.operation(seq=2)
    case.plan(1, [case.op_id], end="2026-09-09T11:00:00")
    case.conn.execute(
        "INSERT INTO WorkCalendar(date,day_type,efficiency,"
        "allow_normal,allow_urgent,periods_json) VALUES ('2026-09-09','workday',1,'yes','yes',"
        "'[{\"start\":\"08:00\",\"end\":\"16:00\",\"day_offset\":0}]')"
    )
    case.conn.execute(
        "INSERT INTO MachineDowntimes(machine_id,scope_type,scope_value,start_time,end_time,start_us,end_us,"
        "reason_code,status) VALUES ('M1','machine','M1','2026-09-09 16:00:00','2026-09-09 17:00:00',?,?,"
        "'maintenance','active')",
        (datetime_to_us(datetime(2026, 9, 9, 16)), datetime_to_us(datetime(2026, 9, 9, 17))),
    )
    case.conn.commit()
    ref = candidate(case, case.settings(hold_window={"start": "2026-09-09T09:00", "end": "2026-09-09T09:01"}))
    saved = saved_scenario(case, {"base": {"candidate_ref": ref}}, changed=False)
    before, changes = snapshot(case.conn), case.conn.total_changes
    optimizer = (
        (input_runtime, "build_resource_pool", input_runtime.build_resource_pool),
        (input_runtime, "extend_downtime_map_for_resource_pool", input_runtime.extend_downtime_map_for_resource_pool),
        (input_effort, "build_operation_efforts", input_effort.build_operation_efforts),
        (input_effort, "saved_seed_efforts", input_effort.saved_seed_efforts),
    )
    checks = (
        (input_runtime, "_freeze_hold_window", input_runtime._freeze_hold_window),
        (input_runtime, "RuntimeResourceInputs", input_runtime.RuntimeResourceInputs),
        (runtime_support, "_resolve_algo_ops_to_schedule", runtime_support._resolve_algo_ops_to_schedule),
    )
    calls = {}
    for module, name, original in optimizer + checks:
        calls[name] = Mock(wraps=original)
        monkeypatch.setattr(module, name, calls[name])
    qualifications = create_autospec(
        CapturedResourceFacts.validate_fixed, side_effect=CapturedResourceFacts.validate_fixed
    )
    monkeypatch.setattr(CapturedResourceFacts, "validate_fixed", qualifications)
    resource_inits = []
    original_resource_init = CapturedResourceFacts.__init__

    def count_resource_init(self, tables):
        resource_inits.append(True)
        original_resource_init(self, tables)

    monkeypatch.setattr(CapturedResourceFacts, "__init__", count_resource_init)

    evidence = validate_adoption(case.conn, ref)
    assert evidence.prepared.seeds.frozen_op_ids == {case.op_id}
    rows = {row.op_id: row for row in evidence.outcome.validated_payload.schedule_rows}
    assert rows[case.op_id].start_time == datetime(2026, 9, 9, 8)
    assert rows[case.op_id].end_time == datetime(2026, 9, 9, 11)
    assert rows[successor].start_time >= rows[case.op_id].end_time
    for _, name, _ in checks:
        assert calls[name].call_count == 1, name
    assert len(resource_inits) == 1
    candidate_qualifications = qualifications.call_count
    assert candidate_qualifications > 0

    resource_inits.clear()
    preview = trial_adoption_service(case.conn).preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    for _, name, _ in checks:
        expected = 1 if name == "RuntimeResourceInputs" else 2
        assert calls[name].call_count == expected, name
    assert len(resource_inits) == 1
    assert qualifications.call_count > candidate_qualifications
    for _, name, _ in optimizer:
        calls[name].assert_not_called()
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_full_workspace_keeps_two_version_quantities_and_exact_output(adopted_versions):
    case, first, second = adopted_versions
    history_row = case.conn.execute(
        "SELECT source_ref, run_ref FROM ScheduleHistory WHERE version=?",
        (second["version"],),
    ).fetchone()
    artifact = json.loads(
        case.conn.execute(
            "SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=? AND run_ref=?",
            (history_row["source_ref"], history_row["run_ref"]),
        ).fetchone()[0]
    )
    before, changes = snapshot(case.conn), case.conn.total_changes
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
    assert provenance["source_ref"] == history_row["source_ref"] and provenance["run_ref"] == history_row["run_ref"]
    assert provenance["run_ref"] and provenance["source_ref"] and provenance["adopted_at"]
    assert data["tasks"][0]["quantity"] == 5
    assert baseline["item_count"] == 1 and baseline["items"] == [] and baseline["items_complete"] is False
    baseline_detail, scope_dict, baseline_state = _baseline(case, second)
    assert baseline_state == state and scope_dict == data["scope"]
    assert baseline_detail["items_complete"] is True and baseline_detail["item_count"] == 1
    assert baseline_detail["items"][0]["before"]["quantity"] == 3
    assert baseline_detail["items"][0]["after"] == {"task_ref": data["tasks"][0]["task_ref"]}
    assert len(canonical_json(data).encode("utf-8")) <= MAX_WINDOW_RESPONSE_BYTES
    repeated_data, repeated_state = _workspace(case, second)
    assert canonical_json(data) == canonical_json(repeated_data) and state == repeated_state
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_dashboard_keeps_frozen_quantity_across_live_batch_edits(adopted_versions):
    case, _, second = adopted_versions
    case.conn.execute("UPDATE Batches SET quantity=7 WHERE batch_id='B1'")
    case.conn.commit()
    before, changes = snapshot(case.conn), case.conn.total_changes
    data, _ = read_dashboard_analysis(
        case.conn,
        second["plan_ref"],
        query=DashboardAnalysisQuery("timeline"),
        as_of=datetime.now().replace(microsecond=0),
    )
    assert data["tasks"][0]["quantity"] == data["tasks"][0]["batch_quantity"] == 5
    assert data["tasks"][0]["quantity_basis"] == "run_admission"
    assert snapshot(case.conn) == before and case.conn.total_changes == changes


def test_nested_query_only_restores_readonly_on_exception():
    first, second = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    statements, other_statements = [], []
    try:
        first.execute("BEGIN")
        second.execute("BEGIN")
        first.set_trace_callback(statements.append)
        second.set_trace_callback(other_statements.append)
        with pytest.raises(ValueError, match="scope exit"):
            with query_only(first):
                with query_only(second), query_only(first):
                    with pytest.raises(sqlite3.OperationalError, match="readonly"):
                        first.execute("CREATE TABLE forbidden(value)")
                    with pytest.raises(sqlite3.OperationalError, match="readonly"):
                        second.execute("CREATE TABLE forbidden(value)")
                raise ValueError("scope exit")
        for sql in (statements, other_statements):
            assert not any("data_version" in statement.lower() for statement in sql)
            assert [statement for statement in sql if statement.startswith("PRAGMA")] == [
                "PRAGMA query_only",
                "PRAGMA query_only=ON",
                "PRAGMA query_only=OFF",
            ]
        first.set_trace_callback(None)
        second.set_trace_callback(None)
        assert first.execute("PRAGMA query_only").fetchone()[0] == 0
        assert second.execute("PRAGMA query_only").fetchone()[0] == 0
        first.execute("PRAGMA query_only=ON")
        statements.clear()
        first.set_trace_callback(statements.append)
        with query_only(first):
            pass
        assert statements == ["PRAGMA query_only"]
        first.set_trace_callback(None)
        assert first.execute("PRAGMA query_only").fetchone()[0] == 1
    finally:
        first.close()
        second.close()


def test_candidate_store_reuses_instance_local_facts_without_global_cache_retention(adopted_versions):
    from core.services.workbench.facts import candidate_archive, candidate_store
    from core.services.workbench.run.decision_source import DecisionSource

    case, _, second = adopted_versions
    history_row = case.conn.execute(
        "SELECT source_ref, run_ref FROM ScheduleHistory WHERE version=?", (second["version"],)
    ).fetchone()
    candidate_ref, run_ref = history_row["source_ref"], history_row["run_ref"]
    before, changes = snapshot(case.conn), case.conn.total_changes

    with TransactionManager(case.conn).transaction():
        store = candidate_store.CandidateStore(case.conn)
        _, _, _, scope, tasks, first_capture, _, first_facts = candidate_archive.load_adoption_candidate(
            case.conn, candidate_ref, store=store
        )
        assert store.capture(run_ref) is first_capture
        assert store.generation_facts(first_capture) is first_facts
        decision = DecisionSource(store, run_ref)
        assert decision.facts is first_facts
        assert tasks and scope

        # A separate CandidateStore instance does not retain cross-request global caches.
        separate_store = candidate_store.CandidateStore(case.conn)
        separate_capture = separate_store.capture(run_ref)
        assert separate_capture is not first_capture
        assert separate_store.generation_facts(separate_capture) is not first_facts

    dto, _ = _workspace(case, second)
    original_strategy = candidate_store.CandidateStore(case.conn).candidate(candidate_ref)["artifact"]["origin"][
        "strategy"
    ]
    dto["provenance"]["algorithm"]["origin"]["strategy"] = "mutated-strategy"
    assert (
        candidate_store.CandidateStore(case.conn).candidate(candidate_ref)["artifact"]["origin"]["strategy"]
        == original_strategy
    )
    fresh_dto, _ = _workspace(case, second)
    assert fresh_dto["provenance"]["algorithm"]["origin"]["strategy"] == original_strategy
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
