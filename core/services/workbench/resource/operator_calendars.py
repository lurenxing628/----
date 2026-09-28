"""个人工作日历的工作台适配层。只改一个人的日历，不碰全局日历和班次档案。

个人日历会整体盖过班次轮换：排产读到某人某天的个人日历行时，就不再叠加他的班次档案。所以这一层
必须把"哪些天有个人行"如实报给界面，绝不凭空补行，也绝不把默认规则固化成数据。

范围清除是这一层存在的另一半理由：个人日历原先没有任何批量删除入口，导错一年只能逐日改或者删人。
"""

from __future__ import annotations

import calendar as calendar_module
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager, in_transaction_context
from core.models.calendar_periods import decode_periods
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_operator_calendar import (
    normalize_operator_calendar_input,
    operator_calendar_date,
    operator_domain_fields,
    operator_range_dates,
)
from core.services.scheduler.calendar.defaults import read_default_periods
from core.services.scheduler.calendar.service import CalendarService
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

_PUBLIC_FIELDS = ("day_type", "shift_start", "shift_end", "shift_hours", "efficiency",
                  "allow_normal", "allow_urgent", "remark")


def _patch_day_hours(payload, fields, before):
    payload.update(operator_domain_fields(fields))
    if "shiftEnd" in fields and fields["shiftEnd"] is None:
        payload.pop("shift_hours", None)
    if fields.get("type") == "work" and before["row"] is not None and before["row"]["day_type"] == "holiday":
        payload.pop("shift_hours", None)
    if payload.get("day_type") == "holiday":
        payload["shift_start"] = payload["shift_end"] = None
        payload["shift_hours"] = 0
        if payload.get("periods_json") is not None or "periods" in payload:
            payload["periods"] = []


def _date_key(value: Any) -> str:
    if type(value) is date:
        return value.isoformat()
    try:
        return operator_calendar_date(value)
    except ValidationError as exc:
        raise WorkbenchCommandRejected("constraint_conflict", "存储的个人日历日期无效，不能当作本地日期读取。") from exc


