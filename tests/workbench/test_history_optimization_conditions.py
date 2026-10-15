"""Saved shared-search metadata remains independent of production availability."""

from copy import deepcopy

from core.services.workbench.history.conditions import (
    compare_history_conditions,
    prepare_history_condition_source,
)


def test_saved_primary_order_and_native_budget_keep_their_original_sources():
    primary = "min_overdue"
    targets = [primary, "min_tardiness", "min_changeover"]
    order = ["failed_ops", "overdue_count", "weighted_tardiness_hours", "total_tardiness_hours", "makespan_hours", "changeover_count"]
    selection = {"generation_policy_version": "unified_search_v1", "selection_policy_version": "business_objectives_v1",
        "primary_objective": primary, "target_objectives": targets,
        "selected_candidate_ref": "b" * 48,
        "objective_field_order": {"min_changeover": ["failed_ops", "changeover_count"], primary: order}}
    run = {"kind": "run", "ref": "a" * 48, "entry_ref": "run:" + "a" * 48,
        "capture": None, "facts": None, "candidate": {"candidate_ref": "b" * 48}, "receipt": {"selection": selection}}
    saved = prepare_history_condition_source(run)["objective"]
    assert saved["state"] == "known" and saved["source"]["path"] == "receipt.selection"
    assert saved["value"] == {"name": primary, "field_order": order}

    native = {"kind": "legacy", "ref": "1", "entry_ref": "legacy:1", "parsed_summary": {"algo": {
        "generation_policy_version": "unified_search_v1", "time_budget_seconds": 10,
        "candidate_comparison": {"generation_policy_version": "unified_search_v1",
            "primary_objective": primary, "target_objectives": targets,
            "run_time_budget_seconds": 30, "selection": selection}}}}
    prepared = prepare_history_condition_source(native)
    assert prepared["source"].available is False
    assert prepared["objective"]["value"] == saved["value"]
    assert prepared["objective"]["source"]["path"] == "parsed_summary.algo.candidate_comparison.selection"
    rows = {row["field"]: row["side"] for row in prepared["configurations"].rows.values()
            if row["entity"]["key"] == "run_options"}
    assert set(rows) == {"generation_policy_version", "selection_policy_version", "primary_objective", "target_objectives", "time_budget_seconds"}
    assert all(row["state"] == "known" for row in rows.values())
    assert rows["time_budget_seconds"]["value"] == 30
    assert rows["time_budget_seconds"]["source"]["path"] == "parsed_summary.algo.candidate_comparison.run_time_budget_seconds"
    assert rows["target_objectives"]["value"] == targets

    shorter = deepcopy(native)
    shorter["parsed_summary"]["algo"]["candidate_comparison"]["run_time_budget_seconds"] = 10
    compared = compare_history_conditions(shorter, native, {"start": "2026-10-15T08:00:00", "end": "2026-10-15T16:00:00"})
    assert compared["conditions"]["state"] == "unknown"
    assert compared["configurations"]["state"] == "different"
    budget = next(row for row in compared["configurations"]["rows"] if row["field"] == "time_budget_seconds")
    assert budget["state"] == "different" and budget["before"]["value"] == 10 and budget["after"]["value"] == 30

    unrecorded = deepcopy(native)
    del unrecorded["parsed_summary"]["algo"]["candidate_comparison"]["selection"]["objective_field_order"]
    assert prepare_history_condition_source(unrecorded)["objective"]["state"] == "unknown"
