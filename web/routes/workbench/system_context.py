"""System-only opaque contexts and response boundary. No shared namespace edits."""

import os
from datetime import datetime
from functools import wraps
from types import MappingProxyType
from uuid import uuid4

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import ValidationError
from core.infrastructure.backup import MaintenanceWindowError
from core.models.workbench_command import (
    WorkbenchCommandRejected,
    validate_request_key,
)
from core.models.workbench_system import object_fields
from core.services.workbench import messages
from core.services.workbench.facts.system_journal import SystemMaintenanceJournal
from web.api_responses import failure, failure_payload, json_response, query_success
from web.public_token_registry import issue_public_token, resolve_public_token

BASE = "/api/workbench/v1/system"
SCOPE = "workbench-system-maintenance-v1"


def system_endpoint(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = current_app.make_response(function(*args, **kwargs))
        except (WorkbenchCommandRejected, MaintenanceWindowError) as exc:
            status = exc.status if isinstance(exc, WorkbenchCommandRejected) else 503
            response = failure(exc.code, str(exc) if isinstance(exc, WorkbenchCommandRejected) else exc.message, status)
        except HTTPException as exc:
            response = failure("invalid_input", "提交的内容格式不正确，还没有保存。请刷新页面后重新填写。", exc.code or 400)
        except Exception:
            request_ref = uuid4().hex
            current_app.logger.exception("系统工作区请求失败 endpoint=%s request_ref=%s", request.endpoint, request_ref)
            key = getattr(g, "system_request_key", None)
            payload = failure_payload("storage_failure", messages.unknown("这次维护操作") if key else messages.FAILURE, 500,
                                      committed="unknown" if key else False, request_ref=request_ref)
            if key:
                payload["error"].update({"request_key": key, "result_target": BASE + "/results/" + key})
            response = json_response(payload, status=500)
        response.headers["Cache-Control"] = "no-store"
        return response
    return wrapped


def database_scope():
    if current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"):
        return journal().database_scope
    return os.path.normcase(os.path.realpath(current_app.config["DATABASE_PATH"]))


def issue_context(kind, value, *, database=None):
    from .read_context import fact_value

    db_scope = database_scope() if database is None else database
    return issue_public_token(SCOPE, MappingProxyType({"database": db_scope, "kind": kind, "value": value}),
                              key=(db_scope, kind), group=fact_value(value), ttl_seconds=900)


def resolve_context(kind, token, *, database=None):
    try:
        payload = resolve_public_token(SCOPE, token, message=messages.STALE, field="write_token")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("stale_write", messages.STALE) from exc
    db_scope = database_scope() if database is None else database
    if payload["database"] != db_scope or payload["kind"] != kind:
        raise WorkbenchCommandRejected("stale_write", "本页数据已过期，和这次操作对不上，数据没有改动。请刷新页面后重试。")
    return payload["value"]


def command_body():
    if request.args or request.mimetype != "application/json":
        raise WorkbenchCommandRejected("invalid_input", "提交的内容格式不正确，数据没有改动。请刷新页面后重新填写。", 400)
    body = object_fields(request.get_json(), ("request_key", "write_token", "input"))
    validate_request_key(body["request_key"])
    if not isinstance(body["write_token"], str):
        raise WorkbenchCommandRejected("invalid_input", "本页数据已过期，数据没有改动。请刷新页面后重试。", 400)
    if type(body["input"]) is not dict:
        raise WorkbenchCommandRejected("invalid_input", "提交的内容格式不正确，数据没有改动。请刷新页面后重新填写。", 400)
    g.system_request_key = body["request_key"]
    return body


def journal():
    return SystemMaintenanceJournal(current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"), current_app.config["DATABASE_PATH"])


def query_payload(data):
    return query_success(data, {"as_of": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")})
