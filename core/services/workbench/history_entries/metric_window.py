"""Fixed resource window anchored at each saved source's own scheduling start."""

from datetime import timedelta

from core.models.workbench_run_candidate import local_time

from .packets import HistoryPacket, LightRunPacket, RunPacket, TrialPacket


def _fixed_window(anchor, days):
    """The anchor is a saved source's start; without one, or unreadable, the fixed window is unknown."""
    if anchor is None:
        return None, None
    try:
        start = local_time(anchor)
        return start.isoformat(), (start + timedelta(days=days)).isoformat()
    except (ValueError, OverflowError):
        # 保存的起点不是工厂本地时间，或加上窗口天数超出可表示的日期。
        return None, None


def _source_settings(packet: HistoryPacket):
    """The run settings a source recorded; an unavailable source saved none, and a trial's are its source's."""
    if isinstance(packet, RunPacket):
        return packet.capture["input"]
    if isinstance(packet, LightRunPacket):
        return packet.run_input
    if isinstance(packet, TrialPacket):
        return packet.origin.source.settings
    return None


def history_window(packet: HistoryPacket, query):
    start, end = query["range_start"], query["range_end"]
    absolute = start is not None
    days = None
    if not absolute:
        days = query["resource_window_days"]
        settings = _source_settings(packet)
        start, end = _fixed_window(settings["start_date"] + "T00:00:00" if settings is not None else None, days)
    reason = None if start is not None and end is not None else {
        "code": "history_window_start_missing", "message": "保存来源未记录有效排产起点，固定资源窗口未知。"}
    return {"mode": "absolute" if absolute else "fixed_days", "start": start, "end": end, "days": days,
            "anchor": "common_absolute_window" if absolute else "source_start", "time_basis": "factory_local",
            "boundary": "half_open", "state": "available" if reason is None else "unavailable", "reason": reason,
            "cohort": {"machine_refs": None, "operator_refs": None}}
