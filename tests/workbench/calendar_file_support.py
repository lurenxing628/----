"""日历文件测试的独立取值口径：直接读 WorkCalendar 表，不调生产读取来验证生产写入。"""

import csv
from io import BytesIO, StringIO

import openpyxl

HEADERS = ("日期", "类型", "班次开始", "班次结束", "效率（%）", "允许普通件", "允许急件", "备注")


def file_bytes(rows, fmt="csv", headers=HEADERS):
    if fmt == "csv":
        target = StringIO(newline="")
        writer = csv.writer(target)
        writer.writerow(headers)
        writer.writerows(rows)
        return target.getvalue().encode("utf-8-sig")
    wb = openpyxl.Workbook()
    ws = wb.worksheets[0]
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    output = BytesIO()
    wb.save(output)
    wb.close()
    return output.getvalue()
