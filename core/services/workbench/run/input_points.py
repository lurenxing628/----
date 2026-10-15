"""Freeze only evidenced points; supplement the legacy overlap query's left edge."""

from core.shared.local_datetime import parse_local_datetime as parse_dt


def read_point_freeze_rows(svc, *, version, op_ids, start_time, end_time, facts):
    low, high = parse_dt(start_time), parse_dt(end_time)
    if low is None or high is None:
        raise ValueError("冻结窗口查询时间写法不对，无法读取旧排程种子")
    ids = set(op_ids)
    result = []
    for row in facts.capture.business_table("Schedule"):
        if row["version"] != version or row["op_id"] not in ids:
            continue
        start, end = parse_dt(row["start_time"]), parse_dt(row["end_time"])
        if start is not None and end is not None and start < high and (end > low or start == end == low):
            result.append(row)
    return result
