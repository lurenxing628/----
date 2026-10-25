"""现行导出文字防止公式注入。"""

from core.services.common.excel_templates import sanitize_export_cell


def test_export_cells_escape_formula_like_strings() -> None:
    """导出到 Excel 的文字里，四个会被当公式起头的字符必须先加单引号。

    原来这条挂在 build_xlsx_bytes 上，那个构建器 2026-09-21 随旧模板清单一起退役了；
    防注入本身没退役——排产实际导出、校准导出、报表导出、报表 xlsx 四处生产代码都
    直接用 sanitize_export_cell，所以契约改挂在它身上。
    """
    assert sanitize_export_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_export_cell("+SUM(1,1)") == "'+SUM(1,1)"
    assert sanitize_export_cell("-1") == "'-1"
    assert sanitize_export_cell("@A1") == "'@A1"
    assert sanitize_export_cell("正常文字") == "正常文字"
    assert sanitize_export_cell(123) == 123
    # 控制字符会让 openpyxl 写出打不开的文件，一并剔掉；制表和换行保留。
    assert sanitize_export_cell("甲\x00乙\x07") == "甲乙"
    assert sanitize_export_cell("甲\t乙\n丙") == "甲\t乙\n丙"
