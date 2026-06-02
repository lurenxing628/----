from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, g

from core.infrastructure.errors import ValidationError


class _ExplodingFloat:
    def __float__(self):
        raise RuntimeError("float conversion exploded")


class _ExplodingHistoryRow:
    def to_dict(self):
        raise RuntimeError("history row conversion exploded")


def test_scheduler_trend_numeric_helpers_only_swallow_parse_errors() -> None:
    from web.viewmodels import scheduler_analysis_trends as trends

    assert trends.safe_float("bad", default=7.5) == 7.5
    assert trends.safe_int("bad", default=7) == 7

    with pytest.raises(RuntimeError, match="float conversion exploded"):
        trends.safe_float(_ExplodingFloat(), default=0.0)

    with pytest.raises(RuntimeError, match="history row conversion exploded"):
        trends.build_trend_rows([_ExplodingHistoryRow()], extract_metrics_from_summary=lambda _summary: {"ok": 1})

    with pytest.raises(RuntimeError, match="history row conversion exploded"):
        trends.build_selected_details(
            selected_ver=1,
            selected_item=_ExplodingHistoryRow(),
            trend_all=[],
            extract_metrics_from_summary=lambda _summary: {"ok": 1},
            comparison_metric_from_algo=lambda _algo: "ok",
        )


def test_report_numeric_helpers_keep_empty_values_but_reject_bad_service_numbers() -> None:
    from core.services.report.delay_diagnosis_presentation import _delay_text
    from core.services.report.execution_review import ExecutionReviewMixin
    from core.services.report.exporters import export_utilization_xlsx
    from core.services.report.report_engine import ReportEngine
    from web.routes import reports_export_support
    from web.viewmodels import scheduler_reports_workbench as reports_vm

    assert reports_vm.decorate_utilization_rows([{"machine_id": "M1", "utilization": ""}], {}, resource_type="machine")[0]["utilization_percent"] is None
    assert reports_vm.decorate_utilization_rows([{"machine_id": "M1", "utilization": 0.125}], {}, resource_type="machine")[0]["utilization_percent"] == 12.5

    with pytest.raises(reports_vm.ReportPresentationValueError, match="利用率"):
        reports_vm.decorate_utilization_rows([{"machine_id": "M1", "utilization": "坏数据"}], {}, resource_type="machine")

    with pytest.raises(ValidationError, match="利用率"):
        export_utilization_xlsx([{"machine_id": "M1", "utilization": "坏数据"}], [])

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int("1.5", field="导出行数")

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int("-1", field="导出行数")

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int("1.0", field="导出行数")

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int(1.0, field="导出行数")

    engine = ReportEngine.__new__(ReportEngine)
    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("-1")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("2.000")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("坏数据")  # type: ignore[arg-type]

    with pytest.raises(reports_vm.ReportPresentationValueError, match="downtime_hours"):
        reports_vm._sum_number([{"downtime_hours": "坏数据"}], "downtime_hours")

    with pytest.raises(ValidationError, match="暂停时长"):
        ExecutionReviewMixin._pause_duration_label("坏数据", True)

    class _Review(ExecutionReviewMixin):
        execution_feedback_service = SimpleNamespace(get_execution_state=lambda _op_ids: {})

    with pytest.raises(ValidationError, match="工序编号"):
        _Review()._execution_review_rows([{"op_id": "坏数据"}])

    with pytest.raises(ValidationError, match="延期小时"):
        _delay_text(SimpleNamespace(delay_hours="坏数据", delay_days=0, bucket="scheduled_overdue"))


def test_system_time_range_and_job_detail_parse_errors_stay_visible() -> None:
    from web.routes import system_utils

    with pytest.raises(ValidationError, match="开始时间不能晚于结束时间"):
        system_utils._normalize_time_range("2026-03-14", "2026-03-13")

    app = Flask(__name__)
    with app.test_request_context("/system/backup"):
        g.services = SimpleNamespace(
            system_job_state_query_service=SimpleNamespace(
                get=lambda key: SimpleNamespace(
                    to_dict=lambda: {
                        "job_key": key,
                        "last_run_time": "2026-03-13 08:00:00",
                        "last_run_detail": "{bad-json",
                    }
                )
            )
        )

        state_map = system_utils._get_job_state_map()

    auto_backup = state_map["auto_backup"]
    assert auto_backup["last_run_detail_obj"] is None
    assert auto_backup["last_run_detail_parse_error"]
    assert auto_backup["last_run_state"] == "valid"
