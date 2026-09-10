"""Immutable server previews and explicit non-material collection selections."""

import hashlib
import json
from dataclasses import dataclass

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_resource_query import ResourcePageRequest

ACTION_KINDS = ("op_type", "machine", "operator", "supplier")


def action_kind(kind):
    if type(kind) is not str or kind not in ACTION_KINDS:
        raise WorkbenchCommandRejected("entity_not_found", "此资源不支持批量或文件操作。", 404)
    return kind


def resource_scope(kind, scope):
    action_kind(kind)
    allowed = {"query", "status", "category", "sort", "direction", "column_filters"}
    if type(scope) is not dict or set(scope) - allowed:
        raise ValidationError("范围只能包含搜索、状态、归属、排序和列筛选，不接受页码。", field="scope")
    page = ResourcePageRequest(kind=kind, **scope)
    return {key: value for key, value in page.scope().items() if key not in ("kind", "size")}


def resource_refs(refs, *, allow_empty=False):
    if type(refs) is not list or (not refs and not allow_empty):
        raise ValidationError("必须明确列出资源永久引用。", field="refs")
    if any(type(ref) is not str or len(ref) != 48 or any(c not in "0123456789abcdef" for c in ref) for ref in refs):
        raise ValidationError("选择必须使用永久引用，不能用业务编号。", field="refs")
    if len(set(refs)) != len(refs):
        raise ValidationError("选择中有重复引用。", field="refs")
    return list(refs)


def check_category(kind, raw, scope):
    if kind == "op_type" and scope["category"] is not None and raw["category"] != scope["category"]:
        raise WorkbenchCommandRejected("constraint_conflict", "工种不属于本次自制/外协范围，请重新选择。")


@dataclass(frozen=True)
class ResourceActionPreview:
    document: str

    @classmethod
    def build(cls, operation, request, rows):
        summary = {key: sum(row["result"] == key for row in rows)
                   for key in ("new", "update", "unchanged", "delete", "rejected")}
        try:
            return cls(canonical_json({"version": 1, "operation": operation, "request": request,
                                       "commit_policy": "atomic", "rows": rows, "summary": summary}))
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkbenchCommandRejected("storage_failure", "原始事实不能形成完整预览，未写入数据。", 500) from exc

    def as_dict(self):
        return json.loads(self.document)

    @property
    def digest(self):
        return hashlib.sha256(self.document.encode("utf-8")).hexdigest()

    def intent(self):
        body = self.as_dict()
        return {"preview_hash": self.digest, "operation": body["operation"], "request": body["request"]}


def check_resource_preview(original, current):
    if not isinstance(original, ResourceActionPreview) or original.document != current.document:
        raise WorkbenchCommandRejected("stale_write", "原预览、文件、范围或关联事实已变化，请重新核对整批。")
    if current.as_dict()["summary"]["rejected"]:
        raise WorkbenchCommandRejected("constraint_conflict", "预览包含拒绝行，本批未写入任何数据。")


def action_row(number, code=None, action=None):
    return {"row": number, "business_code": code, "entity_ref": None, "action": action,
            "result": "rejected", "before": None, "after": None, "changes": {}, "errors": [],
            "requires_confirmation": False, "reference_count": 0, "expected": None, "input": None}


def reject_action_row(row, message, *, field="input", code="invalid_input"):
    row["result"] = "rejected"
    row["errors"].append({"row": row["row"], "field": field, "code": code, "message": message})


def public_action_row(row):
    return {key: value for key, value in row.items() if key not in ("expected", "input", "related")}
