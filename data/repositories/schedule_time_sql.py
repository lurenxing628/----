from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional

_SQL_PARSE_FUNCTION = "aps_parse_dt"


def _time_column(alias: Optional[str], name: str) -> str:
    return f"{alias}.{name}" if alias else name


def _time_text(alias: Optional[str], name: str) -> str:
    return f"TRIM(CAST({_time_column(alias, name)} AS TEXT))"


def time_dt(alias: Optional[str], name: str) -> str:
    # 使用注册到 SQLite 连接上的 Python 解析函数，避免 SQLite datetime()
    # 对不存在日期、24 点、毫秒等值过于宽松，和上层 Python 解析口径漂移。
    return f"{_SQL_PARSE_FUNCTION}({_time_text(alias, name)})"


def parse_dt_for_sql(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return None


def require_dt_for_sql(value: Any, error_message: str) -> str:
    parsed = parse_dt_for_sql(value)
    if parsed is None:
        raise ValueError(error_message)
    return parsed


def register_schedule_time_sql_functions(conn: sqlite3.Connection) -> None:
    # 只有真实 sqlite 连接支持自定义函数。测试里大量使用只答 pragma 的占位/替身连接
    # （_DummyConn 等），它们既不支持 create_function、也不会执行真正的 aps_parse_dt SQL，
    # 故直接跳过注册。生产连接全部来自 get_connection()（真 sqlite3.Connection，必有
    # create_function），此守卫在生产路径恒为真、绝不静默跳过真实注册。
    register = getattr(conn, "create_function", None)
    if not callable(register):
        return
    try:
        register(_SQL_PARSE_FUNCTION, 1, parse_dt_for_sql, deterministic=True)
    except sqlite3.NotSupportedError:
        register(_SQL_PARSE_FUNCTION, 1, parse_dt_for_sql)


def valid_time_range_sql(alias: Optional[str]) -> str:
    start_text = _time_text(alias, "start_time")
    end_text = _time_text(alias, "end_time")
    start_dt = time_dt(alias, "start_time")
    end_dt = time_dt(alias, "end_time")
    return (
        f"{start_text} <> '' "
        f"AND {end_text} <> '' "
        f"AND {start_dt} IS NOT NULL "
        f"AND {end_dt} IS NOT NULL "
        f"AND {end_dt} > {start_dt}"
    )


def overlap_or_bad_time_sql(alias: Optional[str]) -> str:
    """区间与绑定参数 [?, ?]（顺序：end_param, start_param）重叠，或本身是坏时间行。

    用于"既捞回与查询窗重叠的有效区间、也把坏时间行兜回上层做降级提示"的查询，
    让 schedule 计划明细与设备停机明细对"坏时间/重叠"的判定来自同一处定义，避免漂移。
    """
    valid = valid_time_range_sql(alias)
    start_dt = time_dt(alias, "start_time")
    end_dt = time_dt(alias, "end_time")
    return (
        "(\n"
        f"    ({valid} AND {start_dt} < {_SQL_PARSE_FUNCTION}(?) AND {end_dt} > {_SQL_PARSE_FUNCTION}(?))\n"
        f"    OR NOT ({valid})\n"
        ")"
    )


DETAIL_OVERLAP_OR_BAD_TIME_SQL = overlap_or_bad_time_sql("s")


__all__ = [
    "DETAIL_OVERLAP_OR_BAD_TIME_SQL",
    "overlap_or_bad_time_sql",
    "parse_dt_for_sql",
    "require_dt_for_sql",
    "register_schedule_time_sql_functions",
    "time_dt",
    "valid_time_range_sql",
]
