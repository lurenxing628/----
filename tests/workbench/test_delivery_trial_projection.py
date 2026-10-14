"""Trial delivery keeps saved route facts and uses the shared due contract."""

from copy import deepcopy

from core.infrastructure.transaction import TransactionManager
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.facts.trial_policy import load_draft, load_scenario
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.services.workbench.trial import projection
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as adoption_service
from tests.workbench.test_material_stage_release import add_requirement
from tests.workbench.trial_support import change, create, official, service
from tests.workbench.trial_support import trial_case as trial_case


def test_unspecified_trial_due_is_excluded_without_losing_complete_finish(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET due_date='9999-12-31',part_name='Saved part'")
    draft = create(case, official(case))
    updated = change(case, draft)["data"]
    row, = updated["comparison"]["batches"]
    summary = updated["comparison"]["delivery_summary"]
    assert row["due_state"] == "unspecified" and row["risk"] == "not_applicable"
    assert row["late_hours"] is None and row["due_exclusive"] is None
    assert row["completion_state"] == "complete"
    assert row["baseline_finish"] == "2026-09-09T11:00:00"
    assert row["finish"] == "2026-09-09T16:00:00"
    assert row["finish_delta_hours"] == 5 and row["improvement_hours"] == -5
    assert row["change_kinds"] == ["later"]
    assert summary["state"] == "not_applicable" and summary["excluded_due_count"] == 1
    assert summary["due_eligible_count"] == summary["due_evaluation_count"] == 0
    assert updated["comparison"]["late_count"] is None
    assert updated["comparison"]["total_delay_hours"] is None


def test_trial_route_coverage_keeps_creation_snapshot_after_current_route_grows(trial_case):
    case = trial_case
    draft = create(case)
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    case.operation(seq=2)
    current = projection.comparison(draft["tasks"], {"constraints_status": "valid"}, rows, head["admission"])
    row, = current["batches"]
    assert row["after"]["operation_count"] == row["before"]["operation_count"] == 1
    assert row["after"]["schedule_complete"] is True
    assert row["after"]["ordinary_unscheduled_operation_count"] == 0


def test_bad_trial_due_preserves_complete_chain_and_its_specific_reason(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET due_date='bad due'")
    draft = create(case)
    assert draft["validation"]["constraints_status"] == "blocked"
    issue, = draft["validation"]["issues"]
    assert issue["field"] == "due_date"
    row, = draft["comparison"]["batches"]
    assert row["due_state"] == "invalid" and row["due_issue"] == "due_date_invalid"
    assert row["risk"] == "unknown" and row["late_hours"] is None
    assert row["before"]["schedule_complete"] is row["after"]["schedule_complete"] is True
    assert row["completion_state"] == "complete" and row["finish"] is not None
    assert "trial_constraints_blocked" not in row["after"]["issues"]
    assert draft["comparison"]["delivery_summary"]["invalid_due_count"] == 1
    historical = deepcopy(draft["validation"])
    historical["issues"][0].pop("field")
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    legacy = projection.comparison(draft["tasks"], historical, rows, head["admission"])
    assert legacy["batches"][0]["after"]["schedule_complete"] is True


def test_trial_missing_origin_operation_never_claims_whole_batch_finish(trial_case):
    case = trial_case
    case.operation(seq=2)
    draft = create(case, official(case, ids=[case.op_id]))
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    comparison = projection.comparison(draft["tasks"], {"constraints_status": "valid"}, rows, head["admission"])
    row, = comparison["batches"]
    assert row["completion_state"] == "incomplete" and row["risk"] == "unknown"
    assert row["after"]["operation_count"] == 2
    assert row["after"]["ordinary_unscheduled_operation_count"] == 1
    assert row["finish"] is None and row["baseline_finish"] is None
    assert row["partial_finish"] == "2026-09-09T11:00:00"
    assert row["improvement_hours"] is None and row["delay_delta_hours"] is None
    assert comparison["delivery_summary"]["unknown_due_count"] == 1


def test_candidate_trial_retains_explicit_material_deferral_from_run_capture(trial_case):
    case = trial_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    accepted = case.accept(settings=case.settings(material_strategy="stage"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    ref = result["candidates"][0]["candidate_ref"]
    draft = create(case, {"base": {"candidate_ref": ref}})
    assert draft["validation"]["constraints_status"] != "blocked", draft["validation"]
    assert draft["comparison"]["batches"][0]["completion_state"] == "deferred"
    adopter = adoption_service(case.conn)
    preview = adopter.preview(ref)
    assert preview["validation"]["can_adopt"] is True, preview
    adopted = adopter.adopt(ref, preview["write_context"]["write_token"], "stage-source-delivery-adopt", INTENT)["data"]
    official_draft = create(case, {"base": {"plan_ref": adopted["official_plan"]["plan_ref"]}}, key="stage-source-official-trial")
    assert official_draft["comparison"]["batches"][0]["completion_state"] == "deferred"
    assert official_draft["comparison"]["batches"][0]["after"]["deferred_operation_count"] == 1
    official_head, official_rows = load_draft(service(case.conn).repo, official_draft["draft_ref"])
    historical = deepcopy(official_head["admission"])
    historical["source"].pop("deferred_operation_ids")
    historical["source"].pop("deferred_operation_issues")
    legacy = projection.comparison(official_draft["tasks"], official_draft["validation"], official_rows, historical)
    assert legacy["batches"][0]["completion_state"] == "deferred"
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    case.operation(seq=3)
    comparison = projection.comparison(draft["tasks"], {"constraints_status": "valid"}, rows, head["admission"])
    row, = comparison["batches"]
    assert row["completion_state"] == "deferred" and row["risk"] == "unknown"
    assert row["after"]["operation_count"] == 2
    assert row["after"]["deferred_operation_count"] == 1
    assert row["after"]["ordinary_unscheduled_operation_count"] == 0
    assert row["finish"] is None and row["partial_finish"] is not None
    assert comparison["delivery_summary"]["deferred_batch_count"] == 1


def test_trial_includes_selected_batch_with_only_material_deferred_operations(trial_case):
    case = trial_case
    case.batch("B2")
    second = case.operation(batch="B2")
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                                      (str(second),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B2"), {"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3,
            "available_quantity": 0, "operation_ref": operation_ref, "arrivals": []}]})
    accepted = case.accept(settings=case.settings("B1", "B2", material_strategy="stage"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    draft = create(case, {"base": {"candidate_ref": result["candidates"][0]["candidate_ref"]}})
    assert {task["batch_id"] for task in draft["tasks"]} == {"B1"}
    delivery = {row["batch_id"]: row for row in draft["comparison"]["batches"]}
    assert set(delivery) == {"B1", "B2"}
    assert delivery["B2"]["completion_state"] == "deferred"
    assert delivery["B2"]["after"]["scheduled_operation_count"] == 0
    assert delivery["B2"]["after"]["deferred_operation_count"] == 1
    assert delivery["B2"]["changed"] is False and delivery["B2"]["moved"] is False
    head, rows = load_draft(service(case.conn).repo, draft["draft_ref"])
    checked = {"constraints_status": "blocked", "issues": [{"code": "calendar_duration_conflict", "severity": "blocker",
                                                             "task_ref": draft["tasks"][0]["task_ref"]}]}
    scoped = projection.comparison(draft["tasks"], checked, rows, head["admission"])
    deliveries = {row["batch_id"]: row for row in scoped["batches"]}
    assert deliveries["B1"]["completion_state"] == "unknown"
    assert deliveries["B2"]["completion_state"] == "deferred"
    ref = result["candidates"][0]["candidate_ref"]
    adopter = adoption_service(case.conn)
    preview = adopter.preview(ref)
    adopted = adopter.adopt(ref, preview["write_context"]["write_token"], "stage-two-batch-delivery-adopt", INTENT)["data"]
    formal = create(case, {"base": {"plan_ref": adopted["official_plan"]["plan_ref"]}}, key="stage-two-batch-official-trial")
    assert {task["batch_id"] for task in formal["tasks"]} == {"B1"}
    assert {row["batch_id"]: row["completion_state"] for row in formal["comparison"]["batches"]} == {"B1": "complete", "B2": "deferred"}


def test_saved_legacy_trial_read_reprojects_due_without_rewriting_archive(trial_case, monkeypatch):
    case = trial_case
    case.conn.execute("UPDATE Batches SET due_date='9999-12-31'")
    draft = create(case)
    shared = projection.comparison

    def legacy_comparison(*args, **kwargs):
        result = deepcopy(shared(*args, **kwargs))
        result.pop("delivery_summary")
        result.pop("before_delivery_summary")
        for row in result["batches"]:
            row["risk"], row["late_hours"] = "due_unspecified", 0.0
        result["late_count"], result["total_delay_hours"] = 0, 0.0
        return result

    with monkeypatch.context() as patch:
        patch.setattr(projection, "comparison", legacy_comparison)
        saved = service(case.conn).save(draft["draft_ref"], {"name": "Historical trial"},
            draft["write_context"]["write_token"], "trial-save-legacy-due-001")["data"]
    svc = service(case.conn)
    changes = case.conn.total_changes
    current = svc.scenario(saved["scenario_ref"])
    assert current["comparison"]["batches"][0]["risk"] == "not_applicable"
    assert current["comparison"]["batches"][0]["late_hours"] is None
    assert current["comparison"]["delivery_summary"]["excluded_due_count"] == 1
    assert load_scenario(svc.repo, saved["scenario_ref"])["comparison"] == saved["comparison"]
    assert case.conn.total_changes == changes


def test_missing_saved_trial_source_is_explicit_unknown_from_saved_tasks(trial_case):
    case = trial_case
    draft = create(case)
    summary = projection.scenario_comparison(draft, None, [])
    row, = summary["batches"]
    assert row["completion_state"] == "unknown" and row["risk"] == "unknown"
    assert "trial_source_unavailable" in row["after"]["issues"]
    assert row["finish"] is None and row["improvement_hours"] is None
    assert summary["delivery_summary"]["unknown_due_count"] == 1
