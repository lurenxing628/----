"""全局工作日历的文件预检与确认。只改文件里列出的日期，没列出的日期完全不动。

文件不做删除：把某一天恢复成默认规则要用日历页的范围清除。这样文件里少写一天永远是安全的，
不会因为漏抄一行就把配置抹掉。

取值校验在这里做，领域一致性交给 `WorkbenchCalendarService.proposed_state`，与日历页走同一条校验链，
所以界面拒绝的组合文件也拒绝。唯一的例外是假期带工时：界面的输入模型禁止，文件放行，见 4.5 的裁决。
"""

from datetime import date
from typing import Any, Dict, List, Optional

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.calendar_period_columns import export_period_columns, parse_period_columns
from core.models.calendar_periods import period_hours
from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_calendar import operator_clock
from core.models.workbench_calendar_file import (
    CLOCK_FIELDS,
    ENUMS,
    LABELS,
    MAX_RANGE_DAYS,
    NULLABLE,
    NUMERIC,
    READONLY,
    REQUIRED,
    UI_FIELDS,
    file_columns,
    import_request,
    row_identity,
)
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
)
from core.models.workbench_resource_action import (
    action_row,
    reject_action_row,
)
from core.models.workbench_resource_file_source import PreparedImportSource
from core.shared.stored_dates import stored_day

from ..calendars import WorkbenchCalendarService
from .file_codec import read_calendar_file, read_clock, read_date, read_number
from .file_writer import number_text, percent_text

_LIMITS = {"efficiency": (0.0, 200.0, True)}
DAY_TYPE_TEXT = {"workday": "工作日", "holiday": "假期"}
YES_NO_TEXT = {"yes": "是", "no": "否"}


def row_blocked(row) -> bool:
    """这一行是不是已经出错。预检行的初始状态就是 rejected，判据只能是错误列表。"""
    return bool(row["errors"])


def zero_hour_workday_note(after: Dict[str, Any], periods, subject: str, remedy: str) -> Optional[str]:
    """工作日却没有可排工时时的预检提醒；全局与个人日历文件共用这句事实，各自补上本文件的列操作提示。

    只有把工作时段数明确填成 0 才会走到这里：假期改成工作日却没填时段，在保存规则里就被拒绝了。
    """
    if after["day_type"] != "workday" or periods:
        return None
    return "这一天是工作日，但可排工时是 0，排产时" + subject + "一道工序也排不进来。" + remedy


#: 保存规则里补丁字段名（及领域层的效率字段）对应的文件列。
_RULE_COLUMNS = {"allowNormal": "allow_normal", "allowUrgent": "allow_urgent", "效率": "efficiency"}


def file_error_field(field: Optional[str], values: Dict[str, Any]) -> str:
    """校验报错的字段落到文件里该改的那一列；全局和个人日历文件都只在这里映射一次。

    时段规则与日历服务的补丁规则都报领域的中立字段 periods，落到这一行该填的时段列：
    填了段数归段数，否则归班次开始。文件列自己报的错原样保留，其余归日期列。
    这一天的现状本身算不出来（例如库里的默认工作时间坏了）不经过这里，调用方直接归日期列。
    """
    if field == "periods":
        return "period_count" if "period_count" in values else "shift_start"
    if field in _RULE_COLUMNS:
        return _RULE_COLUMNS[field]
    return field if field in LABELS else "date"


def check_range(start_date: str, end_date: str) -> None:
    start, end = stored_day(start_date), stored_day(end_date)
    if start is None or end is None:
        raise WorkbenchCommandRejected("invalid_input", "日期范围必须填成 2026-10-01 这样的年月日，没有开始下载。", 400)
    if end < start:
        raise WorkbenchCommandRejected("invalid_input", "结束日期不能早于开始日期，没有开始下载。请重新选择范围。", 400)
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise WorkbenchCommandRejected(
            "invalid_input", "一次最多处理 " + str(MAX_RANGE_DAYS) + " 天，没有开始下载。请把范围缩小后重试。", 400)


