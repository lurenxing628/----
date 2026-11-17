"""System-only opaque contexts and response boundary. No shared namespace edits."""

from functools import wraps
from types import MappingProxyType
from uuid import uuid4

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import ValidationError
from core.infrastructure.backup import MaintenanceWindowError
from core.models.workbench_command import SHAPE_REJECTED, WorkbenchCommandRejected
from core.services.workbench import messages
from core.services.workbench.facts.system_journal import SystemMaintenanceJournal
from web.api_responses import failure, failure_payload, json_response, query_success
from web.public_token_registry import issue_public_token, resolve_public_token

from .api_responses import rejection_failure
from .read_context import fact_value, unbound_snapshot
from .request_json import BodyTexts, command_body, rejecter

BASE = "/api/workbench/v1/system"
SCOPE = "workbench-system-maintenance-v1"
_UNREADABLE = "提交的内容格式不正确，数据没有改动。请刷新页面后重新填写。"
_COMMAND = BodyTexts(transport=_UNREADABLE, malformed=_UNREADABLE, incomplete=SHAPE_REJECTED)


def system_endpoint(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = current_app.make_response(function(*args, **kwargs))
        except WorkbenchCommandRejected as exc:
            response = rejection_failure(exc)
        except MaintenanceWindowError as exc:
            response = failure(exc.code, exc.message, 503)
        except HTTPException as exc:
            response = failure("invalid_input", "提交的内容格式不正确，还没有保存。请刷新页面后重新填写。", exc.code or 400)
        except Exception:
            request_ref = uuid4().hex
            current_app.logger.exception("系统工作区请求失败 endpoint=%s request_ref=%s", request.endpoint, request_ref)
            key = g.get("workbench_request_key")
            payload = failure_payload("storage_failure", messages.unknown("这次维护操作") if key else messages.FAILURE, 500,
                                      committed="unknown" if key else False, request_ref=request_ref)
            if key:
                payload["error"].update({"request_key": key, "result_target": BASE + "/results/" + key})
            response = json_response(payload, status=500)
        response.headers["Cache-Control"] = "no-store"
        return response
    return wrapped


def database_scope():
    return journal().database_scope


def issue_context(kind, value, *, database=None):
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


def system_command_body():
    """A maintenance command: ``application/json`` only (no ``+json`` variants), its input an object."""
    if request.mimetype != "application/json":
        rejecter(_UNREADABLE)()
    body = command_body(_COMMAND, stale="本页数据已过期，数据没有改动。请刷新页面后重试。")
    if type(body["input"]) is not dict:
        rejecter(_UNREADABLE)()
    return body


def journal():
    return SystemMaintenanceJournal(current_app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"], current_app.config["DATABASE_PATH"])


def query_payload(data, as_of):
    return query_success(data, unbound_snapshot(as_of))
