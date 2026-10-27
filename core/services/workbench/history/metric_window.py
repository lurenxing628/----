"""Fixed resource window anchored at each saved source's own scheduling start."""

from datetime import timedelta

from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_candidate import local_time


def _fixed_window(anchor, days):
    """The anchor is a saved source value; unreadable text leaves the fixed window unknown."""
    if type(anchor) is not str:
        return None, None
    try:
        start = local_time(anchor.replace(" ", "T"))
        return start.isoformat(), (start + timedelta(days=days)).isoformat()
    except (ValueError, OverflowError):
        # 保存的起点不是工厂本地时间，或加上窗口天数超出可表示的日期。
        return None, None


def history_window(packet, query):
    start, end = query["range_start"], query["range_end"]
    absolute = start is not None
    days = None
    if not absolute:
        days = query["resource_window_days"]
        anchor = None
        if packet["kind"] == "run" and packet["capture"] is not None:
            anchor = preflight_window(packet["capture"]["input"])[0]
        elif packet["kind"] == "trial" and packet["saved"] is not None:
            admission = packet["head"]["admission"]
            source = admission["source"]
            inputs = (admission["input"], (source.get("capture") or {}).get("input") or {},
                      source.get("material_policy") or {})
            explicit = next((values for values in inputs if "start_date" in values), None)
            if explicit is not None:
                day = explicit["start_date"]
                anchor = day + "T00:00:00" if type(day) is str else None
        start, end = _fixed_window(anchor, days)
    reason = None if start is not None and end is not None else {
        "code": "history_window_start_missing", "message": "保存来源未记录有效排产起点，固定资源窗口未知。"}
    return {"mode": "absolute" if absolute else "fixed_days", "start": start, "end": end, "days": days,
            "anchor": "common_absolute_window" if absolute else "source_start", "time_basis": "factory_local",
            "boundary": "half_open", "state": "available" if reason is None else "unavailable", "reason": reason,
            "cohort": {"machine_refs": None, "operator_refs": None}}
