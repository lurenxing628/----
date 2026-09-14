"""Sparse hours-file values; no inference, template confirmation or writes."""

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import process_number
from core.models.workbench_process_file import COLUMNS, INT64_MAX
from core.services.workbench.process_projection import public_sequence
from core.services.workbench.process_queries import _plain

HOURS_FIELDS = ("setup_hours", "unit_hours", "external_days", "group_total_days")


def supplied_values(values):
    if type(values) is not dict or set(values) - set(COLUMNS["hours"]):
        raise ValidationError("工时文件里有认不出的列。请下载模板对照后重新导入。", field="input")
    # The codec omits empty cells. Also retain this contract for direct callers.
    return {key: value for key, value in values.items() if value != ""}


def row_key(values):
    code, sequence = values.get("business_code"), values.get("sequence")
    if type(code) is not str or not code.strip():
        raise ValidationError("图号必须填文本，不能留空。", field="business_code")
    if type(sequence) is not int or not 1 <= sequence <= INT64_MAX:
        raise ValidationError("工序号必须是正整数，系统不会猜，也不会四舍五入。", field="sequence")
    return code, sequence


def flat_hours(operation, group):
    internal = operation["source"] == "internal"
    return _plain({"business_code": operation["part_no"], "sequence": public_sequence(operation["seq"]),
                   "op_type_name": operation["op_type_name"], "source": operation["source"],
                   "setup_hours": operation["setup_hours"] if internal else None,
                   "unit_hours": operation["unit_hours"] if internal else None,
                   "external_days": operation["ext_days"] if not internal else None,
                   "group_start": public_sequence(group["start_seq"]) if group else None,
                   "group_end": public_sequence(group["end_seq"]) if group else None,
                   "group_total_days": group["total_days"] if group and group["merge_mode"] == "merged" else None})


def assertions(values, operation, group):
    original = {"source": operation["source"], "op_type_name": operation["op_type_name"],
                "group_start": group["start_seq"] if group else None,
                "group_end": group["end_seq"] if group else None}
    for field, previous in original.items():
        if field not in values:
            continue
        value = values[field]
        if field in ("group_start", "group_end") and value is not None:
            if type(value) is not int or not 1 <= value <= INT64_MAX:
                raise ValidationError("外协组起止序必须是正整数。", field=field)
        if value != previous:
            raise ValidationError("这一列只用来核对原记录，改不了归属、工种或外协组范围。", field=field)


def hours_values(values, operation, group):
    applicable = {"setup_hours", "unit_hours"} if operation["source"] == "internal" else {"external_days"}
    merged = group is not None and group["merge_mode"] == "merged"
    if merged:
        applicable.add("group_total_days")
    result = {}
    for field in HOURS_FIELDS:
        if field not in values:
            continue
        value = values[field]
        if field not in applicable:
            if value is not None:
                raise ValidationError("这一列不适用于当前归属或现有外协组，系统不会偷偷写值，也不会新增合并组。", field=field)
        elif field == "external_days" and value is None and merged:
            result[field] = None
        else:
            # Keep exactly the same finite/nonnegative/positive rules as stage input.
            try:
                result[field] = process_number(value, positive=field in ("external_days", "group_total_days"))
            except WorkbenchCommandRejected as exc:
                raise ValidationError(str(exc), field=field) from exc
    return result
