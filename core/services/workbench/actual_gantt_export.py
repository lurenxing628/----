"""Whole-cohort CSV, including each report and explicit unknown/legacy semantics."""

import csv
from io import StringIO

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json

from .actual_gantt_scope import view_items

HEADERS = ["计划引用", "任务引用", "工序引用", "批次", "工序", "计划开工", "计划完工", "计划设备", "计划人员",
           "目标数量", "整道状态", "完成依据", "已知完成数量", "未知记录数", "整道实际完工", "数据质量",
           "报工引用", "报工单号", "录入依据计划", "录入依据任务", "本次开工", "本次结束", "本次数量", "有效加工小时",
           "实际设备", "实际人员", "备注", "登记时间", "剩余数量", "剩余计划开工", "剩余计划完工", "剩余设备", "剩余人员",
           "旧事实", "数据缺项", "数据截至", "快照引用", "服务端范围", "本地筛选", "计划事件类型", "计划时长秒", "计划占用资源",
           "单件编号", "计划应做数量", "计划批次数量", "计划数量依据", "计划数量缺失原因"]
STATES = {"unreported": "待报工", "started": "已开工", "partial": "部分报工", "paused": "已暂停", "exception": "异常", "complete": "整道已完工"}


def _cell(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def actual_gantt_csv(data, snapshot, view):
    if data["availability"]["state"] != "available":
        raise WorkbenchCommandRejected("execution_ledger_unavailable", "执行投影不可用，不能导出为完整实际数据。")
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
                  STATES[e["execution_state"]], e["completion_basis"], e["known_completed_quantity"], e["unknown_record_count"],
                  e["confirmed_finish"], e["data_quality"]]
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
