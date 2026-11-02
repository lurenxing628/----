"""Physical CSV/XLSX rows; schema, limits and value policies stay in the codecs.

CSV row numbers identify the first physical line, including quoted multiline
records. XLSX reads the first sheet without trusting cached dimensions and keeps
formula/error cells visible to each domain. Closing the generator releases the
workbook even when a caller rejects the header or stops at its row limit.
"""

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

from core.errors import ValidationError
from core.services.common.excel_cell_values import cell_value, is_formula_or_error
from core.services.workbench.facts.process_file_xml import check_sheet_order

XLSX_EXPANDED_BYTE_LIMIT = 64 * 1024 * 1024
_WORKBOOK_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


@dataclass(frozen=True)
class FileReadMessages:
    csv_encoding: str
    csv_format: str
    xlsx_empty: str
    xlsx_read: str
    xlsx_cell: str


_CSV_ERROR = "这个 CSV 不是 UTF-8 编码，或者引号不成对，一行都没有导入。请另存为 UTF-8 编码后重新上传。"
DEFAULT_READ_MESSAGES = FileReadMessages(
    csv_encoding=_CSV_ERROR,
    csv_format=_CSV_ERROR,
    xlsx_empty="这个 XLSX 里没有工作表，没有导入。请确认文件完整后重新上传。",
    xlsx_read="这个 XLSX 打不开，没有导入。请确认文件完整后重新上传。",
    xlsx_cell="这个格子是公式或者显示为错误值，没有导入。请改成纯文本后重新上传。",
)


def source_rows(content, fmt, state, *, error, messages=DEFAULT_READ_MESSAGES):
    if fmt == "csv":
        yield from _csv_rows(content, error, messages)
    else:
        yield from _xlsx_rows(content, state, error, messages)


def _csv_rows(content, error, messages):
    reader = None
    try:
        reader = csv.reader(StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        while True:
            number = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                return
            # Python 3.8's CSV reader rejects NUL; newer host Pythons accept it.
            # Keep identical file admission on the host and the Win7 runtime.
            if any("\x00" in value for value in row):
                raise csv.Error("line contains NUL")
            yield number, row, {}
    except UnicodeDecodeError as exc:
        raise error(messages.csv_encoding) from exc
    except csv.Error as exc:
        raise error(messages.csv_format, reader.line_num if reader is not None else 1) from exc


def _check_xlsx_package(content, error):
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len({item.filename for item in entries}) != len(entries):
            raise error("这个 XLSX 内部有重复内容，认不出原始数据。请用 Excel 另存一份后重新上传。")
        if sum(item.file_size for item in entries) > XLSX_EXPANDED_BYTE_LIMIT:
            raise error("XLSX 展开后超过 64 MB 上限。请拆分文件后重新上传。")
        if any(item.flag_bits & 1 for item in entries):
            raise error("加了密码的 XLSX 读不了。请去掉密码后重新上传。")
        if archive.testzip() is not None:
            raise error("这个 XLSX 的完整性检查没通过，文件可能已损坏。请用 Excel 另存一份后重新上传。")
        types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
        workbooks = [
            item.attrib.get("ContentType", "")
            for item in types
            if "spreadsheetml" in item.attrib.get("ContentType", "")
            and "main+xml" in item.attrib.get("ContentType", "")
            or "macroEnabled.main+xml" in item.attrib.get("ContentType", "")
        ]
        if workbooks != [_WORKBOOK_TYPE]:
            raise error("这个文件不是标准 XLSX 工作簿，只改扩展名或带宏的模板都不行。请用 Excel 另存为 xlsx 后重新上传。")
        for item in types:
            if item.attrib.get("ContentType", "").endswith("spreadsheetml.worksheet+xml"):
                with archive.open(item.attrib["PartName"].lstrip("/")) as stream:
                    check_sheet_order(stream, error=error)


def _xlsx_rows(content, state, error, messages):
    import openpyxl

    wb: Any = None
    try:
        _check_xlsx_package(content, error)
        wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        if not wb.worksheets:
            raise error(messages.xlsx_empty)
        # Templates include an instruction sheet; import only their data sheet.
        state["sheets"] = len(wb.worksheets)
        ws = wb.worksheets[0]
        ws.reset_dimensions()
        for number, cells in enumerate(ws.iter_rows(), 1):
            errors = {index: messages.xlsx_cell for index, cell in enumerate(cells) if is_formula_or_error(cell)}
            yield number, [cell_value(cell) for cell in cells], errors
    except ValidationError:
        raise
    except Exception as exc:
        raise error(messages.xlsx_read) from exc
    finally:
        if wb is not None:
            wb.close()
