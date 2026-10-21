"""Factory wall-clock presentation; unknown values are not zero measurements."""

from core.services.execution.processing_hours import hour_totals as hour_totals
from core.services.report import calculations


def _local_dt(value):
    parsed = calculations.parse_dt(value)
    if parsed is None or parsed.tzinfo is not None:
        return None
    return parsed


def _minutes_between(planned_dt, actual_dt):
    if planned_dt is None or actual_dt is None:
        return None
    return round((actual_dt - planned_dt).total_seconds() / 60, 2)


def local_time(value):
    parsed = _local_dt(value)
    return parsed.isoformat() if parsed is not None else None


def minutes(planned, actual):
    return _minutes_between(_local_dt(planned), _local_dt(actual))


def execution_deviation(planned_end, projection, as_of):
    """One rounded-minute deadline rule for the saved plan and execution ledger."""
    result = {"state": "unavailable", "as_of": as_of,
              "finish_deviation_minutes": None, "elapsed_since_planned_minutes": None,
              "forecast_deviation_minutes": None, "due": False, "complete": False,
              "unclosed": False, "late_open": False, "finish_late": False, "forecast_late": False}
    if projection is None:
        return result
    planned, clock = _local_dt(planned_end), _local_dt(as_of)
    complete = projection["execution_state"] == "complete"
    confirmed = _local_dt(projection["confirmed_finish"])
    remaining = projection["remaining_plan"] if not complete else None
    forecast = _local_dt(remaining["end"]) if remaining else None
    due = planned is not None and clock is not None and planned <= clock
    finish = _minutes_between(planned, confirmed) if complete else None
    elapsed = _minutes_between(planned, clock) if due and not complete else None
    forecast_delta = _minutes_between(planned, forecast) if remaining else None
    missing = planned is None or clock is None or (complete and confirmed is None) or (remaining is not None and forecast is None)
    result.update(state="partial" if missing else "available", due=due, complete=complete,
                  finish_deviation_minutes=finish, elapsed_since_planned_minutes=elapsed,
                  forecast_deviation_minutes=forecast_delta, unclosed=due and not complete,
                  late_open=elapsed is not None and elapsed > 10,
                  finish_late=finish is not None and finish > 10,
                  forecast_late=forecast_delta is not None and forecast_delta > 10)
    return result
