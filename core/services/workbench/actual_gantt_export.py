"""Whole-cohort CSV, including each report and explicit unknown/legacy semantics."""

import csv
from io import StringIO

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json

from .actual_gantt_scope import view_items
from .execution_ledger_projection import COMPLETION_BASIS_TEXT, DATA_QUALITY_TEXT, EXECUTION_STATE_TEXT

HEADERS = ["计划编号", "任务编号", "工序编号", "批次", "工序", "计划开工", "计划完工", "计划设备", "计划人员",
           "目标数量", "整道状态", "完成依据", "已知完成数量", "未知记录数", "整道实际完工", "资料完整性",
           "报工编号", "报工单号", "录入依据计划", "录入依据任务", "本次开工", "本次结束", "本次数量", "有效加工工时（小时）",
           "实际设备", "实际人员", "备注", "登记时间", "剩余数量", "剩余计划开工", "剩余计划完工", "剩余设备", "剩余人员",
           "历史记录", "数据缺项", "数据截至", "数据版本编号", "查询范围", "本地筛选", "计划事件类型", "计划时长（秒）", "计划占用资源",
           "单件编号", "计划应做数量", "计划批次数量", "计划数量依据", "计划数量缺失原因"]


def _cell(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def actual_gantt_csv(data, snapshot, view):
    if data["availability"]["state"] != "available":
        raise WorkbenchCommandRejected("execution_ledger_unavailable", "现场报工记录读不出来，导不出完整的实际数据。请刷新后重试。")
    selected = view_items(data, snapshot["as_of"], view)
    names = {row["ref"]: row["label"] or row["business_code"] for row in data["resources"]}
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(HEADERS)
    count = 0
    for item in selected:
        t, e = item["task"], item["execution"]
        future = e["remaining_plan"] or {}
        prefix = [t["plan_ref"], t["task_ref"], t["operation_ref"], t["batch_id"], str(t["sequence"]) + " " + t["process_label"],
                  t["start"], t["end"], names.get(t["machine_ref"]), names.get(t["operator_ref"]), e["target_quantity"],
                  EXECUTION_STATE_TEXT[e["execution_state"]], COMPLETION_BASIS_TEXT.get(e["completion_basis"]),
                  e["known_completed_quantity"], e["unknown_record_count"],
                  e["confirmed_finish"], DATA_QUALITY_TEXT[e["data_quality"]]]
        suffix = [e["remaining_quantity"], future.get("start"), future.get("end"), names.get(future.get("machine_ref")),
                  names.get(future.get("operator_ref")), canonical_json(e["legacy_facts"]), canonical_json(e["data_gaps"]),
                  snapshot["as_of"], snapshot["snapshot_ref"], canonical_json(data["scope"]), canonical_json(view),
                  t.get("event_kind"), t.get("duration_seconds"), t.get("occupies_resources"), t["piece_id"],
                  t["quantity"], t["batch_quantity"], t["quantity_basis"], t["quantity_reason"]]
        for report in e["reports"] or [None]:
            r = report or {}
            details = [r.get(key) for key in ("report_ref", "report_no", "recorded_against_plan_ref", "recorded_against_task_ref",
                                             "actual_start", "actual_end", "completed_quantity", "effective_processing_hours")]
            details += [names.get(r.get("actual_machine_ref")), names.get(r.get("actual_operator_ref")), r.get("remark"), r.get("recorded_at")]
            writer.writerow([_cell(value) for value in prefix + details + suffix])
            count += 1
    return ("\ufeff" + stream.getvalue()).encode("utf-8"), count, len(selected)
