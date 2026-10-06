"""Factory wall-clock presentation; unknown values are not zero measurements."""

from datetime import datetime

from core.services.execution.processing_hours import hour_totals as hour_totals
from core.services.report import calculations


def local_time(value):
    parsed = calculations.parse_dt(value)
    if parsed is None or parsed.tzinfo is not None:
        return None
    return parsed.isoformat()


def minutes(planned, actual):
    if planned is None or actual is None:
        return None
    return round((datetime.fromisoformat(actual) - datetime.fromisoformat(planned)).total_seconds() / 60, 2)
