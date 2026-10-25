"""Sparse hours-file values; no inference, template confirmation or writes."""

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import process_number
from core.models.workbench_process_file import INT64_MAX

from .part_actions_facts import plain_part_action_facts as _plain
from .projection import public_sequence

HOURS_FIELDS = ("setup_hours", "unit_hours", "external_days", "group_total_days")


def supplied_values(values):
    # The codec omits empty cells. Also retain this contract for direct callers.
    return {key: value for key, value in values.items() if value != ""}


def row_key(values):
    code, sequence = values.get("business_code"), values.get("sequence")
    if type(code) is not str or not code.strip():
        raise ValidationError("图号必须填文本，不能留空。", field="business_code")
    if type(sequence) is not int or not 1 <= sequence <= INT64_MAX:
        raise ValidationError("工序号必须是正整数。", field="sequence")
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
                raise ValidationError("这一列不适用于当前归属或现有外协组，请核对列值。", field=field)
            continue
        # 与工序确认同一规则：合并组成员按外协段总周期排产，逐序旧周期不生效、原样保留，
        # 留空或填原值都不写入；保留的旧值可能本就不合法，不能再当有效输入。
        member_cycle = field == "external_days" and merged
        if member_cycle and value is None:
            continue
        # Keep exactly the same finite/nonnegative/positive rules as stage input.
        try:
            number = process_number(value, positive=field in ("external_days", "group_total_days"))
        except WorkbenchCommandRejected as exc:
            raise ValidationError(str(exc), field=field) from exc
        if member_cycle:
            if number != operation["ext_days"]:
                raise ValidationError("这道工序使用外协段总周期，请修改合并周期；不能单独改逐序外协周期。", field=field)
            continue
        result[field] = number
    return result
