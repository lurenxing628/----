"""Freeze only evidenced points; supplement the legacy overlap query's left edge."""

from data.repositories.schedule_time_sql import time_dt


def read_point_freeze_rows(svc, *, version, op_ids, start_time, end_time):
    rows = svc.schedule_repo.list_version_rows_by_op_ids_start_range(
        version=version, op_ids=op_ids, start_time=start_time, end_time=end_time)
    # The legacy query already returns interior points, but excludes end == low.
    # Do not deduplicate: repeated operation rows must fail at the seed boundary.
    for offset in range(0, len(op_ids), 900):
        keys = op_ids[offset:offset + 900]
        marks = ",".join("?" for _ in keys)
        sql = ("SELECT op_id,machine_id,operator_id,start_time,end_time FROM Schedule "
               "WHERE version=? AND op_id IN (" + marks + ") AND "
               + time_dt(None, "start_time") + "=aps_parse_dt(?) AND "
               + time_dt(None, "end_time") + "=aps_parse_dt(?)")
        rows.extend(dict(row) for row in svc.conn.execute(sql, [version] + keys + [start_time, start_time]))
    return rows
