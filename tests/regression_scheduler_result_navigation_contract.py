from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g

from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_week_plan import build_week_plan_rows
from core.services.scheduler.resource_dispatch_range import resolve_dispatch_range
from core.services.scheduler.resource_dispatch_rows import build_dispatch_calendar_matrix
from web.routes.domains.scheduler.scheduler_gantt_redirect import build_success_gantt_redirect_kwargs
from web.viewmodels.scheduler_resource_dispatch import decorate_resource_dispatch_payload


def test_week_plan_cross_day_segments_use_clear_day_labels() -> None:
    wr = resolve_week_range(start_date="2026-03-02", end_date="2026-03-05")
    outcome = build_week_plan_rows(
        rows=[
            {
                "start_time": "2026-03-02 08:00:00",
                "end_time": "2026-03-05 17:00:00",
                "batch_id": "B001",
                "part_no": "P001",
                "seq": 10,
                "machine_id": "MC001",
                "machine_name": "车床",
                "operator_id": "OP001",
                "operator_name": "张三",
            }
        ],
        wr=wr,
    )

    slots = [row["时段"] for row in outcome.value]

    assert slots == ["08:00-24:00", "全天", "全天", "00:00-17:00"]
    assert "00:00-00:00" not in slots


def test_resource_dispatch_calendar_keeps_clear_day_segment_labels() -> None:
    dr = resolve_dispatch_range(period_preset="custom", start_date="2026-03-02", end_date="2026-03-05")
    outcome = build_dispatch_calendar_matrix(
        scope_type="operator",
        scope_id="",
        dr=dr,
        rows=[
            {
                "schedule_id": 1,
                "start_time": "2026-03-02 08:00:00",
                "end_time": "2026-03-05 17:00:00",
                "op_code": "OP10",
                "part_no": "P001",
                "current_resource_id": "OP001",
                "current_resource_name": "张三",
                "machine_id": "MC001",
                "machine_name": "数控车床",
                "operator_id": "OP001",
                "operator_name": "张三",
            }
        ],
    )
    headers, rows = outcome.value

    payload = decorate_resource_dispatch_payload({"calendar_headers": headers, "calendar_rows": rows})
    texts = [item["text"] for cell in payload["calendar_rows"][0]["cells"] for item in cell["items"]]

    assert [text.split(" ", 1)[0] for text in texts] == ["08:00-24:00", "全天", "全天", "00:00-17:00"]
    assert all("00:00-00:00" not in text for text in texts)


def test_schedule_success_redirect_uses_version_real_span() -> None:
    app = Flask(__name__)

    with app.app_context():
        g.services = SimpleNamespace(
            gantt_service=SimpleNamespace(
                get_version_time_span_dates=lambda version: {
                    "version": version,
                    "start_date": "2026-05-11",
                    "end_date": "2026-05-18",
                }
            )
        )

        kwargs = build_success_gantt_redirect_kwargs({"version": 12})

    assert kwargs == {
        "view": "machine",
        "version": 12,
        "start_date": "2026-05-11",
        "end_date": "2026-05-18",
    }
