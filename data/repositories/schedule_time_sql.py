from __future__ import annotations

from typing import Optional


def _time_column(alias: Optional[str], name: str) -> str:
    return f"{alias}.{name}" if alias else name


def _time_text(alias: Optional[str], name: str) -> str:
    return f"TRIM(CAST({_time_column(alias, name)} AS TEXT))"


def time_dt(alias: Optional[str], name: str) -> str:
    # 归一化与 core 层 parse_dt 对齐：/→-、T→空格、全角冒号→半角，
    # 避免 SQL 侧与 Python 侧对“坏时间”判定漂移（同一脏数据在不同报表上结论不一致）。
    text_expr = _time_text(alias, name)
    return f"datetime(REPLACE(REPLACE(REPLACE({text_expr}, '/', '-'), 'T', ' '), '：', ':'))"


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
        f"    ({valid} AND {start_dt} < datetime(?) AND {end_dt} > datetime(?))\n"
        f"    OR NOT ({valid})\n"
        ")"
    )


DETAIL_OVERLAP_OR_BAD_TIME_SQL = overlap_or_bad_time_sql("s")


__all__ = ["DETAIL_OVERLAP_OR_BAD_TIME_SQL", "overlap_or_bad_time_sql", "time_dt", "valid_time_range_sql"]
