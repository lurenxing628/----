"""Decision differences preserve factual coverage and saved selection identities."""

from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.decision_delivery import project_decision_delivery
from core.services.workbench.facts.decision_metrics import (
    METRIC_VERSION,
    delivery_coverage,
    operation_change_metrics,
)
from core.services.workbench.facts.preparation_projection import project_operation_effort
from core.services.workbench.run.decision import read_run_decision
from core.services.workbench.run.decision_impact import (
    arrangement_view,
    by_operation,
    iter_operation_comparisons,
    operation_changes,
    operation_delta,
)
from core.services.workbench.run.decision_queries import read_decision_details
from core.services.workbench.run.decision_resource_engine import DecisionResources
from core.services.workbench.run.decision_source import DecisionSource, OfficialReading
from core.services.workbench.run.decision_workspace import _reference_workspace
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.run_candidate_support import compute
from tests.workbench.test_material_stage_release import add_requirement
from tests.workbench.test_run_candidate_partial_adoption import persisted_partial_run


def test_archive_builder_reuses_its_admission_scope_for_candidate_metrics(candidate_case, monkeypatch):
    from core.services.workbench.facts import decision_metrics, decision_read_model

    scopes = []
    original_summary = decision_read_model.project_candidate_summary

    def prepared_summary(*args, **kwargs):
        scopes.append(kwargs["operation_scope"])
        return original_summary(*args, **kwargs)

    def repeated_admission(*args, **kwargs):
        raise AssertionError("候选摘要重复派生本次已准备的准入集合")

    monkeypatch.setattr(decision_metrics, "admission_operations", repeated_admission)
    monkeypatch.setattr(decision_read_model, "project_candidate_summary", prepared_summary)
    _, refs = compute(candidate_case)
    assert len(scopes) == len(refs) > 0
    assert all(scope is scopes[0] for scope in scopes)


def test_unspecified_due_is_excluded_while_invalid_due_keeps_delivery_unknown():
    facts = GenerationFacts.__new__(GenerationFacts)
    facts.__dict__.update(
        operations={"op-a": 1, "op-b": 2},
        entity_refs={("batch", "B1"): "batch-a", ("batch", "B2"): "batch-b"},
        tables={"BatchOperations": {1: {"id": 1, "batch_id": "B1"}, 2: {"id": 2, "batch_id": "B2"}},
                "Batches": {"B1": {"batch_id": "B1", "part_no": "P1", "part_name": "零件A", "due_date": "9999-12-31"},
                            "B2": {"batch_id": "B2", "part_no": "P2", "part_name": "零件B", "due_date": "2026-09-09"}}},
    )
    tasks = [{"row_ref": "row-a", "operation_ref": "op-a", "batch_ref": "batch-a", "start": "2026-09-10T08:00:00", "end": "2026-09-10T10:00:00"},
             {"row_ref": "row-b", "operation_ref": "op-b", "batch_ref": "batch-b", "start": "2026-09-10T08:00:00", "end": "2026-09-10T10:00:00"}]

    def evaluate():
        return delivery_coverage(project_decision_delivery(facts, tasks, ["batch-a", "batch-b"]))

    coverage, values = evaluate()
    assert coverage["state"] == "complete" and coverage["excluded_due_count"] == 1
    assert values["overdue_count"]["value"] == 1 and values["total_tardiness_hours"]["value"] == 10
    facts.tables["Batches"]["B2"]["due_date"] = "9999-12-31"
    _, values = evaluate()
    assert values["total_tardiness_hours"]["state"] == "not_applicable"
    assert values["total_tardiness_hours"]["value"] is None
    items = project_decision_delivery(facts, tasks, ["batch-a", "batch-b"])
    common = common_completed_delivery(items, items)["common_delivery"]
    assert common["before"]["excluded_due_count"] == common["after"]["excluded_due_count"] == 2
    assert common["delay_delta_hours"] is common["overdue_delta_count"] is None
    facts.tables["Batches"]["B2"]["due_date"] = None
    coverage, values = evaluate()
    assert coverage["invalid_due_count"] == coverage["unknown_due_count"] == 1
    assert values["total_tardiness_hours"]["value"] is None
    items = project_decision_delivery(facts, tasks, ["batch-a", "batch-b"])
    common = common_completed_delivery(items, items)["common_delivery"]
    assert common["before"]["invalid_due_count"] == common["after"]["unknown_due_count"] == 1
    assert common["delay_delta_hours"] is common["overdue_delta_count"] is None


