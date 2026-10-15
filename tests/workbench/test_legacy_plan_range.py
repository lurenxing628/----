"""Retained bookmark navigation and reports keep their inclusive date bounds."""

from datetime import date
from types import SimpleNamespace

import pytest

from core.errors import ValidationError
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.report.date_range_limits import ensure_report_date_range_within_limit
from web.routes.workbench.legacy_navigation_plan import ResolvedLegacyPlan, gantt_context


def _plan():
    return ResolvedLegacyPlan(WorkbenchPlanLocator(7, "baseline_best"), "a" * 48, False, {})


def _queries():
    return SimpleNamespace(get_plan_time_span=lambda version, role: {
        "start_time": "2026-01-01 08:00:00", "end_time": "2026-05-31 17:00:00"})


def test_legacy_gantt_bookmark_defaults_to_the_complete_plan_span():
    assert gantt_context(_queries(), _plan(), {}) == {"plan_ref": _plan().plan_ref}


def test_legacy_gantt_explicit_dates_keep_the_62_day_limit_and_override_week_offset():
    context = gantt_context(_queries(), _plan(), {
        "start_date": "2026-01-01", "end_date": "2026-03-03", "offset_weeks": "ignored"})
    assert context == {"plan_ref": _plan().plan_ref,
                       "range_start": "2026-01-01T00:00:00", "range_end": "2026-03-04T00:00:00"}
    with pytest.raises(ValidationError, match="日期范围不能超过 62 天"):
        gantt_context(_queries(), _plan(), {"start_date": "2026-01-01", "end_date": "2026-03-04"})


def test_report_dates_keep_the_62_day_inclusive_limit():
    ensure_report_date_range_within_limit(date(2026, 1, 1), date(2026, 3, 3))
    with pytest.raises(ValidationError, match="日期范围不能超过 62 天"):
        ensure_report_date_range_within_limit(date(2026, 1, 1), date(2026, 3, 4))
