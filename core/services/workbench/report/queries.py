"""Five report topics and review share one cohort and snapshot timestamp."""

from __future__ import annotations

from core.services.execution.processing_hours import covered_legacy_scopes

from .review_projection import project_cohort, project_detail
from .review_summary import charts, resource_rows, summary

GAPS = ["执行状态与累计数量按报工记录统计，历史完工记录单独列示。",
        "晚完成指实际完工比计划晚超过 10 分钟。工时缺项在明细中标注为待补。",
        "新报工使用工厂当地时间；历史记录保留原时间。"]
SORTS = {"delivery": ("batch_label", "planned_end", "finish_deviation_minutes", "effective_processing_hours"),
         "quality": ("batch_label", "event_count", "data_quality"),
         "records": ("event_time", "batch_label", "quantity_done", "effective_processing_hours"),
         "machines": ("resource_label", "events", "effective_processing_hours"),
         "people": ("resource_label", "events", "effective_processing_hours")}


def report_workspace(facts, snapshot, topic, page):
    operations, records, labels = project_cohort(facts, snapshot["as_of"])
    covered = covered_legacy_scopes(records)
    resources = {
        "machines": resource_rows(records, "machine", covered=covered),
        "people": resource_rows(records, "operator", covered=covered),
    }
    rows = records if topic == "records" else resources[topic] if topic in resources else operations
    ordered, visible, pagination = page.apply(rows, SORTS[topic])
    choices = facts["choices"]
    scope_gaps = list(dict.fromkeys(gap for operation in operations for gap in operation["data_gaps"]))
    data = {"plan": facts["plan"], "scope": facts["scope"].scope(), "topic": topic, "provenance": "当前正式计划与报工记录（逐次报工、更正、旧现场记录）",
            "time_scope": {"selection": "plan_finish_date", "boundary": "inclusive_dates", "time_basis": "factory_local"},
            "rows": visible, "summary": summary(operations, records, covered=covered), "page": pagination,
            "charts": charts(operations, snapshot["as_of"]), "resources": resources,
            "capabilities": {"state": "partial" if any(row["data_quality"] != "complete" for row in operations) else "complete",
                             "legacy_events": True, "production_reports": True,
                             "effective_processing_hours": True, "detail": True, "export": True},
            "data_gaps": GAPS + scope_gaps, "choices": {kind: sorted(values.values(), key=lambda row: row["label"])
                                          for kind, values in choices.items()}}
    return data, ordered, labels


def report_detail(facts, snapshot, operation_ref):
    return {"plan": facts["plan"], "detail": project_detail(facts, snapshot["as_of"], operation_ref)}
