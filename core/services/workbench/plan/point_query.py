"""Workbench-only plan spans; legacy SQL keeps its positive-interval default."""

from core.models.schedule_plan_role import SOURCE_ADJUSTMENT_SCENARIO_ROWS, SOURCE_SCHEDULE
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

    @staticmethod
    def _source_key(version, source_table, candidate_id, scenario_id):
        return version, source_table, None if source_table == SOURCE_SCHEDULE else candidate_id, scenario_id

    def source_rows(self, version, source_table, candidate_id, scenario_id=None):
        key = self._source_key(version, source_table, candidate_id, scenario_id)
        if key not in self._source_rows:
            self._source_rows[key] = self.list_plan_storage_rows(
                version=version, source_table=source_table, candidate_id=candidate_id,
                scenario_id=scenario_id,
            )
        return self._source_rows[key]

    def prepared_rows(self, version, source_table, candidate_id, scenario_id=None):
        key = self._source_key(version, source_table, candidate_id, scenario_id)
        if key not in self._prepared_rows:
            raw = self.source_rows(version, source_table, candidate_id, scenario_id)
            fields = ("id", "op_id", "machine_id", "operator_id", "start_time", "end_time", "lock_status")
            rows = []
            for row in raw:
                prepared = {name: row[name] for name in fields}
                prepared["version"] = version if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS else row["version"]
                rows.append(prepared)
            intervals = [_interval(row) for row in rows]
            try:
                if self.context is None:
                    rows = annotate_plan_points(self.conn, rows, source_table=source_table, intervals=intervals)
                else:
                    rows = annotate_plan_points(self.conn, rows, source_table=source_table, context=self.context, intervals=intervals)
            except WorkbenchCommandRejected as exc:
                raise ValueError(str(exc)) from exc
            self._parsed_intervals[key] = intervals
            self._prepared_rows[key] = rows
        return self._prepared_rows[key]

    def _validated_rows(self, version, source_table, candidate_id, scenario_id=None):
        return self.prepared_rows(version, source_table, candidate_id, scenario_id)

    def parsed_intervals(self, version, source_table, candidate_id, scenario_id=None):
        self.prepared_rows(version, source_table, candidate_id, scenario_id)
        return self._parsed_intervals[self._source_key(version, source_table, candidate_id, scenario_id)]

    def validate_detail_times(self, resolution):
        self._validated_rows(resolution.version, resolution.source_table, resolution.candidate_id, resolution.scenario_id)

    def get_first_plan_identity_row(self, *, version, source_table, candidate_id, scenario_id=None):
        rows = self.source_rows(version, source_table, candidate_id, scenario_id)
        return {"source_row_id": rows[0]["id"], "lock_status": rows[0]["lock_status"]} if rows else None

    def has_candidate_rows(self, *, version, candidate_id):
        return bool(self.source_rows(version, "candidate_rows", candidate_id))

    def list_plan_role_options(self, version):
        if self.context is None:
            return super().list_plan_role_options(version)
        if version not in self._roles:
            self._roles[version] = self.context.references.read_role_options(version)
        return self._roles[version]

    def get_plan_time_span(self, *, version, source_table, candidate_id, scenario_id=None):
        key = self._source_key(version, source_table, candidate_id, scenario_id)
        if key not in self._spans:
            rows = self.prepared_rows(version, source_table, candidate_id, scenario_id)
            intervals = self._parsed_intervals[key]
            if not rows:
                self._spans[key] = None
            else:
                end = max(high for _, high in intervals)
                span: ScheduleTimeSpanRow = {"version": version, "start_time": min(low for low, _ in intervals),
                        "end_time": end, "end_includes_point": any(row.get("_point_work") and high == end
                            for row, (_, high) in zip(rows, intervals))}
                self._spans[key] = span
        return self._spans[key]


class PlanMetadataRepository(WorkbenchPlanCatalogRepository):
    """Validate and aggregate plan metadata without admitting its full details."""

    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        self._metadata_spans = {}

    def get_plan_time_span(self, *, version, source_table, candidate_id, scenario_id=None):
        key = (version, source_table, candidate_id, scenario_id)
        if key not in self._metadata_spans:
            sql, extra = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id)
            low, high, points, point_intervals = None, None, [], []
            for row in self.iter_rows(sql, [version] + extra):
                start, end = _interval(row)
                low = start if low is None else min(low, start)
                high = end if high is None else max(high, end)
                if start == end:
                    points.append(row)
                    point_intervals.append((start, end))
            try:
                annotate_plan_points(self.conn, points, source_table=source_table, intervals=point_intervals)
            except WorkbenchCommandRejected as exc:
                raise ValueError(str(exc)) from exc
            self._metadata_spans[key] = None if low is None else {
                "version": version, "start_time": low, "end_time": high,
                "end_includes_point": any(end == high for _, end in point_intervals),
            }
        return self._metadata_spans[key]

    def validate_detail_times(self, resolution):
        self.get_plan_time_span(version=resolution.version, source_table=resolution.source_table,
                                candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id)
