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

    def __post_init__(self) -> None:
        if self.checked_attr not in ("", "checked"):
            raise ValueError(f"checked_attr 只能是空字符串或 checked: {self.checked_attr!r}")
        if self.disabled_attr not in ("", "disabled"):
            raise ValueError(f"disabled_attr 只能是空字符串或 disabled: {self.disabled_attr!r}")


def validate_tone(tone: str) -> str:
    normalized = str(tone or "").strip()
    if normalized not in VALID_TONES:
        raise ValueError(f"未知 UI tone: {tone!r}")
    return normalized


def checked_attr(enabled: bool) -> str:
    return "checked" if bool(enabled) else ""


def disabled_attr(disabled: bool) -> str:
    return "disabled" if bool(disabled) else ""


__all__ = [
    "UiAction",
    "UiEmptyState",
    "UiNotice",
    "UiSummaryItem",
    "UiToggleRow",
    "VALID_TONES",
    "checked_attr",
    "disabled_attr",
    "validate_tone",
]
