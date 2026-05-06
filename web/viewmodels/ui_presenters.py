from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

VALID_TONES = frozenset({"neutral", "info", "success", "warning", "danger"})


@dataclass(frozen=True)
class UiSummaryItem:
    label: str
    value: str
    desc: str = ""
    tone: str = "neutral"

    def __post_init__(self) -> None:
        validate_tone(self.tone)


@dataclass(frozen=True)
class UiNotice:
    title: str
    body: str
    tone: str = "info"

    def __post_init__(self) -> None:
        validate_tone(self.tone)


@dataclass(frozen=True)
class UiDetailsNotice:
    title: str
    body: str
    tone: str = "info"
    detail_label: str = "查看明细"
    detail_items: Sequence[str] = ()
    footer: str = ""

    def __post_init__(self) -> None:
        validate_tone(self.tone)


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
    submitted_value: str = ""

    def __post_init__(self) -> None:
        if self.checked_attr not in ("", "checked"):
            raise ValueError(f"checked_attr 只能是空字符串或 checked: {self.checked_attr!r}")
        if self.disabled_attr not in ("", "disabled"):
            raise ValueError(f"disabled_attr 只能是空字符串或 disabled: {self.disabled_attr!r}")
        submitted_value = self.submitted_value
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
    "VALID_TONES",
    "checked_attr",
    "disabled_attr",
    "validate_tone",
]