def test_resource_reference_gap_preserves_known_operation_change_subtotal():
    from core.services.workbench.facts.decision_read_models import Memberships

    template = {"start": "2026-09-09T08:00:00", "end": "2026-09-09T10:00:00", "source": "internal",
                "machine": {"ref": "machine-a"}, "operator": {"ref": "operator-a"}, "supplier": None, "data_gaps": []}
    before = [dict(template, row_ref="before-a", operation_ref="op-a"), dict(template, row_ref="before-b", operation_ref="op-b")]
    after = [dict(template, row_ref="after-a", operation_ref="op-a", start="2026-09-09T09:00:00"),
             dict(template, row_ref="after-b", operation_ref="op-b", machine={"ref": None})]
    groups, original = by_operation(before), deepcopy((before, after))
    before_times, after_times = ({row["row_ref"]: (datetime.fromisoformat(row["start"]), datetime.fromisoformat(row["end"]))
                                 for row in rows} for rows in (before, after))
    inputs = {"deferred_refs": set(), "reference_deferred_refs": set(),
              "reference_groups": groups, "selected_groups": by_operation(after),
              "task_intervals": after_times, "reference_task_intervals": before_times}
    values = operation_changes(["op-a", "op-b"], True, selected_available=True, **inputs)
    assert (before, after) == original
    assert values["changed_operation_count"]["value"] is None
    assert values["changed_operation_count"]["known_subtotal"] == 1
    assert values["machine_change_count"]["value"] is None
    assert values["machine_change_count"]["known_subtotal"] == 0
    comparisons = dict(iter_operation_comparisons(["op-a", "op-b"], True, selected_available=True, display=True, **inputs))
    assert operation_change_metrics(comparisons.values(), ["op-a", "op-b"], True) == values
    unavailable = operation_change_metrics(comparisons.values(), ["op-a", "op-b"], False)
    assert unavailable == operation_changes(["op-a", "op-b"], False, selected_available=True, **inputs)
    assert all(value["value"] is value["known_subtotal"] is None and value["unknown_count"] == 2
               and value["reason"]["code"] == "reference_required" for value in unavailable.values())
    unavailable = operation_change_metrics(comparisons.values(), ["op-a", "op-b"], True, selected_available=False)
    assert unavailable == operation_changes(["op-a", "op-b"], True, selected_available=False, **inputs)
    assert all(value["value"] is value["known_subtotal"] is None and value["unknown_count"] == 2
               and value["reason"]["code"] == "candidate_result_unavailable" for value in unavailable.values())
    first = next(iter_operation_comparisons(["op-a"], True, selected_available=True, **inputs))[1]
    assert first["before"] is before[0] and first["after"] is after[0]
    missing = list(iter_operation_comparisons(["missing"], True, selected_available=True, **inputs))
    assert missing[0][1]["change_kinds"] == ["unknown"] and set(groups) == {"op-a", "op-b"}
    source = object.__new__(DecisionSource)
    source.comparison_mode, source.reference_ref = "candidates", "candidate-a"
    source._analysis = {"candidate-a": before}
    assert source.computation_key("reference") == "candidate-a"
    assert source.computation_key("candidate-b") == "candidate-b"
    assert source.analysis_groups("reference") is source.analysis_groups("reference")
    source._task_intervals = {"candidate-a": before_times}
    assert source.task_intervals("reference") is source.task_intervals("candidate-a")
    source._official_reading = OfficialReading(
        {"identity": {"state": "available"}, "tasks": before, "operation_refs": ["op-a", "op-b"]}, False)
    source.memberships = Memberships({"operation_refs": [], "batch_refs": [], "operation_sets": [], "batch_sets": []})
    assert source.official_members == {"identity": {"state": "available"}, "operation_refs": ["op-a", "op-b"]}
    source.comparison_mode = "admission_official"
    assert source.computation_key("reference") == "reference"
    source.comparison_mode, source.reference_ref = "candidates", None
    assert source.computation_key("reference") == "reference"


