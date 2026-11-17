"""Strict, JSON-shaped inputs for explicit process-stage confirmations."""

from __future__ import annotations

from typing import Dict, Optional, Union

from core.models.enums import SOURCE_TYPE_VALUES
from core.models.workbench_command import SHAPE_REJECTED, WorkbenchCommandRejected
from core.shared.key_sets import keys_conform
from core.shared.refs import is_ref
from core.shared.strict_parse import EXTERNAL_DAYS_RANGE_TEXT, JS_SAFE_INT_MAX, is_external_days, is_stored_number

PROCESS_ACTIONS = ("route_confirm", "source_confirm", "hours_confirm", "groups_confirm")
MAX_STAGE_ITEMS = 10000


def process_object(value, keys):
    if not keys_conform(value, keys):
        raise WorkbenchCommandRejected("invalid_input", SHAPE_REJECTED, 400)
    return value


def process_ref(value):
    if not is_ref(value):
        raise WorkbenchCommandRejected("invalid_input", "所选记录已失效，请刷新后重新选择。", 422)
    return value


def process_number(value, path):
    """Template hours (setup / unit): a finite non-negative stored number."""
    if type(value) not in (int, float):
        raise WorkbenchCommandRejected("invalid_input", "请输入有效的工时，不能留空。", 422, fields=(path,))
    if not is_stored_number(value):
        message = "工时超出有效数字范围。" if value > JS_SAFE_INT_MAX else "工时必须是有限非负数。"
        raise WorkbenchCommandRejected("invalid_input", message, 422, fields=(path,))
    return float(value)


def process_days(value, path):
    """An operation's own external cycle or a merged group's cycle, in natural days."""
    if not is_external_days(value):
        raise WorkbenchCommandRejected("invalid_input", "外协周期" + EXTERNAL_DAYS_RANGE_TEXT + "。", 422, fields=(path,))
    return float(value)


def process_list(value):
    if type(value) is not list:
        raise WorkbenchCommandRejected("invalid_input", "必须提交完整的列表。", 422)
    if len(value) > MAX_STAGE_ITEMS:
        raise WorkbenchCommandRejected("stage_too_large", "一次最多 10000 条，这次没有提交。请缩小范围后重试。", 413)
    return value


def process_unique(rows, *, refs_only=False):
    refs = [process_ref(row) for row in rows] if refs_only else [row["ref"] for row in rows]
    if len(refs) != len(set(refs)):
        raise WorkbenchCommandRejected("invalid_input", "同一记录不能重复提交。", 422)
    return sorted(rows, key=(lambda row: row) if refs_only else (lambda row: row["ref"]))


def _source_operations(rows):
    result = []
    for row in process_list(rows):
        process_object(row, {"ref", "source", "op_type_ref", "supplier_ref", "confirmed"})
        process_ref(row["ref"])
        if type(row["source"]) is not str or row["source"] not in SOURCE_TYPE_VALUES or row["confirmed"] is not True:
            raise WorkbenchCommandRejected("invalid_input", "每道工序都需要选定归属并确认。", 422)
        process_ref(row["op_type_ref"])
        if row["source"] == "internal":
            if row["supplier_ref"] is not None:
                raise WorkbenchCommandRejected("invalid_input", "自制工序不能选择供应商。", 422)
        else:
            process_ref(row["supplier_ref"])
        result.append(row)
    return process_unique(result)


def _hours_operations(rows):
    result = []
    for row in process_list(rows):
        if type(row) is not dict:
            raise WorkbenchCommandRejected("invalid_input", "工序工时的填写格式不对。", 400)
        keys = {"ref", "external_days"} if "external_days" in row else {"ref", "setup_hours", "unit_hours"}
        process_object(row, keys)
        ref = process_ref(row["ref"])
        normalized: Dict[str, Optional[Union[str, float]]] = {"ref": ref}
        for key in sorted(keys - {"ref"}):
            value, path = row[key], "operations." + ref + "." + key
            if key == "external_days":
                normalized[key] = None if value is None else process_days(value, path)
            else:
                normalized[key] = process_number(value, path)
        result.append(normalized)
    return process_unique(result)


def _normalize_group_input(payload):
    process_object(payload, {"groups", "discard_group_refs"})
    discarded = process_unique(process_list(payload["discard_group_refs"]), refs_only=True)
    discarded_set = set(discarded)
    groups, existing, members = [], set(), set()
    # New groups have no ref and the rows are sorted below: the submitted position is the only identity a cycle
    # rejection can point back at.
    for index, row in enumerate(process_list(payload["groups"])):
        process_object(row, {"ref", "operation_refs", "supplier_ref", "total_days"})
        ref = None if row["ref"] is None else process_ref(row["ref"])
        refs = process_unique(process_list(row["operation_refs"]), refs_only=True)
        if not refs or members.intersection(refs) or ref is not None and (ref in existing or ref in discarded_set):
            raise WorkbenchCommandRejected("invalid_input", "外协段必须包含工序，工序不能属于两段；同一段不能同时修改和解除。", 422)
        members.update(refs)
        if ref is not None:
            existing.add(ref)
        groups.append({"ref": ref, "operation_refs": refs, "supplier_ref": process_ref(row["supplier_ref"]),
                       "total_days": process_days(row["total_days"], "groups." + str(index) + ".total_days")})
    if len(members) > 10000:
        raise WorkbenchCommandRejected("stage_too_large", "一次最多维护 10000 道工序，请缩小范围后重试。", 413)
    return {"groups": sorted(groups, key=lambda row: (row["ref"] or "", row["operation_refs"])),
            "discard_group_refs": discarded}


def normalize_process_input(action, payload):
    if type(action) is not str or action not in PROCESS_ACTIONS:
        raise WorkbenchCommandRejected("invalid_input", "不支持的工艺阶段操作。", 400)
    if action == "groups_confirm":
        return _normalize_group_input(payload)
    if action == "hours_confirm":
        process_object(payload, {"operations", "groups", "confirm_zero_unit_hours"})
        if type(payload["confirm_zero_unit_hours"]) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "零单件工时的保存选项必须是明确的是或否。", 422)
        operations = _hours_operations(payload["operations"])
        groups = []
        for row in process_list(payload["groups"]):
            process_object(row, {"ref", "total_days"})
            ref = process_ref(row["ref"])
            groups.append({"ref": ref, "total_days": process_days(row["total_days"], "groups." + ref + ".total_days")})
        return {"operations": operations, "groups": process_unique(groups),
                "confirm_zero_unit_hours": payload["confirm_zero_unit_hours"]}
    field = "route" if action == "route_confirm" else "operations"
    if not keys_conform(payload, (field,), ("discard_group_refs",)):
        raise WorkbenchCommandRejected("invalid_input", SHAPE_REJECTED, 400)
    discarded = process_unique(process_list(payload.get("discard_group_refs", [])), refs_only=True)
    if action == "source_confirm":
        return {field: _source_operations(payload[field]), "discard_group_refs": discarded}
    return {field: payload[field], "discard_group_refs": discarded}
