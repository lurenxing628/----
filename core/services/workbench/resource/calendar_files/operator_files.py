"""个人工作日历的文件预检与确认。只改文件里列出的"那个人那一天"，别人和别的日期完全不动。

和全局日历文件一样不做删除：要取消某几天的特殊安排，用人员详情里的按日期范围清除。

取值校验在这里做，领域一致性交给 `WorkbenchOperatorCalendarService`，与人员详情的面板走同一条链路，
所以界面存不了的组合文件也存不了。工时不是可填列：它由班次起止算出来，导出时作为只读列带出。
"""

from dataclasses import replace
from datetime import date
from typing import Any, Dict, List, Optional, cast

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.calendar import OperatorCalendar
from core.models.calendar_period_columns import export_period_columns, parse_period_columns
from core.models.workbench_action_values import FileDownload
from core.models.workbench_calendar_file import (
    CLOCK_FIELDS,
    CODE_FIELDS,
    DATE_FIELDS,
    ENUMS,
    MAX_RANGE_DAYS,
    NULLABLE,
    NUMERIC,
    READONLY,
    REQUIRED,
    UI_FIELDS,
    CalendarFilePreview,
    file_columns,
    import_request,
    row_identity,
)
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
)
from core.models.workbench_operator_calendar import apply_rest_day_rules, operator_clock
from core.models.workbench_resource_action import (
    action_row,
    check_resource_preview,
    reject_action_row,
    resource_refs,
)
from core.models.workbench_resource_file_source import PreparedImportSource
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.scheduler.calendar.service import CalendarService
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from ..operator_calendars import WorkbenchOperatorCalendarService, engine_read_row
from ..queries import WorkbenchResourceQueryService
from .file_codec import read_calendar_file, read_clock, read_date, read_number
from .file_writer import check_capacity, number_text, percent_text, write_calendar_file
from .files import DAY_TYPE_TEXT, YES_NO_TEXT, check_range, range_fingerprint, row_blocked, zero_hour_workday_note

KIND = "operator_calendar"


