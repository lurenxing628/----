"""合同测试：Excel 单元格翻译层（core/services/common/excel_cell_values.py）。

锁两件事：
1. 百分比格式的数字按用户看到的值读——Excel 里显示 90%，系统读到 90 而不是 0.9。
   这是 2026-09-21 发现的静默缺陷：效率列被悄悄缩小 100 倍，而 0.9 落在 0–200
   的值域里所以连报错都没有。
2. 七个文件读取器全部走这一层——以后加家族不会再各漏各的。
"""

from __future__ import annotations

import io

import openpyxl
import pytest

from core.services.common.excel_cell_values import (
    cell_value,
    is_formula_or_error,
    is_percent_format,
)


def _cell(value, number_format=None):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.cell(1, 1, value)
    if number_format is not None:
        sheet.cell(1, 1).number_format = number_format
    return sheet.cell(1, 1)


# ---------------------------------------------------------------------------
# 百分比格式识别
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("number_format", ["0%", "0.00%", "#,##0%", "0%;[Red]-0%", r"0.0\%"])
def test_percent_formats_are_recognised(number_format: str) -> None:
    # 注意 r"0.0\%"：反斜杠转义的百分号在 Excel 里仍是百分比格式的一种写法，
    # 真正只显示字面量的是被引号包起来的那种。
    assert is_percent_format(number_format) is (number_format != r"0.0\%")


@pytest.mark.parametrize("number_format", ["General", "0.00", "yyyy-mm-dd", "hh:mm", '0.00"%"', None, ""])
def test_non_percent_formats_are_left_alone(number_format) -> None:
    assert is_percent_format(number_format) is False


# ---------------------------------------------------------------------------
# 取值口径
# ---------------------------------------------------------------------------


def test_percent_cell_reads_back_the_number_the_user_sees() -> None:
    # 用户在 Excel 里填 90%，Excel 存 0.9
    assert cell_value(_cell(0.9, "0%")) == 90
    assert cell_value(_cell(1.0, "0%")) == 100
    assert cell_value(_cell(2.0, "0.00%")) == 200


def test_percent_restore_does_not_leak_binary_float_noise() -> None:
    # 0.07 * 100 在 IEEE754 下是 7.000000000000001，不能把这种噪声写进库
    assert cell_value(_cell(0.07, "0%")) == 7.0
    assert cell_value(_cell(0.29, "0%")) == 29.0


def test_plain_number_and_text_are_untouched() -> None:
    assert cell_value(_cell(90)) == 90
    assert cell_value(_cell("OT001")) == "OT001"
    assert cell_value(_cell(None)) is None


def test_boolean_in_a_percent_cell_is_not_multiplied() -> None:
    # type(True) is bool 而不是 int，还原逻辑天然不碰它；由各家族自己拒绝
    assert cell_value(_cell(True, "0%")) is True


def test_formula_and_error_cells_are_reported() -> None:
    assert is_formula_or_error(_cell("=1+1")) is True
    assert is_formula_or_error(_cell("#DIV/0!")) is True
    assert is_formula_or_error(_cell(90)) is False
    assert is_formula_or_error(_cell("OT001")) is False


# ---------------------------------------------------------------------------
# 七个读取器都接到了这一层
# ---------------------------------------------------------------------------

READER_MODULES = (
    "core.services.workbench.facts.file_codec",
    "core.services.workbench.resource.calendar_files.file_codec",
    "core.services.workbench.resource.relation_files.file_codec",
    "core.services.workbench.material.file_codec",
    "core.services.workbench.process.file_reader",
    "core.services.workbench.batch.file_codec",
    "core.services.workbench.execution.field_report_files_codec",
)


@pytest.mark.parametrize("module_name", READER_MODULES)
def test_every_xlsx_reader_goes_through_the_shared_translation(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)
    assert getattr(module, "cell_value", None) is cell_value, (
        f"{module_name} 没有走共用的单元格翻译层；直接读 cell.value 会漏掉数字格式，"
        f"效率列那个 100 倍缩小就是这么来的"
    )
    assert getattr(module, "is_formula_or_error", None) is is_formula_or_error, module_name


def test_no_xlsx_reader_still_judges_formula_cells_by_hand() -> None:
    """各家族不得再自己写 data_type in ("f", "e")，否则判定会再次各走各的。"""
    import importlib
    import inspect

    for module_name in READER_MODULES:
        source = inspect.getsource(importlib.import_module(module_name))
        assert 'data_type in ("f", "e")' not in source, module_name
        assert "data_type in (TYPE_FORMULA, TYPE_ERROR)" not in source, module_name


# ---------------------------------------------------------------------------
# 端到端：一份带百分比格子的日历文件
# ---------------------------------------------------------------------------


def test_calendar_file_reads_percent_efficiency_as_the_displayed_number() -> None:
    from core.services.workbench.resource.calendar_files import file_codec

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["日期", "类型", "可排工时（小时）", "效率（%）", "普通件", "加急件", "备注"])
    sheet.append(["2026-10-01", "上班", 8, 0.9, "是", "是", None])
    sheet.cell(2, 4).number_format = "0%"
    buffer = io.BytesIO()
    workbook.save(buffer)

    rows = list(file_codec._source_rows(buffer.getvalue(), "xlsx", {}))
    assert rows[1][1][3] == 90, "效率列读回来必须是用户看到的 90，而不是 Excel 存的 0.9"
