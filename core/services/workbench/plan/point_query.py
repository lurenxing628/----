"""Workbench-only plan spans; legacy SQL keeps its positive-interval default."""

from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.schedule_rows import ScheduleTimeSpanRow
from data.repositories.schedule_time_sql import parse_dt_for_sql
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository

from .point_evidence import annotate_plan_points


def _interval(row):
    start, end = (parse_dt_for_sql(row[key]) for key in ("start_time", "end_time"))
    if start is None or end is None or start > end:
        raise ValueError("Invalid lossless plan interval")
    return start, end


class PointPlanCatalogRepository(WorkbenchPlanCatalogRepository):
    def __init__(self, conn, logger=None, *, context=None):
        super().__init__(conn, logger=logger)
        self.context = context
        self._source_rows = {}
        self._prepared_rows = {}
        self._parsed_intervals = {}

    def source_rows(self, version):
        if version not in self._source_rows:
            self._source_rows[version] = self.list_plan_storage_rows(version=version)
        return self._source_rows[version]

    def prepared_rows(self, version):
        if version not in self._prepared_rows:
            raw = self.source_rows(version)
            fields = ("id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status", "version")
            rows = [{name: row[name] for name in fields} for row in raw]
            intervals = [_interval(row) for row in rows]
            try:
                if self.context is None:
                    rows = annotate_plan_points(self.conn, rows, intervals=intervals)
                else:
                    rows = annotate_plan_points(self.conn, rows, context=self.context, intervals=intervals)
            except WorkbenchCommandRejected as exc:
                if exc.status == 413:
                    raise
                raise ValueError(str(exc)) from exc
            self._parsed_intervals[version] = intervals
            self._prepared_rows[version] = rows
        return self._prepared_rows[version]

    def parsed_intervals(self, version):
        self.prepared_rows(version)
        return self._parsed_intervals[version]

    def validate_detail_times(self, resolution):
        self.prepared_rows(resolution.version)

    def get_first_plan_identity_row(self, *, version):
        rows = self.source_rows(version)
        return {"source_row_id": rows[0]["id"], "lock_status": rows[0]["lock_status"]} if rows else None

    def get_plan_time_span(self, *, version):
        if version not in self._spans:
            rows = self.prepared_rows(version)
            intervals = self._parsed_intervals[version]
            if not rows:
                self._spans[version] = None
            else:
                end = max(high for _, high in intervals)
                span: ScheduleTimeSpanRow = {"version": version, "start_time": min(low for low, _ in intervals),
                        "end_time": end, "end_includes_point": any(row.get("_point_work") and high == end
                            for row, (_, high) in zip(rows, intervals))}
                self._spans[version] = span
        return self._spans[version]


class PlanMetadataRepository(WorkbenchPlanCatalogRepository):
    """Validate and aggregate plan metadata without admitting its full details."""

    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        self._metadata_spans = {}

    def get_first_plan_identity_row(self, *, version):
        return self.first_raw_plan_identity_row(version=version)

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
            self._metadata_spans[version] = None if low is None else {
                "version": version, "start_time": low, "end_time": high,
                "end_includes_point": any(end == high for _, end in point_intervals),
            }
        return self._metadata_spans[version]

    def validate_detail_times(self, resolution):
        self.get_plan_time_span(version=resolution.version)
