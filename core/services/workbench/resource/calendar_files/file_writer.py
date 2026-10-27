"""一次性离线下载。日期与看起来像公式的文字一律按文本写出。"""

import codecs
import csv
import sys
from tempfile import SpooledTemporaryFile

from core.models.calendar_period_columns import PERIOD_COLUMNS
from core.models.workbench_action_values import FileDownload
from core.models.workbench_calendar_file import (
    file_columns,
    public_columns,
    table_descriptor,
)
from core.services.workbench.facts.file_writer import (
    ILLEGAL,
    XLSX_MAX_CELL_CHARACTERS,
    check_capacity,
    write_template_xlsx,
)
from core.services.workbench.facts.table_cells import number_text

from .file_codec import file_error

# 工时写法 number_text 与页面、其它文件共用（8.0 写成 8，0.00001 不写成 1e-05，能原样还原）；
# 日历的导出、预检对比、回导都经本模块取，所以在这里一并导出。


def percent_text(ratio: float) -> str:
    """效率按百分数写：0.57 × 100 会是 56.99999999999999，只把这种换算尾巴按 15 位有效数字收掉，写成 57。

    与页面显示同一口径，不改真实取值，回导仍判不变。工时不走这里，免得分钟工时被截成存不稳的小数。
    """
    value = ratio * 100
    tidy = float(format(value, ".15g"))
    if abs(value - tidy) <= abs(value) * sys.float_info.epsilon * 2:
        value = tidy
    return number_text(value)


def _value(value, field, row, fmt):
    if value is None:
        return r"\N"
    if type(value) is not str:
        raise file_error("这个格子里存的内容不是文字，没有导出。请到日历页修正后重试。", row, field)
    if value.startswith("\\"):
        value = "\\" + value
    if fmt == "xlsx" and (ILLEGAL.search(value) or len(value) > XLSX_MAX_CELL_CHARACTERS):
        raise file_error("这个格子里有 XLSX 放不下的字符，或者超过 32767 个字，没有导出，内容也没有被截断。请改用 CSV。", row, field)
    if fmt == "csv" and "\x00" in value:
        raise file_error("这个格子里有 CSV 处理不了的空字符，没有导出，原内容也没有被删。请到日历页修正后重试。", row, field)
    return value


def write_calendar_file(kind, rows, fmt, *, template=False):
    check_capacity(0, fmt)
    descriptor = table_descriptor(kind)
    filename = descriptor["file_stem"] + ("导入模板" if template else "清单")
    if fmt == "csv":
        return _csv(kind, rows, filename)
    return write_template_xlsx(
        rows, filename, template, descriptor,
        cell_value=lambda raw, field, row_no: _value(raw, field, row_no, "xlsx"),
    )


def _csv(kind, rows, filename):
    count = 0
    columns = file_columns(kind)
    with SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b") as buffer:
        text = codecs.getwriter("utf-8-sig")(buffer)
        writer = csv.writer(text, lineterminator="\r\n")
        writer.writerow([item["label"] for item in public_columns(kind)])
        for count, row in enumerate(rows, 1):
            values = [_value(row[field], field, count + 1, "csv") for field in columns]
            writer.writerow(["" if field in PERIOD_COLUMNS and value == "" else "'" + value
                             for field, value in zip(columns, values)])
        text.flush()
        buffer.seek(0)
        return FileDownload(filename + ".csv", "text/csv; charset=utf-8", buffer.read(), count)
