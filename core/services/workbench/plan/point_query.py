"""Workbench-only plan spans; legacy SQL keeps its positive-interval default."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_intervals import instant
from core.shared.local_datetime import format_local_datetime
from data.repositories.schedule_rows import ScheduleTimeSpanRow
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository

from .point_evidence import annotate_plan_points


def _interval(row):
    try:
        start, end = instant(row["start_time"]), instant(row["end_time"])
    except ValueError as exc:
        raise ValueError("Invalid lossless plan interval") from exc
    if start > end:
        raise ValueError("Invalid lossless plan interval")
    return start, end


class PointPlanCatalogRepository(WorkbenchPlanCatalogRepository):
    def __init__(self, conn, logger=None, *, context):
        super().__init__(conn, logger=logger)
        self.context = context
        self._source_rows = {}
        self._prepared_rows = {}
        self._datetime_intervals, self._intervals = {}, {}

    def source_rows(self, version):
        if version not in self._source_rows:
            self._source_rows[version] = self.list_plan_storage_rows(version=version)
        return self._source_rows[version]

    def seed_source_rows(self, version, rows):
        """Adopt raw rows the caller's write capture already holds, before any read of this version."""
        self._source_rows[version] = rows

    def prepared_rows(self, version):
        if version not in self._prepared_rows:
            raw = self.source_rows(version)
            fields = ("id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status", "version")
            rows = [{name: row[name] for name in fields} for row in raw]
            intervals = [_interval(row) for row in rows]
            try:
                rows = annotate_plan_points(self.conn, rows, context=self.context, intervals=intervals)
            except WorkbenchCommandRejected as exc:
                if exc.status == 413:
                    raise
                raise ValueError(str(exc)) from exc
            self._datetime_intervals[version] = {row["id"]: interval for row, interval in zip(rows, intervals)}
            self._prepared_rows[version] = rows
        return self._prepared_rows[version]

    def datetime_intervals(self, version):
        self.prepared_rows(version)
        return self._datetime_intervals[version]

    def intervals(self, version):
        if version not in self._intervals:
            self._intervals[version] = {
                row_id: (low.isoformat(), high.isoformat())
                for row_id, (low, high) in self.datetime_intervals(version).items()
            }
        return self._intervals[version]

    def peek_intervals(self, version):
        """Reuse only a completed whole-source map; never load or prove a plan.

        Preparing a version re-enters adoption proof for that same version, so
        an in-progress or absent version returns None and keeps the caller's
        ordinary validation path.
        """
        return self.intervals(version) if version in self._prepared_rows else None

    def get_first_plan_identity_row(self, *, version):
        rows = self.source_rows(version)
        return {"source_row_id": rows[0]["id"]} if rows else None

    def get_plan_time_span(self, *, version):
        if version not in self._spans:
            rows = self.prepared_rows(version)
            intervals = self._datetime_intervals[version]
            if not rows:
                self._spans[version] = None
            else:
                end = max(high for _, high in intervals.values())
                span: ScheduleTimeSpanRow = {
                    "version": version,
                    "start_time": format_local_datetime(min(low for low, _ in intervals.values())),
                    "end_time": format_local_datetime(end),
                    "end_includes_point": any(
                        row.get("_point_work") and intervals[row["id"]][1] == end for row in rows
                    ),
                }
                self._spans[version] = span
        return self._spans[version]


class PlanMetadataRepository(WorkbenchPlanCatalogRepository):
    """Validate and aggregate plan metadata without admitting its full details."""

    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        self._metadata_spans = {}

    def get_plan_time_span(self, *, version):
        if version not in self._metadata_spans:
            low, high, points, point_intervals = None, None, [], []
            for row in self.iter_raw_plan_rows(version=version):
                start, end = _interval(row)
                low = start if low is None else min(low, start)
                high = end if high is None else max(high, end)
                if start == end:
                    points.append(row)
                    point_intervals.append((start, end))
            try:
                annotate_plan_points(self.conn, points, intervals=point_intervals)
            except WorkbenchCommandRejected as exc:
                if exc.status == 413:
                    raise
                raise ValueError(str(exc)) from exc
            self._metadata_spans[version] = None if low is None or high is None else {
                "version": version,
                "start_time": format_local_datetime(low),
                "end_time": format_local_datetime(high),
                "end_includes_point": any(end == high for _, end in point_intervals),
            }
        return self._metadata_spans[version]
