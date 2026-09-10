"""Five report topics and review share one cohort and snapshot timestamp."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import TOPICS

from .review_projection import project_cohort, validate_selected_refs
from .review_records import resource_directory
from .review_summary import charts, resource_rows, summary

GAPS = ["执行状态与累计数量来自唯一执行台账；旧合法整道完工事实保留，旧事件登记数量不按逐次产量累加。",
        "暂无反馈不等于未生产；未知工时与零工时分开。已知工时小计不代表含缺失记录的完整总工时。",
        "实际时段与新报工登记时间按工厂墙钟；旧登记时间保留 legacy_storage 声明，不猜测转换。"]
SORTS = {"delivery": ("batch_label", "planned_end", "finish_deviation_minutes", "effective_processing_hours"),
         "quality": ("batch_label", "event_count", "data_quality"),
         "records": ("event_time", "batch_label", "quantity_done", "effective_processing_hours"),
         "machines": ("resource_label", "events", "effective_processing_hours"),
         "people": ("resource_label", "events", "effective_processing_hours")}


def report_workspace(reader, facts, snapshot, topic, page, operation_ref=None):
    if topic not in TOPICS:
        raise WorkbenchCommandRejected("invalid_input", "未知报表专题。", 400)
    facts["reader"] = reader
    validate_selected_refs(facts["scope"], facts)
    operations, records, labels = project_cohort(facts, snapshot["as_of"])
    resources = {"machines": resource_rows(records, "machine"), "people": resource_rows(records, "operator")}
    rows = records if topic == "records" else resources[topic] if topic in resources else operations
    ordered, visible, pagination = page.apply(rows, SORTS[topic])
    directory = resource_directory(facts)
    choices = {**directory, "batch": facts["resources"]["batch"]}
    scope_gaps = list(dict.fromkeys(gap for operation in operations for gap in operation["data_gaps"]))
    data = {"plan": facts["plan"], "scope": facts["scope"].scope(), "topic": topic, "provenance": "当前正式计划与唯一执行台账（逐次报工、更正、旧现场事实）",
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
            raise WorkbenchCommandRejected("entity_not_found", "工序不在当前筛选快照内，未猜测其他对象。", 404)
        data["detail"] = {"operation": operation, "records": [row for row in records if row["operation_ref"] == operation_ref]}
    return data, ordered, labels
