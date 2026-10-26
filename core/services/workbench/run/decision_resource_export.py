"""Resource values and units from the same filtered decision projection."""

from typing import Any, List

from core.services.workbench.facts.candidate_tasks import operation_labels

from .decision_export_cells import boolean_text

RESOURCE_MEASURES = (
    ("available_hours", "可排总时长（小时）", False),
    ("occupied_hours", "班内已占（小时）", False),
    ("summed_load_hours", "班内工序区间累加（小时）", False),
    ("outside_calendar_hours", "安排跨度跨非工作时段（小时）", False),
    ("overlap_hours", "班内重复计时（小时）", False),
    ("utilization_ratio", "占用比例（%）", True),
    ("demand_ratio", "工序累加时长与可排时长之比（%）", True),
    ("peak_utilization", "时段占用比例（%）", True),
    ("span_occupied_hours", "保留安排跨度合计（小时）", False),
    ("span_summed_hours", "保留工序跨度累加（小时）", False),
    ("span_overlap_hours", "保留安排重复计时（小时）", False),
    ("overlap_span_hours", "保留安排重叠时段（小时）", False),
)
_COMMON = ("排产编号", "查看基准永久编号", "所选方案编号", "资源永久编号", "资源类型", "资源名称", "资源视角", "范围起点（含）", "范围终点（不含）",
           "资源粒度", "高负荷阈值（%）", "筛选时段起点（含）", "筛选时段终点（不含）", "资源指标版本")
_MEASURES = tuple(prefix + label for _field, label, _ratio in RESOURCE_MEASURES for prefix in ("基准", "所选", "变化"))
_WINDOW_MEASURES = tuple(prefix + ("日峰占用比例（%）" if field == "peak_utilization" else label)
                         for field, label, _ratio in RESOURCE_MEASURES for prefix in ("基准", "所选", "变化"))
_STATE = ("基准覆盖状态", "所选覆盖状态", "基准高负荷", "所选高负荷", "基准零容量工作证据", "所选零容量工作证据",
          "基准存在冲突", "所选存在冲突", "基准班表未知天数", "所选班表未知天数", "基准零容量天数", "所选零容量天数",
          "基准安排段数", "所选安排段数", "基准安排工序数", "所选安排工序数", "基准已知可排时长（小时）", "所选已知可排时长（小时）",
          "基准已知班内占用（小时）", "所选已知班内占用（小时）", "基准已知班内工序累加时长（小时）", "所选已知班内工序累加时长（小时）", "基准缺项", "所选缺项",
          "基准高负荷时段数", "所选高负荷时段数",
          "基准需求超载时段数", "所选需求超载时段数", "基准班表完整状态", "所选班表完整状态", "基准实际工作片段状态", "所选实际工作片段状态",
          "基准零容量证据原因", "所选零容量证据原因", "班表外跨度计算方式", "冲突计算方式")
_COVERAGE = ("正式归档工序数", "所选覆盖正式工序数", "所选完整覆盖正式范围", "所选缺失正式工序数", "所选其他未安排工序数", "所选缺料未安排工序数")
RESOURCE_HEADERS = _COMMON + _WINDOW_MEASURES + _STATE + _COVERAGE + ("筛选时段峰占用比例（%）", "筛选时段日峰占用比例（%）",
    "筛选时段高负荷数", "筛选时段需求超载数", "筛选时段班表内冲突数", "筛选时段高负荷区间")
RESOURCE_DAY_HEADERS = _COMMON + ("日期", "时段起点（含）", "时段终点（不含）") + _MEASURES + _STATE + (
    "基准日峰占用比例（%）", "所选日峰占用比例（%）", "基准冲突段数", "所选冲突段数", "基准冲突工序数", "所选冲突工序数")
RESOURCE_CONFLICT_HEADERS = _COMMON + ("日期", "比较侧", "冲突起点（含）", "冲突终点（不含）", "工序永久编号", "安排永久编号", "批次永久编号", "批次编号", "工序名称")
COVERAGE_OPERATION_HEADERS = ("排产编号", "查看基准永久编号", "所选方案编号", "比较侧", "分类", "工序永久编号", "批次永久编号", "批次编号", "工序号", "工序名称")
_COVERAGE_KINDS = (("missing_formal_operation_refs", "缺失正式"), ("unplanned_operation_refs", "其他未安排"),
                   ("deferred_operation_refs", "缺料未安排"))


def _issues(items):
    return "；".join(item["message"] for item in items) or None


def _scope(data, resource):
    baseline, scope = data["baseline"], data["scope"]
    baseline_ref = baseline.get("candidate_ref") if baseline["kind"] == "candidate" else baseline.get("baseline_ref")
    filters = data["filters"]
    pressure = data.get("pressure_scope") or data.get("display_scope") or {"start": scope["range_start"], "end": scope["range_end"]}
    return [data["run_ref"], baseline_ref, data["candidate"]["candidate_ref"], resource["ref"],
            "设备" if resource["kind"] == "machine" else "人员", resource["label"],
            "本次所选批次" if scope["resource_view"] == "selected_batches" else "方案全部安排", scope["range_start"], scope["range_end"],
            {"hour": "小时", "day": "天", "shift": "真实可排班段", "week": "周"}[filters["grain"]], filters["pressure_threshold"] * 100,
            pressure["start"], pressure["end"], data["metric_version"]]


