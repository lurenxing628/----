"""Characterize calendar scalar fast paths without changing scheduling decisions."""

from decimal import Decimal

import pytest

from core.models.enums import BATCH_PRIORITY_VALUES, BatchPriority, YesNo
from core.services.common.normalize import normalize_text
from core.services.scheduler import calendar_engine
from core.services.scheduler.calendar_engine import CalendarEngine, DayPolicy


class NonReflexiveText(str):
    def __ne__(self, other):
        return True


class CustomText(str):
    def strip(self):
        return "custom"


class UnorderedValue:
    def __ne__(self, other):
        raise ValueError("not comparable")

    def __str__(self):
        return "  O1  "


class BrokenValue:
    def __str__(self):
        raise RuntimeError("cannot stringify")


@pytest.mark.parametrize("value", [
    None, "", " \t\r\n", "O1", " O1 ", "0", "\u3000O1\u3000", "\u96f6\u4ef6",
    0, 1, False, True, 1.25, float("nan"), float("inf"), Decimal("NaN"), Decimal("sNaN"),
    Decimal("2.5"), b" O1 ", NonReflexiveText("O1"), CustomText("O1"), UnorderedValue(),
])
def test_normalized_scalar_matches_general_contract(value):
    assert CalendarEngine._normalize_text(value) == normalize_text(value)


def test_stringification_error_remains_visible():
    with pytest.raises(RuntimeError, match="cannot stringify"):
        CalendarEngine._normalize_text(BrokenValue())


def test_plain_strings_do_not_repeat_general_type_normalization(monkeypatch):
    calls = []

    def observe(value):
        calls.append(value)
        return normalize_text(value)

    monkeypatch.setattr(calendar_engine, "normalize_text", observe)
    for value in ("O1", " O1 ", "", " \t", "0", "\u3000O1\u3000"):
        assert CalendarEngine._normalize_text(value) == normalize_text(value)
    assert calls == []
    for value in (0, NonReflexiveText("O1"), CustomText("O1")):
        assert CalendarEngine._normalize_text(value) == normalize_text(value)
    assert len(calls) == 3


def policy(normal="yes", urgent="yes"):
    return DayPolicy("2026-09-09", "workday", 8.0, 1.0, normal, urgent)


def legacy_priority_allowed(day, priority):
    value = str(priority or BatchPriority.NORMAL.value).strip().lower()
    if value not in BATCH_PRIORITY_VALUES:
        value = BatchPriority.NORMAL.value
    if value == BatchPriority.NORMAL.value:
        return day.allow_normal == YesNo.YES.value
    return day.allow_urgent == YesNo.YES.value


@pytest.mark.parametrize("normal,urgent", [
    ("yes", "yes"), ("yes", "no"), ("no", "yes"), ("no", "no"), (None, "YES"),
    (True, False), (YesNo.YES, YesNo.NO),
])
@pytest.mark.parametrize("priority", [
    None, "", " ", "normal", " NORMAL ", "urgent", " UrGeNt ", "critical", "unknown", 0, False, 12,
    BatchPriority.NORMAL, BatchPriority.URGENT,
])
def test_priority_permission_matches_existing_behavior(normal, urgent, priority):
    day = policy(normal, urgent)
    assert day.is_priority_allowed(priority) == legacy_priority_allowed(day, priority)


def test_permissions_are_not_cached_across_policy_changes():
    day = policy("yes", "no")
    assert day.is_priority_allowed("normal") and not day.is_priority_allowed("urgent")
    day.allow_normal, day.allow_urgent = "no", "yes"
    assert not day.is_priority_allowed("normal") and day.is_priority_allowed("urgent")


def test_priority_hot_path_does_not_reread_fixed_enums(monkeypatch):
    day = policy("yes", "no")
    monkeypatch.setattr(calendar_engine, "BatchPriority", None)
    monkeypatch.setattr(calendar_engine, "YesNo", None)
    assert day.is_priority_allowed(None)
    assert day.is_priority_allowed("unknown")
    assert not day.is_priority_allowed("urgent")


@pytest.mark.parametrize("priority", [None, "normal", "urgent", "critical"])
def test_canonical_priority_does_not_repeat_value_membership(monkeypatch, priority):
    day = policy("yes", "no")
    expected = legacy_priority_allowed(day, priority)

    class UnexpectedValues:
        def __contains__(self, value):
            raise AssertionError("Canonical priority should not need generic membership validation")

    monkeypatch.setattr(calendar_engine, "BATCH_PRIORITY_VALUES", UnexpectedValues())
    assert day.is_priority_allowed(priority) == expected
