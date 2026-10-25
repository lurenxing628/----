"""Comparison gate between two saved history metrics of the same definition."""

COVERAGE_FIELDS = ("covered_batch_refs", "covered_operation_refs", "covered_resource_refs")


def metric_reason(code, message):
    return {"code": code, "message": message}


def gate_history_metric(definition, before_metric, after_metric, *, production_state, objective_state, window_comparable=True):
    """Permit an improvement only for sufficiently known, identical evidence scopes."""
    previous, selected = before_metric.get("value"), after_metric.get("value")
    result = {"value": None, "state": "unavailable", "direction": "neutral", "reference_value": previous,
              "selected_value": selected, "reason": None}
    if production_state != "equal":
        state = "different_conditions" if production_state == "different" else "unavailable"
        reason = metric_reason("history_production_conditions_" + production_state, "生产条件有变化。" if state == "different_conditions" else "生产条件缺少充分归档依据。")
    elif objective_state != "equal":
        state = "different_objective" if objective_state == "different" else "unavailable"
        reason = metric_reason("history_objective_" + objective_state, "两侧优化目标不同。" if state == "different_objective" else "优化目标缺少保存依据。")
    elif previous is None or selected is None or any(item.get("state") not in ("complete", "not_applicable")
            or item.get("unknown_count", 0) or item.get("known_count") != item.get("total_count")
            or item.get("unknown_workload_count") not in (None, 0) for item in (before_metric, after_metric)):
        state, reason = "unavailable", metric_reason("history_metric_incomplete", "两侧指标仍有未确认的数值或覆盖。")
    elif any(before_metric.get(key) is None or before_metric.get(key) != after_metric.get(key) for key in ("unit", "metric_version")):
        state, reason = "different_version", metric_reason("history_metric_version_changed", "两侧指标的单位或保存口径版本不同。")
    elif before_metric.get("scope") != after_metric.get("scope") or not window_comparable:
        state, reason = "different_coverage", metric_reason("history_metric_scope_changed", "两侧统计范围或资源窗口不同。")
    elif definition["source"] == "archived_resource_calendar" and definition["key"].endswith(("utilization_ratio", "balance_cv")) and any(
            item.get(key) is None for item in (before_metric, after_metric) for key in ("numerator_hours", "denominator_hours")):
        state, reason = "unavailable", metric_reason("history_resource_ratio_evidence_missing", "资源比例指标缺少真实占用分子或容量分母。")
    elif definition["source"] == "archived_resource_calendar" and definition["key"].endswith(("utilization_ratio", "balance_cv")) and (
            before_metric["denominator_hours"] != after_metric["denominator_hours"]):
        state, reason = "different_coverage", metric_reason("history_resource_capacity_changed", "两侧资源比例指标的容量分母不同。")
    else:
        origin = definition["source"]
        required = ("covered_batch_refs",) if origin == "archived_delivery" or definition["scope"] == "saved_algorithm_batches" else (
            ("covered_resource_refs",) if origin == "archived_resource_calendar" or definition["scope"] == "saved_schedule_resources" else
            ("covered_operation_refs",) if definition["scope"] in ("full_admission", "full_candidate", "fixed_changeover_window") else ())
        members_known = all(before_metric.get(key) is not None and after_metric.get(key) is not None for key in required)
        same = members_known and before_metric.get("total_count") == after_metric.get("total_count") and all(
            (set(before_metric[key]) == set(after_metric[key]) if before_metric.get(key) is not None and after_metric.get(key) is not None
             else before_metric.get(key) is None and after_metric.get(key) is None) for key in COVERAGE_FIELDS)
        if not members_known:
            state, reason = "unavailable", metric_reason("history_metric_members_missing", "保存指标缺少其实际覆盖成员。")
        elif not same:
            state, reason = "different_coverage", metric_reason("history_metric_coverage_changed", "两侧指标覆盖的实际成员不同。")
        else:
            state, reason = "comparable", None
            difference = selected - previous
            improvement = definition["improvement"]
            result["value"] = difference
            result["direction"] = "equal" if difference == 0 else "neutral" if improvement == "neutral" else (
                "better" if (difference < 0) == (improvement == "lower") else "worse")
    result.update(state=state, reason=reason)
    return result