def _measure_values(before, after, deltas):
    values = []
    for field, _label, ratio in RESOURCE_MEASURES:
        for value in (before.get(field), after.get(field), deltas.get(field)):
            values.append(value * 100 if ratio and value is not None else value)
    return values


def _state_values(before, after):
    names = {"complete": "完整", "partial": "部分", "unavailable": "缺少资料", "not_applicable": "范围无适用对象"}
    values: List[Any] = [names[before["state"]], names[after["state"]]]
    for field in ("high_pressure", "zero_capacity_task", "conflict"):
        values.extend(boolean_text(side[field]) for side in (before, after))
    for field in ("unknown_days", "zero_capacity_days", "task_count", "operation_count", "known_available_hours", "known_occupied_hours", "known_summed_load_hours"):
        values.extend(side[field] for side in (before, after))
    values += [_issues(before["issues"]), _issues(after["issues"])]
    for field in ("high_pressure_period_count", "demand_overload_period_count", "calendar_state", "actual_work_state"):
        values.extend(side.get(field) for side in (before, after))
    values += [side["zero_capacity_reason"]["message"] if side.get("zero_capacity_reason") else None for side in (before, after)]
    return values + ["保留安排跨度与非工作窗口的交集", "归档可排窗口内不同永久工序的安排重叠"]


def resource_rows(documents):
    for data in documents:
        coverage = data["coverage"]["after"]
        suffix = [coverage["formal_operation_count"], coverage["covered_formal_operation_count"], boolean_text(coverage["formal_coverage_complete"]),
                  len(coverage["missing_formal_operation_refs"]), len(coverage["unplanned_operation_refs"]),
                  len(coverage["deferred_operation_refs"])]
        for row in data["items"]:
            resource = {"ref": row["resource_ref"], "kind": row["resource_kind"], "label": row["label"]}
            before, after = row["before"], row["after"]
            filtered = row["filter_summary"]
            peaks = [filtered[field] * 100 if filtered[field] is not None else None for field in (
                "period_peak_utilization", "daily_peak_utilization")]
            counts = [filtered[field] for field in ("high_pressure_period_count", "demand_overload_period_count", "conflict_period_count")]
            high_periods = "；".join(period["start"] + " / " + period["end"] for period in filtered["high_pressure_periods"]) or None
            yield _scope(data, resource) + _measure_values(before, after, row["deltas"]) + _state_values(before, after) + suffix + peaks + counts + [high_periods]


def coverage_operation_rows(source, coverage):
    """Keep every saved coverage identity in its own Excel row."""
    baseline = source.baseline
    baseline_ref = baseline.get("candidate_ref") if baseline["kind"] == "candidate" else baseline.get("baseline_ref")
    common = [source.run["run_ref"], baseline_ref, source.selected_ref]
    official_labels = {row["operation_ref"]: row for row in source.official["tasks"]}
    labels_by_ref = {}
    for side, side_label in (("before", "基准"), ("after", "所选")):
        if side == "before" and baseline["state"] != "available":
            continue
        for field, category in _COVERAGE_KINDS:
            for ref in coverage[side][field]:
                if ref not in labels_by_ref:
                    labels_by_ref[ref] = operation_labels(source.facts, ref)[0] if ref in source.facts.operations else official_labels.get(ref, {})
                labels = labels_by_ref[ref]
                yield common + [side_label, category, ref, labels.get("batch_ref"), labels.get("batch_label"),
                                labels.get("sequence"), labels.get("process_label")]


def resource_day_rows(data):
    common = _scope(data, data["resource"])
    for row in data["items"]:
        before, after = row["before"], row["after"]
        operations = [len({ref for conflict in side["conflicts"] for ref in conflict["operation_refs"]}) if side["conflict"] is not None else None
                      for side in (before, after)]
        counts = [len(side["conflicts"]) if side["conflict"] is not None else None for side in (before, after)]
        daily_peaks = [side.get("daily_peak_utilization") * 100 if side.get("daily_peak_utilization") is not None else None for side in (before, after)]
        yield common + [row["date"], row["start"], row["end"]] + _measure_values(before, after, row["deltas"]) + _state_values(before, after) + daily_peaks + counts + operations


def resource_conflict_rows(data):
    """Each conflict membership retains its paired operation and saved row."""
    common = _scope(data, data["resource"])
    for row in data["items"]:
        for side, side_label in (("before", "基准"), ("after", "所选")):
            tasks = {task["row_ref"]: task for task in row[side]["tasks"]}
            for conflict in row[side]["conflicts"]:
                for row_ref in conflict["row_refs"]:
                    task = tasks[row_ref]
                    yield common + [row["date"], side_label, conflict["start"], conflict["end"], task["operation_ref"], row_ref,
                                    task.get("batch_ref"), task.get("batch_label"), task.get("process_label")]
