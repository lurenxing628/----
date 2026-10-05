"""全局工作日历的文件预检与确认。只改文件里列出的日期，没列出的日期完全不动。

文件不做删除：把某一天恢复成默认规则要用日历页的范围清除。这样文件里少写一天永远是安全的，
不会因为漏抄一行就把配置抹掉。

取值校验在这里做，领域一致性交给 `WorkbenchCalendarService.proposed_row`，与日历页走同一条校验链，
所以界面拒绝的组合文件也拒绝。唯一的例外是假期带工时：界面的输入模型禁止，文件放行，见 4.5 的裁决。
"""

from datetime import date
from typing import Any, Dict, List, Optional

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.calendar_period_columns import export_period_columns, parse_period_columns
from core.models.workbench_calendar_file import (
    CLOCK_FIELDS,
    ENUMS,
    MAX_RANGE_DAYS,
    NULLABLE,
    NUMERIC,
    REQUIRED,
    UI_FIELDS,
    CalendarFileDownload,
    calendar_kind,
    file_columns,
    import_request,
    row_identity,
)
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    input_fingerprint,
)
from core.models.workbench_operator_calendar import operator_clock
from core.models.workbench_resource_action import (
    ResourceActionPreview,
    action_row,
    check_resource_preview,
    reject_action_row,
)
from core.models.workbench_resource_file_source import PreparedImportSource

from ..calendars import WorkbenchCalendarService
from .file_codec import read_calendar_file, read_clock, read_date, read_number
from .file_writer import check_capacity, number_text, percent_text, write_calendar_file

_LIMITS = {"shift_hours": (0.0, 24.0, False), "efficiency": (0.0, 200.0, True)}
_DAY_TYPE_TEXT = {"workday": "工作日", "holiday": "假期"}
_YES_NO_TEXT = {"yes": "是", "no": "否"}


def _blocked(row) -> bool:
    """这一行是不是已经出错。预检行的初始状态就是 rejected，判据只能是错误列表。"""
    return bool(row["errors"])


def _blank(value: Any) -> bool:
    # 旧库升级加列时没有回填，工时、效率可能空着；日历引擎和日历页都按默认值解释它们。
    return value is None or isinstance(value, str) and not value.strip()


def range_fingerprint(states: Dict[str, Dict[str, Any]]) -> str:
    """按日期范围的读快照指纹：只认真正落过库的那些天的行与修订号。"""
    return input_fingerprint([{"date": day, "row": state["row"],
                               "revision": state["identity"]["revision"] if state["identity"] else None}
                              for day, state in sorted(states.items())])


def check_range(start_date: str, end_date: str) -> None:
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise WorkbenchCommandRejected("invalid_input", "日期范围必须填成 2026-10-01 这样的年月日，没有开始下载。", 400) from exc
    if end < start:
        raise WorkbenchCommandRejected("invalid_input", "结束日期不能早于开始日期，没有开始下载。请重新选择范围。", 400)
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise WorkbenchCommandRejected(
            "invalid_input", "一次最多处理 " + str(MAX_RANGE_DAYS) + " 天，没有开始下载。请把范围缩小后重试。", 400)


