"""Private global calendar adapter. No HTTP routes, personal calendars or shift profiles."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager, in_transaction_context
from core.models.calendar import WorkCalendar
from core.models.calendar_periods import decode_periods, encode_periods
from core.models.workbench_calendar import (
    CALENDAR_PREVIEW_TTL_SECONDS,
    CalendarRangePreview,
    calendar_date,
    calendar_domain_fields,
    calendar_range_dates,
    normalize_calendar_input,
)
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, input_fingerprint
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.calendar.service import CalendarService
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

from .calendar_summary import owned_hours


def _date_key(value: Any) -> str:
    # get_connection enables SQLite DATE conversion. datetime is deliberately not a date key.
    if type(value) is date:
        return value.isoformat()
    try:
        return calendar_date(value)
    except ValidationError as exc:
        raise WorkbenchCommandRejected("constraint_conflict", "存储日历的日期无效，不能当作本地日期读取。") from exc


class _CalendarProjection(CalendarEngine):
    """Overlay raw/proposed global rows (keyed by date) on the existing engine, without SQL writes."""

    def __init__(self, rows: Dict[str, Dict[str, Any]], periods=None):
        super().__init__(None)
        self._default_periods_json = encode_periods(periods)
        self._rows = rows

    def _resolve_calendar_row(self, date_str: str, op_id: Optional[str]) -> WorkCalendar:
        # 用到哪天才解析哪天：月合计多读的次月 1 日即使存坏了，也只让合计未知，不牵连本月。
        row = self._rows.get(date_str)
        return WorkCalendar.from_row(row) if row is not None else self._default_for_date(date_str)


def _effective(day: str, row: Optional[Dict[str, Any]], periods=None) -> Dict[str, Any]:
    # Date-key policy is deliberate: midnight may still belong to yesterday's shift.
    try:
        policy = _CalendarProjection({day: row} if row is not None else {}, periods)._policy_for_date(day)
    except OverflowError as exc:
        raise ValidationError(f"{day} 的工作时段超出了系统能处理的最后日期 9999-12-31，算不出这一天的工作时间。"
                              "请让这一天的班次在当天结束：单独设置过的改这一天，没设置过的改默认工作时间。",
                              field="date") from exc
    normal, urgent = policy.is_priority_allowed("normal"), policy.is_priority_allowed("urgent")
    working = policy.shift_hours > 0 and (normal or urgent)
    start, end = policy.work_window()
    return {"type": "work" if working else "rest", "day_type": policy.day_type,
            "is_working": working, "is_rest": not working, "hours": policy.shift_hours,
            "effective_hours": policy.shift_hours * policy.efficiency if working else 0.0,
            "efficiency": policy.efficiency, "eff": policy.efficiency * 100,
            "allowNormal": "yes" if normal else "no", "allowUrgent": "yes" if urgent else "no",
            "periods": decode_periods(policy.periods_json),
            "windows": [{"start": left.isoformat(), "end": right.isoformat()} for left, right in policy.work_windows()],
            "window_start": start.isoformat(timespec="seconds"), "window_end": end.isoformat(timespec="seconds")}


# 旧库升级加列时没有回填，这几列可能空着；日历引擎和日历页都按班表默认值解释它们。
_LEGACY_BLANK_COLUMNS = ("shift_start", "shift_end", "shift_hours", "efficiency")


def _defaulted_blanks(day: str, row: Dict[str, Any], proposed: Dict[str, Any]) -> set:
    """旧行空着的班次列被保存规则补成具体值：这一天按引擎算出的时段、工时、效率都不变，就算推导列。

    补出的值和引擎原来的解释不一样（例如假期空着效率，引擎按 1 算、保存规则补成假期默认效率）仍算改写，照旧拒绝。
    """
    blanks = {name for name in _LEGACY_BLANK_COLUMNS
              if row.get(name) is None or isinstance(row.get(name), str) and not row[name].strip()}
    if not blanks:
        return set()
    filled = {**row, **{name: proposed.get(name) for name in blanks}}
    try:
        return blanks if _effective(day, row) == _effective(day, filled) else set()
    except ValidationError:
        return set()


def _owned_effective_hours(days: List[Dict[str, Any]], projection: CalendarEngine) -> Optional[float]:
    """月合计按排产真正可用的时段算：跨夜尾巴和次日班次重叠的部分只算给次日一次。

    逐日的 effective_hours 绑在写入快照里，只看这一天自己的配置，不在这里改。
    次日（可能是下个月 1 日）的日历读不出来时合计记为未知，不拿可能重复的数字充数。
    """
    try:
        return sum(owned_hours(projection, date.fromisoformat(day["date"])) * day["effective"]["efficiency"]
                   for day in days if day["effective"]["is_working"])
    except ValueError:
        return None


def _month_stats(days: List[Dict[str, Any]], projection: CalendarEngine) -> Dict[str, Any]:
    """Count explicit rows separately from configured capacity and default overrides."""
    return {"work_days": sum(day["effective"]["is_working"] for day in days),
            "configured": sum(day["explicit"] for day in days),
            "configured_work_days": sum(day["explicit"] and day["effective"]["is_working"] for day in days),
            "rest_days": sum(day["effective"]["is_rest"] for day in days),
            "overrides": sum(day["explicit"] and day["is_weekend"] == day["effective"]["is_working"] for day in days),
            "weekend_rest": sum(day["is_weekend"] and day["effective"]["is_rest"] for day in days),
            "effective_hours": _owned_effective_hours(days, projection)}


class WorkbenchCalendarService:
    def __init__(self, conn, logger=None, *, clock: Callable[[], datetime] = datetime.now):
        self.conn = conn
        self._clock = clock
        self._calendar = CalendarService(conn, logger=logger)
        self._query = WorkbenchCalendarQueryRepository(conn, logger=logger)
        self._tx = TransactionManager(conn)

    @staticmethod
    def normalize(action: str, payload: Any) -> Dict[str, Any]:
        """Private pure input API; see normalize_calendar_input for the complete shapes."""
        return normalize_calendar_input(action, payload)

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("日历时钟必须使用无时区的工厂本地时间。")
        return now.replace(microsecond=0)

    def range_states(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Merge raw rows with lifetime refs per date; caller owns one transaction for both reads.

        Tombstones detect absent -> created -> deleted ABA. An absent date has row=None
        and identity=None; a GET never invents a ref. A stored date that is not a real
        local date, or a row whose active refs are not exactly one, is a data conflict.
        """
        self._calendar._engine.clear_policy_cache()
        rows: Dict[str, Dict[str, Any]] = {}
        for row in self._query.calendar_rows(start_date, end_date):
            row["date"] = _date_key(row["date"])
            rows[row["date"]] = row
        histories: Dict[str, List[Dict[str, Any]]] = {}
        for identity in self._query.identity_rows(start_date, end_date):
            identity["entity_key"] = _date_key(identity["entity_key"])
            histories.setdefault(identity["entity_key"], []).append(identity)
        result = {}
        for day in sorted(rows.keys() | histories.keys()):
            row, history = rows.get(day), histories.get(day, [])
            active = [item for item in history if item["active"] == 1]
            if len(active) != (1 if row is not None else 0):
                raise WorkbenchCommandRejected("constraint_conflict", "日历与永久引用不一致，请检查数据后重试。")
            result[day] = {"row": row, "identity": active[0] if active else None, "history": history}
        return result

    def _snapshot(self, day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        state = states.get(day, {"row": None, "identity": None, "history": []})
        identity = state["identity"]
        return {"date": day, "explicit": state["row"] is not None,
                "calendar_ref": identity["ref"] if identity else None,
                "revision": identity["revision"] if identity else None,
                **state, "default_periods": self._calendar._engine.default_periods(),
                "effective": _effective(day, state["row"], self._calendar._engine.default_periods())}

    def snapshot(self, date_value: str) -> Dict[str, Any]:
        """Private full guard state, not public DTO: raw row, ref/revision and tombstones.

        No record differs from a stored row, even when both compute the same policy.
        Absent rows have no current ref/revision; historical refs remain in history.
        The HTTP owner must bind this full snapshot to its short-lived write context.
        """
        day = calendar_date(date_value)
        with self._tx.transaction():
            return self._snapshot(day, self.range_states(day, day))

    def month(self, year: int, month: int) -> Dict[str, Any]:
        """Private monthly read: one-based month, real date cells, Monday-first padding.

        Counts/policies use actual domain results, not weekday guesses. No statutory
        holiday feed exists: unconfigured weekdays remain normal domain defaults.
        Rows carry internal revisions for HTTP context assembly, never for public URLs.
        """
        if type(year) is not int or type(month) is not int or not 1 <= year <= 9999 or not 1 <= month <= 12:
            raise ValidationError("年月不合法，月份应为 1 至 12。", field="month")
        first = date(year, month, 1)
        count = calendar.monthrange(year, month)[1]
        last, now = first.replace(day=count), self._now()
        with self._tx.transaction():
            states = self.range_states(first.isoformat(), last.isoformat())
            days = []
            for offset in range(count):
                day = first + timedelta(days=offset)
                snapshot = self._snapshot(day.isoformat(), states)
                days.append({**snapshot, "day": day.day, "weekday": day.weekday(),
                             "is_weekend": day.weekday() >= 5, "is_today": day == now.date()})
            rows = {day: state["row"] for day, state in states.items() if state["row"] is not None}
            rows.update(self._following_row(last, days[-1]))
        cells = [None] * first.weekday() + days
        cells += [None] * (-len(cells) % 7)
        periods = self._calendar._engine.default_periods()
        projection = _CalendarProjection(rows, periods)
        return {"year": year, "month": month, "as_of": now.isoformat(timespec="seconds"),
                "time_basis": "factory_local", "days": days, "cells": cells,
                "previous_month": self._adjacent(year, month, -1), "next_month": self._adjacent(year, month, 1),
                "default_periods": periods, "stats": _month_stats(days, projection)}

    def _following_row(self, last: date, tail: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """月末班次跨过零点时，才补读次月 1 日那一行：重叠段归它，月合计要扣掉。

        这一行只用于月合计，不进本月的日期状态，也不核对永久引用；读坏了只让合计未知，不牵连本月。
        """
        if last == date.max:
            return {}
        following = (last + timedelta(days=1)).isoformat()
        if tail["effective"]["window_end"] <= following + "T00:00:00":
            return {}
        # 日期是主键，按这一天查最多一行。
        rows = self._query.calendar_rows(following, following)
        return {following: {**rows[0], "date": following}} if rows else {}

    @staticmethod
    def _adjacent(year: int, month: int, delta: int) -> Optional[Dict[str, int]]:
        shifted_year, shifted_month = divmod(year * 12 + month - 1 + delta, 12)
        return {"year": shifted_year, "month": shifted_month + 1} if 1 <= shifted_year <= 9999 else None

    # ---------- 供日历文件家族使用的公开入口 ----------
    # 文件导入要一次处理上千天，逐日调 snapshot() 会开上千次事务、查上万次库（见 roadmap 4.7），
    # 所以这几个入口把"一次读回整段 / 算一天 / 写一天"拆开，由调用方持有一个事务。

    def day_state(self, day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """某一天的完整状态。states 必须来自同一次 range_states。"""
        return self._snapshot(day, states)

    def proposed_row(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """按领域规则算出这一天保存后的行；与界面走同一条一致性校验，不合规直接抛拒绝。

        fields 用的是界面字段名（type/hours/eff/allowNormal/allowUrgent/note），不经过界面的
        输入模型，所以文件可以表达界面表达不了的组合（例如假期带工时），取值合法性由调用方自己校验。
        """
        return self._window_checked(before["date"], self._proposed(fields, before))

    def write_day(self, before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> WorkbenchCommandOutcome:
        """写一天。必须由外层 WorkbenchCommandService 持有写事务。"""
        self._require_write_transaction()
        return self._write(before, after)

    def effective_day(self, day: str, row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """这一天按给定的行由日历引擎算出的实际安排（工时、效率、时间窗等），与日历页显示同一口径。"""
        return _effective(day, row, self._calendar._engine.default_periods())

    def _proposed(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        row = before["row"]
        if not fields:
            return row
        payload = dict(row) if row is not None else {"date": before["date"]}
        if row is None and "type" not in fields:
            default = self._calendar._engine._default_for_date(before["date"])
            payload.update(default.to_dict())
            payload["remark"] = None
        patch = calendar_domain_fields(fields)
        self._settle_periods(row, payload, patch, fields)
        payload.update(patch)
        derived = self._shift_window_is_derived(patch, row)
        if derived:
            # 工时或开工时刻改变而未明确结束时刻时，按当前开始时刻重新推算结束。
            payload["shift_end"] = None
        proposed = self._calendar._admin._build_work_calendar_from_payload(payload).to_dict()
        self._check_proposed(before, patch, proposed, derived_shift_window=derived)
        return proposed

    @staticmethod
    def _settle_periods(row: Optional[Dict[str, Any]], payload: Dict[str, Any], patch: Dict[str, Any],
                        fields: Dict[str, Any]) -> None:
        """补丁没给逐段时段时，决定原来的时段是保留、清空还是改回单班；多时段日只改班次列直接拒绝。"""
        shift_patch = "periods" not in patch and bool({"shift_hours", "shift_start", "shift_end"} & patch.keys())
        if row is None:
            if shift_patch:
                payload["periods_json"] = None
            return
        if payload.get("periods_json") is None or "periods" in patch:
            return
        if fields.get("type") == "rest":
            patch["periods"] = []
        elif shift_patch and payload["periods_json"] == "[]":
            # 休息日存成空时段，没有逐段时间要保护；填了工时或班次起止就按单班保存，
            # 与没配置过的日期、旧的休息日行同一种结果。
            patch["periods"] = None
        elif shift_patch:
            raise ValidationError("这一天已按多时段设置，请修改逐段起止时间。", field="fields.periods")

    def _window_checked(self, day: str, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """保存前先把这一天的时间窗算一遍：算不出来（例如跨出 9999-12-31）就在预检和保存前拒绝，不等写库后整批回滚。

        范围预览本来就逐日算保存后的时间窗，不走这里，免得大范围预览重复计算。
        """
        if row is not None:
            _effective(day, row, self._calendar._engine.default_periods())
        return row

    @staticmethod
    def _shift_window_is_derived(patch: Dict[str, Any], row: Optional[Dict[str, Any]]) -> bool:
        return "shift_end" not in patch and bool({"shift_hours", "shift_start"} & patch.keys())

    @staticmethod
    def _derived_names(day: str, row: Dict[str, Any], patch: Dict[str, Any], proposed: Dict[str, Any],
                       derived_shift_window: bool) -> set:
        """跟着补丁或推算规则一起变的列，不算"没改的项被改写"。"""
        # 旧行只存开始和工时时，结束时刻按开始加工时补出，班次没变，不算改写。
        legacy_open_end = row["shift_end"] is None and row["shift_start"] is not None and row.get("periods_json") is None
        names = {"shift_end"} if derived_shift_window or legacy_open_end else set()
        if "periods" in patch:
            names.update(("periods_json", "shift_start", "shift_end", "shift_hours"))
        if "shift_start" in patch or "shift_end" in patch:
            names.add("shift_hours")
        return names | _defaulted_blanks(day, row, proposed)

    def _check_proposed(self, before: Dict[str, Any], patch: Dict[str, Any], proposed: Dict[str, Any],
                        *, derived_shift_window: bool = False) -> None:
        if self._calendar._admin._build_work_calendar_from_payload(proposed).to_dict() != proposed:
            raise WorkbenchCommandRejected("constraint_conflict", "填的工时换成班次的分钟数后存不稳，请核对工时。")
        if "shift_hours" in patch and abs(proposed["shift_hours"] - patch["shift_hours"]) > 1e-9:
            raise WorkbenchCommandRejected(
                "constraint_conflict", f"{before['date']} 按原班次起止算出 {proposed['shift_hours']:g} 小时，"
                f"和你填的 {patch['shift_hours']:g} 小时对不上，所以没有保存；请先核对原班次。")
        row = before["row"]
        if row is not None:
            derived_names = self._derived_names(before["date"], row, patch, proposed, derived_shift_window)
            if any(proposed.get(name) != value for name, value in row.items()
                   if name not in patch and name not in derived_names):
                raise WorkbenchCommandRejected("constraint_conflict", "这一天没改的项会被规则改写，所以没有保存；请先核对原来的配置。")

    def _require_write_transaction(self) -> None:
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("日历写入必须由外层 WorkbenchCommandService 持有写事务。")

    def apply(self, action: str, normalized_input: Dict[str, Any], checked: Any) -> WorkbenchCommandOutcome:
        """Private command mutate callback; never owns/commits the outer write transaction.

        For upsert/delete, checked is the server-held snapshot(date) bound to the
        write context. For confirm it is the original server-held CalendarRangePreview.
        The caller validates write_token in its guard under BEGIN IMMEDIATE, using
        this same connection. Returned outcomes are provisional until the receipt
        and domain writes commit together. Receipts contain only stable dates/refs.
        """
        self._require_write_transaction()
        payload = self.normalize(action, normalized_input)
        if action == "confirm":
            return self.confirm(payload, checked)
        if action not in ("upsert", "delete"):
            raise ValidationError("「预览变更」不能当成保存操作。", field="action")
        before = self.snapshot(payload["date"])
        if checked != before:
            raise WorkbenchCommandRejected("stale_write", "日历已变化，请刷新后重新核对。")
        after = self._window_checked(payload["date"], self._proposed(payload["fields"], before)) if action == "upsert" else None
        return self._write(before, after)

    def _write(self, before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> WorkbenchCommandOutcome:
        ref, day = before["calendar_ref"], before["date"]
        if after == before["row"]:
            return WorkbenchCommandOutcome("unchanged", {"date": day, "calendar_ref": ref})
        if after is None:
            self._calendar.delete(day)
        else:
            self._calendar.upsert_no_tx(after)
        saved = self.snapshot(day)
        if saved["row"] != after:
            raise RuntimeError("日历保存结果与领域预览不一致，不能确认保存。")
        if after is not None and before["row"] is not None and (
                saved["calendar_ref"] != ref or saved["revision"] != before["revision"] + 1):
            raise RuntimeError("日历更新未保持永久引用及修订号，不能确认保存。")
        return WorkbenchCommandOutcome("committed", {"date": day, "calendar_ref": saved["calendar_ref"] or ref})

    def _preview_days(self, request: Dict[str, Any], expected: Optional[CalendarRangePreview] = None) -> Dict[str, Any]:
        dates = calendar_range_dates(request)
        if expected is not None and dates != expected.dates:
            raise WorkbenchCommandRejected("snapshot_stale", "命中的日期已经变了，请重新点「预览变更」。")
        states = self.range_states(request["start_date"], request["end_date"])
        days = []
        for index, day in enumerate(dates):
            before = self._snapshot(day, states)
            if expected is not None and before != expected.days[index]["before"]:
                raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历已经变了，请重新点「预览变更」。")
            row = self._proposed(request["fields"], before) if request["operation"] == "upsert" else None
            days.append({"date": day, "before": before,
                         "after": {"explicit": row is not None, "row": row, "default_periods": self._calendar._engine.default_periods(), "effective": _effective(day, row, self._calendar._engine.default_periods())}})
        return {"request": request, "dates": dates, "days": days}

    def preview(self, payload: Dict[str, Any]) -> CalendarRangePreview:
        """Read-only bounded preview. No placeholder rows, business writes or long lock.

        Weekday/weekend means Gregorian Mon-Fri/Sat-Sun, including configured holidays
        and overtime, exactly as the prototype. Conflicting hidden shift windows reject
        the preview instead of advertising hours that the domain would not save.
        """
        request, now = self.normalize("preview", payload), self._now()
        with self._tx.transaction():
            facts = self._preview_days(request)
        facts.update(preview_ref=uuid.uuid4().hex, created_at=now.isoformat(timespec="seconds"),
                     expires_at=(now + timedelta(seconds=CALENDAR_PREVIEW_TTL_SECONDS)).isoformat(timespec="seconds"))
        return CalendarRangePreview(**facts, fingerprint=input_fingerprint(facts))

    def confirm(self, normalized_input: Dict[str, Any], preview: CalendarRangePreview) -> WorkbenchCommandOutcome:
        """Private confirm callback, inside the same outer write transaction and receipt.

        Revalidate TTL, exact date set and every complete before/after snapshot before
        any writes. Any later failure propagates to the owner for whole-batch rollback.
        A stale preview never silently selects fresh dates or substitutes another ref.
        """
        self._require_write_transaction()
        payload = self.normalize("confirm", normalized_input)
        if not isinstance(preview, CalendarRangePreview) or preview.preview_ref != payload["preview_ref"]:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已失效，请重新点「预览变更」。")
        now = self._now().isoformat(timespec="seconds")
        if not preview.created_at <= now < preview.expires_at or input_fingerprint(preview.facts()) != preview.fingerprint:
            raise WorkbenchCommandRejected("snapshot_stale", "这份变更清单已过期或内容有变化，请重新点「预览变更」。")
        current = self._preview_days(self.normalize("preview", preview.request), expected=preview)
        if current != {"request": preview.request, "dates": preview.dates, "days": preview.days}:
            raise WorkbenchCommandRejected("snapshot_stale", "范围里的日历或命中的日期已经变了，请重新点「预览变更」。")
        results = [self._write(item["before"], item["after"]["row"]) for item in current["days"]]
        return WorkbenchCommandOutcome("committed" if any(item.result == "committed" for item in results) else "unchanged",
                                       {"dates": [{**item.data, "result": item.result} for item in results]})
