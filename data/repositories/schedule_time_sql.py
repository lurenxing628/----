from __future__ import annotations

from typing import Optional

from core.infrastructure.sqlite_udf import SQL_PARSE_FUNCTION


def _time_column(alias: Optional[str], name: str) -> str:
    return f"{alias}.{name}" if alias else name


def _time_text(alias: Optional[str], name: str) -> str:
    return f"TRIM(CAST({_time_column(alias, name)} AS TEXT))"


def time_dt(alias: Optional[str], name: str) -> str:
    # 使用注册到 SQLite 连接上的 Python 解析函数，避免 SQLite datetime()
    # 对不存在日期、24 点、超出微秒精度等值过于宽松，和上层 Python 解析口径漂移。
    return f"{SQL_PARSE_FUNCTION}({_time_text(alias, name)})"


def interval_summary_sql(alias=None, *, allow_points: bool = False):
    return (
        "aps_interval_summary("
        + _time_column(alias, "id")
        + ","
        + _time_text(alias, "start_time")
        + ","
        + _time_text(alias, "end_time")
        + ","
        + ("1" if allow_points else "0")
        + ")"
    )


def overlap_or_bad_time_sql(alias: Optional[str]) -> str:
    """区间与绑定参数 [?, ?]（顺序：end_param, start_param）重叠，或本身是坏时间行。

    用于"既捞回与查询窗重叠的有效区间、也把坏时间行兜回上层做降级提示"的查询，
    让 schedule 计划明细与设备停机明细对"坏时间/重叠"的判定来自同一处定义，避免漂移。
    """
    return "aps_interval_admitted(" + _time_text(alias, "start_time") + "," + _time_text(alias, "end_time") + ",?,?)"


DETAIL_OVERLAP_OR_BAD_TIME_SQL = overlap_or_bad_time_sql("s")


__all__ = [
    "DETAIL_OVERLAP_OR_BAD_TIME_SQL",
    "interval_summary_sql",
    "overlap_or_bad_time_sql",
    "time_dt",
]
