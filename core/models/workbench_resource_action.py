"""Immutable server previews and explicit non-material collection selections."""

from core.errors import ValidationError
from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import is_entity_ref
from core.models.workbench_resource_query import ResourcePageRequest

ACTION_KINDS = ("op_type", "machine", "operator", "supplier")


def action_kind(kind):
    if type(kind) is not str or kind not in ACTION_KINDS:
        raise WorkbenchCommandRejected("entity_not_found", "此资源不支持批量或文件操作。", 404)
    return kind


def resource_scope_request(kind, scope, *, size=20):
    """An external list scope (no page number) as the kind's validated request; size is the viewed page size."""
    allowed = {"query", "status", "category", "sort", "direction", "column_filters"}
    if type(scope) is not dict or set(scope) - allowed:
        raise ValidationError("范围只能包含搜索、状态、归属、排序和列筛选，不接受页码。", field="scope")
    return ResourcePageRequest(kind=kind, size=size, **scope)


def wire_resource_scope(request):
    """A validated request's scope as its wire dictionary, without kind or page size."""
    return {key: value for key, value in request.scope().items() if key not in ("kind", "size")}


def resource_refs(refs, *, allow_empty=False):
    if type(refs) is not list or (not refs and not allow_empty):
        raise ValidationError("请先选择要操作的设备或人员。", field="refs")
    if any(not is_entity_ref(ref) for ref in refs):
        raise ValidationError("所选设备或人员已失效，请刷新后重新选择。", field="refs")
    if len(set(refs)) != len(refs):
        raise ValidationError("选择里有重复，请重新选择。", field="refs")
    return refs


def check_category(kind, raw, category):
    if kind == "op_type" and category is not None and not supports_source(raw["category"], category):
        raise WorkbenchCommandRejected("constraint_conflict", "工种不属于本次自制/外协范围，请重新选择。")


def action_row(number, action=None):
    return {"row": number, "business_code": None, "entity_ref": None, "action": action,
            "result": "rejected", "before": None, "after": None, "changes": {}, "errors": [],
            "requires_confirmation": False, "reference_count": 0, "expected": None, "input": None}


def reject_action_row(row, message, *, field="input", code="invalid_input"):
    row["result"] = "rejected"
    row["errors"].append({"row": row["row"], "field": field, "code": code, "message": message})


def public_action_row(row):
    return {key: value for key, value in row.items() if key not in ("expected", "input", "related")}
