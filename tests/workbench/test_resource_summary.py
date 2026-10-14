"""Resource totals retain fixed cohorts, evidence coverage and weighted balance."""

from math import sqrt

import pytest

from core.services.workbench.facts.resource_summary import resource_summary


def window(capacity, occupied, *, kind="machine", ref="M1", load=None):
    load = occupied if load is None else load
    ratio = occupied / capacity if occupied is not None and capacity is not None and capacity > 0 else None
    values = {"available_hours": capacity, "occupied_hours": occupied, "summed_load_hours": load,
              "outside_calendar_hours": 0, "overlap_hours": load - occupied if load is not None and occupied is not None else None,
              "span_occupied_hours": occupied, "span_summed_hours": load,
              "span_overlap_hours": load - occupied if load is not None and occupied is not None else None,
              "overlap_span_hours": 0}
    task_count = int(bool(occupied))
    return {**values, **{"known_" + key: value for key, value in values.items()},
            "resource_ref": ref, "resource_kind": kind, "label": ref,
            "state": "complete", "work_available": True, "work_state": "complete", "unknown_workload_count": 0,
            "peak_utilization": ratio, "known_peak_utilization": ratio, "high_pressure": ratio is not None and ratio >= 0.9,
            "zero_capacity_task": False, "conflict": load is not None and occupied is not None and load > occupied,
            "unknown_days": 0, "task_count": task_count, "operation_count": task_count,
            "known_task_count": task_count, "known_operation_count": task_count, "issues": []}


def test_capacity_weighted_balance_includes_positive_idle_resources_and_filters_kind():
    rows = [window(8, 8), window(24, 0, ref="M2"), window(2, 1, kind="operator", ref="O1")]
    result = resource_summary(rows, kind="machine")
    assert result["state"] == "complete" and result["resource_count"] == 2
    assert result["used_resource_count"] == result["known_used_resource_count"] == 1
    assert result["available_hours"] == 32 and result["occupied_hours"] == 8
    assert result["numerator_hours"] == 8 and result["denominator_hours"] == 32
    assert result["utilization_ratio"] == result["demand_ratio"] == 0.25
    assert result["balance_cv"] == pytest.approx(sqrt(3))
    assert result["known_balance_cv"] == result["balance_cv"]
    assert result["balance_state"] == "complete" and result["balance_reason"] is None


def test_all_idle_is_complete_and_balance_is_not_applicable():
    result = resource_summary([window(8, 0), window(24, 0, ref="M2")])
    assert result["state"] == "complete" and result["utilization_ratio"] == 0
    assert result["used_resource_count"] == 0
    assert result["balance_cv"] is result["known_balance_cv"] is None
    assert result["balance_state"] == "not_applicable"
    assert result["balance_reason"]["code"] == "no_occupied_resources"


def test_known_zero_capacity_peak_is_excluded_without_masking_positive_peak():
    result = resource_summary([window(8, 4), window(0, 0, ref="M2")])
    assert result["peak_utilization"] == result["known_peak_utilization"] == 0.5
    assert result["balance_cv"] == 0 and result["balance_state"] == "complete"


def test_partial_workload_lower_bound_does_not_enter_known_ratio_or_balance():
    partial = window(8, None)
    partial.update(state="partial", work_state="partial", unknown_workload_count=1,
                   task_count=None, operation_count=None, known_task_count=1, known_operation_count=1,
                   known_occupied_hours=2, known_summed_load_hours=2, known_span_occupied_hours=2,
                   high_pressure=None, conflict=None)
    result = resource_summary([partial, window(24, 12, ref="M2")])
    assert result["state"] == "partial" and result["resource_count"] == 2
    assert result["available_hours"] == 32 and result["known_occupied_hours"] == 14
    assert result["occupied_hours"] is result["utilization_ratio"] is result["task_count"] is None
    assert result["known_task_count"] == result["known_operation_count"] == 2
    assert type(result["known_task_count"]) is int
    assert result["used_resource_count"] is None and result["known_used_resource_count"] == 2
    assert result["known_utilization_ratio"] == result["known_demand_ratio"] == 0.5
    assert result["known_numerator_hours"] == 12 and result["known_denominator_hours"] == 24
    assert result["balance_cv"] is None and result["known_balance_cv"] == 0
    assert result["balance_state"] == "partial" and result["unknown_workload_resource_count"] == 1


