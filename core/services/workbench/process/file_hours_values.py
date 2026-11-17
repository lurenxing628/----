"""Sparse hours-file values; no inference, template confirmation or writes."""

from core.errors import ValidationError
from core.models.workbench_process_commands import process_days, process_number
from core.shared.strict_parse import wire_sequence

from .part_actions_facts import plain_part_action_facts as _plain

HOURS_FIELDS = ("setup_hours", "unit_hours", "external_days", "group_total_days")


def flat_hours(operation, group):
    internal = operation["source"] == "internal"
    return _plain({"business_code": operation["part_no"], "sequence": wire_sequence(operation["seq"]),
                   "op_type_name": operation["op_type_name"], "source": operation["source"],
                   "setup_hours": operation["setup_hours"] if internal else None,
                   "unit_hours": operation["unit_hours"] if internal else None,
                   "external_days": operation["ext_days"] if not internal else None,
                   "group_start": wire_sequence(group["start_seq"]) if group else None,
                   "group_end": wire_sequence(group["end_seq"]) if group else None,
                   "group_total_days": group["total_days"] if group and group["merge_mode"] == "merged" else None})


def assertions(values, operation, group):
    original = {"source": operation["source"], "op_type_name": operation["op_type_name"],
                "group_start": group["start_seq"] if group else None,
                "group_end": group["end_seq"] if group else None}
    for field, previous in original.items():
        if field not in values:
            continue
        if values[field] != previous:
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
        # 留空或填原值都不写入。
        member_cycle = field == "external_days" and merged
        if member_cycle and value is None:
            continue
        # The stage-input rules and their field rejection, pointed at this column: hours are finite non-negative,
        # cycles are external days. This is the file's only value-range diagnosis.
        number = (process_days if field in ("external_days", "group_total_days") else process_number)(value, field)
        if member_cycle:
            if number != operation["ext_days"]:
                raise ValidationError("这道工序使用外协段总周期，请修改合并周期；不能单独改逐序外协周期。", field=field)
            continue
        result[field] = number
    return result
