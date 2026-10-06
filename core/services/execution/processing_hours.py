"""Reported processing hours, with linked legacy evidence counted only once."""

from decimal import Decimal


def covered_legacy_scopes(records):
    sources = {row["legacy_fact_ref"]: (row["operation_ref"], row["recorded_against_task_ref"])
               for row in records if not row.get("report_ref") and row.get("event_type") == "finish"
               and row.get("recorded_against_task_ref") is not None}
    return {sources[row["legacy_fact_ref"]] for row in records
            if row.get("report_ref") and row.get("legacy_fact_ref") in sources}


def hour_totals(records, *, covered_scopes=None):
    """Keep old records visible without treating a supplemented scope as extra work."""
    covered = covered_legacy_scopes(records) if covered_scopes is None else covered_scopes
    included = [row for row in records if row.get("report_ref") or
                (row.get("operation_ref"), row.get("recorded_against_task_ref")) not in covered]
    values = [row["effective_processing_hours"] for row in included if row["effective_processing_hours"] is not None]
    unknown = sum(row["effective_processing_hours"] is None for row in included)
    # Decimal keeps user-entered 0.1 + 0.2 equal to 0.3.
    known = float(sum((Decimal(str(value)) for value in values), Decimal(0))) if values else None
    return {"effective_processing_hours": known if not unknown else None,
            "known_effective_processing_hours": known, "unknown_hour_events": unknown}