class WorkbenchOperatorCalendarFileService:
    def __init__(self, conn, logger=None):
        self.conn, self.kind = conn, KIND
        self.logger = logger
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.tx = TransactionManager(conn)
        self._calendars: Dict[str, WorkbenchOperatorCalendarService] = {}
        self._domain_calendar = CalendarService(conn, logger=logger)

    def _calendar(self, operator_code: str) -> WorkbenchOperatorCalendarService:
        if operator_code not in self._calendars:
            self._calendars[operator_code] = WorkbenchOperatorCalendarService(
                self.conn, operator_code, self.logger, calendar_service=self._domain_calendar
            )
        return self._calendars[operator_code]

    def _reader(self):
        return WorkbenchResourceQueryService(self.conn, "operator", self.logger)

    # ---------- 导入 ----------

    def _prepare_source(self, content, *, file_format, mode):
        request = import_request(self.kind, content, file_format, mode)
        source, notices = read_calendar_file(self.kind, content, file_format)
        prepared = PreparedImportSource.build(self.kind + ".import", request, source, notices, content=content)
        request["actual_source_ref"] = prepared.source_ref
        return prepared, request

    def preview_import(self, content, *, file_format, mode="upsert"):
        prepared, request = self._prepare_source(content, file_format=file_format, mode=mode)
        with self.tx.transaction():
            return self._preview_import(prepared, request)

    def _preview_import(self, prepared: PreparedImportSource, request: Dict[str, Any]):
        source, notices = prepared.parsed()
        with self._domain_calendar.normalization_operation():
            rows = self._build_rows(source)
            calendars = {row["row"]: row.pop("calendar") for row in rows if "calendar" in row}
            return replace(CalendarFilePreview.build(self.kind + ".import", request, rows, notices, source=prepared),
                           calendars=calendars)

    def _build_rows(self, source) -> List[Dict[str, Any]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_pairs(rows)
        self._resolve_operators(rows)
        states = self._load_states(rows)
        for row in rows:
            if not row_blocked(row):
                self._classify(row, states)
        return rows

    def _parse_row(self, source) -> Dict[str, Any]:
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        row["notes"] = []
        values = source["values"]
        row["reference_fields"] = [key for key in READONLY[self.kind] if key in values]
        row["input"] = None
        parsed: Dict[str, Any] = {}
        for key in file_columns(self.kind):
            if key in READONLY[self.kind] or key not in values:
                continue
            try:
                parsed[key] = self._value(key, values[key])
            except ValidationError as exc:
                reject_action_row(row, exc.message, field=key)
        for key in REQUIRED[self.kind]:
            if key not in parsed and not any(item["field"] == key for item in row["errors"]):
                reject_action_row(row, "这一项必须填写。", field=key)
        row["business_code"] = row_identity(self.kind, parsed)
        row["values"] = parsed
        return row

    def _value(self, key: str, raw: Any) -> Any:
        if raw is None:
            if key not in NULLABLE[self.kind]:
                raise ValidationError("这一项不能清除，留空表示保持原样。要取消这一天的安排请到人员详情里按日期范围清除。",
                                      field=key)
            return None
        if key in CODE_FIELDS[self.kind]:
            return self._code(raw, key)
        if key in DATE_FIELDS[self.kind]:
            return read_date(raw, key)
        if key in CLOCK_FIELDS[self.kind]:
            return operator_clock(read_clock(raw, key), key)
        if key in NUMERIC[self.kind]:
            return self._efficiency(raw, key)
        if key in ENUMS:
            return self._choice(raw, key)
        text = str(raw).strip() if not isinstance(raw, str) else raw.strip()
        if not text:
            # 与全局日历同一口径：空格子是"保持原样"，纯空格原来被当成"清除"，
            # 两者在文件里看不出区别。
            raise ValidationError("这一格只填了空格。留空表示保持原样，要清除请填 \\N。", field=key)
        return text

    @staticmethod
    def _code(raw: Any, key: str) -> str:
        code = cast(str, resource_text(raw, key))
        if raw != code:
            raise ValidationError("工号不能有首尾空格，请修正后重新导入。", field=key)
        return code

    @staticmethod
    def _efficiency(raw: Any, key: str) -> float:
        number = read_number(raw, key)
        if not 0 < number <= 200:
            raise ValidationError("效率要填大于 0 且不超过 200 的数字。", field=key)
        return number

    @staticmethod
    def _choice(raw: Any, key: str) -> str:
        text = raw.strip() if type(raw) is str else raw
        if text not in ENUMS[key]:
            raise ValidationError("只能填：" + " / ".join(ENUMS[key]) + "。", field=key)
        return ENUMS[key][text]

    @staticmethod
    def _reject_duplicate_pairs(rows) -> None:
        seen: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            if row["business_code"] is not None:
                seen.setdefault(row["business_code"], []).append(row)
        for repeated in seen.values():
            if len(repeated) > 1:
                numbers = ", ".join(str(item["row"]) for item in repeated)
                for item in repeated:
                    reject_action_row(item, "同一个人的同一个日期在文件里出现了多次，这些行都没有导入：第 " + numbers
                                      + " 行。请只保留一行。", field="date", code="duplicate_entry")

    def _resolve_operators(self, rows) -> None:
        """按文件里的工号分块读取人员原行。"""
        codes = sorted({row["values"]["operator_code"] for row in rows if not row_blocked(row)})
        loaded = self.repo.raw_many("operator", codes)
        histories = self.repo.identity_histories("operator", codes)
        for row in rows:
            if row_blocked(row):
                continue
            code = row["values"]["operator_code"]
            raw = loaded.get(code)
            if raw is None:
                reject_action_row(row, "系统里找不到这个工号，这一行没有导入。请先在人员资料里维护好再导入。",
                                  field="operator_code")
                continue
            if not any(item["active"] == 1 for item in histories.get(code, ())):
                raise WorkbenchCommandRejected(
                    "storage_failure",
                    "这条资源在资料里查不到编号，这一行没有导入，资料也没有被改动。请到资料总览核对后重试。",
                    500,
                )
            row["expected"] = {"operator": raw, "operator_history": histories[code]}
            row["values"]["operator_label"] = raw["name"]

    def _load_states(self, rows) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """按工号分块读回日历和永久编号历史。"""
        days = sorted({row["values"]["date"] for row in rows if not row_blocked(row)})
        if not days:
            return {}
        if (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 > MAX_RANGE_DAYS:
            raise ValidationError(
                "文件里最早和最晚的日期相差超过 " + str(MAX_RANGE_DAYS) + " 天，一行都没有导入。请拆成几个文件分次上传。",
                field="date")
        codes = sorted({row["values"]["operator_code"] for row in rows if not row_blocked(row)})
        return self._states_for(codes, days[0], days[-1])

    def _states_for(self, codes, start_date, end_date):
        repo = WorkbenchCalendarQueryRepository(self.conn, self.logger)
        rows = repo.operator_calendar_rows_many(codes, start_date, end_date)
        histories = repo.operator_identity_rows_many(codes, start_date, end_date)
        return {code: WorkbenchOperatorCalendarService.states_from_rows(rows[code], histories[code]) for code in codes}

    def _classify(self, row, states) -> None:
        code, day = row["values"]["operator_code"], row["values"]["date"]
        calendar = self._calendar(code)
        before = calendar.day_state(day, states[code])
        fields = self._fields_for(row, before)
        if fields is None:
            return
        try:
            filled = engine_read_row(before["row"], fill_shift_end=True) if before["row"] is not None else None
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=self._field_of(exc.field))
            return
        before_for_propose = (
            before if filled is None else {**before, "reading": {**filled, "shift_end": before["row"].get("shift_end")}}
        )
        after = self._after_row(row, calendar, fields, before_for_propose)
        if after is None:
            return
        row["expected"] = {**row["expected"], "state": before}
        row["calendar"] = after
        row["input"] = after.to_dict()
        self._describe(row, before, row["input"], before_reading=filled)

    def _fields_for(self, row, before) -> Optional[Dict[str, Any]]:
        """把这一行的取值翻成人员详情用的字段名；人员详情存不了的组合在这里就挡住，返回 None。"""
        fields = {UI_FIELDS[self.kind][key]: value for key, value in row["values"].items()
                  if key in UI_FIELDS[self.kind]}
        try:
            fields.update(parse_period_columns(row["values"]))
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "period_count")
            return None
        fields.setdefault("type", "rest" if (before["row"] or {}).get("day_type") == "holiday" else "work")
        if fields["type"] == "rest":
            try:
                apply_rest_day_rules(fields)
            except ValidationError as exc:
                reject_action_row(row, exc.message, field=self._field_of(exc.field))
                return None
        # 人员详情存不了"上班却没挑班次开始"的一天（见 workbench_operator_calendar._fields），文件也不能存。
        # 领域层对缺失的开始时刻会补 08:00，所以判据只能放在填进来的值上：原来就上班才有已确认的窗口可留空继承，
        # 新建的一天和从假期改回上班的一天都必须自己填，不能让 08:00 悄悄替用户做主。
        if fields["type"] == "work" and fields.get("shiftStart") is None and "periods" not in fields \
                and (before["row"] or {}).get("day_type") != "workday":
            reject_action_row(row, "这一天原来不上班，改成上班必须填班次开始时刻，这一行没有导入。"
                                   "要让这一天休息请把类型填成「假期」。", field="shift_start")
            return None
        return fields

    def _after_row(self, row, calendar, fields, before) -> Optional[OperatorCalendar]:
        """交给人员详情那条链算出保存后的行；它不认的组合按原因标红这一行。"""
        try:
            return calendar.proposed_row(fields, before)
        except WorkbenchCommandRejected as exc:
            reject_action_row(row, str(exc), code=exc.code, field="date")
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=self._field_of(exc.field))
        return None

    def _describe(self, row, before, after, *, before_reading) -> None:
        label = row["values"]["operator_label"]
        row["before"] = self._public(before["row"], label, reading=before_reading)
        row["after"] = self._public(after, label)
        row["action"] = "create" if before["row"] is None else "update"
        if before["row"] is None:
            row["result"] = "new"
        else:
            writable = [key for key in file_columns(self.kind)
                        if key not in READONLY[self.kind] and key not in ("operator_code", "date")]
            row["changes"] = {key: {"before": row["before"][key], "after": row["after"][key]}
                              for key in writable if row["before"][key] != row["after"][key]}
            row["result"] = "update" if row["changes"] else "unchanged"
        row["reference_count"] = 1 if before["row"] is not None else 0
        self._add_notes(row, after)

    @staticmethod
    def _add_notes(row, after) -> None:
        # 不写入的行不提醒、也不要求确认，与全局日历文件和关系文件同一口径。
        if row["result"] == "unchanged":
            return
        # 要写入的每一行都要说明它会盖过班次轮换，不然用户看不出导进去的代价。
        row["notes"].append("这一天这个人整天按这里的安排排产，不再套用他的班次轮换，也不看全局工作日历。")
        # 工作时段数填 0 又把类型填成工作日，会存成 0 工时的工作日；与全局日历文件同样在预检里说清楚。
        zero_hours = zero_hour_workday_note(after, "这个人", "要上班请填班次起止或工作时段；要休息请把类型填成「假期」。")
        if zero_hours is not None:
            row["notes"].append(zero_hours)
        row["requires_confirmation"] = True

    @staticmethod
    def _field_of(field: Optional[str]) -> str:
        mapping: Dict[Optional[str], str] = {"fields.shiftStart": "shift_start", "fields.shiftEnd": "shift_end", "fields.eff": "efficiency",
                   "fields.allowNormal": "allow_normal", "fields.allowUrgent": "allow_urgent",
                   "fields.periods": "period_count",
                   "班次开始": "shift_start", "班次结束": "shift_end", "效率": "efficiency", "可用工时": "shift_start"}
        return mapping.get(field, "date")

    def _public(self, row: Optional[Dict[str, Any]], label: Optional[str],
                *, reading: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """把领域行翻成文件列口径，导出、预检对比、回导用的是同一份翻译。

        旧行空着的班次开始、工时、效率按排产引擎的解释写出（与全局日历文件同一口径）；原样回导时这几格与引擎解释相同，不算改动。
        """
        if row is None:
            return None
        row = engine_read_row(row, fill_shift_end=True) if reading is None else reading
        return {"operator_code": row["operator_id"], "date": row["date"],
                "day_type": DAY_TYPE_TEXT[row["day_type"]],
                "shift_start": row["shift_start"], "shift_end": row["shift_end"],
                "efficiency": percent_text(row["efficiency"]),
                "allow_normal": YES_NO_TEXT[row["allow_normal"]], "allow_urgent": YES_NO_TEXT[row["allow_urgent"]],
                "remark": row["remark"], "operator_label": label, "shift_hours": number_text(row["shift_hours"]),
                **export_period_columns(row)}

    def confirm_import(self, preview, content, *, file_format, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历文件导入确认必须在外层工作台写事务中执行。")
        try:
            prepared = PreparedImportSource.confirmation(preview, content)
            request = prepared.request_for(self.kind + ".import", file_format, mode)
            current = self._preview_import(prepared, request)
        except ValidationError as exc:
            raise WorkbenchCommandRejected(
                "stale_write", "文件或个人日历已经变了，没有导入。请点「重新预检」后再确认。") from exc
        body = check_resource_preview(preview, current)
        calendars = [current.calendars[row["row"]] for row in body["rows"] if row["result"] != "unchanged"]
        if calendars:
            self._domain_calendar._admin.operator_calendar_repo.upsert_many(calendars)
            self._domain_calendar._engine.clear_policy_cache()
        results = [{"row": row["row"], "business_code": row["business_code"],
                    "result": "unchanged" if row["result"] == "unchanged" else "committed"}
                   for row in body["rows"]]
        changed = any(item["result"] == "committed" for item in results)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                       {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def _codes_for(self, selected_refs) -> List[str]:
        reader = self._reader()
        if selected_refs is not None:
            refs = resource_refs(selected_refs, allow_empty=True)
            return [identity.entity_key for identity in reader.resolve_refs(refs)]
        return reader.toolbar_matching_keys(ResourcePageRequest(kind="operator"))

    def _rows_for(self, start_date: str, end_date: str, codes: List[str]):
        """只导出这段时间里单独设置过的日期；没设置过的天按班次或全局日历走，不出现在文件里。"""
        rows = []
        codes = sorted(set(codes))
        operators = self.repo.raw_many("operator", codes)
        states = self._states_for(codes, start_date, end_date)
        fingerprint = {}
        for code in codes:
            label = operators[code]["name"]
            fingerprint[code] = {"label": label, "days": range_fingerprint(states[code])}
            for state in states[code].values():
                if state["row"] is not None:
                    rows.append(self._public(state["row"], label))
        return fingerprint, rows

    def _states_and_rows(self, start_date: str, end_date: str, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历范围读取必须在快照事务中执行。")
        check_range(start_date, end_date)
        return self._rows_for(start_date, end_date, self._codes_for(selected_refs))

    def preview_export(self, *, start_date: str, end_date: str, selected_refs=None, rows):
        arguments: Dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if selected_refs is not None:
            arguments["selected_refs"] = selected_refs
        return arguments, len(rows)

    def export(self, file_format, *, rows) -> FileDownload:
        check_capacity(len(rows), file_format)
        return write_calendar_file(self.kind, rows, file_format)
