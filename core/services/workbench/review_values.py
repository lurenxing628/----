"""Factory wall-clock presentation; unknown values are not zero measurements."""

from datetime import datetime

from core.services.report import calculations


def local_time(value):
    parsed = calculations.parse_dt(value)
    if parsed is None or parsed.tzinfo is not None:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def minutes(planned, actual):
    if planned is None or actual is None:
        return None
    return round((datetime.fromisoformat(actual) - datetime.fromisoformat(planned)).total_seconds() / 60, 2)


def hour_totals(records):
    values = [row["effective_processing_hours"] for row in records if row["effective_processing_hours"] is not None]
    unknown = sum(row["effective_processing_hours"] is None for row in records)
    known = sum(values) if values else None
    return {"effective_processing_hours": known if not unknown else None,
            "known_effective_processing_hours": known, "unknown_hour_events": unknown}
