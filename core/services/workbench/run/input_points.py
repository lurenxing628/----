"""Freeze only evidenced points; supplement the legacy overlap query's left edge."""

from data.repositories.workbench_run_input_repo import WorkbenchRunInputRepository


def read_point_freeze_rows(svc, *, version, op_ids, start_time, end_time):
    rows = svc.schedule_repo.list_version_rows_by_op_ids_start_range(
        version=version, op_ids=op_ids, start_time=start_time, end_time=end_time)
    # The legacy query already returns interior points, but excludes end == low.
    # Do not deduplicate: repeated operation rows must fail at the seed boundary.
    rows.extend(WorkbenchRunInputRepository(svc.conn).point_rows_at(version=version, op_ids=op_ids, start_time=start_time))
    return rows
