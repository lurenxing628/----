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
    from web.routes import reports

    assert reports._with_utilization_percent([{"name": "设备A", "utilization": ""}])[0]["utilization_percent"] is None
    assert reports._with_utilization_percent([{"name": "设备A", "utilization": 0.125}])[0]["utilization_percent"] == 12.5

    with pytest.raises(ValidationError, match="利用率"):
        reports._with_utilization_percent([{"name": "设备A", "utilization": "坏数据"}])

    with pytest.raises(ValidationError, match="导出行数"):
        reports._report_nonnegative_int("1.5", field="导出行数")

    with pytest.raises(ValidationError, match="downtime_hours"):
        reports._sum_report_number([{"downtime_hours": "坏数据"}], "downtime_hours")


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
