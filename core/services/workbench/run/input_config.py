"""A validated one-run configuration copy with no bootstrap or write service."""

from dataclasses import replace
from datetime import datetime, timedelta

from core.errors import ValidationError
from core.models.workbench_preflight import hold_window_bounds, local_date
from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot
from data.repositories.config_repo import ConfigRepository


def configuration_snapshot(conn):
    return build_schedule_config_snapshot(ConfigRepository(conn), strict_mode=True)


def candidate_config(conn, settings, *, snapshot=None):
    # 工作台不按配置里的冻结开关和天数推算窗口：不重排时段由 hold_window() 定好后显式交给冻结逻辑。
    return replace(
        configuration_snapshot(conn) if snapshot is None else snapshot,
        enforce_ready_default="yes" if settings["ready_check"] else "no",
        auto_assign_enabled="yes" if settings["missing_resource_policy"] == "auto_assign" else "no",
        auto_assign_persist="no",
        graph_analysis_mode="on",
        freeze_window_enabled="no",
        freeze_window_days=0,
    )


def hold_window(conn, settings, *, snapshot=None):
    """本次不重排时段 ((开始, 结束) 或 None, 来源)。

    本次参数带了 hold_window 就照它（null 即不设，来源 explicit）；没带这个键（旧调用、旧排产记录、页面还没动过）
    按交付设置推算：「锁定近期排程」开着且天数 N>0 时为 [排产起日 00:00, 起日后 N 天 00:00)，来源 default。
    交付设置读不出来时按不设处理，由排产计算按原样报出是哪项参数。
    """
    if "hold_window" in settings:
        return hold_window_bounds(settings["hold_window"]), "explicit"
    try:
        cfg = configuration_snapshot(conn) if snapshot is None else snapshot
    except ValidationError:
        return None, "default"
    days = cfg.freeze_window_days if str(cfg.freeze_window_enabled).strip().lower() == "yes" else 0
    if not isinstance(days, int) or days <= 0:
        return None, "default"
    start = datetime.combine(local_date(settings["start_date"]), datetime.min.time())
    try:
        end = start + timedelta(days=days)
    except OverflowError:
        end = datetime.max.replace(second=0, microsecond=0)  # 天数大到越过 9999 年：按一直保留到最后处理
    return (start, end), "default"


def window_label(window):
    """不重排时段的提示写法，精确到分。"""
    return f"{window[0]:%Y-%m-%d %H:%M} 至 {window[1]:%Y-%m-%d %H:%M}" if window else "未设"


def window_text(window):
    """(开始, 结束) 的页面写法，精确到分。"""
    return {"start": window[0].strftime("%Y-%m-%dT%H:%M"), "end": window[1].strftime("%Y-%m-%dT%H:%M")} if window else None
