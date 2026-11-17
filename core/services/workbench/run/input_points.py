"""Freeze only evidenced points; supplement the legacy overlap query's left edge."""

from core.shared.local_datetime import datetime_to_us, row_interval


def read_point_freeze_rows(*, version, op_ids, start_time, end_time, facts):
    low, high = datetime_to_us(start_time), datetime_to_us(end_time)
    ids = set(op_ids)
    result = []
    for row in facts.capture.business_table("Schedule"):
        if row["version"] != version or row["op_id"] not in ids:
            continue
        start, end = row["start_us"], row["end_us"]
        if start < high and (end > low or start == end == low):
            result.append({**row, "_parsed_times": row_interval(row)})
    return result
