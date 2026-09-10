"""Bounded CSV/XLSX byte sources, including all physical records and cells."""

import csv
from io import BytesIO, StringIO
from xml.etree import ElementTree
from zipfile import ZipFile

import openpyxl

from core.errors import ValidationError
from core.models.workbench_process_file import IMPORT_BYTE_LIMIT, XLSX_EXPANDED_BYTE_LIMIT, file_error
from core.services.workbench.process_file_xml import check_sheet_order

_WORKBOOK_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


def check_bytes(content, file_format):
    if type(content) is not bytes:
        raise file_error("必须提供 CSV/XLSX 原始文件字节。")
    if len(content) > IMPORT_BYTE_LIMIT:
        raise file_error("文件超过 16 MiB 大小上限，未读取或截断前半部分。")
    if file_format == "xlsx":
        _check_package(content)


def _check_package(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len({item.filename for item in entries}) != len(entries):
                raise file_error("XLSX 压缩包含重复文件项，无法确定原始内容。")
            if sum(item.file_size for item in entries) > XLSX_EXPANDED_BYTE_LIMIT:
                raise file_error("XLSX 解压后超过 64 MiB 上限，未读取或截断数据。")
            if any(item.flag_bits & 1 for item in entries):
                raise file_error("不接受加密 XLSX，请提供可读取的原始数据文件。")
            if archive.testzip() is not None:
                raise file_error("XLSX 压缩包完整性检查失败。")
            _check_workbook_content(archive)
    except ValidationError:
        raise
    except Exception as exc:
        raise file_error("XLSX 压缩包读取失败，请核对文件字节。") from exc


def _check_workbook_content(archive):
    types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
    workbooks = [item.attrib.get("ContentType", "") for item in types
                 if "spreadsheetml" in item.attrib.get("ContentType", "") and "main+xml" in item.attrib.get("ContentType", "")
                 or "macroEnabled.main+xml" in item.attrib.get("ContentType", "")]
    if workbooks != [_WORKBOOK_TYPE]:
        raise file_error("文件内容不是标准 XLSX 工作簿，不能仅改扩展名或导入宏模板。")
    for item in types:
        if item.attrib.get("ContentType", "").endswith("spreadsheetml.worksheet+xml"):
            with archive.open(item.attrib["PartName"].lstrip("/")) as stream:
                check_sheet_order(stream)


def csv_rows(content):
    reader = None
    try:
        reader = csv.reader(StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        while True:
            number = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                return
            yield number, values, {}
    except (UnicodeDecodeError, csv.Error) as exc:
        raise file_error("CSV 必须为有效 UTF-8，不能猜编码或修补引号。", reader.line_num if reader else 1) from exc


def xlsx_rows(content):
    wb = None
    try:
        wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        if len(wb.sheetnames) != 1 or len(wb.worksheets) != 1:
            raise file_error("文件必须只有一张数据工作表，不能忽略其他表。")
        ws = wb.worksheets[0]
        ws.reset_dimensions()
        for number, cells in enumerate(ws.iter_rows(), 1):
            errors = {index: "不接受公式或 Excel 错误单元格，请填写实际值。"
                      for index, cell in enumerate(cells) if cell.data_type in ("f", "e")}
            yield number, [cell.value for cell in cells], errors
    except ValidationError:
        raise
    except Exception as exc:
        raise file_error("XLSX 读取失败，请核对文件字节和单元格格式。") from exc
    finally:
        if wb is not None:
            wb.close()
