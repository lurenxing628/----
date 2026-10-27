"""Reported processing hours."""

from decimal import Decimal


def hour_totals(records):
    values = [row["effective_processing_hours"] for row in records if row["effective_processing_hours"] is not None]
    unknown = len(records) - len(values)
    # Decimal keeps user-entered 0.1 + 0.2 equal to 0.3.
    known = float(sum((Decimal(str(value)) for value in values), Decimal(0))) if values else None
    return {"effective_processing_hours": known if not unknown else None,
            "known_effective_processing_hours": known, "unknown_hour_events": unknown}
