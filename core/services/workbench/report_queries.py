"""Five report topics and review share one cohort and snapshot timestamp."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import TOPICS

from .review_projection import project_cohort, validate_selected_refs
from .review_records import resource_directory
from .review_summary import charts, resource_rows, summary

GAPS = ["执行情况和累计数量都只认报工记录；旧系统的整道完工记录照样保留，它登记的数量不会再按逐次报工累加一遍。",
        "暂无反馈不等于没生产；工时未知和零工时分开算。已知工时小计不是完整总工时，缺记录的部分没算进去。",
        "实际时段和新报工的登记时间都按车间挂钟；旧系统登记的时间按原样显示，系统不猜着换算。"]
SORTS = {"delivery": ("batch_label", "planned_end", "finish_deviation_minutes", "effective_processing_hours"),
         "quality": ("batch_label", "event_count", "data_quality"),
         "records": ("event_time", "batch_label", "quantity_done", "effective_processing_hours"),
         "machines": ("resource_label", "events", "effective_processing_hours"),
         "people": ("resource_label", "events", "effective_processing_hours")}


def report_workspace(reader, facts, snapshot, topic, page, operation_ref=None):
    if topic not in TOPICS:
        raise WorkbenchCommandRejected("invalid_input", "没有这个报表专题，报表没有变化。请从上方专题里重新选择。", 400)
    facts["reader"] = reader
    validate_selected_refs(facts["scope"], facts)
    operations, records, labels = project_cohort(facts, snapshot["as_of"])
    resources = {"machines": resource_rows(records, "machine"), "people": resource_rows(records, "operator")}
    rows = records if topic == "records" else resources[topic] if topic in resources else operations
    ordered, visible, pagination = page.apply(rows, SORTS[topic])
    directory = resource_directory(facts)
    choices = {**directory, "batch": facts["resources"]["batch"]}
    scope_gaps = list(dict.fromkeys(gap for operation in operations for gap in operation["data_gaps"]))
    data = {"plan": facts["plan"], "scope": facts["scope"].scope(), "topic": topic, "provenance": "当前正式计划与报工记录（逐次报工、更正、旧现场记录）",
            "time_scope": {"selection": "plan_finish_date", "boundary": "inclusive_dates", "time_basis": "factory_local"},
            "rows": visible, "summary": summary(operations, records), "page": pagination,
            "charts": charts(operations, snapshot["as_of"]), "resources": resources,
            "capabilities": {"state": "partial" if any(row["data_quality"] != "complete" for row in operations) else "complete",
                             "legacy_events": True, "production_reports": True,
                             "effective_processing_hours": True, "detail": True, "export": True},
            "data_gaps": GAPS + scope_gaps, "choices": {kind: sorted(values.values(), key=lambda row: row["label"])
                                          for kind, values in choices.items()}}
    if operation_ref is not None:
        operation = next((row for row in operations if row["operation_ref"] == operation_ref), None)
        if operation is None:
            raise WorkbenchCommandRejected("entity_not_found", "这道工序不在当前筛选结果里，详情没有打开。请调整筛选条件后重新点这一行。", 404)
        data["detail"] = {"operation": operation, "records": [row for row in records if row["operation_ref"] == operation_ref]}
    return data, ordered, labels
