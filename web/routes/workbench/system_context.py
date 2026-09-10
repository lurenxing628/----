"""System-only opaque contexts and response boundary. No shared namespace edits."""

import json
import os
from datetime import datetime
from functools import wraps

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.infrastructure.backup import MaintenanceWindowError
from core.models.workbench_command import (
    WorkbenchCommandRejected,
    canonical_json,
    input_fingerprint,
    validate_request_key,
)
from core.models.workbench_system import object_fields
from core.services.workbench.system_journal import SystemMaintenanceJournal
from web.public_token_registry import issue_public_token, resolve_public_token

from .api_responses import failure, query_success

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
            response = failure("invalid_input", "请求格式不正确。", exc.code or 400)
        except Exception:
            current_app.logger.exception("系统工作区请求失败 endpoint=%s", request.endpoint)
            key = getattr(g, "system_request_key", None)
            response = failure("storage_failure", "本机维护请求失败，请核查原请求结果后再操作。", 500,
                               committed="unknown" if key else False)
            if key:
                payload = response.get_json()
                payload["error"].update({"request_key": key, "result_target": BASE + "/results/" + key})
                response.set_data(current_app.json.dumps(payload))
        response.headers["Cache-Control"] = "no-store"
        return response
    return wrapped


def database_scope():
    return input_fingerprint(os.path.normcase(os.path.realpath(current_app.config["DATABASE_PATH"])))


def issue_context(kind, value):
    return issue_public_token(SCOPE, canonical_json({"source": "production", "database": database_scope(),
                                                    "kind": kind, "value": value}), ttl_seconds=900)


def resolve_context(kind, token):
    try:
        payload = json.loads(resolve_public_token(SCOPE, token, message="维护上下文已失效，请刷新后重新核对。", field="write_token"))
    except (ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("stale_write", "维护上下文已失效，请刷新后重新核对。") from exc
    except Exception as exc:
        from core.errors import ValidationError
        if isinstance(exc, ValidationError):
            raise WorkbenchCommandRejected("stale_write", "维护上下文已失效，请刷新后重新核对。") from exc
        raise
    if payload.get("source") != "production" or payload.get("database") != database_scope() or payload.get("kind") != kind:
        raise WorkbenchCommandRejected("stale_write", "维护上下文不属于本机当前操作。")
    return payload["value"]


def command_body():
    if request.args or request.mimetype != "application/json":
        raise WorkbenchCommandRejected("invalid_input", "维护动作须提交JSON对象。", 400)
    body = object_fields(request.get_json(), ("request_key", "write_token", "input"))
    validate_request_key(body["request_key"])
    if not isinstance(body["write_token"], str):
        raise WorkbenchCommandRejected("invalid_input", "维护上下文无效。", 400)
    object_fields(body["input"], (), body["input"].keys() if isinstance(body["input"], dict) else ())
    g.system_request_key = body["request_key"]
    return body


def journal():
    return SystemMaintenanceJournal(current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"), current_app.config["DATABASE_PATH"])


def query_payload(data):
    return query_success(data, {"as_of": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                "snapshot_ref": issue_context("query", input_fingerprint(data))})
