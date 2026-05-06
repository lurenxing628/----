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
        UiNotice("提示", "内容", tone="mystery")
    with pytest.raises(ValueError, match="未知 UI tone"):
        UiDetailsNotice("提示", "内容", tone="mystery")


@pytest.mark.parametrize("value", (None, "", "   "))
def test_summary_item_rejects_empty_display_values(value) -> None:
    with pytest.raises(ValueError, match="UiSummaryItem.value"):
        UiSummaryItem("标题", value)


@pytest.mark.parametrize("value", ("0", "-", "未记录"))
def test_summary_item_accepts_explicit_display_values(value: str) -> None:
    assert UiSummaryItem("标题", value).value == value


def test_notice_presenters_keep_accessibility_metadata_explicit() -> None:
    notice = UiNotice("提示", "内容")
    details = UiDetailsNotice("说明", "内容")
    assert notice.role == ""
    assert notice.aria_live == ""
    assert details.role == ""
    assert details.aria_live == ""

    live_notice = UiNotice("提示", "内容", role="status", aria_live="polite")
    live_details = UiDetailsNotice("说明", "内容", role="alert", aria_live="assertive")
    assert live_notice.role == "status"
    assert live_notice.aria_live == "polite"
    assert live_details.role == "alert"
    assert live_details.aria_live == "assertive"

    note = UiNotice("说明", "内容", role="note", aria_live="off")
    assert note.role == "note"
    assert note.aria_live == "off"

    with pytest.raises(ValueError, match="notice role"):
        UiNotice("提示", "内容", role="button")
    with pytest.raises(ValueError, match="aria-live"):
        UiDetailsNotice("说明", "内容", aria_live="poltie")


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
    binary_toggle = UiToggleRow("toggleH", "field_h", "标题", "说明", "checked", value="1", hidden_value="0")
    assert binary_toggle.value == "1"
    assert binary_toggle.hidden_value == "0"
    assert binary_toggle.submitted_value == "0"

    with pytest.raises(ValueError, match="checked_attr"):
        UiToggleRow("toggleF", "field_f", "标题", "说明", "yes")
    with pytest.raises(ValueError, match="disabled_attr"):
        UiToggleRow("toggleG", "field_g", "标题", "说明", "", "readonly")
    with pytest.raises(ValueError, match="value"):
        UiToggleRow("toggleI", "field_i", "标题", "说明", "", value="maybe")
    with pytest.raises(ValueError, match="hidden_value"):
        UiToggleRow("toggleJ", "field_j", "标题", "说明", "", hidden_value="??")
    with pytest.raises(ValueError, match="submitted_value"):
        UiToggleRow("toggleK", "field_k", "标题", "说明", "", submitted_value="later")
    with pytest.raises(TypeError, match="checked_attr 只接受 bool"):
        checked_attr("no")
    with pytest.raises(TypeError, match="disabled_attr 只接受 bool"):
        disabled_attr("false")
