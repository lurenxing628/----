"""Workbench-only plan spans; legacy SQL keeps its positive-interval default."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from data.repositories.schedule_time_sql import parse_dt_for_sql
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository

from .plan_point_evidence import annotate_plan_points


def _interval(row):
    start, end = (parse_dt_for_sql(row[key]) for key in ("start_time", "end_time"))
    if start is None or end is None or start > end:
        raise ValueError("Invalid lossless plan interval")
    return start, end


class PointPlanCatalogRepository(WorkbenchPlanCatalogRepository):
    def _validated_rows(self, version, source_table, candidate_id, scenario_id):
        sql, params = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id)
        rows = self.fetchall("SELECT * FROM (" + sql + ") LIMIT ?", [version] + params + [MAX_PLAN_TASKS + 1])
        if len(rows) > MAX_PLAN_TASKS:
            raise WorkbenchCommandRejected("query_too_large", "整个计划超过 10000 条上限。请缩小时间范围后重试。", 413)
        try:
            for row in rows:
                _interval(row)
            return annotate_plan_points(self.conn, rows, source_table=source_table)
        except WorkbenchCommandRejected as exc:
            raise ValueError(str(exc)) from exc

    def validate_detail_times(self, resolution):
        self._validated_rows(resolution.version, resolution.source_table, resolution.candidate_id, resolution.scenario_id)

    def get_plan_time_span(self, *, version, source_table, candidate_id, scenario_id=None):
        rows = self._validated_rows(version, source_table, candidate_id, scenario_id)
        if not rows:
            return None
        intervals = [_interval(row) for row in rows]
        end = max(high for _, high in intervals)
        return {"version": version, "start_time": min(low for low, _ in intervals),
                "end_time": end, "end_includes_point": any(row.get("_point_work") and high == end
                    for row, (_, high) in zip(rows, intervals))}