def test_unknown_calendar_preserves_workload_spans_and_actual_known_capacity():
    missing = window(None, None)
    missing.update(state="partial", span_occupied_hours=4, known_span_occupied_hours=4,
                   span_summed_hours=4, known_span_summed_hours=4,
                   known_available_hours=4, known_occupied_hours=1, known_summed_load_hours=1,
                   task_count=1, operation_count=1, known_task_count=1, known_operation_count=1,
                   outside_calendar_hours=None, known_outside_calendar_hours=None, unknown_days=1, high_pressure=None,
                   zero_capacity_task=None)
    result = resource_summary([missing, window(8, 4, ref="M2")])
    assert result["available_hours"] is result["occupied_hours"] is result["outside_calendar_hours"] is None
    assert result["known_available_hours"] == 12 and result["known_occupied_hours"] == 5
    assert result["known_numerator_hours"] == 5 and result["known_denominator_hours"] == 12
    assert result["known_utilization_ratio"] == result["known_demand_ratio"] == pytest.approx(5 / 12)
    assert result["balance_cv"] is None and result["known_balance_cv"] == 0
    assert result["span_occupied_hours"] == result["span_summed_hours"] == 8
    assert result["task_count"] == result["used_resource_count"] == 2
    assert result["known_capacity_count"] == result["unknown_capacity_count"] == 1
    assert result["unknown_day_resource_count"] == 1 and result["zero_capacity_task_count"] is None
    assert result["known_zero_capacity_task_count"] == 0


def test_nullable_flags_keep_confirmed_risks_without_claiming_complete_counts():
    known = window(8, 8, load=16)
    uncertain = window(0, None, ref="M2")
    uncertain.update(state="partial", work_state="partial", unknown_workload_count=1,
                     high_pressure=None, zero_capacity_task=None, conflict=None,
                     operation_count=None, task_count=None, known_operation_count=0, known_task_count=0)
    result = resource_summary([known, uncertain])
    assert result["high_pressure_count"] is result["conflict_resource_count"] is result["zero_capacity_task_count"] is None
    assert result["known_high_pressure_count"] == result["known_conflict_resource_count"] == 1
    assert result["known_zero_capacity_task_count"] == 0
    assert result["unknown_day_resource_count"] == 0


def test_identity_gaps_keep_fixed_capacity_and_normalise_issues():
    issue = {"kind": "machine", "code": "identity_missing", "message": "设备编号缺失。", "field": "machine", "row_ref": "old-row"}
    result = resource_summary([window(8, 2)], kind="machine", identity_issues=[issue, issue,
        {"kind": "operator", "code": "other_gap", "message": "人员编号缺失。"}])
    assert result["resource_count"] == 1 and result["known_capacity_count"] == 1
    assert result["available_hours"] == result["known_available_hours"] == 8
    assert result["occupied_hours"] is result["task_count"] is result["used_resource_count"] is None
    assert result["known_occupied_hours"] == 2 and result["known_used_resource_count"] == 1
    assert result["state"] == "partial" and result["balance_cv"] is None
    assert result["issues"] == [{"code": "identity_missing", "message": "设备编号缺失。", "field": "machine"}]


def test_unavailable_source_has_no_invented_known_workload():
    missing = window(None, None)
    missing.update(state="unavailable", work_available=False, work_state="unavailable",
                   task_count=None, operation_count=None, known_task_count=None, known_operation_count=None,
                   span_occupied_hours=None, span_summed_hours=None, span_overlap_hours=None, overlap_span_hours=None,
                   high_pressure=None, conflict=None, unknown_days=1)
    result = resource_summary([missing])
    assert result["resource_count"] == 1 and result["state"] == "unavailable"
    assert result["known_available_hours"] is result["known_occupied_hours"] is result["known_span_occupied_hours"] is None
    assert result["task_count"] is result["known_task_count"] is None
    assert result["known_high_pressure_count"] == result["known_conflict_resource_count"] == 0
    assert result["balance_state"] == "unavailable" and result["known_balance_cv"] is None


def test_empty_filtered_cohort_has_zero_totals_and_no_ratio():
    result = resource_summary([window(8, 4, kind="operator")], kind="machine")
    assert result["resource_count"] == result["used_resource_count"] == 0
    assert result["state"] == "not_applicable"
    assert result["available_hours"] == result["occupied_hours"] == result["known_occupied_hours"] == 0
    assert result["task_count"] == result["operation_count"] == 0
    assert result["utilization_ratio"] is result["demand_ratio"] is result["balance_cv"] is None
    missing = resource_summary([], kind="machine", identity_issues=[{
        "kind": "machine", "code": "identity_missing", "message": "安排的设备编号缺失。"}])
    assert missing["resource_count"] == 0 and missing["state"] == "unavailable"
    assert missing["occupied_hours"] is missing["known_occupied_hours"] is None
    assert missing["used_resource_count"] is missing["high_pressure_count"] is missing["conflict_resource_count"] is None
    assert missing["task_count"] is missing["known_task_count"] is None
    assert missing["balance_state"] == "unavailable" and missing["issues"]
    absent = resource_summary([], work_available=False)
    assert absent["resource_count"] == 0 and absent["state"] == "unavailable"
    assert absent["available_hours"] == absent["known_available_hours"] == 0
    assert absent["occupied_hours"] is absent["known_occupied_hours"] is absent["known_used_resource_count"] is None
    assert absent["task_count"] is absent["known_task_count"] is absent["high_pressure_count"] is absent["known_high_pressure_count"] is None
    assert absent["balance_state"] == "unavailable" and absent["known_balance_cv"] is None
