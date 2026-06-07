"""回归测试：resolve_schedule_result_week_range 的展示区间解析——无请求区间且 default_to_version_span=True 时回落到版本跨度（range_source=version_span），显式 week_start/offset_weeks 或 start_date+end_date 时用请求区间且对显式起止区间忽略 offset，周计划模式不回落版本跨度；非法 offset_weeks 与非法 plan_role 分别抛带 field 的 ValidationError，并校验 has_explicit_display_range 判定。"""

from __future__ import annotations

from typing import Optional

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.schedule_result_view_range import (
    get_plan_time_span_dates,
    has_explicit_display_range,
    normalize_week_offset_for_explicit_range,
    resolve_schedule_result_week_range,
)


class FakePlanQueryService:
    def __init__(self, span=None) -> None:
        self.span = span
        self.calls = []

    def get_plan_time_span(self, version: int, role: Optional[str]):
        self.calls.append({"version": version, "role": role})
        if role == "bad":
            raise ValueError("未知的排产方案角色：bad")
        return self.span


def _span(start: str = "2026-03-10 08:00:00", end: str = "2026-03-12 17:00:00"):
    return {"start_time": start, "end_time": end}


def test_gantt_default_range_uses_version_span_when_request_has_no_range() -> None:
    plan_query = FakePlanQueryService(_span())

    wr, version_span, range_source = resolve_schedule_result_week_range(
        plan_query_service=plan_query,
        version=7,
        plan_role="baseline_best",
        default_to_version_span=True,
    )

    assert wr.week_start_date.isoformat() == "2026-03-10"
    assert wr.week_end_date.isoformat() == "2026-03-12"
    assert range_source == "version_span"
    assert version_span == {
        "version": 7,
        "start_time": "2026-03-10 08:00:00",
        "end_time": "2026-03-12 17:00:00",
        "start_date": "2026-03-10",
        "end_date": "2026-03-12",
    }
    assert plan_query.calls == [{"version": 7, "role": "baseline_best"}]


def test_explicit_week_start_uses_requested_week() -> None:
    wr, version_span, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        week_start="2026-03-02",
        default_to_version_span=True,
    )

    assert wr.week_start_date.isoformat() == "2026-03-02"
    assert wr.week_end_date.isoformat() == "2026-03-08"
    assert range_source == "request"
    assert version_span is not None


def test_explicit_week_start_with_offset_uses_next_week() -> None:
    wr, _, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        week_start="2026-03-02",
        offset_weeks=1,
        default_to_version_span=True,
    )

    assert wr.week_start_date.isoformat() == "2026-03-09"
    assert wr.week_end_date.isoformat() == "2026-03-15"
    assert range_source == "request"


def test_explicit_start_end_dates_ignore_offset() -> None:
    wr, _, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        start_date="2026-03-10",
        end_date="2026-03-12",
        offset_weeks=1,
        default_to_version_span=True,
    )

    assert wr.week_start_date.isoformat() == "2026-03-10"
    assert wr.week_end_date.isoformat() == "2026-03-12"
    assert range_source == "request"
    assert normalize_week_offset_for_explicit_range(
        start_date="2026-03-10",
        end_date="2026-03-12",
        offset_weeks=1,
    ) == 0


def test_explicit_start_end_dates_ignore_invalid_offset() -> None:
    wr, _, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        start_date="2026-03-10",
        end_date="2026-03-12",
        offset_weeks="bad",
        default_to_version_span=True,
    )

    assert wr.week_start_date.isoformat() == "2026-03-10"
    assert wr.week_end_date.isoformat() == "2026-03-12"
    assert range_source == "request"


def test_single_explicit_date_ignores_offset() -> None:
    start_wr, _, _ = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        start_date="2026-03-10",
        offset_weeks=1,
        default_to_version_span=True,
    )
    end_wr, _, _ = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        end_date="2030-03-12",
        offset_weeks=1,
        default_to_version_span=True,
    )

    assert start_wr == resolve_week_range(start_date="2026-03-10", offset_weeks=0)
    assert end_wr == resolve_week_range(end_date="2030-03-12", offset_weeks=0)


def test_only_start_date_keeps_existing_range_mode_defaults() -> None:
    wr, _, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        start_date="2026-03-10",
        default_to_version_span=True,
    )
    expected = resolve_week_range(start_date="2026-03-10", offset_weeks=0)

    assert wr == expected
    assert range_source == "request"


def test_only_end_date_keeps_existing_range_mode_defaults() -> None:
    wr, _, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span()),
        version=7,
        plan_role=None,
        end_date="2030-03-12",
        default_to_version_span=True,
    )
    expected = resolve_week_range(end_date="2030-03-12", offset_weeks=0)

    assert wr == expected
    assert range_source == "request"


def test_week_plan_mode_does_not_default_to_version_span() -> None:
    wr, version_span, range_source = resolve_schedule_result_week_range(
        plan_query_service=FakePlanQueryService(_span("2026-01-01 08:00:00", "2026-01-02 17:00:00")),
        version=7,
        plan_role=None,
        default_to_version_span=False,
    )
    expected = resolve_week_range()

    assert wr == expected
    assert wr.week_start_date.isoformat() != "2026-01-01"
    assert version_span is not None
    assert range_source == "request"


def test_invalid_offset_reports_offset_weeks() -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_schedule_result_week_range(
            plan_query_service=FakePlanQueryService(_span()),
            version=7,
            plan_role=None,
            offset_weeks="bad",
            default_to_version_span=True,
        )

    assert exc_info.value.details == {"field": "offset_weeks"}


def test_invalid_plan_role_reports_plan_role_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        get_plan_time_span_dates(FakePlanQueryService(_span()), 7, "bad")

    assert exc_info.value.details == {"field": "plan_role"}


def test_start_end_make_range_explicit_without_offset_taking_effect() -> None:
    assert has_explicit_display_range(
        week_start=None,
        offset_weeks=1,
        start_date="2026-03-10",
        end_date="2026-03-12",
    )
    assert not has_explicit_display_range(
        week_start=None,
        offset_weeks=0,
        start_date=None,
        end_date=None,
    )
