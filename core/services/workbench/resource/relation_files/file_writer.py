"""一次性离线下载。编号与看起来像公式的文字一律按文本写出。"""

import codecs
import csv
from tempfile import SpooledTemporaryFile

from core.models.workbench_action_values import FileDownload
from core.models.workbench_relation_file import (
    file_columns,
    public_columns,
    relation_kind,
    table_descriptor,
)
from core.services.workbench.facts.file_writer import (
    ILLEGAL,
    XLSX_MAX_CELL_CHARACTERS,
    check_capacity,
    write_template_xlsx,
)

from .file_codec import file_error


def _value(value, field, row, fmt):
    if value is None:
        return r"\N"
    if type(value) is not str:
        raise file_error("这个格子里存的内容不是文字，没有导出。请到资料总览修正后重试。", row, field)
    if value.startswith("\\"):
        value = "\\" + value
    if fmt == "xlsx" and (ILLEGAL.search(value) or len(value) > XLSX_MAX_CELL_CHARACTERS):
        raise file_error("这个格子里有 XLSX 放不下的字符，或者超过 32767 个字，没有导出，内容也没有被截断。请改用 CSV。", row, field)
    if fmt == "csv" and "\x00" in value:
        raise file_error("这个格子里有 CSV 处理不了的空字符，没有导出，原内容也没有被删。请到资料总览修正后重试。", row, field)
    return value


def write_relation_file(kind, rows, fmt, *, template=False):
    relation_kind(kind)
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
            writer.writerow(["'" + value for value in values])
        text.flush()
        buffer.seek(0)
        return FileDownload(filename + ".csv", "text/csv; charset=utf-8", buffer.read(), count)
