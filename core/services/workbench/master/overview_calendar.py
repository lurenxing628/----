"""Inspect stored global dates only, without filling defaults or extending a range."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors import ValidationError
from core.models.calendar_periods import decode_periods, period_hours
from core.shared.stored_dates import stored_date
from core.shared.strict_parse import is_stored_number

from .overview_facts import plain
from .overview_graph import text

if TYPE_CHECKING:
    from .overview_graph import MasterOverviewGraph

VALUE_TEXT = {"workday": "工作日", "weekend": "周末", "holiday": "节假日", "yes": "允许", "no": "不允许"}


def add_calendar(graph: MasterOverviewGraph):
    for row in graph.facts.rows("WorkCalendar"):
        day = plain(row["date"])
        entity = graph.add("calendar", row["date"], day, "全局工作日历")
        valid = stored_date(day) is not None
        graph.field(entity, "日期", day, "WorkCalendar.date", valid=valid)
        if not valid:
            graph.issue(entity, "calendar.date", "日历日期无效", "资料里记的日期是「" + text(day) + "」，不是年-月-日格式。")
            entity["target"]["unavailable_reason"] = "这一天的日期填得不对，系统定不出是哪个月，请先核对资料里的日期。"
        for key, label, allowed in (("day_type", "日期类型", ("workday", "weekend", "holiday")),
                                    ("allow_normal", "允许普通任务", ("yes", "no")),
                                    ("allow_urgent", "允许紧急任务", ("yes", "no"))):
            graph.field(entity, label, VALUE_TEXT.get(row[key], row[key]), "WorkCalendar." + key, valid=row[key] in allowed)
            if row[key] not in allowed:
                graph.issue(entity, "calendar." + key, label + "待核对", "资料里记的是「" + text(row[key]) + "」，不在允许填的取值里。")
        valid_efficiency = is_stored_number(row["efficiency"], positive=True)
        graph.field(entity, "效率系数", row["efficiency"], "WorkCalendar.efficiency", valid=valid_efficiency)
        if not valid_efficiency:
            graph.issue(entity, "calendar.efficiency", "效率系数待核对", "资料里记的是" + text(row["efficiency"]) + "，请核对。")
        _periods(graph, entity, row)
        graph.field(entity, "备注", row["remark"], "WorkCalendar.remark", required=False)


def _periods(graph: MasterOverviewGraph, entity, row):
    try:
        periods = decode_periods(row["periods_json"])
    except ValidationError as exc:
        graph.issue(entity, "calendar.periods_invalid", "工作时段无效", exc.message)
        return
    label = "、".join(("次日 " if p["day_offset"] else "") + p["start"] + " 至 "
                     + ("次日 " if p["end"] <= p["start"] else "") + p["end"] for p in periods)
    graph.field(entity, "实际工作时段", label or "无工作时段", "WorkCalendar.periods_json", required=False)
    graph.field(entity, "可排工时（小时）", period_hours(periods), "WorkCalendar.periods_json", required=False)
