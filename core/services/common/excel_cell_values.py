"""openpyxl 单元格到业务值的翻译，七个文件读取器共用。

原来每个家族各写一份"这个格子能不能用、值是多少"：公式与错误值的判定重复了七次，
而 Excel 的**数字格式**一次也没处理。后果是效率列被悄悄缩小 100 倍——用户把格子设成
百分比格式填 90%，Excel 存的是 0.9，读取层当成"效率 0.9%"写进库；0.9 又正好落在
0–200 的值域里，所以连报错都不会有。

取值口径：**用户在 Excel 里看到几，系统就读到几**。这与 read_date 接受原生日期格子
是同一条原则——尊重 Excel 的格式语义，而不是猜格子背后的存储值。误设百分比格式的情况
还原后基本都会撞上各列自己的值域上限（填 100 显示 10000%，还原成 10000 超过 200 被拒），
仍然 fail loud。

这里只做翻译，不产出面向用户的文案：各家族的措辞留在它们自己的 codec 里，那些目录在
tools/scan_ui_copy.py 的扫描范围内，core/services/common 不在。
"""

from __future__ import annotations

import re
from typing import Any

#: openpyxl 的 data_type：f = 公式，e = 错误值。两者都不是用户想导入的实际值。
_FORMULA_AND_ERROR_TYPES = ("f", "e")

#: 数字格式里被引号包起来的部分是字面量文本，`\x` 是转义字符，都不表示百分比。
#: 例如 `0.00"%"` 显示一个百分号但并不把数值放大 100 倍。
_QUOTED_LITERAL = re.compile(r'"[^"]*"')
_ESCAPED_CHAR = re.compile(r"\\.")

#: 乘 100 会引入二进制浮点噪声（0.07 * 100 = 7.000000000000001），
#: 按 10 位小数收一下；业务上没有哪一列需要比这更细的精度。
_PERCENT_DECIMALS = 10


def is_formula_or_error(cell: Any) -> bool:
    """这个格子装的是公式或 Excel 错误值，取不到实际值。"""
    return cell.data_type in _FORMULA_AND_ERROR_TYPES


def is_percent_format(number_format: Any) -> bool:
    if not number_format:
        return False
    text = _ESCAPED_CHAR.sub("", _QUOTED_LITERAL.sub("", str(number_format)))
    return "%" in text


def cell_value(cell: Any) -> Any:
    """取格子的值，百分比格式的数字还原成用户看到的那个数。

    bool 不走还原：Python 里 type(True) is bool 而不是 int，这里的 type 判断
    天然把它挡在外面，交给各家族自己去拒绝。
    """
    value = cell.value
    if type(value) in (int, float) and is_percent_format(cell.number_format):
        return round(value * 100, _PERCENT_DECIMALS)
    return value
