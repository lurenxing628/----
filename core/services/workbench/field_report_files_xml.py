"""Preserve physical row/cell boundaries before openpyxl normalizes the sheet."""

import posixpath
import re
from io import BytesIO
from typing import NoReturn
from xml.etree import ElementTree
from zipfile import ZipFile

from core.models.workbench_command import WorkbenchCommandRejected

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def invalid(message: str) -> NoReturn:
    raise WorkbenchCommandRejected('invalid_input', message, 422)


def _sheet(archive):
    book = ElementTree.fromstring(archive.read('xl/workbook.xml'))
    sheets = book.find(NS + 'sheets')
    if sheets is None or not len(sheets):
        invalid('工作簿缺少首张工作表。')
    target_id = sheets[0].get(REL + 'id')
    relationships = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    links = [node for node in relationships if node.get('Id') == target_id]
    if len(links) != 1 or links[0].get('TargetMode') == 'External' or not links[0].get('Type', '').endswith('/worksheet'):
        invalid('第一张工作表的链接坏了，系统不会改去读别的工作表。')
    target = links[0].get('Target', '')
    return posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl', target))


def check_package(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) != len({item.filename for item in entries}) or any(item.flag_bits & 1 for item in entries):
                invalid('不接受加密或含重复文件项的工作簿。')
            if sum(item.file_size for item in entries) > 64 * 1024 * 1024:
                invalid('工作簿解压后超过读取上限。')
            types = ElementTree.fromstring(archive.read('[Content_Types].xml'))
            if not any(node.get('ContentType') == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml' for node in types):
                invalid('这不是标准的 XLSX 文件，只把扩展名改成 .xlsx 不行。')
            with archive.open(_sheet(archive)) as stream:
                return _rows(stream)
    except WorkbenchCommandRejected:
        raise
    except Exception as exc:
        raise WorkbenchCommandRejected('invalid_input', '这个 XLSX 的内部结构不对，系统没有跳过文件内容。请重新下载模板再填。', 422) from exc


def _rows(stream):
    previous, columns = 0, 0
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
                continue
            match = re.fullmatch(r'([A-M])([1-9][0-9]*)', cell.get('r', ''))
            if match is None or int(match[2]) != number or match[1] <= column:
                invalid('有单元格超出 13 列、重复或错位，系统不会覆盖或忽略原来的值。')
            column = match[1]
            columns = max(columns, ord(column) - ord('A') + 1)
        node.clear()
    return columns
