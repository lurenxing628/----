from __future__ import annotations

import io
from typing import Any, Dict, List

import openpyxl


def export_overdue_xlsx(items: List[Dict[str, Any]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.title = "overdue"
        ws.append(["类别", "批次号", "图号", "名称", "数量", "交期", "完工/截至时间", "超期(小时)", "超期(天)"])
        for it in items:
            ws.append(
                [
                    it.get("bucket_label"),
                    it.get("batch_id"),
                    it.get("part_no"),
                    it.get("part_name"),
                    it.get("quantity"),
                    it.get("due_date"),
                    it.get("finish_time") or it.get("as_of_time"),
                    it.get("delay_hours"),
                    it.get("delay_days"),
                ]
            )
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass


def export_utilization_xlsx(machines: List[Dict[str, Any]], operators: List[Dict[str, Any]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws1 = wb.active
        ws1.title = "machines"
        ws1.append(["设备编号", "设备名称", "负荷(小时)", "任务数", "可用工时(小时)", "利用率"])
        for r in machines:
            ws1.append(
                [
                    r.get("machine_id"),
                    r.get("machine_name"),
                    r.get("hours"),
                    r.get("task_count"),
                    r.get("capacity_hours"),
                    r.get("utilization"),
                ]
            )

        ws2 = wb.create_sheet("operators")
        ws2.append(["工号", "姓名", "负荷(小时)", "任务数", "可用工时(小时)", "利用率"])
        for r in operators:
            ws2.append(
                [
                    r.get("operator_id"),
                    r.get("operator_name"),
                    r.get("hours"),
                    r.get("task_count"),
                    r.get("capacity_hours"),
                    r.get("utilization"),
                ]
            )

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass


def export_downtime_impact_xlsx(machines: List[Dict[str, Any]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.title = "downtime"
        ws.append(["设备编号", "设备名称", "停机时长(小时)", "停机次数", "与排程重叠(小时)", "重叠次数"])
        for r in machines:
            ws.append(
                [
                    r.get("machine_id"),
                    r.get("machine_name"),
                    r.get("downtime_hours"),
                    r.get("downtime_count"),
                    r.get("schedule_overlap_hours"),
                    r.get("schedule_overlap_count"),
                ]
            )
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass

