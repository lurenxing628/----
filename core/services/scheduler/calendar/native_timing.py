"""Calendar timing guard helpers."""

from .engine import CalendarEngine


def _make_guard(service_type):
    def supported(service):
        return isinstance(service, service_type) and isinstance(getattr(service, "_engine", None), CalendarEngine)

    return supported


def make_timing_memo_guard(service_type):
    return _make_guard(service_type)


def make_calendar_days_guard(service_type):
    return _make_guard(service_type)
