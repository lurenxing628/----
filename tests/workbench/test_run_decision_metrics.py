"""Decision differences preserve factual coverage and saved selection identities."""

import itertools
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.decision_delivery import project_decision_delivery
from core.services.workbench.facts.decision_metrics import delivery_coverage, metric_definitions
from core.services.workbench.facts.decision_read_models import build_side_operation_rows, by_operation
from core.services.workbench.run.decision import operation_change_metrics_from_sql, read_run_decision
from core.services.workbench.run.decision_resource_engine import DecisionResources
from core.services.workbench.run.decision_source import DecisionSource
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.run_candidate_support import compute
from tests.workbench.test_material_stage_release import add_requirement

_SQL_RUN_KEYS = itertools.count(1)


def sql_operation_changes(case, before, after, operation_refs, *, before_intervals, after_intervals):
    """Save both sides as the read-model builder does, then compare them with the production operation-change SQL.

    Returns ``(metrics, kinds)``: ``metrics(reference_available=...)`` is the decision metric pair from
    ``operation_change_metrics_from_sql``; ``kinds`` maps each operation to its saved comparison kinds.
    """
    run_ref = case.accept(key=f"sql-operation-changes-{next(_SQL_RUN_KEYS):04d}")["run_ref"]
    preparation = [{"operation_ref": ref, "allocation_state": "new_schedule", "setup_standard_hours": None,
                    "required_standard_hours": None} for ref in operation_refs]
    side_operations = [row for side_key, tasks, intervals in (("official", before, before_intervals),
                                                             ("selected", after, after_intervals))
                       for row in build_side_operation_rows(side_key, operation_refs, by_operation(tasks), intervals, preparation, set(), set())]
    catalog = [{"operation_ref": ref, "batch_ref": None, "batch_label": None, "sequence": index, "sequence_unknown": 0,
                "op_id": index, "saved_machine_ref": None, "label": {}} for index, ref in enumerate(operation_refs, 1)]
    repo = WorkbenchRunRepository(case.conn)
    repo.insert_decision_read_models(
        run_ref, {**{name: {} for name in ("header", "context", "memberships", "calendar", "official")}, "process": None}, [],
        operation_catalog=catalog, side_operations=side_operations)
    case.conn.commit()

    def metrics(*, reference_available=True):
        source = SimpleNamespace(run={"run_ref": run_ref}, repo=repo, admitted_operation_refs=list(operation_refs),
                                 baseline={"state": "available" if reference_available else "absent"},
                                 side_key=lambda _key: "official")
        return operation_change_metrics_from_sql(source, "selected")

    rows, _ = repo.page_side_operations(run_ref, "official", "selected", ref_avail=True, filters={
        "batch_ref": None, "change_kind": "all", "resource_ref": None, "sort": "sequence", "order": "asc"},
        offset=0, limit=len(operation_refs), all_rows=True)
    return metrics, {row["operation_ref"]: row["change_kinds_csv"].split(",") for row in rows}


