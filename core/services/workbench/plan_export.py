"""Export the admitted workspace only, with lossless text and explicit nulls.

CSV text has one reversible apostrophe prefix. In both formats null is \\N and
literal leading backslashes are escaped once, as in the resource file writer.
No plan lookup, widened scope, receipts or writes belong in this codec.
"""

import codecs
import csv
import os
from tempfile import SpooledTemporaryFile

import openpyxl
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

from core.models.workbench_resource_file import ResourceFileDownload

from .process_file_xml import preserve_carriage_returns
from .resource_file_writer import _value, check_capacity

HEADERS = (
    "计划编号", "来源版本", "计划类型", "计划名称", "是否当前正式", "计划完整性", "数据版本", "读取时间",
    "范围起点（含）", "范围终点（不含）", "时间计算方式", "任务编号", "工序编号", "批次编号", "工序号", "工序名称",
    "设备编号", "设备名称", "人员编号", "人员名称", "外协商编号", "外协商名称", "安排开始", "安排结束",
    "交付风险", "计划完成", "部分计划完成", "交期", "交期截止（不含）", "超期小时", "超期天数", "交付完整性",
)

# 导出单元格只写用户看得懂的中文，英文枚举值不外显。
PLAN_KINDS = {"official": "正式计划", "candidate": "候选方案", "scenario": "试调方案"}
PLAN_COMPLETENESS = {"complete": "记录完整", "partial": "部分记录", "invalid": "无效记录", "unknown": "暂无数据"}
DELIVERY_RISKS = {"overdue": "预计超期", "on_time": "预计按期", "unknown": "暂无数据"}
DELIVERY_COMPLETENESS = {"complete": "完整", "incomplete": "尚不完整", "unknown": "暂无数据"}


def export_rows(data, snapshot):
    plan = data["plan"]
    resources = {item["ref"]: item for item in data["resources"]}
    delivery = {item["batch_id"]: item for item in data["projections"]["delivery_risks"]["items"]}
    common = [plan["plan_ref"], str(plan["version"]), PLAN_KINDS[plan["kind"]],
              plan["display_name"], "是" if plan["is_current_official"] else "否",
              PLAN_COMPLETENESS[plan["completeness"]],
              snapshot["snapshot_ref"], snapshot["as_of"], data["time_scope"]["range_start"],
              data["time_scope"]["range_end"], "含起日，不含止日"]
    for task in data["tasks"]:
        values = common + [task["task_ref"], task["operation_ref"], task["batch_id"], str(task["sequence"]), task["process_label"]]
        for kind in ("machine", "operator", "supplier"):
            resource = resources.get(task[kind + "_ref"])
            values += [resource["business_code"], resource["label"]] if resource is not None else [None, None]
        item = delivery[task["batch_id"]]
        values += [task["start"], task["end"], DELIVERY_RISKS[item["risk"]],
                   item["planned_finish"], item["partial_planned_finish"],
                   item["due_date"], item["delivery_deadline_exclusive"], item["delay_hours"], item["delay_days"],
                   DELIVERY_COMPLETENESS[item["completeness"]]]
        yield values


def _values(values, number, fmt):
    # Reuse the established numeric validation, null escaping and cell limits.
    return [_value(value, "default_days" if index in (29, 30) else "text", number, fmt)
            for index, value in enumerate(values)]


def write_plan_export(data, snapshot, fmt):
    check_capacity(data["task_count"], fmt)
    if fmt == "csv":
        return _csv(data, snapshot)
    return _xlsx(data, snapshot)


def _download(content, fmt, count):
    mime = "text/csv; charset=utf-8" if fmt == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return ResourceFileDownload("计划范围导出." + fmt, mime, content, count)


def _csv(data, snapshot):
    with SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b") as buffer:
        text = codecs.getwriter("utf-8-sig")(buffer)
        writer = csv.writer(text, lineterminator="\r\n")
        writer.writerow(HEADERS)
        for number, row in enumerate(export_rows(data, snapshot), 2):
            writer.writerow(["'" + value if type(value) is str else value for value in _values(row, number, "csv")])
        text.flush()
        buffer.seek(0)
        return _download(buffer.read(), "csv", data["task_count"])


def _xlsx(data, snapshot):
    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("计划任务")
    try:
        ws.freeze_panes = "A2"
        headers = [WriteOnlyCell(ws, value=value) for value in HEADERS]
        for cell in headers:
            cell.font = Font(bold=True)
        ws.append(headers)
        for number, row in enumerate(export_rows(data, snapshot), 2):
            cells = []
            for value in _values(row, number, "xlsx"):
                cell = WriteOnlyCell(ws, value=value)
                if type(value) is str:
                    cell.data_type, cell.number_format = "s", "@"
                cells.append(cell)
            ws.append(cells)
        preserve_carriage_returns(ws)
        with SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b") as buffer:
            wb.save(buffer)
            buffer.seek(0)
            return _download(buffer.read(), "xlsx", data["task_count"])
    finally:
        if not ws.closed:
            ws.close()
        if ws._writer is not None and os.path.exists(ws._writer.out):
            ws._writer.cleanup()
        wb.close()
