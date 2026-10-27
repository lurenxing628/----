"""Preserve physical row/cell boundaries before openpyxl normalizes the sheet."""

import posixpath
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import NoReturn
from xml.etree import ElementTree
from zipfile import ZipFile

from core.models.workbench_command import WorkbenchCommandRejected

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PKG_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def invalid(message: str) -> NoReturn:
    raise WorkbenchCommandRejected('invalid_input', message, 422)


def _sheet(archive, names):
    book = ElementTree.fromstring(archive.read('xl/workbook.xml'))
    sheets_nodes = [
        node for node in book
        if node.tag == NS + 'sheets' or node.tag.endswith('}sheets') or node.tag == 'sheets'
    ]
    if book.tag != NS + 'workbook' or len(sheets_nodes) != 1 or sheets_nodes[0].tag != NS + 'sheets' or not len(sheets_nodes[0]):
        invalid('工作簿缺少首张工作表。')
    sheets = sheets_nodes[0]
    if any(child.tag != NS + 'sheet' for child in sheets):
        invalid('第一张工作表损坏，请重新保存文件后导入。')
    target_id = sheets[0].get(REL + 'id')
    if not target_id:
        invalid('第一张工作表损坏，请重新保存文件后导入。')
    relationships = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    if relationships.tag != PKG_REL + 'Relationships' or any(node.tag != PKG_REL + 'Relationship' for node in relationships):
        invalid('第一张工作表损坏，请重新保存文件后导入。')
    links = [node for node in relationships if node.get('Id') == target_id]
    if (
        len(links) != 1
        or links[0].get('TargetMode') == 'External'
        or links[0].get('Type') != 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet'
    ):
        invalid('第一张工作表损坏，请重新保存文件后导入。')
    target = links[0].get('Target', '')
    sheet_path = target[1:] if target.startswith('/') else posixpath.normpath(posixpath.join('xl', target))
    if not target or sheet_path != posixpath.normpath(sheet_path) or sheet_path.startswith('/') or sheet_path not in names:
        invalid('第一张工作表损坏，请重新保存文件后导入。')
    return sheet_path


def check_package(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {item.filename for item in entries}
            if len(entries) != len(names) or any(item.flag_bits & 1 for item in entries):
                invalid('不接受加密或含重复文件项的工作簿。')
            if sum(item.file_size for item in entries) > 64 * 1024 * 1024:
                invalid('工作簿解压后超过读取上限。')
            types = ElementTree.fromstring(archive.read('[Content_Types].xml'))
            workbook_parts = [
                node for node in types
                if 'spreadsheetml' in node.get('ContentType', '') and 'main+xml' in node.get('ContentType', '')
                or 'macroEnabled.main+xml' in node.get('ContentType', '')
            ]
            if (
                len(workbook_parts) != 1
                or not workbook_parts[0].tag.endswith('Override')
                or workbook_parts[0].get('ContentType') != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'
                or workbook_parts[0].get('PartName') != '/xl/workbook.xml'
            ):
                invalid('这不是标准的 XLSX 文件，只把扩展名改成 .xlsx 不行。')
            for name in sorted(names):
                if name.endswith(('.xml', '.rels')):
                    with archive.open(name) as xml_stream:
                        for _event, node in ElementTree.iterparse(xml_stream, events=('end',)):
                            node.clear()
            with archive.open(_sheet(archive, names)) as stream:
                return _rows(stream)
    except WorkbenchCommandRejected:
        raise
    except Exception as exc:
        raise WorkbenchCommandRejected('invalid_input', '这个 XLSX 的内部结构不对，系统没有跳过文件内容。请重新下载模板再填。', 422) from exc


def _rows(stream):
    previous = 0
    raw_numbers = {}
    for _event, node in ElementTree.iterparse(stream, events=('end',)):
        if node.tag == NS + 'mergeCell':
            invalid('第一张报工记录表里不能有合并单元格。')
        if node.tag != NS + 'row':
            continue
        number = int(node.get('r', '0'))
        if not previous < number <= 5001:
            invalid('最多允许 5000 行，且原始行号不能重复或倒序。')
        previous, column = number, ''
        for cell in node:
            if cell.tag != NS + 'c':
                invalid('文件存在超出 13 列、重复或错位的单元格，请按模板修正。')
            match = re.fullmatch(r'([A-M])([1-9][0-9]*)', cell.get('r', ''))
            if match is None or int(match[2]) != number or match[1] <= column:
                invalid('文件存在超出 13 列、重复或错位的单元格，请按模板修正。')
            column = match[1]
            if cell.find(NS + 'f') is None and cell.get('t', 'n') in ('', 'n'):
                v_node = cell.find(NS + 'v')
                if v_node is not None:
                    raw_text = (v_node.text or '').strip()
                    try:
                        parsed_decimal = Decimal(raw_text)
                    except InvalidOperation:
                        invalid('这个 XLSX 文件里的数字格损坏，请重新保存文件后导入。')
                    if not parsed_decimal.is_finite():
                        invalid('这个 XLSX 文件里的数字格损坏，请重新保存文件后导入。')
                    raw_numbers[(number, ord(match[1]) - ord('A'))] = parsed_decimal
        node.clear()
    return raw_numbers
