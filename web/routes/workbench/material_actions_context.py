"""Material action wire validation and temporary, server-owned preview storage."""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import wraps

from flask import request
from werkzeug.exceptions import HTTPException

from core.errors import AppError, ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_material_file import normalize_scope
from core.models.workbench_material_query import MaterialPageRequest
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .api_responses import api_endpoint
from .material_actions_previews import retain_preview, stored_preview
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context

PREVIEW_SCOPE = "workbench-material-preview-v1"
EXPORT_SCOPE = "workbench-material-export-v1"
TTL_SECONDS = 900


def read_endpoint(function):
    """POST previews are reads too; unexpected failures cannot mean committed."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (AppError, HTTPException, WorkbenchCommandRejected):
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("storage_failure", "物料预检或下载失败，未写入数据；请查看运行日志。", 500) from exc
    return api_endpoint(wrapped)


def json_body(required, optional=()):
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "请求必须使用JSON内容，不能带查询参数。", 400)
    # Reject duplicate keys rather than silently taking the last scope or ref.
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    try:
        body = json.loads(request.get_data(), object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise WorkbenchCommandRejected("invalid_input", "JSON内容无效或包含重复字段。", 400) from exc
    if type(body) is not dict or not set(required) <= set(body) or set(body) - set(required) - set(optional):
        raise WorkbenchCommandRejected("invalid_input", "请求缺少必要字段或包含未知字段。", 400)
    return body


def opaque_ref(value, field):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{32}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "操作引用无效，请重新打开当前操作。", 400)
    return value


def scope_input(body):
    scope = normalize_scope(body["scope"])
    page = MaterialPageRequest(**scope, size=body.get("page_size", 20))
    token = opaque_ref(body["snapshot_ref"], "snapshot_ref")
    return scope, page.scope(), token


def issue_binding(namespace, binding):
    token, expiry = issue_public_token_with_expiry(namespace, canonical_json(binding), ttl_seconds=TTL_SECONDS)
    return token, datetime.fromtimestamp(expiry).isoformat(timespec="seconds")


def resolve_binding(namespace, token, *, field, code):
    try:
        raw = resolve_public_token(namespace, token, message="操作预览已失效，请重新预检。", field=field)
    except ValidationError as exc:
        raise WorkbenchCommandRejected(code, "操作预览已失效，请重新预检；未自动更换范围。") from exc
    binding = json.loads(raw)
    if binding["version"] != 1 or binding["source"] != "production":
        raise WorkbenchCommandRejected(code, "操作预览来源不正确，请重新预检。")
    return binding


def issue_preview(preview, content=None):
    binding = {"version": 1, "source": "production", "preview_key": preview.digest}
    ref, expiry = issue_public_token_with_expiry(PREVIEW_SCOPE, canonical_json(binding), ttl_seconds=TTL_SECONDS)
    retain_preview(preview, content, expiry)
    expires_at = datetime.fromtimestamp(expiry).isoformat(timespec="seconds")
    document = preview.as_dict()
    action = document["operation"]
    context = issue_write_context(ref, [action], preview.intent())
    rejected = document["summary"]["rejected"] != 0
    if rejected:
        context["capabilities"][action] = False
        context["blocked_reasons"] = [{"action": action, "code": "constraint_conflict", "message": "预览包含拒绝行，本批不能提交。"}]
    result = {"preview_ref": ref, "expires_at": expires_at, "operation": action, "commit_policy": "atomic",
              "summary": document["summary"], "rows": [public_row(row) for row in document["rows"]],
              "can_confirm": not rejected, "write_context": context}
    if action == "material.import":
        result.update({key: document["request"][key] for key in ("file_sha256", "format", "mode")})
        result["template_version"] = 1
    return result


def resolve_preview(ref, action, write_token):
    binding = resolve_binding(PREVIEW_SCOPE, ref, field="preview_ref", code="stale_write")
    preview, content = stored_preview(binding["preview_key"])
    if preview.as_dict()["operation"] != action:
        raise WorkbenchCommandRejected("stale_write", "预览不适用于当前操作，请重新预检。")
    validate_write_context(write_token, ref, action, preview.intent())
    return preview, content


def public_row(row):
    expected = row["expected"]
    raw = expected["material"] if expected else None
    names = {"material_id": "business_code", "name": "label", "spec": "spec", "unit": "unit",
             "stock_qty": "stock_qty", "status": "status", "remark": "remark", "created_at": "created_at"}
    before = {public: raw[key] for key, public in names.items()} if raw else None
    after = None
    if row["action"] != "delete" and row["input"] is not None:
        payload = row["input"]
        after = dict(before or {})
        after.update(payload.get("fields", {}))
        after.update({key: payload[key] for key in ("business_code", "label") if key in payload})
    identity = expected["identity"] if expected else None
    return {"row": row["row"], "business_code": row["business_code"],
            "entity_ref": row.get("entity_ref") or (identity["ref"] if identity else None),
            "action": row["action"], "result": row["result"], "before": before, "after": after,
            "changes": {names[key]: value for key, value in row["changes"].items() if key in names},
            "errors": row["errors"], "requires_confirmation": row["requires_confirmation"],
            "reference_count": len(expected["requirements"]) if expected else 0}


def check_source_snapshot(query_scope, fingerprint, snapshot_ref):
    return bind_read_snapshot(query_scope, fingerprint, snapshot_ref)
