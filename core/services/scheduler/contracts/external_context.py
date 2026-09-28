"""One interpretation of frozen external facts for scheduling, preflight and display."""

import math

from core.errors import ValidationError
from core.models.batch_external_context import context_group_key as context_group_key
from core.models.enums import BatchExternalContextOrigin

_MISSING_CONTEXT = "批次外协周期记录缺失。请先完成版本升级；已升级的批次请核对来源后从工艺模板更新工序。"


def _positive_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _reference(value):
    return isinstance(value, str) and len(value) == 48 and all(c in "0123456789abcdef" for c in value)


def context_problem(row, *, operation_id, part_no, sequence):
    if row is None:
        return _MISSING_CONTEXT
    if row["operation_id"] != operation_id or row["part_no"] != part_no or row["sequence"] != sequence:
        return "批次外协周期记录与这道工序的零件或工序号不一致，不能按当前模板猜测。"
    if type(row["template_operation_id"]) is not int or row["template_operation_id"] <= 0 or row["template_status"] != "active":
        return "建立批次外协周期记录时没有有效的模板工序。请核对来源后从工艺模板更新工序。"
    if not _reference(row["template_operation_ref"]):
        return "批次外协周期记录缺少模板工序来源编号，请联系维护人员核对。"
    if row["origin"] not in tuple(item.value for item in BatchExternalContextOrigin):
        return "批次外协周期记录的来源不完整，请联系维护人员核对。"
    return _group_problem(row, part_no, sequence)


def _group_problem(row, part_no, sequence):
    if row["group_id"] is None:
        if any(row[key] is not None for key in ("group_part_no", "start_sequence", "end_sequence", "merge_mode",
                                               "total_days", "supplier_id", "group_ref")):
            return "批次保存的外协分组记录不完整，不能改按单道周期推测。"
        return None
    if row["group_part_no"] != part_no or row["merge_mode"] not in ("merged", "separate"):
        return "批次保存的外协分组关系不完整，不能按当前模板猜测。"
    low, high = row["start_sequence"], row["end_sequence"]
    if type(low) is not int or type(high) is not int or not 0 < low <= sequence <= high:
        return "批次保存的外协分组范围与本工序不一致，请核对批次工序。"
    if not _reference(row["group_ref"]):
        return "批次保存的外协分组缺少来源编号，请联系维护人员核对。"
    if row["merge_mode"] == "merged" and not _positive_number(row["total_days"]):
        return "批次保存的整组外协周期未填写或无效，请核对批次工序。"
    return None


def require_context(row, *, operation_id, part_no, sequence):
    if row is None:
        raise ValidationError(_MISSING_CONTEXT, field="external_context")
    problem = context_problem(row, operation_id=operation_id, part_no=part_no, sequence=sequence)
    if problem:
        raise ValidationError(problem, field="external_context")
    return row


def group_from_context(row):
    if row["group_id"] is None:
        return None
    return {"ref": row["group_ref"], "business_code": row["group_id"],
            "merge_mode": row["merge_mode"], "total_days": row["total_days"],
            "start_sequence": row["start_sequence"], "end_sequence": row["end_sequence"]}


def origin_notice(row):
    if row and row["origin"] == BatchExternalContextOrigin.MIGRATION_V33.value:
        return "外协周期按升级时的有效资料保留；更早的原始周期没有可核实记录。"
    return None


_SUPPLIER_CONFLICT = "合并外协段的供应商与保存的规则不一致。请核对整段供应商后，从工艺模板预览更新批次工序。"


def member_index(contexts, operations):
    """One linear pass; each group stores one verdict rather than repeated member lists."""
    groups, invalid = {}, set()
    for op in operations:
        row = contexts.get(op["id"])
        if row is None or row["merge_mode"] != "merged":
            continue
        identity = (op["batch_id"], row["group_ref"], op.get("piece_id"))
        if context_problem(row, operation_id=op["id"], part_no=row["part_no"], sequence=op["seq"]):
            invalid.add(identity)
            continue
        key = (op["batch_id"], context_group_key(row), op.get("piece_id"))
        check = groups.setdefault(key, {"supplier_id": op["supplier_id"], "problem": None, "identity": identity})
        if (check["supplier_id"] != op["supplier_id"]
                or row["supplier_id"] is not None and row["supplier_id"] != op["supplier_id"]):
            check["problem"] = _SUPPLIER_CONFLICT
        if str(op["source"] or "").strip().lower() != "external":
            check["problem"] = "合并外协段包含已改为自制的工序，请先核对整个批次。"
    for check in groups.values():
        if check.pop("identity") in invalid:
            check["problem"] = "合并外协段有成员的周期记录不完整，请先核对整个批次。"
    return groups


def merged_supplier_problem(context, supplier_id, check):
    """Constant work per operation; all member traversal happens once in member_index."""
    if context is None or context["merge_mode"] != "merged":
        return None
    if check is None:
        return "找不到合并外协段的完整成员资料，不能猜测供应商和周期。"
    if check["problem"]:
        return check["problem"]
    if check["supplier_id"] != supplier_id:
        return _SUPPLIER_CONFLICT
    return None
