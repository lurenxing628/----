"""Worksheet XML invariants that openpyxl otherwise normalizes or hides."""

import re
from shutil import copyfileobj
from tempfile import SpooledTemporaryFile
from xml.etree import ElementTree

from openpyxl.utils import column_index_from_string

from core.models.workbench_process_file import file_error

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_COORDINATE = re.compile(r"([A-Z]{1,3})([1-9][0-9]*)\Z")


def check_sheet_order(stream):
    """Reject duplicate/out-of-order physical records before read-only iteration."""
    previous, data = 0, None
    for event, node in ElementTree.iterparse(stream, events=("start", "end")):
        if event == "start" and node.tag == _NS + "sheetData":
            data = node
        if event != "end" or node.tag != _NS + "row":
            continue
        number = int(node.attrib.get("r", "0"))
        if not previous < number <= 1048576:
            raise file_error("这个 XLSX 的行号有重复、倒序或不合法。请用 Excel 另存一份后重新上传。", max(1, number))
        previous = number
        column = 0
        for cell in node:
            if cell.tag != _NS + "c":
                continue
            match = _COORDINATE.fullmatch(cell.attrib.get("r", ""))
            if match is None:
                raise file_error("这个 XLSX 有单元格缺少坐标，系统不猜它原来在哪。请用 Excel 另存一份后重新上传。", number)
            current = column_index_from_string(match[1])
            if int(match[2]) != number or not column < current <= 16384:
                raise file_error("这个 XLSX 有重复、倒序或错位的单元格。请用 Excel 另存一份后重新上传。", number)
            column = current
        node.clear()
        if data is not None:
            data.clear()


def preserve_carriage_returns(ws):
    """XML character references preserve CR; literal CR is normalized on read."""
    ws.close()
    changed = False
    with SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b") as escaped:
        with open(ws._writer.out, "rb") as source:
            for block in iter(lambda: source.read(64 * 1024), b""):
                changed = changed or b"\r" in block
                escaped.write(block.replace(b"\r", b"&#13;"))
        if changed:
            escaped.seek(0)
            with open(ws._writer.out, "wb") as target:
                copyfileobj(escaped, target)