def test_unproven_official_point_keeps_time_difference_unknown():
    template = {"row_ref": "row-a", "operation_ref": "op-a", "start": "2026-09-09T08:00:00", "end": "2026-09-09T08:00:00", "source": "internal",
                "machine": {"ref": "machine-a"}, "operator": {"ref": "operator-a"}, "supplier": None, "locked": False, "data_gaps": []}
    before = dict(template, interval_comparable=False, data_gaps=[{"field": "point_evidence", "code": "source_missing"}])
    after = dict(template, start="2026-09-09T09:00:00", end="2026-09-09T10:00:00")
    # Production intervals come from task_interval: the unproven point has none.
    after_times = {"row-a": (datetime.fromisoformat(after["start"]), datetime.fromisoformat(after["end"]))}
    difference = operation_delta(arrangement_view([before]), arrangement_view([after]),
                                 task_intervals=after_times, reference_task_intervals={"row-a": None})
    assert difference["start_delta_hours"] is difference["end_delta_hours"] is None
    assert difference["change_kinds"] == ["unknown"]
    unchanged_scope = {"selected_available": True, "deferred_refs": set(), "reference_deferred_refs": set()}
    values = operation_changes(["op-a"], True, reference_groups=by_operation([before]), selected_groups=by_operation([after]),
                               task_intervals=after_times, reference_task_intervals={"row-a": None}, **unchanged_scope)
    assert values["changed_operation_count"]["value"] is None
    assert values["changed_operation_count"]["known_subtotal"] == 0
    assert values["machine_change_count"]["value"] == 0
    point_time = datetime.fromisoformat(template["start"])
    point_times = {"row-a": (point_time, point_time), "row-b": (point_time, point_time)}
    point = operation_changes(["op-a"], True, reference_groups=by_operation([template]), selected_groups=by_operation([template]),
                              task_intervals=point_times, reference_task_intervals=point_times, **unchanged_scope)
    assert point["changed_operation_count"]["value"] == point["machine_change_count"]["value"] == 0
    assert point["changed_operation_count"]["unknown_count"] == 0
    segments = [template, dict(template, row_ref="row-b")]
    segment_inputs = {"reference_groups": by_operation(segments), "selected_groups": by_operation([after]),
                      "task_intervals": after_times, "reference_task_intervals": point_times, **unchanged_scope}
    comparisons = dict(iter_operation_comparisons(["op-a"], True, display=True, **segment_inputs))
    multiple = operation_change_metrics(comparisons.values(), ["op-a"], True)
    assert multiple == operation_changes(["op-a"], True, **segment_inputs)
    assert all(value["value"] is None and value["known_subtotal"] == 0 and value["unknown_count"] == 1
               for value in multiple.values())
    window = {"range_start": "2026-09-09T07:00:00", "range_end": template["start"]}
    engine = object.__new__(DecisionResources)
    engine.source = SimpleNamespace(scope=window, run={"run_ref": "a" * 48}, selected_ref="b" * 48, reference_ref=None,
                                    baseline={"state": "available", "plan_ref": "c" * 48}, comparison_mode="admission_official", resource_view="selected_batches")
    engine.start, engine.end = window["range_start"], window["range_end"]
    target = engine.drill("reference", {"ref": "d" * 48, "kind": "machine"}, tasks=[before], start=engine.start, end=engine.end)
    assert target["range_end"] == "2026-09-09T08:00:00.000001"
    assert target["reference_view"] is True and target["plan_ref"] == "c" * 48


