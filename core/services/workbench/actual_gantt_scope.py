"""Exact actual-Gantt cohort and independent local-view export filters."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn, Optional, Tuple

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope, local_time, plan_reference
from core.services.workbench.zero_duration_evidence import overlaps

COHORT_KEYS = ("plan_ref", "source", "range_start", "range_end", "plan_finish_date_from",
               "plan_finish_date_to", "resource_type", "resource_ref", "batch_ids")
VIEW_KEYS = ("local_query", "late_filter", "selected_task_ref")
LATE_FILTERS = ("all", "finishLate", "unclosed", "forecastLate")


def invalid(message: str) -> NoReturn:
    raise WorkbenchCommandRejected("invalid_input", message, 400)


def _date(value):
    if value is not None:
        local_time(value + "T00:00:00")
    return value


def _validate_finish_dates(first, last):
    start, end = _date(first), _date(last)
    if (start is None) != (end is None) or start is not None and end is not None and start > end:
        invalid("计划完工日期必须同时提供，开始日不得晚于结束日。")


def _validate_resource(kind, ref):
    if (kind is None) != (ref is None):
        invalid("资源类型和具体资源要一起选，只选一个不行。")
    if kind is not None:
        if kind not in ("machine", "operator"):
            invalid("资源条件只接受设备或人员；批次使用批次范围。")
        plan_reference(ref)


def _validate_batches(values):
    if (type(values) is not tuple or len(values) > 10000
            or any(type(value) is not str or not value.strip() or len(value) > 200 for value in values)
            or len(set(values)) != len(values)):
        invalid("批次范围必须是明确且不重复的批次编号集合。")


@dataclass(frozen=True)
class ActualGanttScope:
    plan_ref: str
    source: str = "production"
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    plan_finish_date_from: Optional[str] = None
    plan_finish_date_to: Optional[str] = None
    resource_type: Optional[str] = None
    resource_ref: Optional[str] = None
    batch_ids: Tuple[str, ...] = ()

    def __post_init__(self):
        PlanReadScope(self.plan_ref, self.range_start, self.range_end)
        if self.source != "production":
            invalid("数据来源无效，请重新打开现场实际甘特。")
        _validate_finish_dates(self.plan_finish_date_from, self.plan_finish_date_to)
        _validate_resource(self.resource_type, self.resource_ref)
        _validate_batches(self.batch_ids)

    def scope(self):
        return dict(source=self.source, kind="actual_gantt", plan_ref=self.plan_ref,
                    range_start=self.range_start, range_end=self.range_end,
                    plan_finish_date_from=self.plan_finish_date_from,
                    plan_finish_date_to=self.plan_finish_date_to,
                    resource_type=self.resource_type, resource_ref=self.resource_ref,
                    batch_ids=sorted(self.batch_ids))

    @classmethod
    def parse(cls, values):
        args = dict(values)
        if "batch_ids" in args:
            try:
                batches = json.loads(args["batch_ids"])
            except (ValueError, TypeError) as exc:
                raise WorkbenchCommandRejected("invalid_input", "批次范围必须是 JSON 数组。", 400) from exc
            if not isinstance(batches, list):
                invalid("批次范围必须是数组。")
            args["batch_ids"] = tuple(batches)
        if "plan_ref" not in args:
            invalid("请先选择计划。")
        return cls(**args)


def cohort_match(item, scope):
    task, execution = item["task"], item["execution"]
    if scope.range_start is not None and not overlaps(task["start"], task["end"], scope.range_start, scope.range_end):
        return False
    if scope.plan_finish_date_from is not None and not scope.plan_finish_date_from <= task["end"][:10] <= scope.plan_finish_date_to:
        return False
    if scope.batch_ids and task["batch_id"] not in scope.batch_ids:
        return False
    if scope.resource_ref is not None:
        return _resource_match(task, execution, scope)
    return True


def _resource_match(task, execution, scope):
    field = scope.resource_type + "_ref"
    owners = [task]
    if execution and execution["remaining_plan"]:
        owners.append(execution["remaining_plan"])
    if any(owner.get(field) == scope.resource_ref for owner in owners):
        return True
    if not execution:
        return False
    if any(report.get("actual_" + field) == scope.resource_ref
           for report in execution["reports"] + execution["legacy_facts"]):
        return True
    if _resource_unresolved(execution["data_gaps"], "actual_" + field):
        raise WorkbenchCommandRejected("execution_resource_unavailable", "历史报工的设备或人员资料无法对应，请核对资源资料。")
    return False


def _resource_unresolved(gaps, field):
    return any(gap["code"] == "legacy_resource_identity_unresolved"
               and (not gap.get("fields") or field in gap["fields"]) for gap in gaps)


def deadlines(item, as_of):
    task, execution = item["task"], item["execution"]
    if execution is None:
        return dict(finishLate=False, unclosed=False, forecastLate=False)
    end = datetime.fromisoformat(task["end"])
    complete = execution["execution_state"] == "complete"
    actual = execution["confirmed_finish"]
    remaining = execution["remaining_plan"]
    return dict(finishLate=bool(complete and actual and (datetime.fromisoformat(actual) - end).total_seconds() > 600),
                unclosed=bool(not complete and task["end"] <= as_of),
                forecastLate=bool(not complete and remaining and (datetime.fromisoformat(remaining["end"]) - end).total_seconds() > 600))


def search_text(item, names):
    task, execution = item["task"], item["execution"]
    terms = [task["batch_id"], str(task["sequence"]), task["process_label"], task.get("piece_id") or "",
             names.get(task["machine_ref"], ""), names.get(task["operator_ref"], "")]
    if execution:
        for report in execution["reports"]:
            terms.extend([report["report_no"], names.get(report["actual_machine_ref"], ""),
                          names.get(report["actual_operator_ref"], "")])
        remaining = execution["remaining_plan"]
        for fact in execution["legacy_facts"]:
            terms.extend([names.get(fact.get("actual_machine_ref"), ""), names.get(fact.get("actual_operator_ref"), "")])
        if remaining:
            terms.extend([names.get(remaining.get("machine_ref"), ""), names.get(remaining.get("operator_ref"), "")])
    return " ".join(terms).lower()


def _view_arguments(data, values):
    query = values.get("local_query", "")
    late = values.get("late_filter", "all")
    selected = values.get("selected_task_ref")
    if type(query) is not str or len(query) > 200 or late not in LATE_FILTERS:
        invalid("本地搜索或晚期筛选无效。")
    if selected is not None:
        plan_reference(selected)
        if not any(item["task"]["task_ref"] == selected for item in data["items"]):
            invalid("所选工序不在当前范围，请刷新后重选。")
    return query.strip().lower(), late, selected


def view_items(data, as_of, values):
    query, late, selected = _view_arguments(data, values)
    names = {row["ref"]: row["label"] or row["business_code"] for row in data["resources"]}
    return [item for item in data["items"] if (not query or query in search_text(item, names))
            and (late == "all" or deadlines(item, as_of)[late])
            and (selected is None or item["task"]["task_ref"] == selected)]
