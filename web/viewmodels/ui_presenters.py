from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from core.models.toggle_values import TOGGLE_SUBMIT_VALUES, normalize_toggle_submit_value

VALID_TONES = frozenset({"neutral", "info", "success", "warning", "danger"})
VALID_NOTICE_ROLES = frozenset({"", "status", "alert", "note"})
VALID_ARIA_LIVE = frozenset({"", "polite", "assertive", "off"})


@dataclass(frozen=True)
class UiSummaryItem:
    label: str
    value: str
    desc: str = ""
    tone: str = "neutral"
    details_summary: str = ""

    def __post_init__(self) -> None:
        validate_tone(self.tone)
        if not isinstance(self.value, str):
            raise ValueError(f"UiSummaryItem.value 必须是展示字符串：{self.label!r}")
        if not self.value.strip():
            raise ValueError(f"UiSummaryItem.value 不能为空：{self.label!r}")


@dataclass(frozen=True)
class UiNotice:
    title: str
    body: str
    tone: str = "info"
    role: str = ""
    aria_live: str = ""

    def __post_init__(self) -> None:
        validate_tone(self.tone)
        validate_notice_a11y(self.role, self.aria_live)


@dataclass(frozen=True)
class UiDetailsNotice:
    title: str
    body: str
    tone: str = "info"
    detail_label: str = "查看明细"
    detail_items: Sequence[str] = ()
    footer: str = ""
    role: str = ""
    aria_live: str = ""

    def __post_init__(self) -> None:
        validate_tone(self.tone)
        validate_notice_a11y(self.role, self.aria_live)


@dataclass(frozen=True)
class UiAction:
    label: str
    endpoint: str
    tone: str = "neutral"

    def __post_init__(self) -> None:
        validate_tone(self.tone)


@dataclass(frozen=True)
class UiEmptyState:
    title: str
    desc: str
    actions: Sequence[UiAction] = ()


@dataclass(frozen=True)
class UiToggleRow:
    id: str
    name: str
    title: str
    desc: str
    checked_attr: str
    disabled_attr: str = ""
    value: str = "yes"
    hidden_value: str = "no"
    # 这个值只代表 hidden input 的提交值；最终开关含义由 form_yes_no_value 读取同名字段后决定。
    submitted_value: str = ""

    def __post_init__(self) -> None:
        if self.checked_attr not in ("", "checked"):
            raise ValueError(f"checked_attr 只能是空字符串或 checked: {self.checked_attr!r}")
        if self.disabled_attr not in ("", "disabled"):
            raise ValueError(f"disabled_attr 只能是空字符串或 disabled: {self.disabled_attr!r}")
        _validate_toggle_submit_token(self.value, field="value")
        _validate_toggle_submit_token(self.hidden_value, field="hidden_value")
        submitted_value = self.submitted_value
        if submitted_value:
            _validate_toggle_submit_token(submitted_value, field="submitted_value")
        if not submitted_value:
            if self.disabled_attr == "disabled" and self.checked_attr == "checked":
                submitted_value = self.value
            else:
                submitted_value = self.hidden_value
        object.__setattr__(self, "submitted_value", submitted_value)


def validate_tone(tone: str) -> str:
    normalized = str(tone or "").strip()
    if normalized not in VALID_TONES:
        raise ValueError(f"未知 UI tone: {tone!r}")
    return normalized


def validate_notice_a11y(role: str, aria_live: str) -> None:
    normalized_role = str(role or "").strip()
    normalized_aria_live = str(aria_live or "").strip()
    if normalized_role not in VALID_NOTICE_ROLES:
        raise ValueError(f"未知 notice role: {role!r}")
    if normalized_aria_live not in VALID_ARIA_LIVE:
        raise ValueError(f"未知 aria-live: {aria_live!r}")


def _validate_toggle_submit_token(value: Any, *, field: str) -> str:
    normalized = normalize_toggle_submit_value(value)
    if normalized not in TOGGLE_SUBMIT_VALUES:
        raise ValueError(f"{field} 不是合法 toggle 提交值：{value!r}")
    return normalized


def checked_attr(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise TypeError(f"checked_attr 只接受 bool，实际为：{enabled!r}")
    return "checked" if enabled else ""


def disabled_attr(disabled: bool) -> str:
    if not isinstance(disabled, bool):
        raise TypeError(f"disabled_attr 只接受 bool，实际为：{disabled!r}")
    return "disabled" if disabled else ""


__all__ = [
    "UiAction",
    "UiDetailsNotice",
    "UiEmptyState",
    "UiNotice",
    "UiSummaryItem",
    "UiToggleRow",
    "VALID_ARIA_LIVE",
    "VALID_NOTICE_ROLES",
    "VALID_TONES",
    "checked_attr",
    "disabled_attr",
    "validate_notice_a11y",
    "validate_tone",
]