def test_archive_builder_reuses_its_admission_scope_for_candidate_metrics(candidate_case, monkeypatch):
    from core.services.workbench.facts import decision_metrics, decision_read_model

    scopes = []
    original_summary = decision_read_model.project_candidate_summary

    def prepared_summary(*args, **kwargs):
        scopes.append(kwargs["operation_scope"])
        return original_summary(*args, **kwargs)

    def repeated_admission(*args, **kwargs):
        raise AssertionError("候选摘要重复派生本次已准备的准入集合")

    for name in ("admission_operation_refs", "admission_deferred_refs"):
        monkeypatch.setattr(decision_metrics, name, repeated_admission)
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
                "Batches": {"B1": {"batch_id": "B1", "part_no": "P1", "part_name": "零件A", "quantity": 1, "priority": "normal",
                                   "due_date": "9999-12-31"},
                            "B2": {"batch_id": "B2", "part_no": "P2", "part_name": "零件B", "quantity": 1, "priority": "normal",
                                   "due_date": "2026-09-09"}}},
    )
    tasks = [{"row_ref": "row-a", "operation_ref": "op-a", "batch_ref": "batch-a", "start": "2026-09-10T08:00:00", "end": "2026-09-10T10:00:00"},
             {"row_ref": "row-b", "operation_ref": "op-b", "batch_ref": "batch-b", "start": "2026-09-10T08:00:00", "end": "2026-09-10T10:00:00"}]
    intervals = {
        "row-a": (datetime(2026, 9, 10, 8), datetime(2026, 9, 10, 10)),
        "row-b": (datetime(2026, 9, 10, 8), datetime(2026, 9, 10, 10)),
    }

    def evaluate():
        return delivery_coverage(project_decision_delivery(facts, tasks, ["batch-a", "batch-b"], deferred_ids=frozenset(), intervals=intervals))

    coverage, values = evaluate()
    assert coverage["state"] == "complete" and coverage["excluded_due_count"] == 1
    assert values["overdue_count"]["value"] == 1 and values["total_tardiness_hours"]["value"] == 10
    facts.tables["Batches"]["B2"]["due_date"] = "9999-12-31"
    _, values = evaluate()
    assert values["total_tardiness_hours"]["state"] == "not_applicable"
    assert values["total_tardiness_hours"]["value"] is None
    items = project_decision_delivery(facts, tasks, ["batch-a", "batch-b"], deferred_ids=frozenset(), intervals=intervals)
    common = common_completed_delivery(items, items)["common_delivery"]
    assert common["before"]["excluded_due_count"] == common["after"]["excluded_due_count"] == 2
    assert common["delay_delta_hours"] is common["overdue_delta_count"] is None
    facts.tables["Batches"]["B2"]["due_date"] = None
    coverage, values = evaluate()
    assert coverage["invalid_due_count"] == coverage["unknown_due_count"] == 1
    assert values["total_tardiness_hours"]["value"] is None
    items = project_decision_delivery(facts, tasks, ["batch-a", "batch-b"], deferred_ids=frozenset(), intervals=intervals)
    common = common_completed_delivery(items, items)["common_delivery"]
    assert common["before"]["invalid_due_count"] == common["after"]["unknown_due_count"] == 1
    assert common["delay_delta_hours"] is common["overdue_delta_count"] is None


def test_resource_reference_gap_preserves_known_operation_change_subtotal(candidate_case):
    from core.services.workbench.facts.decision_read_models import Memberships

    template = {"start": "2026-09-09T08:00:00", "end": "2026-09-09T10:00:00", "source": "internal",
                "machine": {"ref": "machine-a"}, "operator": {"ref": "operator-a"}, "supplier": None,
                "locked": False, "data_gaps": []}
    before = [dict(template, row_ref="before-a", operation_ref="op-a"), dict(template, row_ref="before-b", operation_ref="op-b")]
    after = [dict(template, row_ref="after-a", operation_ref="op-a", start="2026-09-09T09:00:00"),
             dict(template, row_ref="after-b", operation_ref="op-b", machine={"ref": None})]
    original = deepcopy((before, after))
    before_times, after_times = ({row["row_ref"]: (datetime.fromisoformat(row["start"]), datetime.fromisoformat(row["end"]))
                                 for row in rows} for rows in (before, after))
    metrics, kinds = sql_operation_changes(candidate_case, before, after, ["op-a", "op-b"],
                                           before_intervals=before_times, after_intervals=after_times)
    assert (before, after) == original
    assert kinds == {"op-a": ["moved"], "op-b": ["unknown"]}
    values = metrics()
    assert values["changed_operation_count"]["value"] is None
    assert values["changed_operation_count"]["known_subtotal"] == 1
    assert values["machine_change_count"]["value"] is None
    assert values["machine_change_count"]["known_subtotal"] == 0
    assert all(value["value"] is value["known_subtotal"] is None and value["unknown_count"] == 2
               and value["reason"]["code"] == "reference_required" for value in metrics(reference_available=False).values())
    _, kinds = sql_operation_changes(candidate_case, before, after, ["missing"], before_intervals={}, after_intervals={})
    assert kinds == {"missing": ["unknown"]}
    source = object.__new__(DecisionSource)
    source.comparison_mode, source.reference_ref = "candidates", "candidate-a"
    source._analysis, source._operation_arrangements = {"candidate-a": before}, {}
    assert source.computation_key("reference") == "candidate-a"
    assert source.computation_key("candidate-b") == "candidate-b"
    assert source.operation_arrangements("reference") is source.operation_arrangements("reference")
    source._task_intervals = {"candidate-a": before_times}
    assert source.task_intervals("reference") is source.task_intervals("candidate-a")
    source.context = {"official_members": {"identity": {"state": "available"}, "operation_refs": ["op-a", "op-b"]}}
    source.memberships = Memberships({"operation_refs": [], "batch_refs": [], "operation_sets": [], "batch_sets": []})
    assert source.official_members == {"identity": {"state": "available"}, "operation_refs": ["op-a", "op-b"]}
    source.comparison_mode = "admission_official"
    assert source.computation_key("reference") == "reference"
    source.comparison_mode, source.reference_ref = "candidates", None
    assert source.computation_key("reference") == "reference"


