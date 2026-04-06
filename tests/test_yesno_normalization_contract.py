from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.models.enums import YesNo
from core.plugins.manager import _normalize_yes_no as plugin_yes_no
from core.services.common.excel_validators import _normalize_yesno as core_excel_yesno
from core.services.scheduler.calendar_admin import CalendarAdmin
from core.services.scheduler.number_utils import to_yes_no
from core.services.system.system_config_service import _normalize_yes_no as system_yes_no
from web.routes.normalizers import _normalize_yesno as route_yesno


def test_to_yes_no_wide_truthy_and_falsy_and_default() -> None:
    for raw in ("yes", "YES", " y ", "true", "1", "on"):
        assert to_yes_no(raw, default=YesNo.NO.value) == YesNo.YES.value

    for raw in ("no", "n", "false", "0", "off", "", "maybe", "2"):
        assert to_yes_no(raw, default=YesNo.NO.value) == YesNo.NO.value

    assert to_yes_no(None, default=YesNo.YES.value) == YesNo.YES.value
    assert to_yes_no(None, default=YesNo.NO.value) == YesNo.NO.value


def test_system_config_yes_no_unknown_is_no() -> None:
    for raw in ("yes", "YES", "true", "1", "on", " y "):
        assert system_yes_no(raw) == YesNo.YES.value
    for raw in (None, "no", "NO", "false", "0", "off", "", "maybe", "2"):
        assert system_yes_no(raw) == YesNo.NO.value


def test_plugin_yes_no_unknown_follows_default_param() -> None:
    assert plugin_yes_no(None, default="yes") == "yes"
    assert plugin_yes_no(None, default="no") == "no"

    assert plugin_yes_no("maybe", default="yes") == "yes"
    assert plugin_yes_no("maybe", default="no") == "no"

    assert plugin_yes_no("YES", default="no") == "yes"
    assert plugin_yes_no("", default="yes") == "no"


def test_excel_and_route_yesno_is_narrow_default_yes_unknown_passthrough() -> None:
    for fn in (core_excel_yesno, route_yesno):
        assert fn(None) == YesNo.YES.value
        assert fn("") == YesNo.YES.value
        assert fn("Yes") == YesNo.YES.value
        assert fn("NO") == YesNo.NO.value
        assert fn("是") == YesNo.YES.value
        assert fn("否") == YesNo.NO.value

        # 窄口径现已放宽：接受 true/false/1/0，但 on/off 仍透传给上层校验
        assert fn("true") == YesNo.YES.value
        assert fn("1") == YesNo.YES.value
        assert fn("false") == YesNo.NO.value
        assert fn("0") == YesNo.NO.value
        assert fn("on") == "on"

        # unknown：保持原样（strip 后）
        assert fn("  Maybe  ") == "Maybe"


def test_calendar_admin_yesno_is_narrow_unknown_raises() -> None:
    assert CalendarAdmin._normalize_yesno(None, field="允许普通件") == YesNo.YES.value
    assert CalendarAdmin._normalize_yesno("Yes", field="允许普通件") == YesNo.YES.value
    assert CalendarAdmin._normalize_yesno("NO", field="允许普通件") == YesNo.NO.value
    assert CalendarAdmin._normalize_yesno("是", field="允许普通件") == YesNo.YES.value
    assert CalendarAdmin._normalize_yesno("否", field="允许普通件") == YesNo.NO.value
    assert CalendarAdmin._normalize_yesno("true", field="允许普通件") == YesNo.YES.value
    assert CalendarAdmin._normalize_yesno("1", field="允许普通件") == YesNo.YES.value
    assert CalendarAdmin._normalize_yesno("false", field="允许普通件") == YesNo.NO.value
    assert CalendarAdmin._normalize_yesno("0", field="允许普通件") == YesNo.NO.value

    with pytest.raises(ValidationError):
        CalendarAdmin._normalize_yesno("maybe", field="允许普通件")
    with pytest.raises(ValidationError):
        CalendarAdmin._normalize_yesno("on", field="允许普通件")

