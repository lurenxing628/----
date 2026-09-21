"""个人工作日历的文件预检与确认。只改文件里列出的"那个人那一天"，别人和别的日期完全不动。

和全局日历文件一样不做删除：要取消某几天的特殊安排，用人员详情里的按日期范围清除。

取值校验在这里做，领域一致性交给 `WorkbenchOperatorCalendarService`，与人员详情的面板走同一条链路，
所以界面存不了的组合文件也存不了。工时不是可填列：它由班次起止算出来，导出时作为只读列带出。
"""

from datetime import date
from typing import Any, Dict, List, Optional

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
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
    CalendarFileDownload,
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
    resource_refs,
)
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_query import ResourcePageRequest
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from ..operator_calendars import WorkbenchOperatorCalendarService
from ..queries import WorkbenchResourceQueryService
from .file_codec import read_calendar_file, read_clock, read_date, read_number
from .file_writer import check_capacity, write_calendar_file

KIND = "operator_calendar"
_DAY_TYPE_TEXT = {"workday": "工作日", "holiday": "假期"}
_YES_NO_TEXT = {"yes": "是", "no": "否"}


def _blocked(row) -> bool:
    return bool(row["errors"])


def _text(value: float) -> str:
    return f"{value:f}".rstrip("0").rstrip(".") or "0"


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