def test_official_point_compares_and_drills_by_its_saved_instant(candidate_case):
    point = {"row_ref": "row-a", "operation_ref": "op-a", "start": "2026-09-09T08:00:00", "end": "2026-09-09T08:00:00",
             "source": "internal", "machine": {"ref": "machine-a"}, "operator": {"ref": "operator-a"}, "supplier": None,
             "locked": False, "data_gaps": [], "event_kind": "point", "occupies_resources": False}
    point_time = datetime.fromisoformat(point["start"])
    point_times = {"row-a": (point_time, point_time)}
    metrics, kinds = sql_operation_changes(candidate_case, [point], [point], ["op-a"],
                                           before_intervals=point_times, after_intervals=point_times)
    values = metrics()
    assert kinds == {"op-a": ["unchanged"]}
    assert values["changed_operation_count"]["value"] == values["machine_change_count"]["value"] == 0
    assert values["changed_operation_count"]["unknown_count"] == 0
    window = {"range_start": "2026-09-09T07:00:00", "range_end": point["start"]}
    engine = object.__new__(DecisionResources)
    engine.source = SimpleNamespace(scope=window, run={"run_ref": "a" * 48}, selected_ref="b" * 48, reference_ref=None,
                                    baseline={"state": "available", "plan_ref": "c" * 48}, comparison_mode="admission_official",
                                    resource_view="selected_batches", task_intervals=lambda _key: point_times)
    engine.start, engine.end = window["range_start"], window["range_end"]
    target = engine.drill("reference", {"ref": "d" * 48, "kind": "machine"}, tasks=[point], start=engine.start, end=engine.end)
    assert target is not None
    assert target["range_end"] == "2026-09-09T08:00:00.000001"
    assert target["reference_view"] is True and target["plan_ref"] == "c" * 48


def test_material_ready_after_formal_adoption_compares_delivery_without_equating_work(candidate_case):
    case = candidate_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    _, original = compute(case, case.settings(material_strategy="stage"))
    service(case.conn).adopt(original[0], preview(case, original[0]), "decision-stage-adoption-01", INTENT)
    case.conn.execute("UPDATE BatchMaterials SET available_qty=required_qty")
    case.conn.commit()
    accepted = case.accept(settings=case.settings(material_strategy="stage"), key="decision-ready-run-000001")
    result = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted["run_ref"])
    data, _ = read_run_decision(case.conn, result["run_ref"], bind_snapshot=lambda scope, state: state, comparison_mode="admission_official")
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
    original_label = metric_definitions()[0]["label"]
    mutated = metric_definitions()
    mutated[0]["label"] = "mutated-direct-label"
    assert metric_definitions()[0]["label"] == original_label
    data["metric_definitions"][0]["label"] = "mutated-response-label"
    assert metric_definitions()[0]["label"] == original_label
