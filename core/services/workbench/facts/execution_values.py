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
    planned, actual = local_time(planned), local_time(actual)
    if planned is None or actual is None:
        return None
    return round((datetime.fromisoformat(actual) - datetime.fromisoformat(planned)).total_seconds() / 60, 2)


def execution_deviation(planned_end, projection, as_of):
    """One rounded-minute deadline rule for the saved plan and execution ledger."""
    result = {"state": "unavailable", "as_of": as_of,
              "finish_deviation_minutes": None, "elapsed_since_planned_minutes": None,
              "forecast_deviation_minutes": None, "due": False, "complete": False,
              "unclosed": False, "late_open": False, "finish_late": False, "forecast_late": False}
    if projection is None:
        return result
    planned, clock = local_time(planned_end), local_time(as_of)
    complete = projection["execution_state"] == "complete"
    confirmed = local_time(projection["confirmed_finish"])
    remaining = projection["remaining_plan"] if not complete else None
    forecast = local_time(remaining["end"]) if remaining else None
    due = planned is not None and clock is not None and datetime.fromisoformat(planned) <= datetime.fromisoformat(clock)
    finish = minutes(planned, confirmed) if complete else None
    elapsed = minutes(planned, clock) if due and not complete else None
    forecast_delta = minutes(planned, forecast) if remaining else None
    missing = planned is None or clock is None or (complete and confirmed is None) or (remaining is not None and forecast is None)
    result.update(state="partial" if missing else "available", due=due, complete=complete,
                  finish_deviation_minutes=finish, elapsed_since_planned_minutes=elapsed,
                  forecast_deviation_minutes=forecast_delta, unclosed=due and not complete,
                  late_open=elapsed is not None and elapsed > 10,
                  finish_late=finish is not None and finish > 10,
                  forecast_late=forecast_delta is not None and forecast_delta > 10)
    return result
