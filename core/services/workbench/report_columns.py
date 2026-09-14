"""Visible columns are also the exported columns, without private locators."""

OPERATION_COLUMNS = [("batch_label", "批次"), ("operation_label", "工序"),
    ("planned_start", "计划开工"), ("planned_end", "计划完工"), ("actual_start", "实际开工"),
    ("confirmed_finish", "已确认整道完工"), ("execution_label", "执行情况"),
    ("finish_deviation_minutes", "完工偏差（分钟）"), ("elapsed_since_planned_minutes", "到期未确认已过（分钟）"),
    ("known_completed_quantity", "已知累计完成数量"), ("effective_processing_hours", "有效加工工时（小时）"),
    ("operation_ref", "工序编号"), ("batch_ref", "批次编号"),
    ("remaining_quantity", "剩余数量"), ("unknown_record_count", "数量未知记录"),
    ("known_effective_processing_hours", "已知加工工时小计（小时）"), ("data_quality", "数据完整性"),
    ("completion_basis", "完成依据"), ("production_report_count", "逐次报工数"),
    ("event_count", "旧现场事件数"), ("record_count", "全部记录数"), ("unknown_hour_events", "工时未知记录")]
RECORD_COLUMNS = [("record_kind_label", "记录来源"), ("batch_label", "批次"), ("operation_label", "工序"),
    ("event_label", "记录类型"), ("event_time", "实际记录时间"), ("quantity_done", "记录登记数量"),
    ("effective_processing_hours", "有效加工工时（小时）"), ("machine_label", "实际设备"),
    ("operator_label", "实际人员"), ("remark", "备注"), ("operation_ref", "工序编号"),
    ("report_no", "报工单号"), ("report_ref", "报工编号"), ("revision_ref", "当前版本编号"),
    ("actual_start", "实际开工"), ("actual_end", "本次实际结束"), ("quantity_scrapped", "旧事件报废数量"),
    ("recorded_at", "登记时间"), ("recorded_at_time_basis", "登记时间说明"),
    ("recorded_against_plan_ref", "原报工计划编号"), ("recorded_against_task_ref", "原报工任务编号"),
    ("machine_ref", "实际设备编号"), ("operator_ref", "实际人员编号"),
    ("legacy_fact_ref", "关联旧记录编号"), ("correction_history", "完整更正记录"),
    ("source", "报工来源"), ("completed_quantity", "本次完成数量"), ("local_operator", "记录人"),
    ("declared_operator", "经办人"), ("legacy_evidence", "旧记录与时间依据")]
RESOURCE_COLUMNS = [("resource_label", "实际资源"), ("operations", "涉及工序"), ("batches", "涉及批次"),
    ("events", "旧现场事件数"), ("effective_processing_hours", "有效加工工时（小时）"), ("unknown_hour_events", "工时未知记录"),
    ("production_reports", "逐次报工数"), ("records", "全部记录数"),
    ("known_effective_processing_hours", "已知加工工时小计（小时）"), ("resource_ref", "资源编号")]
QUALITY_COLUMNS = [("batch_label", "批次"), ("operation_label", "工序"), ("execution_label", "执行情况"),
    ("event_count", "旧现场事件数"), ("data_quality", "数据完整性"), ("data_gaps", "数据缺口"), ("operation_ref", "工序编号"),
    ("production_report_count", "逐次报工数"), ("record_count", "全部记录数"),
    ("unknown_record_count", "数量未知记录"), ("records_complete", "报工内容完整")]
COLUMNS = {"delivery": OPERATION_COLUMNS, "records": RECORD_COLUMNS,
           "machines": RESOURCE_COLUMNS, "people": RESOURCE_COLUMNS, "quality": QUALITY_COLUMNS}


def public_columns(topic):
    return [{"key": key, "label": label} for key, label in COLUMNS[topic]]
