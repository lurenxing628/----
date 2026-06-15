from __future__ import annotations

import time

from flask import g, request

from core.services.report import ReportEngine
from web.routes.report_plan_preview import export_date_range_or_version_span
from web.routes.reports_export_support import log_report_export, send_report_export_file
from web.routes.reports_request_support import (
    export_version_or_latest as _export_version_or_latest,
)
from web.routes.reports_request_support import (
    request_plan_role as _request_plan_role,
)
from web.routes.reports_request_support import (
    request_resource_filter as _request_resource_filter,
)
from web.routes.reports_request_support import (
    request_scenario_id as _request_scenario_id,
)
from web.routes.reports_request_support import (
    require_execution_review_adopted_plan as _require_execution_review_adopted_plan,
)


def register_report_export_routes(bp) -> None:
    @bp.get("/overdue/export")
    def overdue_export():
        started_at = time.time()
        engine = ReportEngine(g.db)
        version = _export_version_or_latest(engine)
        plan_role = _request_plan_role()
        scenario_id = _request_scenario_id()
        resource_type, resource_id = _request_resource_filter()
        x = engine.export_overdue_xlsx(
            version,
            plan_role=plan_role,
            scenario_id=scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=request.args.get("batch_id") or "",
        )
        log_report_export(
            engine=engine,
            report_export=x,
            target_type="overdue",
            export_type="超期清单.xlsx",
            version=version,
            raw_plan_role=plan_role,
            scenario_id=scenario_id,
            started_at=started_at,
        )
        return send_report_export_file(x)

    @bp.get("/utilization/export")
    def utilization_export():
        started_at = time.time()
        engine = ReportEngine(g.db)
        version = _export_version_or_latest(engine)
        plan_role = _request_plan_role()
        scenario_id = _request_scenario_id()
        resource_type, resource_id = _request_resource_filter()
        raw_start_date = request.args.get("start_date") or ""
        raw_end_date = request.args.get("end_date") or ""
        start_date, end_date = export_date_range_or_version_span(
            engine,
            int(version or 0),
            plan_role,
            scenario_id,
            raw_start_date,
            raw_end_date,
        )
        x = engine.export_utilization_xlsx(
            version,
            start_date,
            end_date,
            plan_role=plan_role,
            scenario_id=scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=request.args.get("batch_id") or "",
            enforce_date_range_limit=bool(raw_start_date or raw_end_date),
        )
        log_report_export(
            engine=engine,
            report_export=x,
            target_type="utilization",
            export_type="资源负荷与利用率.xlsx",
            version=version,
            raw_plan_role=plan_role,
            scenario_id=scenario_id,
            time_range={"start": start_date, "end": end_date},
            started_at=started_at,
        )
        return send_report_export_file(x)

    @bp.get("/execution-review/export")
    def execution_review_export():
        started_at = time.time()
        engine = ReportEngine(g.db)
        version = _export_version_or_latest(engine)
        plan_role, scenario_id = _require_execution_review_adopted_plan()
        date_from = request.args.get("date_from") or ""
        date_to = request.args.get("date_to") or ""
        batch_id = request.args.get("batch_id") or ""
        resource_type, resource_id = _request_resource_filter()
        x = engine.export_execution_review_xlsx(
            version,
            date_from=date_from,
            date_to=date_to,
            batch_id=batch_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        log_report_export(
            engine=engine,
            report_export=x,
            target_type="execution_review",
            export_type="计划和现场实际.xlsx",
            version=version,
            raw_plan_role=plan_role,
            scenario_id=scenario_id,
            time_range={"date_from": date_from, "date_to": date_to, "batch_id": batch_id},
            started_at=started_at,
        )
        return send_report_export_file(x)

    @bp.get("/downtime/export")
    def downtime_export():
        started_at = time.time()
        engine = ReportEngine(g.db)
        version = _export_version_or_latest(engine)
        plan_role = _request_plan_role()
        scenario_id = _request_scenario_id()
        resource_type, resource_id = _request_resource_filter()
        raw_start_date = request.args.get("start_date") or ""
        raw_end_date = request.args.get("end_date") or ""
        start_date, end_date = export_date_range_or_version_span(
            engine,
            int(version or 0),
            plan_role,
            scenario_id,
            raw_start_date,
            raw_end_date,
        )
        x = engine.export_downtime_impact_xlsx(
            version,
            start_date,
            end_date,
            plan_role=plan_role,
            scenario_id=scenario_id,
            resource_type=resource_type,
            resource_id=resource_id,
            batch_id=request.args.get("batch_id") or "",
            enforce_date_range_limit=bool(raw_start_date or raw_end_date),
        )
        log_report_export(
            engine=engine,
            report_export=x,
            target_type="downtime",
            export_type="停机影响统计.xlsx",
            version=version,
            raw_plan_role=plan_role,
            scenario_id=scenario_id,
            time_range={"start": start_date, "end": end_date},
            started_at=started_at,
        )
        return send_report_export_file(x)


__all__ = ["register_report_export_routes"]
