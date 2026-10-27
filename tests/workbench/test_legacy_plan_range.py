"""Report date filters keep their inclusive 62-day bound."""

from datetime import date

import pytest

from core.errors import ValidationError
from core.services.report.date_range_limits import ensure_report_date_range_within_limit


def test_report_dates_keep_the_62_day_inclusive_limit():
    ensure_report_date_range_within_limit(date(2026, 1, 1), date(2026, 3, 3))
    with pytest.raises(ValidationError, match="日期范围不能超过 62 天"):
        ensure_report_date_range_within_limit(date(2026, 1, 1), date(2026, 3, 4))
