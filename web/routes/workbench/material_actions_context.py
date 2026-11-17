"""Material action wire validation and temporary, server-owned preview storage."""

from __future__ import annotations

from core.models.workbench_material_file import scope_request
from core.services.workbench.messages import local_created_at
from core.shared.key_sets import keys_conform

from .api_responses import worded_read_endpoint
from .request_json import BodyTexts, opaque_ref, read_json_body, rejecter
from .write_context import preview_write_context, retain_action_preview

PREVIEW_SCOPE = "workbench-material-preview-v1"
EXPORT_SCOPE = "workbench-material-export-v1"
EXPIRED_MESSAGE = "预检结果已过期，物料没有改动，范围也没有自动更换。请点「重新预检」。"


read_endpoint = worded_read_endpoint("物料预检或下载没有完成，数据没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。")


STALE_REF_MESSAGE = "这次操作的编号已失效，物料没有改动。请关掉弹窗后重新打开。"
CONFIRM_MISMATCH_MESSAGE = "只能确认刚才预检过的那一批，物料没有改动。请点「重新预检」。"
# Duplicate keys share the syntax-error text rather than silently taking the last scope or ref.
BODY = BodyTexts(transport="提交的内容格式不正确，物料没有改动。请刷新页面后重新填写。",
                 malformed="提交的内容格式不正确或有重复项，物料没有改动。请刷新页面后重新填写。",
                 incomplete="提交的内容不完整或有多余项，物料没有改动。请刷新页面后重新填写。")


def json_body(required, optional=()):
    body = read_json_body(BODY)
    if not keys_conform(body, required, optional):
        rejecter(BODY.incomplete)()
    return body


def scope_input(body):
    """The viewed list's validated request, its read-binding scope and snapshot token."""
    request = scope_request(body["scope"], size=body.get("page_size", 20))
    return request, request.scope(), opaque_ref(body["snapshot_ref"], STALE_REF_MESSAGE)


def issue_preview(preview):
    """Retain the frozen preview itself; an import preview already carries its parsed source."""
    ref, expires_at = retain_action_preview(PREVIEW_SCOPE, preview)
    document = preview.as_dict()
    action = document["operation"]
    context = preview_write_context(ref, expires_at, [action])
    rejected = document["summary"]["rejected"] != 0
    if rejected:
        context["capabilities"][action] = False
        context["blocked_reasons"] = [{"action": action, "code": "constraint_conflict", "message": "这一批里有不能提交的行，物料没有改动。请修好标红的行后重新预检。"}]
    result = {"preview_ref": ref, "expires_at": expires_at, "operation": action, "commit_policy": "atomic",
              "summary": document["summary"], "rows": [public_row(row) for row in document["rows"]],
              "can_confirm": not rejected, "write_context": context}
    if action == "material.import":
        result.update({key: document["request"][key] for key in ("actual_source_ref", "format", "mode")})
        result["template_version"] = 1
    return result


# Stored material column -> public field name shown in preview rows.
_PUBLIC_FIELD_NAMES = {"material_id": "business_code", "name": "label", "spec": "spec", "unit": "unit",
                       "stock_qty": "stock_qty", "status": "status", "remark": "remark", "created_at": "created_at"}


def _public_before(expected):
    raw = expected["material"] if expected else None
    before = {public: raw[key] for key, public in _PUBLIC_FIELD_NAMES.items()} if raw else None
    if before is not None:
        # 与导出同一条换算：认不出的旧写法原样给，不让"导出再原样回导"的预检因为这一格报错。
        before["created_at"] = local_created_at(before["created_at"])
    return before


def _public_after(row, before):
    if row["action"] != "delete" and row["input"] is not None:
        payload = row["input"]
        after = dict(before or {})
        after.update(payload["fields"])
        after.update({key: payload[key] for key in ("business_code", "label") if key in payload})
        return after
    return None


def public_row(row):
    expected = row["expected"]
    before = _public_before(expected)
    after = _public_after(row, before)
    identity = expected["identity"] if expected else None
    return {"row": row["row"], "business_code": row["business_code"],
            "entity_ref": row["entity_ref"] or (identity["ref"] if identity else None),
            "action": row["action"], "result": row["result"], "before": before, "after": after,
            "changes": {_PUBLIC_FIELD_NAMES[key]: value for key, value in row["changes"].items()},
            "errors": row["errors"], "notes": row["notes"], "requires_confirmation": row["requires_confirmation"],
            "reference_fields": row["reference_fields"],
            "reference_count": len(expected["requirements"]) if expected else 0}
