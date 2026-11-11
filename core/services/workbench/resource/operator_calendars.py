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
from core.infrastructure.transaction import in_transaction_context
from core.infrastructure.workbench_metadata_schema import entity_key
from core.models.calendar import OperatorCalendar
from core.models.workbench_calendar import (
    calendar_date,
    calendar_domain_fields,
    form_field_error,
    require_periods_when_rest_turns_work,
)
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_operator_calendar import normalize_operator_calendar_input
from core.services.scheduler.calendar.admin import CalendarAdmin, CalendarNormalizationContext
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.workbench.facts.calendar_inputs import calendar_inputs_from_connection
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

from .calendar_reading import CalendarProjection, effective_calendar_day, is_working_row

_PUBLIC_FIELDS = ("day_type", "efficiency", "allow_normal", "allow_urgent", "remark")


def _date_key(value: Any) -> str:
    if type(value) is date:
        return value.isoformat()
    try:
        return calendar_date(value)
    except ValidationError as exc:
        raise WorkbenchCommandRejected("constraint_conflict", "存储的个人日历日期无效，不能当作本地日期读取。") from exc


class WorkbenchOperatorCalendarService:
    def __init__(self, conn, operator_code: str, logger=None, *, clock: Callable[[], datetime] = datetime.now,
                 calendar_admin: Optional[CalendarAdmin] = None):
        self.conn = conn
        self.operator_code = operator_code
        self.logger = logger
        self._clock = clock
        self._admin = CalendarAdmin(conn, logger=logger) if calendar_admin is None else calendar_admin
        self._engine: Optional[CalendarEngine] = None
        self._query = WorkbenchCalendarQueryRepository(conn, logger=logger)

    def _base_engine(self) -> CalendarEngine:
        if self._engine is None:
            self._engine = CalendarEngine(calendar_inputs_from_connection(self.conn, public_days=()))
        return self._engine

    def _normalization_context(self) -> CalendarNormalizationContext:
        return CalendarNormalizationContext(
            self.conn,
            logger=self.logger,
            period_reader=lambda: self._base_engine().default_periods(),
        )

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
        return self.states_from_rows(
            self._query.operator_calendar_rows(self.operator_code, start_date, end_date),
            self._query.operator_identity_rows(self.operator_code, start_date, end_date))

    @staticmethod
    def states_from_rows(calendar_rows, identities) -> Dict[str, Dict[str, Any]]:
        """单人读取和文件批读共用同一条日期、永久编号与历史状态规则。"""
        rows: Dict[str, Dict[str, Any]] = {}
        for row in calendar_rows:
            row["date"] = _date_key(row["date"])
            rows[row["date"]] = row
        histories: Dict[str, List[Dict[str, Any]]] = {}
        for identity in identities:
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

    def _listed_state(self, day: str, states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """月历和范围预览列出的一天：单独设置过的行经引擎缓存解码一次时段，月合计和 public_day 共用这一份。"""
        state = self._state(day, states)
        row = state["row"]
        state["periods"] = None if row is None else self._base_engine().decoded_periods_for_json(row["periods_json"])
        return state

    def month(self, year: int, month: int) -> Dict[str, Any]:
        """一个月的个人日历。没有单独设置的日期只回 explicit=False，不替排产猜它当天怎么上班。"""
        if type(year) is not int or type(month) is not int or not 1 <= year <= 9999 or not 1 <= month <= 12:
            raise ValidationError("年月不合法，月份应为 1 至 12。", field="month")
        first = date(year, month, 1)
        count = calendar_module.monthrange(year, month)[1]
        last, now = first.replace(day=count), self._now()
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历读取必须在快照事务中执行。")
        states = self.range_states(first.isoformat(), last.isoformat())
        default_periods = self._base_engine().default_periods()
        days = []
        for offset in range(count):
            day = first + timedelta(days=offset)
            state = self._listed_state(day.isoformat(), states)
            days.append({**state, "day": day.day, "weekday": day.weekday(),
                         "is_weekend": day.weekday() >= 5, "is_today": day == now.date()})
        cells = [None] * first.weekday() + days
        cells += [None] * (-len(cells) % 7)
        return {"operator_code": self.operator_code, "year": year, "month": month,
                "as_of": now.isoformat(timespec="seconds"), "time_basis": "factory_local",
                "days": days, "cells": cells, "default_periods": default_periods,
                "previous_month": self._adjacent(year, month, -1), "next_month": self._adjacent(year, month, 1),
                "stats": {"configured": sum(day["explicit"] for day in days),
                          "work_days": sum(is_working_row(day["row"], day["periods"]) for day in days if day["explicit"])}}

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

    def proposed_row(
        self,
        fields: Dict[str, Any],
        before: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
        projection: CalendarProjection,
    ) -> OperatorCalendar:
        """按领域规则算出这一天保存后的行；与人员详情面板走同一条一致性校验，不合规直接抛拒绝。

        fields 用的是界面字段名（type/periods/eff/allowNormal/allowUrgent/note），
        不经过界面的输入模型，取值合法性由调用方自己校验。
        """
        return self._proposed(fields, before, context=context, projection=projection)

    # ---------- 写 ----------

    def _proposed(
        self,
        fields: Dict[str, Any],
        before: Dict[str, Any],
        *,
        context: CalendarNormalizationContext,
        projection: CalendarProjection,
    ) -> OperatorCalendar:
        """以这一天的原行为基底再打补丁，没给的项保持原样。

        新增上班的一天必须填工作时段（没有个人行的日子按班次或全局日历走，不替它套默认时段）；
        原来是假期的一天改成上班同样必须填。显式空数组表示明确零工时。
        """
        row = before["row"]
        payload: Dict[str, Any] = {"operator_id": self.operator_code, "date": before["date"]}
        if row is not None:
            payload.update({key: row[key] for key in
                            ("day_type", "efficiency", "allow_normal", "allow_urgent", "remark", "periods_json")})
        patch = calendar_domain_fields(fields)
        if row is None and patch["day_type"] == "workday" and "periods" not in patch:
            raise ValidationError("上班的日子必须填写工作时段。", field="periods")
        require_periods_when_rest_turns_work(before["date"], row, patch)
        payload.update(patch)
        model = self._admin.build_operator_calendar_from_payload(payload, context=context)
        effective_calendar_day(before["date"], model, projection=projection)
        return model

    def _require_write_transaction(self) -> None:
        if not self.conn.in_transaction or not in_transaction_context(self.conn):
            raise RuntimeError("个人日历写入必须由外层 WorkbenchCommandService 持有写事务。")

    def apply_checked(self, action, normalized_input, checked):
        """The guard has already read and bound these facts under this command lock."""
        payload = normalized_input
        if action == "range_clear":
            return self._clear_checked_range(checked)
        if action not in ("upsert", "delete"):
            raise ValidationError("不支持的个人日历操作。", field="action")
        return self._apply_day(action, payload, checked)

    def _apply_day(self, action, payload, before):
        context = self._normalization_context()
        try:
            after = (self._proposed(payload["fields"], before, context=context,
                                    projection=CalendarProjection({}, engine=self._base_engine()))
                     if action == "upsert" else None)
        except ValidationError as exc:
            # 表单入口：领域规则报的中立字段名在这里映射成界面路径。
            raise form_field_error(exc) from exc
        return self._write(before, after)

    def _write(self, before, after) -> WorkbenchCommandOutcome:
        return self.write_days([(before, after)])[0]

    def write_days(self, changes):
        self._require_write_transaction()
        results, calendars, deleted, created = [], [], [], []
        for before, after in changes:
            day, ref = before["date"], before["calendar_ref"]
            row = after.to_dict() if isinstance(after, OperatorCalendar) else after
            changed = row != before["row"]
            results.append(WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                                   {"date": day, "calendar_ref": ref}))
            if not changed:
                continue
            if after is None:
                deleted.append((self.operator_code, day))
            else:
                calendars.append(after)
                if ref is None:
                    created.append(entity_key(self.operator_code, day))
        repo = self._admin.operator_calendar_repo
        if calendars:
            repo.upsert_many(calendars)
        if deleted:
            repo.delete_many(deleted)
        if calendars or deleted:
            self._engine = None
        refs = self._query.created_refs("operator_calendar", created) if created else {}
        for outcome in results:
            if outcome.result == "committed" and outcome.data["calendar_ref"] is None:
                outcome.data["calendar_ref"] = refs[entity_key(self.operator_code, outcome.data["date"])]
        return results

    def preview_range_clear(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """只读：这段日期里有哪些天是单独设过的，清除后会恢复成班次或全局日历。"""
        request = self.normalize("range_clear", payload)
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历读取必须在快照事务中执行。")
        states = self.range_states(request["start_date"], request["end_date"])
        days = [self._listed_state(day, states) for day, state in states.items() if state["row"] is not None]
        return {"request": request, "days": days, "count": len(days)}

    def _clear_checked_range(self, current):
        results = self.write_days([(state, None) for state in current["days"]])
        return WorkbenchCommandOutcome("committed" if any(item.result == "committed" for item in results) else "unchanged",
                                       {"dates": [{**item.data, "result": item.result} for item in results],
                                        "cleared_count": sum(item.result == "committed" for item in results)})

    @staticmethod
    def public_day(state: Dict[str, Any]) -> Dict[str, Any]:
        """对外投影：只暴露这一天的业务字段与是否单独设置，不暴露内部修订号以外的元数据。"""
        row = state["row"]
        return {"date": state["date"], "explicit": state["explicit"],
                "calendar_ref": state["calendar_ref"], "periods": state["periods"],
                **({key: row[key] for key in _PUBLIC_FIELDS} if row is not None
                   else {key: None for key in _PUBLIC_FIELDS})}