class WorkbenchOperatorCalendarService:
    def __init__(self, conn, operator_code: str, logger=None, *, clock: Callable[[], datetime] = datetime.now):
        self.conn = conn
        self.operator_code = operator_code
        self._clock = clock
        self._calendar = CalendarService(conn, logger=logger)
        self._query = WorkbenchCalendarQueryRepository(conn, logger=logger)
        self._tx = TransactionManager(conn)

    @staticmethod
    def normalize(action: str, payload: Any) -> Dict[str, Any]:
        return normalize_operator_calendar_input(action, payload)

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("日历时钟必须使用无时区的工厂本地时间。")
        return now.replace(microsecond=0)

    # ---------- 读 ----------

    def range_states(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """这段日期里这个人已经单独设过的天；没设过的日期不出现在结果里。"""
        rows: Dict[str, Dict[str, Any]] = {}
        for row in self._query.operator_calendar_rows(self.operator_code, start_date, end_date):
            row["date"] = _date_key(row["date"])
            rows[row["date"]] = row
        histories: Dict[str, List[Dict[str, Any]]] = {}
        for identity in self._query.operator_identity_rows(self.operator_code, start_date, end_date):
            day = _date_key(identity["entity_key"].split(":", 1)[1])
            histories.setdefault(day, []).append(identity)
        result: Dict[str, Dict[str, Any]] = {}
        for day in sorted(rows.keys() | histories.keys()):
            row, history = rows.get(day), histories.get(day, [])
            active = [item for item in history if item["active"] == 1]
            if len(active) != (1 if row is not None else 0):
                raise WorkbenchCommandRejected("constraint_conflict", "个人日历与永久编号不一致，请检查数据后重试。")
            result[day] = {"row": row, "identity": active[0] if active else None, "history": history}
        return result

    @staticmethod
    def _state(day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        state = states.get(day, {"row": None, "identity": None, "history": []})
        identity = state["identity"]
        return {"date": day, "explicit": state["row"] is not None,
                "calendar_ref": identity["ref"] if identity else None,
                "revision": identity["revision"] if identity else None, **state}

    def snapshot(self, date_value: str) -> Dict[str, Any]:
        day = operator_calendar_date(date_value)
        with self._tx.transaction():
            return self._state(day, self.range_states(day, day))

    def month(self, year: int, month: int) -> Dict[str, Any]:
        """一个月的个人日历。没有单独设置的日期只回 explicit=False，不替排产猜它当天怎么上班。"""
        if type(year) is not int or type(month) is not int or not 1 <= year <= 9999 or not 1 <= month <= 12:
            raise ValidationError("年月不合法，月份应为 1 至 12。", field="month")
        first = date(year, month, 1)
        count = calendar_module.monthrange(year, month)[1]
        last, now = first.replace(day=count), self._now()
        with self._tx.transaction():
            states = self.range_states(first.isoformat(), last.isoformat())
            days = []
            for offset in range(count):
                day = first + timedelta(days=offset)
                state = self._state(day.isoformat(), states)
                days.append({**state, "day": day.day, "weekday": day.weekday(),
                             "is_weekend": day.weekday() >= 5, "is_today": day == now.date()})
        cells = [None] * first.weekday() + days
        cells += [None] * (-len(cells) % 7)
        return {"operator_code": self.operator_code, "year": year, "month": month,
                "as_of": now.isoformat(timespec="seconds"), "time_basis": "factory_local",
                "days": days, "cells": cells, "default_periods": read_default_periods(self.conn),
                "previous_month": self._adjacent(year, month, -1), "next_month": self._adjacent(year, month, 1),
                "stats": {"configured": sum(day["explicit"] for day in days),
                          "work_days": sum(day["explicit"] and day["row"]["shift_hours"] > 0 for day in days)}}

    @staticmethod
    def _adjacent(year: int, month: int, delta: int) -> Optional[Dict[str, int]]:
        shifted_year, shifted_month = divmod(year * 12 + month - 1 + delta, 12)
        return {"year": shifted_year, "month": shifted_month + 1} if 1 <= shifted_year <= 9999 else None

    # ---------- 供日历文件家族使用的公开入口 ----------
    # 文件导入要一次处理很多人很多天，逐日调 snapshot() 会开上千次事务、查上万次库，
    # 所以这三个入口把"一次读回整段 / 算一天 / 写一天"拆开，由调用方持有一个事务。

    def day_state(self, day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """这个人某一天的完整状态。states 必须来自同一次 range_states。"""
        return self._state(day, states)

    def proposed_row(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Dict[str, Any]:
        """按领域规则算出这一天保存后的行；与人员详情面板走同一条一致性校验，不合规直接抛拒绝。

        fields 用的是界面字段名（type/shiftStart/shiftEnd/eff/allowNormal/allowUrgent/note），
        不经过界面的输入模型，取值合法性由调用方自己校验。
        """
        return self._proposed(fields, before)

    def write_day(self, before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> WorkbenchCommandOutcome:
        """写这个人的一天。必须由外层 WorkbenchCommandService 持有写事务。"""
        self._require_write_transaction()
        return self._write(before, after)

    # ---------- 写 ----------

    def _proposed(self, fields: Dict[str, Any], before: Dict[str, Any]) -> Dict[str, Any]:
        """以这一天的原行为基底再打补丁，没给的项保持原样。

        旧行可能只保存开始和工时；非时间修改须保留这段工时。
        明确填写起止或多时段时由领域层重算；改休息日时清空班次和工时。
        """
        payload: Dict[str, Any] = {"operator_id": self.operator_code, "date": before["date"]}
        if before["row"] is not None:
            payload.update({key: before["row"][key] for key in
                            ("day_type", "shift_start", "shift_end", "shift_hours", "efficiency",
                             "allow_normal", "allow_urgent", "remark", "periods_json")})
        if payload.get("periods_json") is not None and "periods" not in fields and fields.get("type") != "rest":
            if {"shiftStart", "shiftEnd"} & fields.keys():
                raise ValidationError("这一天已按多时段设置，请修改逐段起止时间。", field="fields.periods")
        _patch_day_hours(payload, fields, before)
        proposed = self._calendar._admin._build_operator_calendar_from_payload(payload).to_dict()
        if self._calendar._admin._build_operator_calendar_from_payload(proposed).to_dict() != proposed:
            raise WorkbenchCommandRejected("constraint_conflict", "填的班次换算后存不稳，请核对班次起止。")
        return proposed

    def _require_write_transaction(self) -> None:
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("个人日历写入必须由外层 WorkbenchCommandService 持有写事务。")

    def apply(self, action: str, normalized_input: Dict[str, Any], checked: Any) -> WorkbenchCommandOutcome:
        self._require_write_transaction()
        payload = self.normalize(action, normalized_input)
        if action == "range_clear":
            return self._clear_range(payload, checked)
        if action not in ("upsert", "delete"):
            raise ValidationError("不支持的个人日历操作。", field="action")
        before = self.snapshot(payload["date"])
        if checked != before:
            raise WorkbenchCommandRejected("stale_write", "这一天的个人日历已变化，请刷新后重新核对。")
        after = self._proposed(payload["fields"], before) if action == "upsert" else None
        return self._write(before, after)

    def _write(self, before: Dict[str, Any], after: Optional[Dict[str, Any]]) -> WorkbenchCommandOutcome:
        day, ref = before["date"], before["calendar_ref"]
        if after == before["row"]:
            return WorkbenchCommandOutcome("unchanged", {"date": day, "calendar_ref": ref})
        if after is None:
            self._calendar.delete_operator_calendar(self.operator_code, day)
        else:
            self._calendar.upsert_operator_calendar_no_tx(after)
        saved = self.snapshot(day)
        if saved["row"] != after:
            raise RuntimeError("个人日历保存结果与预览不一致，不能确认保存。")
        if after is not None and before["row"] is not None and (
                saved["calendar_ref"] != ref or saved["revision"] != before["revision"] + 1):
            raise RuntimeError("个人日历更新未保持永久引用及修订号，不能确认保存。")
        return WorkbenchCommandOutcome("committed", {"date": day, "calendar_ref": saved["calendar_ref"] or ref})

    def preview_range_clear(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """只读：这段日期里有哪些天是单独设过的，清除后会恢复成班次或全局日历。"""
        request = self.normalize("range_clear", payload)
        with self._tx.transaction():
            states = self.range_states(request["start_date"], request["end_date"])
        days = [self._state(day, states) for day in operator_range_dates(request["start_date"], request["end_date"])
                if states.get(day, {}).get("row") is not None]
        return {"request": request, "days": days, "count": len(days)}

    def _clear_range(self, payload: Dict[str, Any], checked: Any) -> WorkbenchCommandOutcome:
        current = self.preview_range_clear(payload)
        if checked is not None and checked != current:
            raise WorkbenchCommandRejected("stale_write", "这段日期里的个人日历已变化，请重新点「预览变更」。")
        results = [self._write(state, None) for state in current["days"]]
        return WorkbenchCommandOutcome("committed" if any(item.result == "committed" for item in results) else "unchanged",
                                       {"dates": [{**item.data, "result": item.result} for item in results],
                                        "cleared_count": sum(item.result == "committed" for item in results)})

    @staticmethod
    def public_day(state: Dict[str, Any]) -> Dict[str, Any]:
        """对外投影：只暴露这一天的业务字段与是否单独设置，不暴露内部修订号以外的元数据。"""
        row = state["row"]
        return {"date": state["date"], "explicit": state["explicit"],
                "calendar_ref": state["calendar_ref"],
                "periods": decode_periods(row.get("periods_json")) if row is not None else None,
                **({key: row[key] for key in _PUBLIC_FIELDS} if row is not None
                   else {key: None for key in _PUBLIC_FIELDS})}
