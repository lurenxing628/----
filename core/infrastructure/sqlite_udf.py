"""每个产品 SQLite 连接共用的配置：最低库版本、JSON1 能力、DATE 转换器、打开后配置与确定性 SQL 函数。

打开方式（读写文件、只读归档、内存库）由各连接工厂自己决定；打开之后的配置只走 `configure_connection`。
"""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import Any, Iterator, Optional, Tuple

from core.models.content import StoredJsonCorrupt, read_stored_json
from core.models.workbench_preflight import SCHEDULING_PREFERENCES_ACTION
from core.shared.stored_dates import stored_day
from core.shared.text_keys import text_key

# 门槛取发布运行时（Python 3.8.10）的 3.35.5，产品 SQL 只按这个版本的语法写（如 NULLS LAST、UPSERT）。
# 库版本是进程常量，导入时断言一次，不在每个连接上重查；断言不开连接、不碰磁盘，停机等不触库的入口照常可用。
_MINIMUM_SQLITE_VERSION = (3, 35, 5)
if sqlite3.sqlite_version_info < _MINIMUM_SQLITE_VERSION:
    raise RuntimeError(
        f"当前 SQLite 版本 {sqlite3.sqlite_version} 低于本程序要求的 3.35.5，请使用随程序发布的运行环境启动。"
    )

# JSON1 是 SQLite 的编译选项，版本达标不代表可用：仓储用 json_each 展开编号集合，历史触发器用 json_extract / json_set。
_JSON1_PROBE_SQL = (
    "SELECT (SELECT value FROM json_each('[7]')), "
    "json_extract('{\"a\":2}', '$.a'), "
    "json_set('{}', '$.k', 3)"
)
_JSON1_PROBE_ROW = (7, 2, '{"k":3}')


@lru_cache(maxsize=1)
def ensure_sqlite_runtime() -> None:
    """在内存库上实跑产品依赖的三个 JSON1 函数；缺函数或结果不符时抛 RuntimeError。

    产品连接边界在本进程首次触库前、构建预检在冻结前都走这一个探针：成功结果缓存，失败不缓存、下次照样拒绝。
    只管 JSON1 能力：最低版本门槛由本模块导入时的断言独占，调用方导入本模块即已通过。
    """
    try:
        with closing(sqlite3.connect(":memory:")) as conn:
            row = conn.execute(_JSON1_PROBE_SQL).fetchone()
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"当前 SQLite（{sqlite3.sqlite_version}）缺少本程序必需的 JSON1 函数支持（{exc}），请使用随程序发布的运行环境启动。"
        ) from exc
    if row != _JSON1_PROBE_ROW:
        raise RuntimeError(f"当前 SQLite（{sqlite3.sqlite_version}）JSON1 能力探针返回异常结果：{row!r}。")


DETECT_TYPES = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES


def _convert_stored_date(value: bytes):
    """DATE 列只把规范的 `YYYY-MM-DD` 转成日期；其余写法原样返回文本或原始字节。

    默认转换器遇到 `2026/10/01`、`2026-02-30` 这类旧值会在取数时直接抛 ValueError，
    读取端写好的"日期无效"提示就到不了用户面前，只剩一个 500。`2026-9-9` 这类不补零写法
    和非法 UTF-8 字节也原样保留：排产准入和交付读取按同一口径把它判为日期无效，不会一边排上、一边报无效。
    """
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError:
        return value
    day = stored_day(text)
    return text if day is None else day


sqlite3.register_converter("DATE", _convert_stored_date)

SQL_CASEFOLD_FUNCTION = "aps_casefold"
SQL_TEXT_SORT_KEY_FUNCTION = "aps_text_sort_key"
NON_INPUT_RECEIPT_ACTIONS = (SCHEDULING_PREFERENCES_ACTION, "scheduling.run")
NON_INPUT_RECEIPT_PREFIXES = ("trial.", "dashboard.")
_REMEMBERED_RECEIPT_OUTCOME: ContextVar[Optional[Tuple[str, str]]] = ContextVar(
    "aps_remembered_receipt_outcome", default=None
)


@contextmanager
def remember_receipt_outcome(outcome_json: str, result: str) -> Iterator[None]:
    token = _REMEMBERED_RECEIPT_OUTCOME.set((outcome_json, result))
    try:
        yield
    finally:
        _REMEMBERED_RECEIPT_OUTCOME.reset(token)


def receipt_revision_category(action: Any, outcome_json: Any) -> str:
    if type(action) is str:
        if action in NON_INPUT_RECEIPT_ACTIONS or (
            action != "trial.scenario.adopt" and action.startswith(NON_INPUT_RECEIPT_PREFIXES)
        ):
            return ""
    if type(outcome_json) is str:
        remembered = _REMEMBERED_RECEIPT_OUTCOME.get()
        if remembered is not None and remembered[0] == outcome_json:
            result = remembered[1]
        else:
            # 修订分类在触发器里执行：回执结果读不出来时不能当作“未变化”，按生产输入计（保守多升修订号）。
            try:
                outcome = read_stored_json(outcome_json, dict)
            except StoredJsonCorrupt:
                outcome = None
            result = None if outcome is None else outcome.get("result")
        if result == "unchanged":
            return ""
    if action == "trial.scenario.adopt":
        return "trial_adoption"
    return "production_input"


def casefold_for_sql(value: Any) -> Optional[str]:
    return value.casefold() if type(value) is str else None


def text_sort_key_for_sql(value: Any) -> Optional[str]:
    """``aps_text_sort_key``：与表格文本格同一个 ``text_key``；排序用的都是文本列，SQL NULL 仍是 NULL。"""
    return None if value is None else text_key(value)


def configure_connection(conn: sqlite3.Connection) -> None:
    """刚打开的连接按产品口径配置：行映射、外键约束和 SQL 函数（修订触发器要调用 aps_receipt_revision_category）。"""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for name, count, function in (
        (SQL_CASEFOLD_FUNCTION, 1, casefold_for_sql),
        (SQL_TEXT_SORT_KEY_FUNCTION, 1, text_sort_key_for_sql),
        ("aps_receipt_revision_category", 2, receipt_revision_category),
    ):
        conn.create_function(name, count, function, deterministic=True)


__all__ = [
    "DETECT_TYPES",
    "NON_INPUT_RECEIPT_ACTIONS",
    "NON_INPUT_RECEIPT_PREFIXES",
    "SQL_CASEFOLD_FUNCTION",
    "SQL_TEXT_SORT_KEY_FUNCTION",
    "casefold_for_sql",
    "configure_connection",
    "ensure_sqlite_runtime",
    "receipt_revision_category",
    "remember_receipt_outcome",
    "text_sort_key_for_sql",
]
