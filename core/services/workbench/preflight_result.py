"""Counts and public result assembly; no inferred scheduling feasibility."""

from core.models.workbench_preflight import issue, preflight_window


def result_counts(batches, rows, no_route, unready):
    counts = {key: sum(row["status"] == state for row in rows) for key, state in (
        ("ready_tasks", "eligible"), ("auto_assign_required", "auto_assign_required"), ("skipped_tasks", "skipped"),
        ("blocked_tasks", "blocked"), ("protected_tasks", "protected"))}
    counts.update(selected_batches=len(batches), selected_tasks=len(rows), no_route_batches=len(no_route), unready_batches=len(unready))
    resource_codes = {"machine_missing", "operator_missing", "operator_skill_missing", "machine_authorization_missing"}
    counts["missing_resource_tasks"] = sum(any(item["code"] in resource_codes for item in row["issues"]) for row in rows)
    counts["eligible_tasks"] = counts["ready_tasks"] + counts["auto_assign_required"]
    counts["actual_fact_tasks"] = sum(row["has_execution_facts"] for row in rows)
    return counts


def result_blockers(rows, no_route, counts):
    blockers = []
    for row in rows:
        if row["status"] == "blocked":
            blockers.append(issue("operation_blocked", "工序有必填资料缺项。", operation_ref=row["operation_ref"], batch_ref=row["batch_ref"]))
        if row["status"] == "protected" and (row["execution"]["execution_state"] != "complete" or row["execution"]["data_quality"] == "invalid"):
            blockers.append(issue("execution_review_required", "已有执行事实需复核，不能解除保护。", operation_ref=row["operation_ref"], batch_ref=row["batch_ref"]))
    blockers.extend(issue("route_not_generated", "批次尚未生成工艺。", batch_ref=row["ref"], batch_id=row["batch_id"]) for row in no_route)
    if not counts["eligible_tasks"]:
        blockers.append(issue("no_eligible_tasks", "当前精确范围没有可进入排产的工序。"))
    return blockers


def result_warnings(settings, counts):
    warnings = [issue("calendar_not_evaluated", "尚未验证设备、人员、夜班、停机及产能日历，不代表排产可行性通过。")]
    if not settings["ready_check"]:
        warnings.append(issue("ready_check_disabled", "本次未校验齐套状态；原齐套事实不变。"))
    if counts["auto_assign_required"]:
        warnings.append(issue("auto_assign_not_evaluated", "待自动分配工序只识别了资料缺口，尚未验证有可用设备人员组合。"))
    return warnings


def summarize(settings, batches, rows, no_route, unready, ledger_reasons):
    counts = result_counts(batches, rows, no_route, unready)
    blockers = result_blockers(rows, no_route, counts)
    included_refs = {row["batch_ref"] for row in rows if row["status"] in ("eligible", "auto_assign_required")}
    included = [{"batch_ref": row["ref"], "batch_id": row["batch_id"]} for row in batches if row["ref"] in included_refs]
    excluded = [{"batch_ref": row["ref"], "batch_id": row["batch_id"], "reason": "没有可排工序；详见工序检查或未生成工艺项。"}
                for row in batches if row["ref"] not in included_refs]
    start, end = preflight_window(settings)
    return {"normalized_input": settings, "scope": {"source": "production", "batch_refs": settings["batch_refs"]},
            "included_batches": included, "excluded_batches": excluded, "tasks": rows, "counts": counts,
            "eligible_tasks": counts["eligible_tasks"], "auto_assign_required": counts["auto_assign_required"],
            "skipped_tasks": counts["skipped_tasks"], "blockers": blockers, "warnings": result_warnings(settings, counts),
            "no_route_batches": [{"batch_ref": row["ref"], "batch_id": row["batch_id"]} for row in no_route],
            "unready_batches": unready, "effective_config": {key: settings[key] for key in (
                "ready_check", "missing_resource_policy", "completed_policy")}, "config_scope": "single_run",
            "effective_start": start, "effective_end_exclusive": end, "effective_start_basis": "window_lower_bound_not_calendar_slot",
            "calendar_check": "not_evaluated", "execution_projection_source": "legacy_guard_only" if ledger_reasons else "execution_ledger",
            "run_blocked": True, "run_blocked_reasons": [issue("schedule_not_computed", "尚未生成排产结果。")]
            + ledger_reasons + blockers}