def test_formal_workspace_preserves_archived_arrangement_with_unknown_time():
    facts = GenerationFacts.__new__(GenerationFacts)
    facts.__dict__.update(
        operations={"op-a": 1}, entity_refs={("batch", "B1"): "batch-a"},
        tables={"BatchOperations": {1: {"id": 1, "batch_id": "B1"}},
                "Batches": {"B1": {"batch_id": "B1", "part_no": "P1", "part_name": "零件A", "due_date": "2026-09-09"}}},
    )
    source = SimpleNamespace(resource_view="selected_batches",
        scope={"batch_refs": ["batch-a"], "operation_refs": ["op-a"], "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-10T00:00:00"},
        before_tasks=[{"row_ref": "row-a", "operation_ref": "op-a", "batch_ref": "batch-a", "start": None, "end": None,
                       "sequence": 1, "data_gaps": [{"field": "start", "code": "source_missing"}], "interval_comparable": False}],
        baseline={"label": "排产时的正式计划 v1", "state": "available", "plan_ref": "c" * 48},
        reference_deferred_ids=set(), selected_ref="b" * 48, reference_ref=None, rows=[], facts=facts,
        run={"run_ref": "a" * 48, "accepted_at": "2026-09-09T00:00:00", "finished_at": "2026-09-09T00:01:00"}, capture={"input": {}},
    )
    effort = project_operation_effort(None, None, allocation_state="unknown", source="internal",
                                     execution={"execution_state": "complete", "target_quantity": 3, "target_basis": "batch", "remaining_quantity": 0})
    source.preparation = SimpleNamespace(compact=lambda _key, _ref: effort)
    saved_delivery = project_decision_delivery(facts, source.before_tasks, source.scope["batch_refs"],
                                              deferred_ids=source.reference_deferred_ids)
    source.completion = SimpleNamespace(delivery={"reference": saved_delivery}.__getitem__)
    data = _reference_workspace(source, None)
    assert [{key: value for key, value in row.items() if key != "operation_effort"} for row in data["tasks"]] == source.before_tasks
    saved = data["tasks"][0]["operation_effort"]
    assert saved["setup_state"] == "already_completed" and saved["requirement_role"] == "completed"
    assert saved["setup_standard_hours"] is saved["required_standard_hours"] is None
    assert data["task_span"] is None and data["candidate_span"] is None
    assert data["gantt_graph"]["state"] == "unavailable"
    assert data["delivery_risks"]["items"][0]["completion_state"] == "unknown"


def test_budget_skipped_siblings_keep_complete_schedulable_result(candidate_case, monkeypatch):
    result = persisted_partial_run(candidate_case, monkeypatch)
    data, _ = read_run_decision(candidate_case.conn, result["run_ref"])
    recommended = next(row for row in data["candidates"] if "recommended" in row["selection_role"])
    assert recommended["coverage"]["search"]["state"] == "partial"
    assert recommended["coverage"]["schedulable"]["state"] == "complete"
    skipped = [row for row in data["candidates"] if row["persisted_status"] == "skipped"]
    assert len(skipped) == 3
    assert all(row["source"]["reason"]["code"] == "candidate_time_budget_reached" for row in skipped)
    assert all(row["metrics"]["unplanned_operation_count"]["value"] is None for row in skipped)
    recommendation = data["recommendation"]
    assert recommendation["recommendation_type"] == "complete"
    assert recommendation["axes"]["completion"]["search"]["state"] == "partial"
    assert recommendation["axes"]["completion"]["schedulable"]["state"] == "complete"
    assert recommendation["completion_scope"]["remaining_work"]["operation_count"] == 0
    groups = data["completion_groups"]
    assert len(groups) == 2
    unavailable = next(group for group in groups if not group["source_available"])
    assert set(unavailable["candidate_refs"]) == {row["candidate_ref"] for row in skipped}
    assert unavailable["complete_batch_count"] == 0
    complete = next(group for group in groups if group["source_available"])
    assert complete["candidate_refs"] == [recommended["candidate_ref"]]
    selected_skip, _ = read_run_decision(candidate_case.conn, result["run_ref"], selected_candidate_ref=skipped[0]["candidate_ref"])
    assert selected_skip["scope"]["selected_candidate_ref"] == skipped[0]["candidate_ref"]
    assert all(item["state"] == "unavailable" and item["value"] is None for item in selected_skip["difference_summary"]["items"])


