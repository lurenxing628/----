"""工作日历行解析。"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(("raw", "expected"), [(1, 1.0), (0.75, 0.75)])
def test_calendar_row_efficiency_requires_positive_finite_number_with_readable_error(raw, expected) -> None:
    from core.errors import ValidationError
    from core.models.calendar import OperatorCalendar, WorkCalendar

    row = {"date": "2026-05-01", "day_type": "workday", "efficiency": raw, "allow_normal": "yes", "allow_urgent": "yes",
           "remark": None, "periods_json": '[{"start":"08:00","end":"16:00","day_offset":0}]'}
    assert WorkCalendar.from_row(row).efficiency == expected
    # 与排产准入同一条严格判断：文本、bytes、bool 都不当数字读。
    for bad in (None, "", "  ", 0, -1, float("nan"), float("inf"), "abc", " 0.75 ", b"2", True):
        with pytest.raises(ValidationError, match="工作日历里 2026-05-01 的效率读不出来或不大于 0") as error:
            WorkCalendar.from_row({**row, "efficiency": bad})
        assert error.value.field == "efficiency"
    with pytest.raises(ValidationError, match="个人日历里 2026-05-01 的效率"):
        OperatorCalendar.from_row({**row, "operator_id": "O1", "efficiency": None})