class WorkbenchCalendarFileService:
    def __init__(self, conn, kind, logger=None):
        self.conn, self.kind = conn, kind
        self.logger = logger
        self.calendar = WorkbenchCalendarService(conn, logger)
        self.tx = TransactionManager(conn)

    # ---------- 导入 ----------

    def _prepare_source(self, content, *, file_format, mode):
        request = import_request(self.kind, file_format, mode)
        source, notices = read_calendar_file(self.kind, content, file_format)
        return PreparedImportSource.build(request, source, notices)

    def preview_import(self, content, *, file_format, mode):
        prepared = self._prepare_source(content, file_format=file_format, mode=mode)
        with self.tx.transaction():
            return self._preview_import(prepared)[0]

    def _preview_import(self, prepared: PreparedImportSource):
        request = prepared.request()
        source, notices = prepared.parsed()
        context = self.calendar._calendar.normalization_context()
        rows = self._build_rows(source, context=context)
        calendars = {row["row"]: row.pop("calendar") for row in rows if "calendar" in row}
        return AtomicActionPreview.build(
            self.kind + ".import", request, rows, notices, source=prepared
        ), calendars

    def _build_rows(self, source, *, context) -> List[Dict[str, Any]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_dates(rows)
        states = self._load_states(rows)
        projection = self.calendar.projection(states)
        for row in rows:
            self._classify(row, states, projection=projection, context=context)
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
                raise ValidationError("这一项不能清除，留空表示保持原样。要把整天恢复成默认规则请到日历页用范围清除。", field=key)
            return None
        if key in CLOCK_FIELDS[self.kind]:
            return operator_clock(read_clock(raw, key), key)
        if key in ("date",):
            return read_date(raw, key)
        if key in NUMERIC[self.kind]:
            number = read_number(raw, key)
            low, high, positive = _LIMITS[key]
            if not low <= number <= high or (positive and number == low):
                raise ValidationError("效率要填大于 0 且不超过 200 的数字。", field=key)
            return number
        if key in ENUMS:
            text = raw.strip() if type(raw) is str else raw
            if text not in ENUMS[key]:
                raise ValidationError("只能填：" + " / ".join(ENUMS[key]) + "。", field=key)
            return ENUMS[key][text]
        text = str(raw).strip() if not isinstance(raw, str) else raw.strip()
        if not text:
            # 只填了空格的格子，和真正的空格子在文件里长得一模一样，含义却相反：
            # 空格子是"保持原样"（根本走不到这里），纯空格原来被 strip 成 None 当作"清除"。
            # 与其替用户猜，不如让他明确表达。
            raise ValidationError("这一格只填了空格。留空表示保持原样，要清除请填 \\N。", field=key)
        return text

    @staticmethod
    def _reject_duplicate_dates(rows) -> None:
        seen: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            if row["business_code"] is not None:
                seen.setdefault(row["business_code"], []).append(row)
        for repeated in seen.values():
            if len(repeated) > 1:
                numbers = ", ".join(str(item["row"]) for item in repeated)
                for item in repeated:
                    reject_action_row(item, "同一个日期在文件里出现了多次，这些行都没有导入：第 " + numbers
                                      + " 行。请只保留一行。", field="date", code="duplicate_entry")

    def _load_states(self, rows) -> Dict[str, Dict[str, Any]]:
        """一次读回整段日期的状态，不逐行查库（roadmap 4.7）。"""
        days = sorted({row["values"]["date"] for row in rows if not row_blocked(row)})
        if not days:
            return {}
        if (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 > MAX_RANGE_DAYS:
            raise ValidationError(
                "文件里最早和最晚的日期相差超过 " + str(MAX_RANGE_DAYS) + " 天，一行都没有导入。请拆成几个文件分次上传。",
                field="date")
        return self.calendar.range_states(days[0], days[-1])

    def _classify(self, row, states, *, projection, context) -> None:
        if row_blocked(row):
            return
        day = row["values"]["date"]
        fields = {UI_FIELDS[self.kind][key]: value for key, value in row["values"].items() if key in UI_FIELDS[self.kind]}
        try:
            # 这一天的现状也可能算不出来（例如 9999-12-31 的班次跨到次日、库里的默认工作时间坏了），
            # 错不在这一行填的哪一列，只拒这一行并归到日期列。
            before = self.calendar.day_state(day, states, projection=projection)
        except ValidationError as exc:
            reject_action_row(row, exc.message, field="date")
            return
        try:
            fields.update(parse_period_columns(row["values"]))
            if fields.get("type") == "rest":
                # 假期留空工作时段按零工时，不沿用这一天原来的时段；填了时段就是 4.5 裁决保留的假期加班。
                fields.setdefault("periods", [])
            model, after, _ = self.calendar.proposed_state(
                fields, before, context=context, projection=projection
            )
        except WorkbenchCommandRejected as exc:
            reject_action_row(row, str(exc), code=exc.code, field="date")
            return
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=file_error_field(exc.field, row["values"]))
            return
        row["expected"], row["input"], row["calendar"] = before, after, model
        row["before"] = self._public(before["row"])
        row["after"] = row["before"] if after == before["row"] else self._public(after)
        row["action"] = "create" if before["row"] is None else "update"
        if before["row"] is None:
            # 只填日期、其余全空的行，对没配置过的天什么都不写（这天继续走默认规则）。
            # 原来一律判 new，回执跟着报 committed 且 summary 里 new 计 1，而库里一行没落——
            # 用户被告知"导入了 1 天"，实际什么都没发生。
            row["result"] = "new" if after is not None else "unchanged"
        else:
            writable = [key for key in file_columns(self.kind) if key not in READONLY[self.kind] and key != "date"]
            row["changes"] = {key: {"before": row["before"][key], "after": row["after"][key]}
                              for key in writable if row["before"][key] != row["after"][key]}
            row["result"] = "update" if row["changes"] else "unchanged"
        row["reference_count"] = 1 if before["row"] is not None else 0
        self._add_notes(row, after)

    def _periods(self, row: Dict[str, Any]):
        return self.calendar._calendar._engine.decoded_periods_for_json(row["periods_json"])

    def _add_notes(self, row, after) -> None:
        # 不写入的行不提醒、也不要求确认：原样再导一次已确认过的天，不必每次再勾一遍（与关系文件同一口径）。
        if after is None or row["result"] == "unchanged":
            return
        periods = self._periods(after)
        if after["day_type"] == "holiday" and periods:
            row["notes"].append(
                "这一天是假期但安排了工时（填了效率按所填算；留空时已有记录保持原效率，"
                "新增填假期取排产设置里的假期工作效率，新增周末类型留空默认 100%）；日历页上会显示成工作日。"
            )
            row["requires_confirmation"] = True
        if periods and after["allow_normal"] == "no" and after["allow_urgent"] == "no":
            # 类型留空时按日期取默认规则，周末的默认是假期且两个优先级都为否。于是"周六只填 4 小时"
            # 会存成假期 4 小时且不可排产：用户看到日历页显示成工作日，排产时却一道工序也排不进来。
            # roadmap 4.5 要求这种情况不能让用户自己撞，这里在预检里说清楚。
            row["notes"].append("这一天安排了工时，但普通件和急件都不可排产，实际一道工序也排不进来。"
                                "这两列留空时，没配置过的周末按假期默认成「否」；要让这天能排产请把它们填成「是」。")
            row["requires_confirmation"] = True
        zero_hours = zero_hour_workday_note(after, periods, "", "要上班请填班次起止或工作时段；要休息请把类型填成「假期」。")
        if zero_hours is not None:
            row["notes"].append(zero_hours)
            row["requires_confirmation"] = True

    def _public(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """把领域行翻成文件列口径，导出、预检对比、回导用的是同一份翻译。"""
        if row is None:
            return None
        periods = self._periods(row)
        return {"date": row["date"], "day_type": DAY_TYPE_TEXT[row["day_type"]],
                "shift_hours": number_text(period_hours(periods)), "efficiency": percent_text(row["efficiency"]),
                "allow_normal": YES_NO_TEXT[row["allow_normal"]], "allow_urgent": YES_NO_TEXT[row["allow_urgent"]],
                "remark": row["remark"], **export_period_columns(periods)}

    def confirm_import(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("日历文件导入确认必须在外层工作台写事务中执行。")
        current, calendars = self._preview_import(preview.source)
        body = preview.check_current(current)
        changes = [(row["expected"], calendars[row["row"]], row["input"]) for row in body["rows"]
                   if row["result"] != "unchanged"]
        self.calendar.write_days(changes, include_refs=False)
        results = [{"row": row["row"], "business_code": row["business_code"],
                    "result": "unchanged" if row["result"] == "unchanged" else "committed"}
                   for row in body["rows"]]
        changed = any(item["result"] == "committed" for item in results)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                       {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def _rows_from_states(self, states: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for state in states.values():
            public = self._public(state["row"])
            if public is not None:
                rows.append(public)
        return rows

    def preview_export(self, *, start_date: str, end_date: str):
        if not self.conn.in_transaction:
            raise RuntimeError("日历范围读取必须在快照事务中执行。")
        states = self.calendar.range_states(start_date, end_date)
        return sum(state["row"] is not None for state in states.values())

    def export_rows(self, *, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        if not self.conn.in_transaction:
            raise RuntimeError("日历范围读取必须在快照事务中执行。")
        states = self.calendar.range_states(start_date, end_date)
        return self._rows_from_states(states)