def test_failed_algorithm_baseline_requires_explicit_viewing_reference(candidate_case, monkeypatch):
    from tests.workbench.legacy_run_archive_support import install_failed_baseline_archive

    install_failed_baseline_archive(monkeypatch)
    candidate_case.config(graph_selection_policy="balanced")
    run_ref, _ = compute(candidate_case)
    data, _ = read_run_decision(candidate_case.conn, run_ref)
    assert len(data["candidates"]) == 4
    assert data["selection_basis"]["selection_policy"] == "balanced"
    assert data["selection_basis"]["overdue_tolerance_count"] == 1
    assert data["selection_basis"]["tardiness_tolerance_ratio"] == 0.10
    assert data["scope"]["reference_state"] == "selection_required"
    assert data["scope"]["reference"]["candidate_ref"] is None
    failed = next(row for row in data["candidates"] if row["kind"] == "baseline")
    assert failed["persisted_status"] == "failed" and "测试数据" in failed["source"]["reason"]["message"]
    selected = data["selection_basis"]["selected_candidate_ref"]
    viewed, _ = read_run_decision(candidate_case.conn, run_ref, reference_candidate_ref=selected)
    assert viewed["scope"]["reference_state"] == "available"
    assert viewed["selection_basis"] == data["selection_basis"]
    assert viewed["recommendation"]["candidate_ref"] == data["recommendation"]["candidate_ref"] == selected
    assert viewed["recommendation"]["recommendation_type"] == "complete"
    assert data["recommendation"]["current_comparison"]["reference"]["candidate_ref"] is None
    assert viewed["recommendation"]["current_comparison"]["reference"]["candidate_ref"] == selected
    groups = data["completion_groups"]
    assert any(not group["source_available"] and failed["candidate_ref"] in group["candidate_refs"] for group in groups)
    evidence = viewed["selection_basis"]["decision_evidence"]
    assert evidence["selected"]["candidate_ref"] == selected
    assert evidence["anchors"]["raw_score_best"]["candidate_ref"] != failed["candidate_ref"]
    failed_view, _ = read_run_decision(candidate_case.conn, run_ref, selected_candidate_ref=failed["candidate_ref"], reference_candidate_ref=selected)
    card = next(row for row in failed_view["candidates"] if row["candidate_ref"] == failed["candidate_ref"])
    assert len(failed_view["candidates"]) == len(data["candidates"])
    assert card["capabilities"]["view"] is True and card["capabilities"]["compare"] is False
    assert card["capabilities"]["gantt"] is card["capabilities"]["adoption_preview"] is False
    assert all(delta["state"] == "unavailable" and delta["value"] is None for delta in card["deltas"].values())
    assert all(item["state"] == "unavailable" and item["selected_value"] is None for item in failed_view["difference_summary"]["items"])
    batches, _ = read_decision_details(candidate_case.conn, run_ref, "batches", selected_candidate_ref=failed["candidate_ref"],
        reference_candidate_ref=selected, selected_batch_ref=candidate_case.ref("batch", "B1"))
    assert batches["candidate"]["status"] == "failed" and batches["candidate"]["result_available"] is False
    assert batches["summary"]["operation_changes"] == {key: card["metrics"][key] for key in
        ("changed_operation_count", "machine_change_count")}
    batch = batches["selected_batch"]
    assert batch["after"]["completion_state"] == "unknown" and batch["after"]["scheduled_operation_count"] is None
    assert "candidate_result_unavailable" in batch["after"]["issues"]
    assert batch["unplanned_operation_refs"] is batch["deferred_operation_refs"] is None
    assert batch["drill"]["selected"] is None
    operations, _ = read_decision_details(candidate_case.conn, run_ref, "operations", selected_candidate_ref=failed["candidate_ref"], reference_candidate_ref=selected)
    assert all(row["after"] is None and row["after_state"]["status"] == "unavailable"
               and row["status_changed"] is None and row["changed_fields"] == [] for row in operations["items"])


