from __future__ import annotations

import pytest

from web.viewmodels.ui_presenters import (
    UiDetailsNotice,
    UiNotice,
    UiSummaryItem,
    UiToggleRow,
    checked_attr,
    disabled_attr,
    validate_tone,
)


def test_ui_tone_contract_rejects_unknown_values() -> None:
    for tone in ("neutral", "info", "success", "warning", "danger"):
        assert validate_tone(tone) == tone
        assert UiSummaryItem("标题", "值", tone=tone).tone == tone
        assert UiNotice("提示", "内容", tone=tone).tone == tone
        assert UiDetailsNotice("提示", "内容", tone=tone).tone == tone

    with pytest.raises(ValueError, match="未知 UI tone"):
        validate_tone("mystery")
    with pytest.raises(ValueError, match="未知 UI tone"):
        UiSummaryItem("标题", "值", tone="mystery")
    with pytest.raises(ValueError, match="未知 UI tone"):
        UiDetailsNotice("提示", "内容", tone="mystery")


def test_toggle_attr_helpers_emit_only_html_attr_tokens() -> None:
    assert checked_attr(True) == "checked"
    assert checked_attr(False) == ""
    assert disabled_attr(True) == "disabled"
    assert disabled_attr(False) == ""

    assert UiToggleRow("toggleA", "field_a", "标题", "说明", "checked").checked_attr == "checked"
    assert UiToggleRow("toggleB", "field_b", "标题", "说明", "", "disabled").disabled_attr == "disabled"
    assert UiToggleRow("toggleC", "field_c", "标题", "说明", "").submitted_value == "no"
    assert UiToggleRow("toggleD", "field_d", "标题", "说明", "checked").submitted_value == "no"
    disabled_checked = UiToggleRow("toggleE", "field_e", "标题", "说明", "checked", "disabled")
    assert disabled_checked.submitted_value == "yes"

    with pytest.raises(ValueError, match="checked_attr"):
        UiToggleRow("toggleF", "field_f", "标题", "说明", "yes")
    with pytest.raises(ValueError, match="disabled_attr"):
        UiToggleRow("toggleG", "field_g", "标题", "说明", "", "readonly")
    with pytest.raises(TypeError, match="checked_attr 只接受 bool"):
        checked_attr("no")
    with pytest.raises(TypeError, match="disabled_attr 只接受 bool"):
        disabled_attr("false")