class WorkbenchOperatorCalendarFileService:
    def __init__(self, conn, logger=None, *, clock=None):
        self.conn, self.kind = conn, KIND
        self.logger, self._clock = logger, clock
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.tx = TransactionManager(conn)
        self._calendars: Dict[str, WorkbenchOperatorCalendarService] = {}

    def _calendar(self, operator_code: str) -> WorkbenchOperatorCalendarService:
        if operator_code not in self._calendars:
            self._calendars[operator_code] = (
                WorkbenchOperatorCalendarService(self.conn, operator_code, self.logger, clock=self._clock)
                if self._clock is not None
                else WorkbenchOperatorCalendarService(self.conn, operator_code, self.logger))
        return self._calendars[operator_code]

    def _reader(self):
        return WorkbenchResourceQueryService(self.conn, "operator", self.logger)

    # ---------- 导入 ----------

    def preview_import(self, content, *, file_format, mode="upsert"):
        request = import_request(self.kind, content, file_format, mode)
        source, notices = read_calendar_file(self.kind, content, file_format)
        with self.tx.transaction():
            return ResourceActionPreview.build(self.kind + ".import", request, self._build_rows(source), notices)

    def _build_rows(self, source) -> List[Dict[str, Any]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_pairs(rows)
        self._resolve_operators(rows)
        states = self._load_states(rows)
        for row in rows:
            if not _blocked(row):
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
            raise ValidationError("这一格只填了空格。留空表示保持原样，要清空请填 \\N。", field=key)
        return text

    @staticmethod
    def _code(raw: Any, key: str) -> str:
        code = resource_text(raw, key)
        if code is None:
            raise ValidationError("这一项必须填写。", field=key)
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
        """按去重后的工号取人员，避免逐行查库。"""
        codes = sorted({row["values"]["operator_code"] for row in rows
                        if not _blocked(row) and row["values"].get("operator_code")})
        loaded = {code: self.repo.raw("operator", code) for code in codes}
        for row in rows:
            if _blocked(row):
                continue
            raw = loaded.get(row["values"]["operator_code"])
            if raw is None:
                reject_action_row(row, "系统里找不到这个工号，这一行没有导入。请先在人员资料里维护好再导入。",
                                  field="operator_code")
                continue
            row["expected"] = {"operator": dict(raw)}
            row["values"]["operator_label"] = dict(raw).get("name")

    def _load_states(self, rows) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """一次按人读回各自那段日期的状态，不逐行查库（roadmap 4.7）。"""
        days = sorted({row["values"]["date"] for row in rows if not _blocked(row)})
        if not days:
            return {}
        if (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 > MAX_RANGE_DAYS:
            raise ValidationError(
                "文件里最早和最晚的日期相差超过 " + str(MAX_RANGE_DAYS) + " 天，一行都没有导入。请拆成几个文件分次上传。",
                field="date")
        codes = sorted({row["values"]["operator_code"] for row in rows if not _blocked(row)})
        return {code: self._calendar(code).range_states(days[0], days[-1]) for code in codes}

    def _classify(self, row, states) -> None:
        code, day = row["values"]["operator_code"], row["values"]["date"]
        calendar = self._calendar(code)
        before = calendar.day_state(day, states.get(code, {}))
        fields = self._fields_for(row, before)
        after = None if fields is None else self._after_row(row, calendar, fields, before)
        if after is None:
            return
        row["expected"] = {**(row["expected"] or {}), "state": before}
        row["input"] = after
        self._describe(row, before, after)

    def _fields_for(self, row, before) -> Optional[Dict[str, Any]]:
        """把这一行的取值翻成人员详情用的字段名；人员详情存不了的组合在这里就挡住，返回 None。"""
        fields = {UI_FIELDS[self.kind][key]: value for key, value in row["values"].items()
                  if key in UI_FIELDS[self.kind]}
        fields.setdefault("type", "rest" if (before["row"] or {}).get("day_type") == "holiday" else "work")
        # 人员详情存不了"上班却没挑班次开始"的一天（见 workbench_operator_calendar._fields），文件也不能存。
        # 领域层对缺失的开始时刻会补 08:00，所以判据只能放在填进来的值上：原来就上班才有已确认的窗口可留空继承，
        # 新建的一天和从假期改回上班的一天都必须自己填，不能让 08:00 悄悄替用户做主。
        if fields["type"] == "work" and fields.get("shiftStart") is None \
                and (before["row"] or {}).get("day_type") != "workday":
            reject_action_row(row, "这一天原来不上班，改成上班必须填班次开始时刻，这一行没有导入。"
                                   "要让这一天休息请把类型填成「假期」。", field="shift_start")
            return None
        return fields

    def _after_row(self, row, calendar, fields, before) -> Optional[Dict[str, Any]]:
        """交给人员详情那条链算出保存后的行；它不认的组合按原因标红这一行。"""
        try:
            return calendar.proposed_row(fields, before)
        except WorkbenchCommandRejected as exc:
            reject_action_row(row, str(exc), code=exc.code, field="date")
        except ValidationError as exc:
            reject_action_row(row, exc.message, field=self._field_of(exc.field))
        return None

    def _describe(self, row, before, after) -> None:
        label = row["values"].get("operator_label")
        row["before"] = self._public(before["row"], label)
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
        # 每一行都要说明它会盖过班次轮换，不然用户看不出导进去的代价。
        row["notes"].append("这一天这个人整天按这里的安排排产，不再套用他的班次轮换，也不看全局工作日历。")
        row["requires_confirmation"] = True

    @staticmethod
    def _field_of(field: Optional[str]) -> str:
        mapping = {"fields.shiftStart": "shift_start", "fields.shiftEnd": "shift_end", "fields.eff": "efficiency",
                   "班次开始": "shift_start", "班次结束": "shift_end", "效率": "efficiency", "可用工时": "shift_start"}
        return mapping.get(field or "", "date")

    def _public(self, row: Optional[Dict[str, Any]], label: Optional[str]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return {"operator_code": row["operator_id"], "date": row["date"],
                "day_type": _DAY_TYPE_TEXT[row["day_type"]],
                "shift_start": row["shift_start"], "shift_end": row["shift_end"],
                "efficiency": _text(row["efficiency"] * 100),
                "allow_normal": _YES_NO_TEXT[row["allow_normal"]], "allow_urgent": _YES_NO_TEXT[row["allow_urgent"]],
                "remark": row["remark"], "operator_label": label, "shift_hours": _text(row["shift_hours"])}

    def confirm_import(self, preview, content, *, file_format, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历文件导入确认必须在外层工作台写事务中执行。")
        with self.tx.transaction():
            try:
                current = self.preview_import(content, file_format=file_format, mode=mode)
            except ValidationError as exc:
                raise WorkbenchCommandRejected(
                    "stale_write", "文件或个人日历已经变了，没有导入。请重新点「开始预检」后再确认。") from exc
            check_resource_preview(preview, current)
            body = current.as_dict()
            if body["summary"]["rejected"]:
                raise WorkbenchCommandRejected(
                    "constraint_conflict", "这一批里有不能导入的行，一行都没有导入。请修好标红的行后重新点「开始预检」。")
            results = []
            for row in body["rows"]:
                if row["result"] == "unchanged":
                    results.append({"row": row["row"], "business_code": row["business_code"], "result": "unchanged"})
                    continue
                outcome = self._calendar(row["values"]["operator_code"]).write_day(
                    row["expected"]["state"], row["input"])
                # 与全局日历同一条守卫：回执照实说，不把"预检说要写、领域层判定无事可写"
                # 包装成成功。个人日历这条路今天走不到（只填工号和日期的行会先被拒），
                # 守在这里是防止将来某个字段变成可选后又悄悄退回假回执。
                if outcome.result != "committed":
                    raise RuntimeError(
                        f"预检判这一行要写入，个人日历领域层却判定无事可写，不能确认保存：第 {row['row']} 行 {row['business_code']}")
                results.append({"row": row["row"], "business_code": row["business_code"], "result": "committed"})
            changed = any(item["result"] == "committed" for item in results)
            return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                           {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def _codes_for(self, selected_refs) -> List[str]:
        reader = self._reader()
        if selected_refs is not None:
            return [reader.resolve(ref).entity_key for ref in resource_refs(selected_refs, allow_empty=True)]
        codes = []
        for item in reader.matching_rows(ResourcePageRequest(kind="operator")):
            if item["ref"] is None:
                raise WorkbenchCommandRejected(
                    "storage_failure", "有人员在资料里查不到编号，没有开始下载，资料也没有被改动。请到资料总览核对后重试。", 500)
            codes.append(reader.resolve(item["ref"]).entity_key)
        return codes

    def _rows_for(self, start_date: str, end_date: str, codes: List[str]) -> List[Dict[str, Any]]:
        """只导出这段时间里单独设置过的日期；没设置过的天按班次或全局日历走，不出现在文件里。"""
        rows = []
        for code in sorted(set(codes)):
            raw = self.repo.raw("operator", code)
            label = dict(raw).get("name") if raw is not None else None
            for _, state in sorted(self._calendar(code).range_states(start_date, end_date).items()):
                if state["row"] is not None:
                    rows.append(self._public(state["row"], label))
        rows.sort(key=lambda item: (item["operator_code"], item["date"]))
        return rows

    def range_snapshot(self, start_date: str, end_date: str, selected_refs=None) -> str:
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历范围读取必须在快照事务中执行。")
        check_range(start_date, end_date)
        return input_fingerprint(self._rows_for(start_date, end_date, self._codes_for(selected_refs)))

    def preview_export(self, *, start_date: str, end_date: str, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历导出预览必须在已验证的查询快照事务中执行。")
        check_range(start_date, end_date)
        count = len(self._rows_for(start_date, end_date, self._codes_for(selected_refs)))
        arguments = {"start_date": start_date, "end_date": end_date}
        if selected_refs is not None:
            arguments["selected_refs"] = resource_refs(selected_refs, allow_empty=True)
        return arguments, count

    def export(self, file_format, *, start_date: str, end_date: str, selected_refs=None) -> CalendarFileDownload:
        if not self.conn.in_transaction:
            raise RuntimeError("个人日历导出必须在已验证的查询快照事务中执行。")
        check_range(start_date, end_date)
        rows = self._rows_for(start_date, end_date, self._codes_for(selected_refs))
        check_capacity(len(rows), file_format)
        return write_calendar_file(self.kind, rows, file_format)
