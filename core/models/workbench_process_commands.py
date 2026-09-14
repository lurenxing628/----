"""Strict, JSON-shaped inputs for explicit process-stage confirmations."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Dict, Optional, Union

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_route import normalize_route_preview_input

PROCESS_ACTIONS = ("route_confirm", "source_confirm", "hours_confirm")
MAX_STAGE_ITEMS = 10000


def process_object(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise WorkbenchCommandRejected("invalid_input", "提交内容缺少必填项或含有多余项，这次操作没有执行。请刷新页面后重试。", 400)
    return value


def process_ref(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "所选记录已失效，请刷新后重新选择。", 422)
    return value


def process_number(value, *, positive=False):
    if type(value) not in (int, float):
        raise WorkbenchCommandRejected("invalid_input", "请输入有效的工时或周期，不能留空。", 422)
    try:
        number = float(value)
    except OverflowError:
        raise WorkbenchCommandRejected("invalid_input", "工时和周期超出有效数字范围。", 422) from None
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        raise WorkbenchCommandRejected("invalid_input", "工时必须是有限非负数，外协周期必须是有限正数。", 422)
    return number


def _list(value):
    if type(value) is not list:
        raise WorkbenchCommandRejected("invalid_input", "必须提交完整的列表。", 422)
    if len(value) > MAX_STAGE_ITEMS:
        raise WorkbenchCommandRejected("stage_too_large", "一次最多 10000 条，这次没有提交。请缩小范围后重试。", 413)
    return value


def _unique(rows, *, refs_only=False):
    refs = [process_ref(row if refs_only else row["ref"]) for row in rows]
    if len(refs) != len(set(refs)):
        raise WorkbenchCommandRejected("invalid_input", "同一记录不能重复提交。", 422)
    return sorted(rows, key=(lambda row: row) if refs_only else (lambda row: row["ref"]))


def _source_operations(rows):
    result = []
    for row in _list(rows):
        process_object(row, {"ref", "source", "op_type_ref", "supplier_ref", "confirmed"})
        if type(row["source"]) is not str or row["source"] not in ("internal", "external") or row["confirmed"] is not True:
            raise WorkbenchCommandRejected("invalid_input", "每道工序都需要选定归属并确认。", 422)
        process_ref(row["op_type_ref"])
        if row["source"] == "internal":
            if row["supplier_ref"] is not None:
                raise WorkbenchCommandRejected("invalid_input", "自制工序不能选择供应商。", 422)
        else:
            process_ref(row["supplier_ref"])
        result.append(dict(row))
    return _unique(result)


def _hours_operations(rows):
    result = []
    for row in _list(rows):
        if type(row) is not dict:
            raise WorkbenchCommandRejected("invalid_input", "工序工时的填写格式不对。", 400)
        keys = {"ref", "external_days"} if "external_days" in row else {"ref", "setup_hours", "unit_hours"}
        process_object(row, keys)
        normalized: Dict[str, Optional[Union[str, float]]] = {"ref": process_ref(row["ref"])}
        for key in keys - {"ref"}:
            value = row[key]
            normalized[key] = None if key == "external_days" and value is None else process_number(value, positive=key == "external_days")
        result.append(normalized)
    return _unique(result)


def normalize_process_input(action, payload):
    if type(action) is not str or action not in PROCESS_ACTIONS:
        raise WorkbenchCommandRejected("invalid_input", "不支持的工艺阶段操作。", 400)
    if action == "hours_confirm":
        process_object(payload, {"operations", "groups", "confirm_zero_unit_hours"})
        if type(payload["confirm_zero_unit_hours"]) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "请明确勾选是否已复核零单件工时。", 422)
        operations = _hours_operations(payload["operations"])
        if any(row.get("unit_hours") == 0 for row in operations) and not payload["confirm_zero_unit_hours"]:
            raise WorkbenchCommandRejected("zero_unit_hours_review", "单件工时为0，必须明确复核后确认。", 422)
        groups = []
        for row in _list(payload["groups"]):
            process_object(row, {"ref", "total_days"})
            groups.append({"ref": process_ref(row["ref"]), "total_days": process_number(row["total_days"], positive=True)})
        return {"operations": operations, "groups": _unique(groups),
                "confirm_zero_unit_hours": payload["confirm_zero_unit_hours"]}
    field = "route" if action == "route_confirm" else "operations"
    if type(payload) is not dict or field not in payload or set(payload) - {field, "discard_group_refs"}:
        raise WorkbenchCommandRejected("invalid_input", "提交内容缺少必填项或含有多余项，这次操作没有执行。请刷新页面后重试。", 400)
    discarded = _unique(_list(payload.get("discard_group_refs", [])), refs_only=True)
    if action == "source_confirm":
        return {field: _source_operations(payload[field]), "discard_group_refs": discarded}
    # The existing normalizer validates shape/capacity without erasing raw spaces.
    normalize_route_preview_input(payload["route"])
    return {field: deepcopy(payload[field]), "discard_group_refs": discarded}
