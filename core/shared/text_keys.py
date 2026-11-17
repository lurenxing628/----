"""文本的比较与排序键，只此一份。"""

import unicodedata


def text_key(value: str) -> str:
    """NFC 规范化后，连续空白（含全角空格、制表符）收成一个空格并去掉首尾空白。

    表格文本格（筛选身份、显示、内存排序）与 SQL 函数 ``aps_text_sort_key`` 都调它，
    所以普通分页（SQL）与列筛选（格子索引）对同一段文字给出同一个键、同一个顺序。
    """
    return " ".join(unicodedata.normalize("NFC", value).split())