class WorkbenchCalendarFileService:
    def __init__(self, conn, kind, logger=None, *, clock=None):
        self.conn, self.kind = conn, calendar_kind(kind)
        self.logger = logger
        self.calendar = (WorkbenchCalendarService(conn, logger, clock=clock) if clock is not None
                         else WorkbenchCalendarService(conn, logger))
        self.tx = TransactionManager(conn)

    # ---------- 导入 ----------

    def prepare_import(self, content, *, file_format, mode="upsert"):
        request = import_request(self.kind, content, file_format, mode)
        source, notices = read_calendar_file(self.kind, content, file_format)
        return PreparedImportSource.build(self.kind + ".import", request, source, notices)

    def preview_import(self, content, *, file_format, mode="upsert"):
        prepared = content if isinstance(content, PreparedImportSource) else self.prepare_import(
            content, file_format=file_format, mode=mode)
        request = prepared.request_for(self.kind + ".import", file_format, mode)
        source, notices = prepared.parsed()
        with self.tx.transaction():
            return ResourceActionPreview.build(self.kind + ".import", request, self._build_rows(source), notices)

    def _build_rows(self, source) -> List[Dict[str, Any]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_dates(rows)
        states = self._load_states(rows)
        for row in rows:
            self._classify(row, states)
        return rows

    def _parse_row(self, source) -> Dict[str, Any]:
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        row["notes"] = []
        row["reference_fields"] = []
        row["input"] = None
        values = source["values"]
        parsed: Dict[str, Any] = {}
        for key in file_columns(self.kind):
            if key not in values:
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
                raise ValidationError("工时要填 0 到 24，效率要填大于 0 且不超过 200 的数字。", field=key)
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
        days = sorted({row["values"]["date"] for row in rows if not _blocked(row)})
        if not days:
            return {}
        if (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 > MAX_RANGE_DAYS:
            raise ValidationError(
                "文件里最早和最晚的日期相差超过 " + str(MAX_RANGE_DAYS) + " 天，一行都没有导入。请拆成几个文件分次上传。",
                field="date")
        return self.calendar.range_states(days[0], days[-1])

    def _classify(self, row, states) -> None:
        if _blocked(row):
            return
        day = row["values"]["date"]
        fields = {UI_FIELDS[self.kind][key]: value for key, value in row["values"].items() if key in UI_FIELDS[self.kind]}
        try:
            # 这一天的现状也可能算不出来（例如 9999-12-31 的班次跨到次日），只拒这一行。
            before = self.calendar.day_state(day, states)
            fields.update(parse_period_columns(row["values"]))
            after = self.calendar.proposed_row(fields, before)
        except WorkbenchCommandRejected as exc:
            reject_action_row(row, str(exc), code=exc.code, field="date")
            return
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=exc.field or "date")
            return
        row["expected"], row["input"] = before, after
        row["before"] = self._public(before["row"])
        row["after"] = self._public(after)
        row["action"] = "create" if before["row"] is None else "update"
        if before["row"] is None:
            # 只填日期、其余全空的行，对没配置过的天什么都不写（这天继续走默认规则）。
            # 原来一律判 new，回执跟着报 committed 且 summary 里 new 计 1，而库里一行没落——
            # 用户被告知"导入了 1 天"，实际什么都没发生。
            row["result"] = "new" if after is not None else "unchanged"
        else:
            row["changes"] = {key: {"before": row["before"][key], "after": row["after"][key]}
                              for key in file_columns(self.kind)
                              if key != "date" and row["before"][key] != row["after"][key]}
            row["result"] = "update" if row["changes"] else "unchanged"
        row["reference_count"] = 1 if before["row"] is not None else 0
        self._add_notes(row, after)

    @staticmethod
    def _add_notes(row, after) -> None:
        # 不写入的行不提醒、也不要求确认：原样再导一次已确认过的天，不必每次再勾一遍（与关系文件同一口径）。
        if after is None or row["result"] == "unchanged":
            return
        if after["day_type"] == "holiday" and after["shift_hours"] > 0:
            row["notes"].append("这一天是假期但安排了工时，效率按排产设置里的假期效率算；日历页上会显示成工作日。")
            row["requires_confirmation"] = True
        if after["shift_hours"] > 0 and after["allow_normal"] == "no" and after["allow_urgent"] == "no":
            # 类型留空时按日期取默认规则，周末的默认是假期且两个优先级都为否。于是"周六只填 4 小时"
            # 会存成假期 4 小时且不可排产：用户看到日历页显示成工作日，排产时却一道工序也排不进来。
            # roadmap 4.5 要求这种情况不能让用户自己撞，这里在预检里说清楚。
            row["notes"].append("这一天安排了工时，但普通件和急件都不可排产，实际一道工序也排不进来。"
                                "这两列留空时，没配置过的周末按假期默认成「否」；要让这天能排产请把它们填成「是」。")
            row["requires_confirmation"] = True
        if after["day_type"] == "workday" and not after["shift_hours"] and after["periods_json"] in (None, "[]"):
            # 假期只把类型改成工作日、工时留空时沿用假期的 0 工时；日历页切换类型会自动填默认班次，文件不替用户补。
            row["notes"].append("这一天是工作日，但可排工时是 0，排产时一道工序也排不进来。"
                                "要上班请填可排工时；要休息请把类型填成「假期」。")
            row["requires_confirmation"] = True

    def _public(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """把领域行翻成文件列口径，导出、预检对比、回导用的是同一份翻译。

        工时、效率空着的旧行按日历引擎的解释写出（工时按时段或起止推算否则 8 小时、效率 1），与日历页显示一致；
        原样回导时这两格与引擎解释相同，不算改动。
        """
        if row is None:
            return None
        hours, ratio = row["shift_hours"], row["efficiency"]
        if _blank(hours) or _blank(ratio):
            effective = self.calendar.effective_day(row["date"], row)
            hours = effective["hours"] if _blank(hours) else hours
            ratio = effective["efficiency"] if _blank(ratio) else ratio
        return {"date": row["date"], "day_type": _DAY_TYPE_TEXT[row["day_type"]],
                "shift_hours": number_text(hours), "efficiency": percent_text(ratio),
                "allow_normal": _YES_NO_TEXT[row["allow_normal"]], "allow_urgent": _YES_NO_TEXT[row["allow_urgent"]],
                "remark": row["remark"], "shift_start": row["shift_start"], "shift_end": row["shift_end"],
                **export_period_columns(row)}

    def confirm_import(self, preview, content, *, file_format, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("日历文件导入确认必须在外层工作台写事务中执行。")
        with self.tx.transaction():
            try:
                current = self.preview_import(content, file_format=file_format, mode=mode)
            except ValidationError as exc:
                raise WorkbenchCommandRejected(
                    "stale_write", "文件或日历已经变了，没有导入。请点「重新预检」后再确认。") from exc
            check_resource_preview(preview, current)
            body = current.as_dict()
            results = []
            for row in body["rows"]:
                if row["result"] == "unchanged":
                    results.append({"row": row["row"], "business_code": row["business_code"], "result": "unchanged"})
                    continue
                outcome = self.calendar.write_day(row["expected"], row["input"])
                # 回执必须照实说。原来这里丢掉了 write_day 的结果一律记 committed，
                # 于是"预检说要写、领域层判定无事可写"这种不一致会被包装成成功回执。
                if outcome.result != "committed":
                    raise RuntimeError(
                        f"预检判这一行要写入，日历领域层却判定无事可写，不能确认保存：第 {row['row']} 行 {row['business_code']}")
                results.append({"row": row["row"], "business_code": row["business_code"], "result": "committed"})
            changed = any(item["result"] == "committed" for item in results)
            return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                           {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def range_snapshot(self, start_date: str, end_date: str) -> str:
        """按日期范围的读快照指纹。月视图指纹绑的是一个月，导出范围要单独算。"""
        if not self.conn.in_transaction:
            raise RuntimeError("日历范围读取必须在快照事务中执行。")
        check_range(start_date, end_date)
        return range_fingerprint(self.calendar.range_states(start_date, end_date))

    def _rows_for(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """只导出这段时间里单独配置过的日期；没配置过的天按默认规则走，导出来回导会把默认固化成数据。"""
        states = self.calendar.range_states(start_date, end_date)
        rows: List[Dict[str, Any]] = []
        for _, state in sorted(states.items()):
            public = self._public(state["row"])
            if public is not None:
                rows.append(public)
        return rows

    def preview_export(self, *, start_date: str, end_date: str):
        if not self.conn.in_transaction:
            raise RuntimeError("日历导出预览必须在已验证的查询快照事务中执行。")
        check_range(start_date, end_date)
        return ({"start_date": start_date, "end_date": end_date}, len(self._rows_for(start_date, end_date)))

    def export(self, file_format, *, start_date: str, end_date: str) -> CalendarFileDownload:
        if not self.conn.in_transaction:
            raise RuntimeError("日历导出必须在已验证的查询快照事务中执行。")
        check_range(start_date, end_date)
        rows = self._rows_for(start_date, end_date)
        check_capacity(len(rows), file_format)
        return write_calendar_file(self.kind, rows, file_format)

    @staticmethod
    def template(kind, file_format="xlsx") -> CalendarFileDownload:
        return write_calendar_file(calendar_kind(kind), [], file_format, template=True)