def test_partial_worker_results_do_not_claim_shorter_span_for_different_work(candidate_case, monkeypatch):
    from tests.workbench.legacy_run_archive_support import install_different_work_archive

    install_different_work_archive(monkeypatch)
    case = candidate_case
    # Eleven hours of real work compete for the single captured eight-hour shift.
    case.conn.execute("UPDATE Batches SET quantity=1,due_date='2026-09-09' WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET unit_hours=5 WHERE id=?", (case.op_id,))
    case.batch("B2", quantity=1, due_date="2026-09-10")
    case.operation("B2", unit_hours=6)
    case.config(dispatch_mode="batch_order", sort_strategy="due_date_first")
    run_ref, _ = compute(case, case.settings("B1", "B2", end_date="2026-09-09"))
    initial, _ = read_run_decision(case.conn, run_ref)
    assert len(initial["candidates"]) == 4
    baseline = next(row for row in initial["candidates"] if row["kind"] == "baseline")
    graph = next(row for row in initial["candidates"] if row["kind"] == "critical_chain")
    compared, state = read_run_decision(case.conn, run_ref, reference_candidate_ref=graph["candidate_ref"])
    selected = next(row for row in compared["candidates"] if row["candidate_ref"] == baseline["candidate_ref"])
    assert selected["coverage"]["schedulable"]["missing_count"] == graph["coverage"]["schedulable"]["missing_count"] == 1
    assert selected["metrics"]["makespan_hours"]["value"] == 5 < graph["metrics"]["makespan_hours"]["value"] == 6
    for key in ("makespan_hours", "changeover_count"):
        assert selected["deltas"][key]["state"] == "different_coverage"
        assert selected["deltas"][key]["value"] is None and selected["deltas"][key]["direction"] == "neutral"
    recommendation = initial["recommendation"]
    current = recommendation["current_comparison"]
    assert recommendation["candidate_ref"] == graph["candidate_ref"]
    assert current["reference"]["candidate_ref"] == baseline["candidate_ref"]
    assert recommendation["recommendation_type"] == "partial"
    assert not {"makespan_hours", "changeover_count"} & {item["metric_key"] for item in current["benefits"]}
    completion = recommendation["completion_scope"]
    assert completion["complete_batch_count"] == completion["ordinary_incomplete_batch_count"] == 1
    assert completion["unplanned_operation_count"] == completion["remaining_work"]["operation_count"] == 1
    assert completion["deferred_operation_count"] == 0
    assert len(compared["completion_groups"]) == 2
    common = current["common_completed_delivery"]
    assert common["scope"] == "common_completed_batches" and common["batch_count"] == 0
    assert common["delay_delta_hours"] is common["overdue_delta_count"] is None
    assert common["state"] == "unavailable"
    assert initial["candidates"][0]["deltas"]["makespan_hours"]["state"] == "comparable"
    assert state["metric_version"] == METRIC_VERSION


def test_material_ready_after_formal_adoption_compares_delivery_without_equating_work(candidate_case):
    case = candidate_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    _, original = compute(case, case.settings(material_strategy="stage"))
    service(case.conn).adopt(original[0], preview(case, original[0]), "decision-stage-adoption-01", INTENT)
    case.conn.execute("UPDATE BatchMaterials SET available_qty=required_qty")
    case.conn.commit()
    accepted = case.accept(settings=case.settings(material_strategy="stage"), key="decision-ready-run-000001")
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    data, _ = read_run_decision(case.conn, result["run_ref"], comparison_mode="admission_official")
    assert data["baseline"]["coverage"]["schedulable"]["state"] == "complete"
    assert data["baseline"]["coverage"]["delivery"]["deferred_batch_count"] == 1
    for row in data["candidates"]:
        assert row["coverage"]["schedulable"]["state"] == "complete"
        assert row["coverage"]["delivery"]["complete_batch_count"] == 1
        assert row["coverage"]["schedulable"]["scheduled_count"] == 2
        for key in ("makespan_hours", "type_changeover_count"):
            assert row["deltas"][key]["state"] == "different_coverage"
            assert row["deltas"][key]["value"] is None
        assert row["deltas"]["changeover_count"]["state"] == "unavailable"
